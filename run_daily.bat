@echo off
REM ============================================================================
REM  PSX AI Scanner - DAILY PIPELINE (schedule this for 18:00 / 6 PM).
REM
REM  Steps:
REM    1) download any new EOD market-summary files from the PSX portal
REM    2) import the latest data + run the full scan (this also builds the
REM       daily signal AND the screeners)
REM    3) refresh news sentiment
REM
REM  The live Cloudflare tunnel / web page reads these files directly, so fresh
REM  results appear as soon as this finishes - no extra deploy step.
REM
REM  Schedule it (run once, elevated PowerShell/cmd):
REM    schtasks /Create /TN "PSX\DailyPipeline" /SC DAILY /ST 18:00 ^
REM      /TR "cmd /c cd /d D:\PSX_AI_SCANNER && run_daily.bat" /F
REM
REM  If the PC was off for several days (gap in data), run once:
REM    python main.py --backfill
REM ============================================================================
cd /d D:\PSX_AI_SCANNER

echo [%date% %time%] 1/3 downloading new EOD files...
python tools\download_eod.py

echo [%date% %time%] 2/3 importing latest + full scan (+ signal + screeners)...
python main.py --daily-import

echo [%date% %time%] 3/3 refreshing news sentiment...
python tools\refresh_sentiment.py

echo [%date% %time%] daily pipeline complete.
