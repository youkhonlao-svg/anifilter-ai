@echo off
title AniFilter AI - Push to Cloud (Auto-Deploy)
chcp 65001 >nul

echo ========================================================
echo   AniFilter AI - ส่งโค้ดขึ้น GitHub เพื่อ Auto-Deploy 24 ชม.
echo ========================================================
cd /d "%~dp0"

"C:\Program Files\Git\cmd\git.exe" add .
set /p msg="พิมพ์ข้อความสรุปการอัปเดต (กด Enter เพื่อใช้ค่าเริ่มต้น): "
if "%msg%"=="" set msg=Update features and curation

"C:\Program Files\Git\cmd\git.exe" commit -m "%msg%"
"C:\Program Files\Git\cmd\git.exe" push origin main

echo.
echo ========================================================
echo   สำเร็จ! Render / Cloud จะเริ่ม Auto-Deploy ให้อัตโนมัติทันที
echo ========================================================
pause
