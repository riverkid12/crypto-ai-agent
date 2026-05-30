@echo off
chcp 65001 > nul
setlocal

REM Live status dashboard: refreshes every 10 seconds. Ctrl+C to exit.

cd /d "%~dp0\.."

if not exist "venv\Scripts\activate.bat" (
  echo ERROR: venv not found at %CD%\venv
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

python -m scripts.status --watch
REM no pause: --watch loop ends on Ctrl+C, user already sees output
exit /b %errorlevel%
