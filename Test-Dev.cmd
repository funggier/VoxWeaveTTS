@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
if exist "%CD%\.venv\Scripts\python.exe" (
    "%CD%\.venv\Scripts\python.exe" -m unittest discover -s tests -v
) else if exist "%CD%\runtime\python\python.exe" (
    "%CD%\runtime\python\python.exe" -m unittest discover -s tests -v
) else (
    python -m unittest discover -s tests -v
)
if errorlevel 1 pause
endlocal
