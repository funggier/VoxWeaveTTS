@echo off
setlocal
rem Force-stop only this VoxWeaveTTS installation and its owned workers.
rem Ollama/other apps are intentionally excluded.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Stop-VoxWeaveTTS.ps1" -ProjectRoot "%~dp0." %*
set "code=%ERRORLEVEL%"
if not "%code%"=="0" (
    echo [VoxWeaveTTS] Stop failed with error %code%.
)
endlocal & exit /b %code%
