@echo off
rem Phase7 smoke test runner (Scheduler algorithm)
rem Runs: tests\smoke_phase7.py
rem Report: evidence\Phase7\smoke_phase7_report.md

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1

echo [Phase7] Start...
echo [Phase7] repo: %CD%
echo.

python tests\smoke_phase7.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [Phase7] PASS
  echo [Phase7] report: evidence\Phase7\smoke_phase7_report.md
) else (
  echo [Phase7] FAIL (exit=%RC%)
  echo [Phase7] report: evidence\Phase7\smoke_phase7_report.md
)

popd >nul 2>&1
endlocal & exit /b %RC%
