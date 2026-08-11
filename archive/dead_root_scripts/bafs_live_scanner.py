"""
BAFS Live / Pre-Open Watcher
Symbol: BAFS — Baba Farid Sugar Mills Limited

Purpose:
- Opens the official PSX company page in Chromium.
- Refreshes repeatedly before/after market open.
- Extracts whichever quote fields are actually published on the page.
- Prints price, change, volume, bid/ask (when exposed), and gap.
- Saves snapshots to reports/live/BAFS_live.csv.

Important:
- This is a public-page watcher, not a licensed exchange feed.
- During pre-open, some fields may remain blank or may be indicative/delayed.
- Do not interpret an unexecuted pre-open order as a confirmed trade.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

SYMBOL = "BAFS"
COMPANY = "Baba Farid Sugar Mills Limited"
URL = f"https://dps.psx.com.pk/company/{SYMBOL}"
DEFAULT_OUTPUT = Path("reports/live/BAFS_live.csv")


@dataclass
class Quote:
    timestamp: str
    symbol: str = SYMBOL
    company: str = COMPANY
    last_price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open_price: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    bid_price: Optional[float] = None
    bid_volume: Optional[int] = None
    ask_price: Optional[float] = None
    ask_volume: Optional[int] = None
    gap_pct: Optional[float] = None
    buy_pressure_pct: Optional[float] = None
    signal: str = "WAIT"
    source_url: str = URL


def clean_number(value: str | None) -> Optional[float]:
    if not value:
        return None
    text = value.replace(",", "").replace("%", "").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def clean_int(value: str | None) -> Optional[int]:
    number = clean_number(value)
    return int(number) if number is not None else None


def first_match(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def extract_quote(page: Page) -> Quote:
    body = page.locator("body").inner_text(timeout=15_000)
    # Normalize unusual spaces but retain line boundaries.
    body = body.replace("\xa0", " ")

    quote = Quote(timestamp=datetime.now().astimezone().isoformat(timespec="seconds"))

    # These patterns deliberately support multiple PSX page layouts.
    quote.last_price = clean_number(first_match(body, [
        r"(?:LAST PRICE|LAST|CURRENT PRICE|PRICE)\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
        rf"\b{SYMBOL}\b[\s\S]{{0,160}}?(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.change = clean_number(first_match(body, [
        r"(?:CHANGE|NET CHANGE)\s*[:\-]?\s*([+-]?[\d,]+(?:\.\d+)?)",
    ]))
    quote.change_pct = clean_number(first_match(body, [
        r"(?:CHANGE %|PERCENT CHANGE|CHANGE)\s*[:\-]?\s*([+-]?[\d,]+(?:\.\d+)?)\s*%",
        r"\(([+-]?[\d,]+(?:\.\d+)?)%\)",
    ]))
    quote.open_price = clean_number(first_match(body, [
        r"\bOPEN\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.high = clean_number(first_match(body, [
        r"\bHIGH\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.low = clean_number(first_match(body, [
        r"\bLOW\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.previous_close = clean_number(first_match(body, [
        r"(?:PREVIOUS CLOSE|PREV\.?\s*CLOSE|LDCP)\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.volume = clean_int(first_match(body, [
        r"\bVOLUME\s*[:\-]?\s*([\d,]+)",
    ]))
    quote.bid_price = clean_number(first_match(body, [
        r"(?:BEST BID|BID PRICE|BID)\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.bid_volume = clean_int(first_match(body, [
        r"(?:BID VOLUME|BID QTY|BUY VOLUME|BUY QTY)\s*[:\-]?\s*([\d,]+)",
    ]))
    quote.ask_price = clean_number(first_match(body, [
        r"(?:BEST ASK|ASK PRICE|ASK|OFFER PRICE|OFFER)\s*[:\-]?\s*(?:RS\.?|PKR)?\s*([\d,]+(?:\.\d+)?)",
    ]))
    quote.ask_volume = clean_int(first_match(body, [
        r"(?:ASK VOLUME|ASK QTY|SELL VOLUME|SELL QTY|OFFER VOLUME|OFFER QTY)\s*[:\-]?\s*([\d,]+)",
    ]))

    reference_price = quote.open_price or quote.last_price
    if (
        reference_price is not None
        and quote.previous_close not in (None, 0)
    ):
        quote.gap_pct = round(
            ((reference_price - quote.previous_close) / quote.previous_close) * 100,
            2,
        )

    if quote.bid_volume is not None and quote.ask_volume is not None:
        total = quote.bid_volume + quote.ask_volume
        if total > 0:
            quote.buy_pressure_pct = round((quote.bid_volume / total) * 100, 2)

    quote.signal = build_signal(quote)
    return quote


def build_signal(quote: Quote) -> str:
    """
    Conservative status only. It does not make a guaranteed buy call.
    """
    if quote.last_price is None and quote.open_price is None:
        return "NO LIVE QUOTE / PRE-OPEN DATA NOT PUBLISHED"

    pressure = quote.buy_pressure_pct
    gap = quote.gap_pct
    volume = quote.volume or 0

    if pressure is not None:
        if pressure >= 70 and (gap is None or gap >= 0):
            return "STRONG BUY QUEUE — WAIT FOR EXECUTED TRADE"
        if pressure <= 30:
            return "SELL PRESSURE — AVOID EARLY ENTRY"

    if gap is not None and gap >= 3 and volume > 0:
        return "GAP-UP WITH TRADED VOLUME — WATCH, DO NOT CHASE"
    if gap is not None and gap <= -3:
        return "WEAK OPEN / GAP-DOWN"

    if volume > 0:
        return "TRADE DETECTED — MONITOR CONTINUATION"
    return "INDICATIVE ONLY — WAIT FOR MARKET EXECUTION"


def save_quote(path: Path, quote: Quote) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(quote)
    new_file = not path.exists()

    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=row.keys())
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def format_value(value: object, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    if isinstance(value, int):
        return f"{value:,}{suffix}"
    return f"{value}{suffix}"


def print_quote(quote: Quote) -> None:
    print("\n" + "=" * 68)
    print(f"{quote.timestamp} | {quote.symbol} — {quote.company}")
    print("-" * 68)
    print(f"Last Price     : {format_value(quote.last_price)}")
    print(f"Open / High/Low: {format_value(quote.open_price)} / "
          f"{format_value(quote.high)} / {format_value(quote.low)}")
    print(f"Previous Close : {format_value(quote.previous_close)}")
    print(f"Change         : {format_value(quote.change)} "
          f"({format_value(quote.change_pct, '%')})")
    print(f"Volume         : {format_value(quote.volume)}")
    print(f"Bid            : {format_value(quote.bid_price)} | "
          f"Qty {format_value(quote.bid_volume)}")
    print(f"Ask            : {format_value(quote.ask_price)} | "
          f"Qty {format_value(quote.ask_volume)}")
    print(f"Gap            : {format_value(quote.gap_pct, '%')}")
    print(f"Buy Pressure   : {format_value(quote.buy_pressure_pct, '%')}")
    print(f"Status         : {quote.signal}")
    print("=" * 68)


def open_browser(headless: bool) -> tuple[object, Browser, BrowserContext, Page]:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    return playwright, browser, context, page


def run(interval: int, headless: bool, once: bool, output: Path) -> int:
    playwright = browser = context = page = None
    try:
        playwright, browser, context, page = open_browser(headless=headless)
        print(f"Opening official PSX page: {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(3_000)

        while True:
            try:
                # Reload so public quote values can update.
                page.reload(wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(2_000)
                quote = extract_quote(page)
                print_quote(quote)
                save_quote(output, quote)
                print(f"Saved: {output.resolve()}")
            except PlaywrightTimeoutError:
                print("PSX page timeout. Retrying on next cycle.", file=sys.stderr)
            except Exception as exc:
                print(f"Snapshot failed: {exc}", file=sys.stderr)

            if once:
                break
            time.sleep(max(interval, 3))
        return 0
    except KeyboardInterrupt:
        print("\nWatcher stopped by user.")
        return 0
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        print(
            "Run: python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1
    finally:
        if context:
            context.close()
        if browser:
            browser.close()
        if playwright:
            playwright.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch BAFS live/pre-open data from the official PSX page."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Refresh interval in seconds (default: 10).",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show Chromium while scanning.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take one snapshot and exit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run(
            interval=args.interval,
            headless=not args.show_browser,
            once=args.once,
            output=args.output,
        )
    )
