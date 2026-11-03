@echo off
title AniFilter AI - Public Online Launcher
chcp 65001 >nul

echo ========================================================
echo   กำลังเริ่มระบบ AniFilter AI + Cloudflare Public Tunnel
echo ========================================================
cd /d "%~dp0"

start "" python run.py
timeout /t 2 >nul
.\cloudflared.exe tunnel --url http://127.0.0.1:8080
pause
