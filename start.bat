@echo off
REM Development launcher; packaged installations run the application exe.
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set APS_ENV=development
set FLASK_ENV=development

REM Python file/pipe encoding is independent of the inherited console code page.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo [start] Starting development server.
echo [start] See logs\aps_host.txt and logs\aps_port.txt for the actual address.

python app.py
exit /b %ERRORLEVEL%

