@echo off
REM ============================================================================
REM  PSX AI Scanner - INTRADAY snapshot (near-live). Runs every ~30 min during
REM  market hours via a scheduled task; grabs the PSX market-watch into
REM  reports/latest/intraday.json for the /intraday endpoint + web card.
REM
REM  Schedule (run once, elevated) - daily 09:30, repeat every 30 min for 8h:
REM    schtasks /Create /TN "PSX_Intraday" /SC DAILY /ST 09:30 /RI 30 ^
REM      /DU 0008:00 /TR "D:\PSX_AI_SCANNER\run_intraday.bat" /F
REM ============================================================================
cd /d D:\PSX_AI_SCANNER
set "PY=C:\Users\Imran\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" tools\fetch_intraday.py
