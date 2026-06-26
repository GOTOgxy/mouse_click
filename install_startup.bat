@echo off
setlocal

cd /d "%~dp0"

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\mouse_remapper.bat"

copy /y "%~dp0启动.bat" "%TARGET%" >nul

if exist "%TARGET%" (
  echo Startup install complete.
) else (
  echo Install failed.
)

echo.
pause
endlocal
