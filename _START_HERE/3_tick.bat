@echo off
chcp 65001 > nul
setlocal

REM Run a single tick against Turso + Binance testnet.
REM Double-click this file to execute manually. .env is auto-loaded by tick.py.

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  echo Run: python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo === crypto-ai-agent: running tick ===
echo.
python -m executor.tick
set EXIT_CODE=%errorlevel%

echo.
echo === Done (exit code %EXIT_CODE%) ===
pause
exit /b %EXIT_CODE%
