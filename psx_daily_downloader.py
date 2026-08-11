import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright


BASE_HOME = "https://dps.psx.com.pk/downloads"
BASE_DOWNLOAD = "https://dps.psx.com.pk/download/mkt_summary/{date}.Z"


def date_range(start_date, end_date):
    d = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def today_text():
    return datetime.now().strftime("%Y-%m-%d")


def yesterday_text():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def last_days_range(days: int):
    end = datetime.now().date()
    start = end - timedelta(days=days - 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


async def download_with_browser_session(page, date_text, save_path):
    url = BASE_DOWNLOAD.format(date=date_text)

    try:
        response = await page.request.get(
            url,
            headers={
                "Referer": BASE_HOME,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
            },
            timeout=60000,
        )

        status = response.status

        if status == 404:
            return "missing", url

        if status == 403:
            return "forbidden", url

        if status != 200:
            return f"failed_http_{status}", url

        data = await response.body()

        if len(data) < 100:
            return "empty", url

        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(data)

        return "ok", url

    except Exception as e:
        return f"error_{e}", url


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--from-date")
    parser.add_argument("--to-date")

    parser.add_argument("--today", action="store_true")
    parser.add_argument("--yesterday", action="store_true")
    parser.add_argument("--last-days", type=int)

    parser.add_argument(
        "--output",
        default=r"D:\PSX_AI_SCANNER\database\historical_files",
    )

    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--show-browser", action="store_true")

    args = parser.parse_args()

    if args.today:
        from_date = today_text()
        to_date = today_text()
    elif args.yesterday:
        from_date = yesterday_text()
        to_date = yesterday_text()
    elif args.last_days:
        from_date, to_date = last_days_range(args.last_days)
    else:
        if not args.from_date or not args.to_date:
            raise ValueError("Use --today, --yesterday, --last-days N, or --from-date and --to-date")

        from_date = args.from_date
        to_date = args.to_date

    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    log_path = output_root / "daily_download_log.txt"

    downloaded = 0
    skipped = 0
    missing = 0
    failed = 0
    forbidden = 0

    print("=" * 70)
    print("PSX DAILY DOWNLOADER")
    print("=" * 70)
    print("From:", from_date)
    print("To:", to_date)
    print("Output:", output_root)
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.show_browser)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(BASE_HOME, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        for d in date_range(from_date, to_date):
            date_text = d.strftime("%Y-%m-%d")
            year_folder = output_root / str(d.year)
            save_path = year_folder / f"{date_text}_mkt_summary.Z"

            print(f"[{date_text}] Checking...")

            if save_path.exists() and save_path.stat().st_size > 100:
                print("  SKIP already exists")
                skipped += 1
                write_log(log_path, date_text, "SKIPPED", "", save_path)
                continue

            result, url = await download_with_browser_session(page, date_text, save_path)

            if result == "ok":
                print("  OK downloaded")
                downloaded += 1
                write_log(log_path, date_text, "OK", url, save_path)

            elif result in ["missing", "empty"]:
                print("  MISSING / holiday / no file")
                missing += 1
                write_log(log_path, date_text, "MISSING", url, "")

            elif result == "forbidden":
                print("  FORBIDDEN 403")
                forbidden += 1
                write_log(log_path, date_text, "FORBIDDEN", url, "")

            else:
                print(f"  FAIL {result}")
                failed += 1
                write_log(log_path, date_text, f"FAIL {result}", url, "")

            await asyncio.sleep(args.delay)

        await browser.close()

    print()
    print("=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Downloaded       : {downloaded}")
    print(f"Skipped existing : {skipped}")
    print(f"Missing/Holidays : {missing}")
    print(f"Forbidden        : {forbidden}")
    print(f"Failed           : {failed}")
    print(f"Output           : {output_root}")
    print(f"Log              : {log_path}")
    print("=" * 70)


def write_log(log_path, date_text, status, url, save_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | {date_text} | {status} | {url} | {save_path}\n")


if __name__ == "__main__":
    asyncio.run(main())