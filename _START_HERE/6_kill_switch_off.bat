@echo off
chcp 65001 > nul
setlocal

REM Resume normal operation (kill_switch back to false).

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo === Resuming: disabling kill_switch ===
python -m scripts.kill_switch --off
set EXIT_CODE=%errorlevel%

echo.
pause
exit /b %EXIT_CODE%
