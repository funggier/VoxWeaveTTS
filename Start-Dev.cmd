@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "HF_HOME=%CD%\cache\huggingface"
set "TORCH_HOME=%CD%\cache\torch"
set "XDG_CACHE_HOME=%CD%\cache"
set "TEMP=%CD%\cache\temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%" >nul 2>nul
if exist "%CD%\.venv\Scripts\python.exe" (
    "%CD%\.venv\Scripts\python.exe" -m voxweavetts --port 8765
) else if exist "%CD%\runtime\python\python.exe" (
    "%CD%\runtime\python\python.exe" -m voxweavetts --port 8765
) else (
    python -m voxweavetts --port 8765
)
if errorlevel 1 (
    echo.
    echo [VoxWeaveTTS] Could not start. Run scripts\Install-ThaiEngine.ps1 for Thai speech setup.
    pause
)
endlocal
