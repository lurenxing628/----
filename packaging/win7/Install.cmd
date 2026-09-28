@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1"
set "APS_RESULT=%ERRORLEVEL%"
if not "%APS_RESULT%"=="0" echo Deployment failed. See the message above and README.txt.
pause
exit /b %APS_RESULT%
