@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul || (
    echo Python is required. Install standard CPython 3.12, then run this file again.
    pause
    exit /b 1
  )
)
set "BOOTPY=python"
where py >nul 2>nul && set "BOOTPY=py"
%BOOTPY% bootstrap_local.py
if errorlevel 1 (
  echo.
  echo Local setup did not complete. Run Python_Doctor.bat for details.
  pause
  exit /b 1
)
echo.
echo Setup complete.
pause
