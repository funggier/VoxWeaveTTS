@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
if exist "%CD%\runtime\python\python.exe" (
    "%CD%\runtime\python\python.exe" -m voxweavetts --port 8765
) else (
    python -m voxweavetts --port 8765
)
if errorlevel 1 (
    echo.
    echo [VoxWeaveTTS] Development launcher needs Python 3.11+.
    pause
)
endlocal
