@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || goto :error
if "%DEV_PASSWORD%"=="" set /p DEV_PASSWORD=Choose your setup password: 
set HOST=127.0.0.1
set PORT=8768
start "" http://127.0.0.1:8768
python server.py
goto :eof
:error
echo.
echo Python was not found on PATH. Install Python 3.11+ and try again.
pause
exit /b 1
