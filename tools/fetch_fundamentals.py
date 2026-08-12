"""
PSX fundamentals fetcher — REAL data, scraped from the official PSX company pages
(https://dps.psx.com.pk/company/<SYMBOL>), which are server-rendered and free.

Extracts the core valuation fundamentals per symbol:
    pe_ttm, eps, market_cap, shares, free_float_pct, wk52_low, wk52_high

Saves to database/fundamentals/psx_fundamentals.json (keyed by symbol, with a
fetch timestamp). This REPLACES the fabricated fundamentals that were quarantined
in F0.1 — it is genuine, sourced data, never invented. Missing/unlisted symbols
are simply skipped.

Usage:
    python tools/fetch_fundamentals.py --symbol HBL
    python tools/fetch_fundamentals.py            # batch over the current universe
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
OUT_PATH = PROJECT_ROOT / "database" / "fundamentals" / "psx_fundamentals.json"
LOG_FILE = PROJECT_ROOT / "logs" / "fundamentals_fetch.log"
URL = "https://dps.psx.com.pk/company/{sym}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _num(s):
    if s is None:
        return None
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def parse(html: str) -> dict:
    def stat(label_re):
        m = re.search(r'stats_label">\s*' + label_re +
                      r'[^<]*</div>\s*<div class="stats_value">(.*?)</div>', html, re.I)
        return m.group(1) if m else None

    pe = _num(stat(r"P/E Ratio"))
    # Market Cap label has a nested <span>, so match tolerantly to the next value.
    mm = re.search(r'Market Cap[\s\S]*?stats_value">([\d,\.]+)', html, re.I)
    mcap_000 = _num(mm.group(1)) if mm else None
    shares = _num(stat(r"Shares"))
    # free float % is the stats_value containing a %
    ff = None
    m = re.search(r'Free Float</div>\s*<div class="stats_value">([\d.]+)\s*%', html)
    if m:
        ff = _num(m.group(1))
    # 52-week range "low – high"
    wk_lo = wk_hi = None
    m = re.search(r'52-WEEK RANGE[^<]*</div>\s*<div class="stats_value">(.*?)</div>', html, re.I)
    if m:
        parts = re.findall(r"[\d,]+\.?\d*", m.group(1))
        if len(parts) >= 2:
            wk_lo, wk_hi = _num(parts[0]), _num(parts[1])
    # EPS from the financials table (latest column)
    eps = None
    m = re.search(r"<td>\s*EPS\s*</td>\s*<td[^>]*>\s*<span[^>]*>(.*?)</span>", html, re.I)
    if m:
        eps = _num(m.group(1))

    return {
        "pe_ttm": pe,
        "eps": eps,
        "market_cap": (mcap_000 * 1000) if mcap_000 is not None else None,
        "shares": shares,
        "free_float_pct": ff,
        "wk52_low": wk_lo,
        "wk52_high": wk_hi,
    }


def fetch_one(sym: str) -> dict | None:
    req = urllib.request.Request(URL.format(sym=sym),
                                 headers={"User-Agent": UA, "Referer": "https://dps.psx.com.pk/"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:
        return None
    data = parse(html)
    # require at least one real number, else treat as no-data
    if all(v is None for v in data.values()):
        return None
    return data


def _universe() -> list[str]:
    con = sqlite3.connect(DB_PATH)
    try:
        mx = con.execute("SELECT MAX(date_parsed) FROM daily_prices").fetchone()[0]
        rows = con.execute(
            "SELECT DISTINCT symbol FROM daily_prices WHERE date_parsed = ?", [mx]).fetchall()
    finally:
        con.close()
    syms = [r[0] for r in rows]
    return [s for s in syms if not re.match(r"^P\d", s) and "TFC" not in s]


def _log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {msg}\n")
    print(f"[fundamentals] {msg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol")
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()

    if args.symbol:
        d = fetch_one(args.symbol.upper())
        print(json.dumps({args.symbol.upper(): d}, indent=2))
        return 0

    syms = _universe()
    _log(f"batch: {len(syms)} symbols")
    store = {}
    ok = 0
    for i, s in enumerate(syms, 1):
        d = fetch_one(s)
        if d:
            store[s] = d
            ok += 1
        if i % 50 == 0:
            _log(f"  {i}/{len(syms)} ({ok} with data)")
        time.sleep(args.delay)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_meta": {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "count": ok, "source": "dps.psx.com.pk (scraped)"}, **store}
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"done: {ok}/{len(syms)} symbols with fundamentals -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
