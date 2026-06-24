@echo off
setlocal

cd /d "%~dp0"

set "SOURCE=%CD%\启动.bat"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\mouse_remapper.bat"

if not exist "%SOURCE%" (
  echo 启动.bat not found:
  echo %SOURCE%
  goto :end
)

copy /y "%SOURCE%" "%TARGET%" >nul
if errorlevel 1 (
  echo Install failed.
  goto :end
)

if exist "%TARGET%" (
  echo Startup install complete.
  echo %TARGET%
) else (
  echo Install failed.
)

:end
echo.
pause
endlocal
