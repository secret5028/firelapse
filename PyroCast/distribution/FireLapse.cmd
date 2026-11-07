@echo off
if "%~1"=="" (
    start "" "%~dp0runtime\python\pythonw.exe" -B -X utf8 "%~dp0app\tools\launch_firelapse.py" --background
    exit /b
)
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0runtime\python\python.exe" -B -X utf8 "%~dp0app\tools\launch_firelapse.py" %*
if errorlevel 1 pause
