@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "PYTHONNOUSERSITE=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "HF_HOME=%CD%\cache\huggingface"
set "TORCH_HOME=%CD%\cache\torch"
set "XDG_CACHE_HOME=%CD%\cache"
set "TEMP=%CD%\cache\temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%" >nul 2>nul
rem The bundled Python is relocatable. A development .venv is only a fallback.
if exist "%CD%\runtime\python\pythonw.exe" (
    start "" "%CD%\runtime\python\pythonw.exe" -m voxweavetts.desktop_ui
) else if exist "%CD%\.venv\Scripts\pythonw.exe" (
    start "" "%CD%\.venv\Scripts\pythonw.exe" -m voxweavetts.desktop_ui
) else (
    start "" pythonw -m voxweavetts.desktop_ui
)
endlocal
