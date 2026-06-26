@echo off
setlocal
cd /d "%~dp0"

set "BAT=%CD%\mouse_remapper.bat"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Mouse Remapper.lnk"

if not exist "%BAT%" (
  echo mouse_remapper.bat not found
  goto :end
)

set "VBS=%TEMP%\pin_to_start_%RANDOM%.vbs"
echo Set ws = CreateObject("WScript.Shell") > "%VBS%"
echo Set sc = ws.CreateShortcut("%LNK%") >> "%VBS%"
echo sc.TargetPath = "%BAT%" >> "%VBS%"
echo sc.WorkingDirectory = "%CD%" >> "%VBS%"
echo sc.Description = "Mouse Remapper" >> "%VBS%"
echo sc.Save >> "%VBS%"
cscript //nologo "%VBS%"
del /f /q "%VBS%"

if exist "%LNK%" (
  echo.
  echo Done! Open Start Menu, find "Mouse Remapper", right-click and select "Pin to Start".
) else (
  echo Create shortcut failed.
)

:end
echo.
pause
endlocal
