@echo off
title AniFilter AI Launcher
chcp 65001 >nul

echo ========================================================
echo   กำลังเริ่มระบบ AniFilter AI (Financial Design)
echo ========================================================
cd /d "%~dp0"

:: Start browser to port 8080 (clean cache origin)
start "" http://localhost:8080

:: Run backend server
python run.py
pause
