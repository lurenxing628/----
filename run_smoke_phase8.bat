@echo off
rem Phase8 smoke test runner (Gantt + Week plan)
rem Runs: tests\smoke_phase8.py
rem Report: evidence\Phase8\smoke_phase8_report.md

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1

echo [Phase8] Start...
echo [Phase8] repo: %CD%
echo.

python tests\smoke_phase8.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [Phase8] PASS
  echo [Phase8] report: evidence\Phase8\smoke_phase8_report.md
) else (
  echo [Phase8] FAIL (exit=%RC%)
  echo [Phase8] report: evidence\Phase8\smoke_phase8_report.md
)

popd >nul 2>&1
endlocal & exit /b %RC%
