@echo off
rem Developer convenience alias; same safe full-stop implementation.
call "%~dp0Stop-VoxWeaveTTS.cmd" %*
exit /b %ERRORLEVEL%
