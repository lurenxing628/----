@echo off
REM Keep the CMD entry ASCII; all Unicode paths and logs stay in PowerShell.
setlocal EnableExtensions DisableDelayedExpansion
where powershell >nul 2>&1
if errorlevel 1 (
  echo [launcher] Windows PowerShell is required to start APS.
  pause
  exit /b 12
)
if not exist "%~dp0aps-launcher.ps1" (
  echo [launcher] aps-launcher.ps1 is missing. Extract the complete APS package.
  pause
  exit /b 12
)
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0aps-launcher.ps1"
set "LAUNCH_RC=%ERRORLEVEL%"
if not "%LAUNCH_RC%"=="0" pause
exit /b %LAUNCH_RC%
