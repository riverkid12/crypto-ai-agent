@echo off
chcp 65001 > nul
setlocal

REM EMERGENCY STOP: block all new entries.
REM (Risk-reducing actions like close/stop/cancel still execute.)

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo === EMERGENCY STOP: enabling kill_switch ===
python -m scripts.kill_switch --on
set EXIT_CODE=%errorlevel%

echo.
echo No new positions will open. Existing positions can still close on stop/target.
echo Run "6_kill_switch_off.bat" to resume.
pause
exit /b %EXIT_CODE%
