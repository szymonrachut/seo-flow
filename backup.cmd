@echo off
setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set PS1=%SCRIPT_DIR%scripts\checkpoint.ps1

if not exist "%PS1%" (
  echo Nie znaleziono pliku: %PS1%
  echo Umiesc backup.cmd w katalogu glownym repo, a checkpoint.ps1 w katalogu scripts.
  exit /b 1
)

if not "%~1"=="" (
  set "CHECKPOINT_NAME=%~1"
) else (
  set /p CHECKPOINT_NAME=Podaj nazwe checkpointu ^(Enter = wygeneruj automatycznie^): 

  if "!CHECKPOINT_NAME!"=="" (
    for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "CHECKPOINT_NAME=checkpoint_%%i"
  )
)

echo Uruchamiam backup: %CHECKPOINT_NAME%
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Name "%CHECKPOINT_NAME%" -Zip

if errorlevel 1 (
  echo Backup zakonczyl sie bledem.
  exit /b 1
)

echo.
echo Backup zakonczony poprawnie.
endlocal
