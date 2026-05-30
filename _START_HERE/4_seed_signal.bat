@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM Interactive: seed a test signal into Turso (manual buy trigger for tick).

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo === Seed a test signal ===
echo Default universe: BTCUSDT / ETHUSDT / SOLUSDT
echo.

set "SYMBOL="
set /p SYMBOL=Symbol (default BTCUSDT):
if "!SYMBOL!"=="" set "SYMBOL=BTCUSDT"

set "SIZE="
set /p SIZE=Size USDT (default 50):
if "!SIZE!"=="" set "SIZE=50"

echo.
echo Seeding: symbol=!SYMBOL!  size=!SIZE!
echo.

python -m scripts.seed_signal --symbol "!SYMBOL!" --size !SIZE!
set EXIT_CODE=%errorlevel%

echo.
pause
exit /b %EXIT_CODE%
