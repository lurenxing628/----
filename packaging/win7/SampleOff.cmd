@echo off
setlocal DisableDelayedExpansion
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1" -Mode SampleOff
set "APS_RESULT=%ERRORLEVEL%"
if not "%APS_RESULT%"=="0" pause
exit /b %APS_RESULT%
