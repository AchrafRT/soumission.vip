@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe server.py
) else (
  where py >nul 2>nul && (py server.py) || (python server.py)
)
if errorlevel 1 pause
