@echo off
REM ============================================================================
REM  PSX AI Scanner - MORNING BRIEFING job (schedule ~09:00, before the open).
REM
REM  1) refresh news sentiment (this morning's headlines)
REM  2) rebuild the pre-market briefing from the latest end-of-day scan
REM     (day/week/month/200-day trends + top setups + news)
REM
REM  Note: before the 9:30 open there is no new PRICE data, so this is analysis
REM  of the latest close + fresh news, NOT a forecast.
REM
REM  Schedule it (run once, elevated):
REM    schtasks /Create /TN "PSX_AI_Scanner_Morning" /SC DAILY /ST 09:00 ^
REM      /TR "D:\PSX_AI_SCANNER\run_morning.bat" /F
REM ============================================================================
cd /d D:\PSX_AI_SCANNER

set "PY=C:\Users\Imran\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=python"

echo [%date% %time%] 1/2 refreshing news...
"%PY%" tools\refresh_sentiment.py

echo [%date% %time%] 2/2 building morning briefing...
"%PY%" -m app.engines.morning_briefing_engine_v1

echo [%date% %time%] morning briefing complete.
