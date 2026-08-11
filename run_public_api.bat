@echo off
REM ============================================================================
REM  PSX AI Scanner - launch the API publicly via Cloudflare Tunnel (no card).
REM
REM  Double-click this file. It:
REM    1) downloads cloudflared once into bin\ (if missing),
REM    2) starts the FastAPI server on 127.0.0.1:8000 (reads PSX_API_KEY from .env),
REM    3) opens a public HTTPS tunnel and prints your URL.
REM
REM  Copy the printed https://xxxx.trycloudflare.com URL and your API key into the
REM  app Settings screen. Keep this window open while using the app.
REM  The URL changes each time you relaunch (quick-tunnel), so re-paste it then.
REM ============================================================================
setlocal
cd /d D:\PSX_AI_SCANNER

if not exist "bin" mkdir bin
if not exist "bin\cloudflared.exe" (
    echo Downloading cloudflared ^(one-time, ~50MB^)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'bin\cloudflared.exe'"
)

echo Starting PSX API server on http://127.0.0.1:8000 ...
start "PSX API server" cmd /k "python -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

timeout /t 5 /nobreak >nul
echo.
echo ============================================================
echo  Your PUBLIC HTTPS URL appears below:
echo    https://xxxx.trycloudflare.com
echo  Put that URL + your API key into the app Settings screen.
echo  Keep this window open while you use the app.  Ctrl+C to stop.
echo ============================================================
echo.
bin\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate
