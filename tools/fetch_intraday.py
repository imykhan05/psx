"""
Intraday (near-live) snapshot fetcher.

Scrapes the PSX market-watch (https://dps.psx.com.pk/market-watch), which updates
during trading hours, into reports/latest/intraday.json — current price, day
high/low, change%, and volume for every stock, plus intraday top gainers /
losers / most-active. Run it every ~30 minutes 09:30–17:00 (a scheduled task).

HONEST scope: this is a periodic snapshot of the exchange's own market-watch page.
It is near-live (page-level, not tick-by-tick) and it is DATA, not a prediction.
It does not "learn" anything — it reports what the market is doing right now.
"""

from __future__ import annotations

import html as H
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "intraday.json"
LOG_FILE = PROJECT_ROOT / "logs" / "intraday.log"
URL = "https://dps.psx.com.pk/market-watch"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _num(s):
    try:
        return float(re.sub(r"[^\d.\-]", "", s))
    except (TypeError, ValueError):
        return None


def _clean(c: str) -> str:
    return H.unescape(re.sub(r"<[^>]+>", "", c)).strip()


def fetch() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Referer": "https://dps.psx.com.pk/"})
    html = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")

    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        if "/company/" not in row:
            continue
        cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 11:
            continue
        sym = cells[0]
        if not sym or re.match(r"^P\d", sym) or "TFC" in sym:
            continue
        rows.append({
            "symbol": sym,
            "ldcp": _num(cells[3]),
            "open": _num(cells[4]),
            "high": _num(cells[5]),
            "low": _num(cells[6]),
            "current": _num(cells[7]),
            "change": _num(cells[8]),
            "change_pct": _num(cells[9]),
            "volume": _num(cells[10]),
        })

    def top(key, reverse, n=15, need_positive=None):
        f = [r for r in rows if r.get(key) is not None]
        if need_positive is not None:
            f = [r for r in f if (r["change_pct"] or 0) * need_positive > 0]
        f.sort(key=lambda r: r[key], reverse=reverse)
        return f[:n]

    return {
        "engine_version": "intraday_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "advancers": sum(1 for r in rows if (r.get("change_pct") or 0) > 0),
        "decliners": sum(1 for r in rows if (r.get("change_pct") or 0) < 0),
        "top_gainers": top("change_pct", True, need_positive=1),
        "top_losers": top("change_pct", False, need_positive=-1),
        "most_active": top("volume", True),
        "rows": rows,
    }


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        data = fetch()
    except Exception as exc:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  ERROR {type(exc).__name__}: {exc}\n")
        print(f"[intraday] ERROR: {exc}")
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    msg = f"snapshot: {data['count']} stocks, {data['advancers']} up / {data['decliners']} down"
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}  {msg}\n")
    print(f"[intraday] {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
