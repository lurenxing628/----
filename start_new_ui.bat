@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

set APS_ENV=development
set FLASK_ENV=development

REM Python file/pipe encoding is independent of the inherited console code page.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo [start] Starting the new UI development server.
echo [start] See logs\aps_port.txt for the actual port.
echo.

python app_new_ui.py
set "APP_RC=%ERRORLEVEL%"
pause
exit /b %APP_RC%
