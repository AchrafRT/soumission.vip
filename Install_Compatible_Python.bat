@echo off
setlocal
cd /d "%~dp0"
echo Installing standard CPython 3.12 with Windows Package Manager...
where winget >nul 2>nul || (
  echo winget was not found. Install standard Python 3.12 from python.org and re-run Launch_DirectoryForge.bat.
  pause
  exit /b 1
)
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo Python installation did not complete.
  pause
  exit /b 1
)
echo.
echo Python 3.12 installation requested. Close this window and run Launch_DirectoryForge.bat again.
pause
