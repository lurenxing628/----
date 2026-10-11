@echo off
REM Keep the CMD entry ASCII; all Unicode paths and logs stay in PowerShell.
setlocal EnableExtensions DisableDelayedExpansion
set "APS_START_CMD_LOCAL_TIME=%DATE% %TIME%"
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
  echo [launcher] Windows PowerShell is required to start APS.
  pause
  exit /b 12
)
if not exist "%~dp0aps-launcher.ps1" (
  echo [launcher] aps-launcher.ps1 is missing. Extract the complete APS package.
  pause
  exit /b 12
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0aps-launcher.ps1"
set "LAUNCH_RC=%ERRORLEVEL%"
if not "%LAUNCH_RC%"=="0" pause
exit /b %LAUNCH_RC%
