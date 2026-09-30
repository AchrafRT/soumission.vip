@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (py bootstrap_local.py --doctor & pause & exit /b)
where python >nul 2>nul && (python bootstrap_local.py --doctor & pause & exit /b)
echo No Python launcher or python.exe found in PATH.
pause
