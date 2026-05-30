@echo off
chcp 65001 > nul
setlocal

REM Show a one-shot status snapshot: positions, signals, orders, events,
REM Binance balance, control flags. Reads .env automatically.

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

python -m scripts.status
set EXIT_CODE=%errorlevel%

echo.
pause
exit /b %EXIT_CODE%
