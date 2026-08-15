@echo off
:: Auto-elevate to admin for site blocking
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"
start "" pythonw main.py
