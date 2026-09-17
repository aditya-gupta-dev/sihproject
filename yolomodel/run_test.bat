@echo off
title Mine Brain Test
cd /d "e:\SIH"
echo ============================================================
echo Starting Mine Brain Test...
echo ============================================================
"C:\Users\omkan\AppData\Local\Microsoft\WindowsApps\python3.11.exe" brain_engine_test.py
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)
