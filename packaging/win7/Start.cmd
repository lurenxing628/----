@echo off
setlocal DisableDelayedExpansion
set "APS_START_CMD_LOCAL_TIME=%DATE% %TIME%"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1" -Mode Start
set "APS_RESULT=%ERRORLEVEL%"
if not "%APS_RESULT%"=="0" pause
exit /b %APS_RESULT%
