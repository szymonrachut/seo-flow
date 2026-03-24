@echo off
powershell -ExecutionPolicy Bypass -File ".\scripts\start-local.ps1"
set EXITCODE=%ERRORLEVEL%
pause
exit /b %EXITCODE%
