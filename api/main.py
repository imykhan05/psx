"""
PSX AI Scanner — FastAPI backend (Phase 2 #4).

A thin, read-only HTTP layer over the scanner's existing output. It does NOT
recompute anything — it serves the files the pipeline already produces
(daily_signal.json, full_market_scan.csv, top_buys.csv, sentiment_cache.json)
and forwards free-text questions to the NL query engine.

AUTH
  A single shared API key checked via the `X-API-Key` header (the "simple, one
  key, not a full user system" gate that was requested). A real per-user
  JWT/auth system is deliberately deferred — it is a strategic, data-model
  decision (ROADMAP F2.3), not something to improvise here. Set the key with
  the PSX_API_KEY env var (or .env); it falls back to a clearly-labelled dev key.

ERRORS
  Every failure returns clean JSON ({"error": ..., "detail": ...}) — never a
  raw traceback. An exception handler enforces this even for unexpected errors.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from pydantic import BaseModel, Field

# Reuse the engine's data locations and helpers — single source of truth.
from app.engines.nl_query_engine import (
    MODEL,
    DAILY_SIGNAL,
    SENTIMENT_CACHE,
    TOP_BUYS,
    FULL_SCAN,
    _read_json,
    _read_csv,
    load_context,
    build_system_prompt,
    get_client,
    stream_answer,
)

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEV_API_KEY = "psx-dev-key-change-me"
API_KEY = os.environ.get("PSX_API_KEY", DEV_API_KEY)

# Comma-separated allowed origins; "*" for open dev access.
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("PSX_CORS_ORIGINS", "*").split(",") if o.strip()
]

app = FastAPI(
    title="PSX AI Scanner API",
    version="1.0.0",
    description="Read-only HTTP access to the PSX scanner's end-of-day output.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth (shared API key via header)
# ---------------------------------------------------------------------------
def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


# ---------------------------------------------------------------------------
# Clean error handling — no raw tracebacks
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "request_error", "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": f"{type(exc).__name__}: {exc}"},
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
WEBUI_FILE = Path(__file__).resolve().parent / "webui.html"


@app.get("/", include_in_schema=False)
def home():
    """Built-in web UI. The API key is injected at serve time so the page (and the
    'Add to Home Screen' iOS/Android web-app) auto-connects with no manual entry.

    The key comes from the PSX_API_KEY env var and is never stored in the repo.
    Trade-off: anyone with this URL gets in — fine for a personal, obscure tunnel
    URL. Set PSX_WEB_AUTOCONNECT=0 to fall back to asking for the key.
    """
    if not WEBUI_FILE.exists():
        return JSONResponse({"service": "psx-ai-scanner-api", "docs": "/docs"})
    html = WEBUI_FILE.read_text(encoding="utf-8")
    if os.environ.get("PSX_WEB_AUTOCONNECT", "1") != "0":
        html = html.replace("__PSX_API_KEY__", API_KEY)
    return HTMLResponse(html)


APK_FILE = (
    Path(__file__).resolve().parents[1]
    / "mobile" / "build" / "app" / "outputs" / "flutter-apk" / "app-debug.apk"
)


@app.get("/app.apk", include_in_schema=False)
def download_apk():
    """Serve the built Android APK so a phone can install it over the tunnel."""
    if APK_FILE.exists():
        return FileResponse(
            APK_FILE,
            media_type="application/vnd.android.package-archive",
            filename="psx-scanner.apk",
        )
    raise HTTPException(status_code=404, detail="APK not built yet.")


@app.get("/download", include_in_schema=False)
def download_page():
    """Mobile-friendly landing page: download the APK + how to configure it.

    The Base URL to enter in the app is this page's own origin (shown live via
    JS), so nothing ephemeral is hard-coded. The API key is NOT shown here — the
    user enters their own key in the app's Settings screen.
    """
    apk_ready = APK_FILE.exists()
    button = (
        '<a class="btn" href="/app.apk">⬇ Download Android app (.apk)</a>'
        if apk_ready
        else '<p class="err">APK not built yet.</p>'
    )
    html = f"""<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Install PSX AI Scanner</title>
<style>
 body{{margin:0;background:#0b0e14;color:#e6edf6;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.5}}
 .wrap{{max-width:520px;margin:0 auto;padding:22px}}
 h1{{font-size:20px}} .muted{{color:#8a97a8}}
 .card{{background:#141a24;border:1px solid #26303f;border-radius:14px;padding:16px;margin:14px 0}}
 .btn{{display:block;text-align:center;background:#4c9ffe;color:#04121f;font-weight:800;
   text-decoration:none;padding:14px;border-radius:12px;font-size:16px}}
 code{{background:#1b2331;padding:2px 7px;border-radius:6px;word-break:break-all}}
 ol{{padding-left:20px}} li{{margin:7px 0}}
 .err{{color:#ff5c6c}}
</style></head><body><div class="wrap">
 <h1>📈 PSX AI Scanner — Android app</h1>
 <div class="card">{button}
   <p class="muted" style="font-size:13px;margin-bottom:0">~145 MB. Phone par kholein.</p>
 </div>
 <div class="card">
   <b>Install ke steps:</b>
   <ol>
     <li>Upar wala button dabayein → APK download hoga.</li>
     <li>Download tap karein → "Unknown sources / is source se install" allow karein → Install.</li>
     <li>App khol kar <b>Settings</b> mein jayein.</li>
     <li><b>Base URL</b>: <code id="base"></code></li>
     <li><b>API Key</b>: apni key paste karein (Claude chat wali).</li>
     <li>Save → data aa jayega.</li>
   </ol>
   <p class="muted" style="font-size:12px">Ya bina install ke: seedha
     <a href="/" style="color:#4c9ffe">yeh web page</a> kholein — wahi data, koi app nahi.</p>
 </div>
 <div class="card">
   <b>🍎 iPhone / iOS:</b>
   <p style="font-size:13px;margin:6px 0">iPhone par APK nahi chalti (Apple ki paband​i). Lekin yehi
   app iPhone par bhi hai — Safari ke zariye:</p>
   <ol>
     <li><b>Safari</b> mein <a href="/" style="color:#4c9ffe">yeh page</a> kholein.</li>
     <li>Neeche <b>Share</b> (⬆️) button dabayein.</li>
     <li><b>"Add to Home Screen"</b> chunein → Add.</li>
     <li>Home screen par app-icon ban jayega — full-screen khulega, key khud lag jaati hai.</li>
   </ol>
 </div>
 <script>document.getElementById('base').textContent = location.origin;</script>
</div></body></html>"""
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict:
    """Liveness + which data artifacts are present. No auth (health checks are open)."""
    files = {
        "daily_signal": DAILY_SIGNAL.exists(),
        "full_market_scan": FULL_SCAN.exists(),
        "top_buys": TOP_BUYS.exists(),
        "sentiment_cache": SENTIMENT_CACHE.exists(),
    }
    return {
        "status": "ok",
        "service": "psx-ai-scanner-api",
        "version": app.version,
        "data_files": files,
    }


@app.get("/signal", dependencies=[Depends(require_api_key)])
def get_signal() -> dict:
    """Today's daily market signal (verdict, confidence, reasons, top opportunities)."""
    signal = _read_json(DAILY_SIGNAL)
    if not signal:
        raise HTTPException(status_code=404, detail="No daily signal available. Run the scanner first.")
    return signal


@app.get("/opportunities", dependencies=[Depends(require_api_key)])
def get_opportunities(limit: int = 100) -> dict:
    """Top opportunities (top_buys.csv) as JSON records."""
    df = _read_csv(TOP_BUYS)
    if df.empty:
        return {"count": 0, "opportunities": []}
    records = df.head(max(1, min(limit, len(df)))).to_dict(orient="records")
    # NaN -> None for valid JSON
    clean = json.loads(pd.DataFrame(records).where(pd.notna(pd.DataFrame(records)), None).to_json(orient="records"))
    return {"count": len(clean), "opportunities": clean}


@app.get("/stock/{ticker}", dependencies=[Depends(require_api_key)])
def get_stock(ticker: str) -> dict:
    """Price, scoring, and news sentiment for one ticker."""
    symbol = ticker.strip().upper()

    df = _read_csv(FULL_SCAN)
    if df.empty or "symbol" not in df.columns:
        raise HTTPException(status_code=404, detail="No market scan available. Run the scanner first.")

    match = df[df["symbol"].astype(str).str.upper() == symbol]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found in today's scan.")

    row = match.iloc[0]

    def num(key):
        value = pd.to_numeric(row.get(key), errors="coerce")
        return None if pd.isna(value) else float(value)

    def text(key):
        value = row.get(key)
        return None if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)

    scoring = {
        "final_decision": text("final_decision"),
        "final_score": num("final_score"),
        "buy_probability": num("buy_probability"),
        "confidence_v3": num("confidence_v3"),
        "risk_permission": text("risk_permission"),
        "entry_timing_action": text("entry_timing_action"),
        "smart_money_score": num("smart_money_score"),
        "suggested_entry_price": num("suggested_entry_price"),
        "stop_loss": num("stop_loss"),
        "target_1": num("target_1"),
        "target_2": num("target_2"),
    }
    price = {
        "close": num("close"),
        "change_pct": num("change_pct"),
        "volume": num("volume"),
        "date": text("date"),
    }

    sentiment_cache = _read_json(SENTIMENT_CACHE)
    ticker_sentiment = (sentiment_cache.get("tickers", {}) or {}).get(symbol)

    try:
        from app.engines.stock_technicals import compute_technicals
        technicals = compute_technicals(symbol)
    except Exception:
        technicals = {}

    try:
        from app.engines.fundamentals_store import get_fundamentals
        fundamentals = get_fundamentals(symbol)
    except Exception:
        fundamentals = {}

    return {
        "symbol": symbol,
        "company": text("company"),
        "sector": text("sector"),
        "price": price,
        "scoring": scoring,
        "technicals": technicals,       # full per-stock panel (facts)
        "fundamentals": fundamentals,   # REAL P/E, EPS, mkt cap, free float (PSX)
        "news_sentiment": ticker_sentiment,  # None if no news matched this ticker
    }


SCREENERS_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "screeners.json"


@app.get("/screeners", dependencies=[Depends(require_api_key)])
def get_screeners() -> dict:
    """List available screeners (name, label, honest note, count) + as-of date."""
    data = _read_json(SCREENERS_FILE)
    if not data or not data.get("screeners"):
        raise HTTPException(status_code=404, detail="No screeners yet. Run the scan first.")
    scr = data["screeners"]
    return {
        "as_of_date": data.get("as_of_date"),
        "generated_at": data.get("generated_at"),
        "universe": data.get("universe"),
        "screeners": [
            {"name": k, "label": v.get("label"), "note": v.get("note"), "count": v.get("count", 0)}
            for k, v in scr.items()
        ],
    }


@app.get("/screener/{name}", dependencies=[Depends(require_api_key)])
def get_screener(name: str) -> dict:
    """Rows for one screener (e.g. upper_circuit, above_ma200, volume_spike)."""
    data = _read_json(SCREENERS_FILE)
    scr = (data.get("screeners") or {}).get(name)
    if not scr:
        raise HTTPException(status_code=404, detail=f"Screener '{name}' not found.")
    return {"name": name, "as_of_date": data.get("as_of_date"), **scr}


MODEL_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "model_picks.json"


@app.get("/model", dependencies=[Depends(require_api_key)])
def get_model() -> dict:
    """Walk-forward-validated model ranking of today's stocks, with its measured
    out-of-sample track record and caveats. A small real edge, not a sure thing."""
    data = _read_json(MODEL_FILE)
    if not data:
        raise HTTPException(status_code=404, detail="No model output yet. Run the scan first.")
    return data


SEASONALITY_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "seasonality.json"


@app.get("/seasonality", dependencies=[Depends(require_api_key)])
def get_seasonality() -> dict:
    """Day-of-week and month-of-year historical return patterns (context, not a rule)."""
    data = _read_json(SEASONALITY_FILE)
    if not data:
        raise HTTPException(status_code=404, detail="No seasonality yet. Run the scan first.")
    return data


HIGHLIGHTS_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "highlights.json"


@app.get("/highlights", dependencies=[Depends(require_api_key)])
def get_highlights() -> dict:
    """Today's Highlights digest: breakouts, accumulation, new highs, hot sectors,
    news — all the day's triggers in one place. Facts / a watch-list, not signals."""
    data = _read_json(HIGHLIGHTS_FILE)
    if not data:
        raise HTTPException(status_code=404, detail="No highlights yet. Run the scan first.")
    return data


SECTORS_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "sector_rotation.json"


@app.get("/sectors", dependencies=[Depends(require_api_key)])
def get_sectors() -> dict:
    """Sector rotation: sectors ranked by this week's move, with 1d/1m/200d
    context, breadth, volume trend, accelerating/fading flag, and top stocks."""
    data = _read_json(SECTORS_FILE)
    if not data:
        raise HTTPException(status_code=404, detail="No sector data yet. Run the scan first.")
    return data


BRIEFING_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "morning_briefing.json"


@app.get("/briefing", dependencies=[Depends(require_api_key)])
def get_briefing() -> dict:
    """Pre-market morning briefing: market pulse, day/week/month/200d trends,
    top movers, relatively strongest setups, news. Analysis, not a forecast."""
    data = _read_json(BRIEFING_FILE)
    if not data:
        raise HTTPException(status_code=404, detail="No briefing yet. Run the scan first.")
    return data


ALL_STOCKS_FILE = Path(__file__).resolve().parents[1] / "reports" / "latest" / "all_stocks.json"


@app.get("/stocks", dependencies=[Depends(require_api_key)])
def get_stocks(page: int = 1, size: int = 50, q: str | None = None, sort: str = "rank") -> dict:
    """
    EVERY stock, paginated (default 50/page), ranked by real buy_probability.
    Optional ?q= filters by symbol/company. This is a ranked list, not a buy
    list — see the returned `note`.
    """
    data = _read_json(ALL_STOCKS_FILE)
    rows = data.get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="No stock list yet. Run the scan first.")

    if q:
        ql = q.strip().upper()
        rows = [
            r for r in rows
            if ql in str(r.get("symbol", "")).upper() or ql in str(r.get("company", "")).upper()
        ]

    # sort options: rank (default), change_pct, ret_1w, ret_1m, ret_200d, buy_probability
    if sort and sort != "rank" and rows and sort in rows[0]:
        rows = sorted(rows, key=lambda r: (r.get(sort) is None, -(r.get(sort) or 0)))

    size = max(1, min(size, 100))
    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, pages))
    start = (page - 1) * size
    return {
        "as_of_date": data.get("as_of_date"),
        "note": data.get("note"),
        "total": total,
        "page": page,
        "pages": pages,
        "size": size,
        "rows": rows[start:start + size],
    }


@app.post("/ask", dependencies=[Depends(require_api_key)])
def post_ask(body: QueryRequest) -> dict:
    """Local NLP assistant — answers questions straight from the pipeline's JSON
    data. NO external AI (no Gemini/Anthropic), no cost, always current, never
    hallucinates. Understands English + Roman-Urdu."""
    from app.engines.local_assistant_v1 import answer
    return {"question": body.question, "answer": answer(body.question), "engine": "local"}


@app.post("/query", dependencies=[Depends(require_api_key)])
def post_query(body: QueryRequest, stream: bool = False):
    """
    Ask the grounded assistant a question. Returns a full JSON answer by default;
    pass ?stream=true for a text/plain streamed response (for the future web/mobile
    clients). Assistant/billing/network failures return a clean JSON error.
    """
    try:
        client = get_client()
        system_prompt = build_system_prompt(load_context())
    except Exception as exc:
        # e.g. missing API key
        raise HTTPException(status_code=503, detail=f"Assistant unavailable: {exc}")

    messages = [{"role": "user", "content": body.question}]

    if stream:
        def generate():
            try:
                for chunk in stream_answer(client, system_prompt, messages):
                    yield chunk
            except Exception as exc:  # best-effort: stream ends with an error marker
                yield f"\n[error] {type(exc).__name__}: {exc}"

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    try:
        answer = "".join(stream_answer(client, system_prompt, messages))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant error: {type(exc).__name__}: {exc}")

    return {"question": body.question, "model": MODEL, "answer": answer}
