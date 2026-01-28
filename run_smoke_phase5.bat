@echo off
rem Phase5 smoke test runner (Process module)
rem Runs: tests\smoke_phase5.py
rem Report: evidence\Phase5\smoke_phase5_report.md

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1

echo [Phase5] Start...
echo [Phase5] repo: %CD%
echo.

python tests\smoke_phase5.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [Phase5] PASS
  echo [Phase5] report: evidence\Phase5\smoke_phase5_report.md
) else (
  echo [Phase5] FAIL (exit=%RC%)
  echo [Phase5] report: evidence\Phase5\smoke_phase5_report.md
)

popd >nul 2>&1
endlocal & exit /b %RC%
