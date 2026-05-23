@echo off
chcp 65001 >nul
title 9router Import Tool
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   9router Import Tool               ║
echo  ║   Import ChatGPT sessions nhanh     ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Dang khoi dong...
echo.
python "%~dp0server.py"
if %errorlevel% neq 0 (
    echo.
    echo  [!] Can cai Python: https://python.org
    echo.
    pause
)
