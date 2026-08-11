# Deployment & Scheduling

This document is built up one Priority-1 item at a time. It currently covers
**item 1: decoupling news sentiment from the scan/API request path and running
it on a schedule.** Items 2–5 (Render.com backend deploy, Flutter base URL,
HTTPS, off-network mobile test) will extend this file as they land.

---

## Why the sentiment model is decoupled

The news sentiment engine loads a ~500MB transformer
(`cardiffnlp/twitter-roberta-base-sentiment`) plus `torch`/`transformers`
(~2GB installed). That is far too heavy to live on:

- **the API request path** — a Render.com free-tier instance has 512MB RAM; it
  cannot hold this model, and no user request should wait on a model load; or
- **the normal EOD scan** — a scan should be fast and dependency-light.

So the model runs in exactly **one** place: a standalone refresher that writes a
small JSON cache. Everything else only ever *reads* that cache.

```
                          tools/refresh_sentiment.py   (the ONLY model load)
                                     │  runs 2×/day via scheduler
                                     ▼
                database/ai_learning/sentiment_cache.json   (small, fast to read)
                          ▲              ▲               ▲
                          │              │               │
             main.py normal scan   daily_signal_engine   api/  (FastAPI)
             (reads + reports        (sentiment tilt)     /stock, /signal
              cache freshness)                            (read-only)
```

- `main.py` (normal scan) reads the cache and prints its age; it loads the model
  **only** if you pass `--refresh-news`.
- `api/main.py`, `app/engines/daily_signal_engine.py`, and
  `app/engines/nl_query_engine.py` **never** import `transformers` — they only
  read `sentiment_cache.json`.

Verify the API path stays model-free at any time:

```bash
python - <<'PY'
import ast, pathlib
for f in ["api/main.py", "app/engines/nl_query_engine.py", "app/engines/daily_signal_engine.py"]:
    src = pathlib.Path(f).read_text(encoding="utf-8")
    hit = "transformers" in src or "torch" in src
    print(f, "IMPORTS MODEL" if hit else "ok (no model import)")
PY
```

---

## The standalone refresher

`tools/refresh_sentiment.py` is what the scheduler calls.

```bash
python tools/refresh_sentiment.py
```

What it does:

1. Takes a lock (`database/ai_learning/.sentiment.lock`) so two scheduled runs
   can't stampede the model load. A lock older than 20 min is treated as
   abandoned and overridden.
2. Runs `run_news_sentiment_engine()` → writes
   `database/ai_learning/sentiment_cache.json`.
3. Appends a timestamped line to `logs/sentiment_refresh.log`.
4. Exit codes (so a scheduler's "failed" flag means something real):
   - `0` — success, **or** feeds were down and the previous cache was kept
     (graceful fallback — not a failure).
   - `1` — unexpected crash.
   - `2` — no headlines fetched **and** no cache to fall back to.

If `feedparser`/`transformers` aren't installed, the engine degrades
gracefully: headlines are still matched to tickers, sentiment is reported as
`model_available: false`, and the run still exits `0`. Install the optional
stack to get real scores:

```bash
pip install -r requirements-optional.txt
```

---

## Schedule: twice a day

PSX trades ~09:30–15:30 **PKT (UTC+5)**. Refresh once before the open and once
during/after the session so the cache is fresh for the pre-open scan and again
for end-of-day review. Suggested local times: **08:00** and **15:00 PKT**.

### Windows Task Scheduler (this PC — local time is PKT)

Run these once from an **elevated** PowerShell. Adjust the paths if the repo
isn't at `D:\PSX_AI_SCANNER` and point `SYSTEM`/your user as appropriate.

```powershell
# Morning refresh — 08:00 daily
schtasks /Create /TN "PSX\SentimentRefresh_AM" /SC DAILY /ST 08:00 ^
  /TR "cmd /c cd /d D:\PSX_AI_SCANNER && python tools\refresh_sentiment.py" /F

# Afternoon refresh — 15:00 daily
schtasks /Create /TN "PSX\SentimentRefresh_PM" /SC DAILY /ST 15:00 ^
  /TR "cmd /c cd /d D:\PSX_AI_SCANNER && python tools\refresh_sentiment.py" /F
```

Check / run / remove:

```powershell
schtasks /Query  /TN "PSX\SentimentRefresh_AM" /V /FO LIST
schtasks /Run    /TN "PSX\SentimentRefresh_AM"          # trigger a test run now
schtasks /Delete /TN "PSX\SentimentRefresh_AM" /F
```

> If Python isn't on PATH for the scheduler's user, replace `python` with the
> absolute interpreter path (e.g. the venv's
> `D:\PSX_AI_SCANNER\.venv\Scripts\python.exe`).

### Linux / cron (e.g. a server; times in **UTC**)

08:00 PKT = **03:00 UTC**, 15:00 PKT = **10:00 UTC**.

```cron
# m h  dom mon dow   command
0 3 * * *  cd /path/to/PSX_AI_SCANNER && /usr/bin/python3 tools/refresh_sentiment.py >> logs/cron.out 2>&1
0 10 * * * cd /path/to/PSX_AI_SCANNER && /usr/bin/python3 tools/refresh_sentiment.py >> logs/cron.out 2>&1
```

(If the host is already on PKT, use `0 8` and `0 15` instead.)

---

## How consumers see freshness

A normal scan now prints, e.g.:

```
NEWS SENTIMENT (cached — from scheduled refresher)
  source              : live
  generated_at        : 2026-08-11T05:47:00+00:00
  cache_age_hours     : 6.2
  stale               : False
  ...
```

`stale` flips to `True` once the cache is older than 12 hours — a cue that the
scheduler hasn't run (machine asleep, task disabled, feeds down for a long
stretch). To force an immediate inline refresh during a scan:

```bash
python main.py --refresh-news
```

---
---

# Item 2 — Render.com deployment (git-commit-on-refresh)

This section takes the API from "runs on my PC" to "runs on a public HTTPS URL
the mobile app can reach from anywhere". The data-sync model is
**git-commit-on-refresh**, chosen because it's free and needs no extra infra:

```
  Your PC                          GitHub (main)                 Render (free web service)
  ───────                          ─────────────                 ─────────────────────────
  python main.py --publish  ──►  commit + push the 4     ──►   autoDeploy pulls the repo,
  (or refresh_sentiment            small output files            installs requirements-api.txt,
   --publish)                                                    restarts uvicorn with fresh data
```

The API itself is stateless and read-only: it just serves whatever data files
are in the checkout. Fresh data reaches it by being committed and pushed.

## What's already in the repo for this

| File | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint — defines the free web service, build/start commands, health check, env vars. |
| `requirements-api.txt` | The **only** file Render installs. Lean: fastapi, uvicorn, pydantic, pandas, numpy, anthropic, python-dotenv. **No PySide6, no torch/transformers.** |
| `.gitignore` | Commits code + the 4 small outputs; ignores the DB, historical data, venv, caches, builds. |
| `tools/publish_outputs.py` | Force-commits the 4 outputs and pushes to `origin`. |
| `main.py --publish`, `tools/refresh_sentiment.py --publish` | Run the publisher automatically after a scan / sentiment refresh. |

> **Why `requirements-api.txt` and not `requirements.txt`?** `requirements.txt`
> pulls in **PySide6** (the desktop Qt GUI, ~100MB+, needs system libraries) which
> the web API never imports and which bloats/can break a headless free-tier build.
> `requirements-api.txt` is the exact, minimal runtime set. Neither file contains
> torch/transformers — confirm anytime with:
> ```bash
> grep -iE "torch|transformers|pyside" requirements-api.txt || echo "clean: none present"
> ```

---

## Step 1 — Create the GitHub repo and push (you run these)

The project is **not a git repo yet**. Run these from `D:\PSX_AI_SCANNER`.

**1a. One-time git identity** (skip if `git config --global user.email` already prints something):

```bash
git config --global user.name "Your Name"
git config --global user.email "mohammaddeveloper38400@gmail.com"
```

**1b. Initialise, review what will be committed, and make the first commit:**

```bash
git init -b main
git add .
git status --short
```

That `git status` should list your code plus exactly these four data files and
`reports/latest/metadata.json` — and **none** of `psx_terminal.db`,
`database/historical_files/`, `.env`, `.venv`, or `__pycache__`. If anything
heavy shows up, stop and tell me before committing. When it looks right:

```bash
git commit -m "Initial commit: PSX AI Scanner (API + data outputs)"
```

**1c. Create the GitHub repo.** Easiest with the GitHub CLI if you have it:

```bash
gh repo create psx-ai-scanner --private --source . --remote origin --push
```

**No `gh`?** Create it in the browser instead: go to <https://github.com/new>,
name it `psx-ai-scanner`, choose **Private**, do **not** add a README/.gitignore
(the repo already has them), click **Create repository**, then:

```bash
git remote add origin https://github.com/<your-username>/psx-ai-scanner.git
git push -u origin main
```

---

## Step 2 — Connect the repo to Render

1. Sign in at <https://render.com> (free; you can sign in with GitHub).
2. Click **New +** → **Blueprint**.
3. **Connect your GitHub account** and pick the `psx-ai-scanner` repo. Render
   finds `render.yaml` automatically and shows one service:
   **`psx-ai-scanner-api`** (Free plan, region Singapore).
4. Click **Apply**. Render starts the first build (`pip install -r
   requirements-api.txt`) — this takes ~2–4 minutes the first time.

If Render asks for anything not in the blueprint, the defaults are:
Runtime **Python 3**, Build `pip install -r requirements-api.txt`,
Start `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, Health check `/health`.

---

## Step 3 — Set environment variables on Render

`render.yaml` declares these but marks the secrets `sync: false`, meaning **you
must set their values in the dashboard** (they're intentionally never in git).

In the service → **Environment** tab → **Add Environment Variable**:

| Key | Value | Needed? |
|-----|-------|---------|
| `PSX_API_KEY` | a long random string you invent (this is the app's password) | **Yes** — set it before using the API |
| `ANTHROPIC_API_KEY` | your Anthropic key | Optional — only the `/query` chat endpoint uses it; leave unset and `/query` returns a clean 503 |
| `PSX_CORS_ORIGINS` | `*` for now; later your web app's exact origin | Already defaulted to `*` in the blueprint |

Generate a strong `PSX_API_KEY` locally if you like:

```bash
python -c "import secrets; print('psx_' + secrets.token_urlsafe(32))"
```

Click **Save Changes** — Render redeploys with the new values. **Use this same
key** in the mobile app and web dashboard settings (that's item 3).

> Security note: keep `PSX_API_KEY` out of git and out of screenshots. If it
> leaks, rotate it here and update your clients. The default `psx-dev-key-change-me`
> must never be used in the deployed service.

---

## Step 4 — Verify the deployed API

Render gives the service a URL like `https://psx-ai-scanner-api.onrender.com`
(HTTPS is automatic and free — that's item 4 done). Replace `<URL>` and `<KEY>`:

```bash
# Health — no key needed. Expect 200 and data_files all true.
curl https://<URL>/health

# Auth gate — no key should be rejected (401).
curl -i https://<URL>/signal

# With the key — today's market verdict.
curl -H "X-API-Key: <KEY>" https://<URL>/signal

# Opportunities and a single stock.
curl -H "X-API-Key: <KEY>" "https://<URL>/opportunities?limit=5"
curl -H "X-API-Key: <KEY>" https://<URL>/stock/MCB
```

Interactive docs are at `https://<URL>/docs`.

> **Free-tier cold start:** the service sleeps after ~15 min idle and takes
> ~30–50s to wake on the next request. The first call after a quiet spell will be
> slow, then fast. This is expected on the free plan.

---

## Step 5 — Publish fresh data on a schedule

Publishing is wired into both entry points via `--publish`. Update the schedule
from item 1 so each run also commits+pushes (which triggers Render's redeploy):

**Windows Task Scheduler** — change the sentiment task's command to add `--publish`:

```powershell
schtasks /Change /TN "PSX\SentimentRefresh_AM" ^
  /TR "cmd /c cd /d D:\PSX_AI_SCANNER && python tools\refresh_sentiment.py --publish"
```

And schedule your end-of-day scan to publish the full report set (adjust the
scan command to however you run the daily import):

```powershell
schtasks /Create /TN "PSX\DailyScan" /SC DAILY /ST 17:30 ^
  /TR "cmd /c cd /d D:\PSX_AI_SCANNER && python main.py --daily-import --publish" /F
```

**Linux/cron** equivalent:

```cron
0 10 * * * cd /path/to/PSX_AI_SCANNER && python3 tools/refresh_sentiment.py --publish >> logs/cron.out 2>&1
30 12 * * * cd /path/to/PSX_AI_SCANNER && python3 main.py --daily-import --publish >> logs/cron.out 2>&1
```

Each `--publish` run:
- commits only the 4 output files (`git add -f`, so `.gitignore` can't drop them),
- skips silently if nothing changed,
- pushes to `origin main` → Render auto-deploys within ~1–2 min.

You can test the publish step by hand any time (safe — it no-ops if unchanged):

```bash
python tools/publish_outputs.py
```

> **A note on churn:** every data push triggers a full Render rebuild, and
> `full_market_scan.csv` (~370 KB) changes daily, so git history grows over time.
> Fine for personal 2×/day use. If it ever outgrows that, the roadmap alternative
> is pushing data to object storage / a data endpoint instead of git — deferred on
> purpose (this was your call: git-first while it's personal-use).

---

## Step 6 — Point the clients at the deployed API (item 3, next)

Once `curl` works, update the **base URL** in:
- **Mobile (Flutter):** Settings screen → set base URL to `https://<URL>` and the
  API key to your `PSX_API_KEY`. (Cleartext is no longer needed — it's HTTPS now.)
- **Web (React):** Settings page → same base URL + key.

That's Priority-1 items 3–5; ping me to do the Flutter/React URL switch and the
off-WiFi mobile-data test.
