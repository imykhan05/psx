@echo off
cd /d D:\PSX_AI_SCANNER
python institutional_terminal_v1.py --project-root "D:\PSX_AI_SCANNER"
if errorlevel 1 pause
