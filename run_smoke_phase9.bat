@echo off
rem Phase9 smoke test runner (System: backup/logs/history)
rem Runs: tests\smoke_phase9.py
rem Report: evidence\Phase9\smoke_phase9_report.md

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1

echo [Phase9] Start...
echo [Phase9] repo: %CD%
echo.

python tests\smoke_phase9.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [Phase9] PASS
  echo [Phase9] report: evidence\Phase9\smoke_phase9_report.md
) else (
  echo [Phase9] FAIL (exit=%RC%)
  echo [Phase9] report: evidence\Phase9\smoke_phase9_report.md
)

popd >nul 2>&1
endlocal & exit /b %RC%
