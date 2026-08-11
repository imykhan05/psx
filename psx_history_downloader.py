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
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument(
        "--output",
        default=str(Path.home() / "Downloads" / "PSX_HISTORY"),
    )
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--show-browser", action="store_true")

    args = parser.parse_args()

    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    log_path = output_root / "download_log.txt"

    downloaded = 0
    skipped = 0
    missing = 0
    failed = 0
    forbidden = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.show_browser)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(BASE_HOME, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        for d in date_range(args.from_date, args.to_date):
            date_text = d.strftime("%Y-%m-%d")
            year_folder = output_root / str(d.year)
            save_path = year_folder / f"{date_text}_mkt_summary.Z"

            print(f"[{date_text}] Checking...")

            if save_path.exists() and save_path.stat().st_size > 100:
                print("  SKIP already exists")
                skipped += 1
                continue

            result, url = await download_with_browser_session(page, date_text, save_path)

            if result == "ok":
                print("  OK downloaded")
                downloaded += 1
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{date_text} | OK | {url} | {save_path}\n")

            elif result == "missing" or result == "empty":
                print("  MISSING / holiday / no file")
                missing += 1
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{date_text} | MISSING | {url}\n")

            elif result == "forbidden":
                print("  FORBIDDEN 403")
                forbidden += 1
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{date_text} | FORBIDDEN | {url}\n")

            else:
                print(f"  FAIL {result}")
                failed += 1
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{date_text} | FAIL | {url} | {result}\n")

            await asyncio.sleep(args.delay)

        await browser.close()

    print("\nDone.")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped: {skipped}")
    print(f"Missing/Holidays: {missing}")
    print(f"Forbidden: {forbidden}")
    print(f"Failed: {failed}")
    print(f"Output: {output_root}")


if __name__ == "__main__":
    asyncio.run(main())