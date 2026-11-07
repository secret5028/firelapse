@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FireLapse-Setup.ps1"
set "status=%errorlevel%"
if not "%status%"=="0" pause
exit /b %status%
