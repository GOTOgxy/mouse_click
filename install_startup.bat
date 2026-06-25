@echo off
setlocal

cd /d "%~dp0"

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\mouse_remapper.bat"

copy /y "%~dp0启动.bat" "%TARGET%" >nul
copy /y "%~dp0launch.vbs" "%STARTUP_DIR%\launch.vbs" >nul

if exist "%TARGET%" (
  echo Startup install complete.
) else (
  echo Install failed.
)

:end
echo.
pause
endlocal
