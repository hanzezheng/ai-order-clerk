@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Install once with: .venv\Scripts\python.exe -m pip install -e ".[dev]"
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\start_clerk.py" %*
if errorlevel 1 pause
