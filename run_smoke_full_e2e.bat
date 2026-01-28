@echo off
rem Full E2E smoke test runner (Excel -> schedule -> gantt/week-plan -> system)
rem Runs: tests\smoke_e2e_excel_to_schedule.py
rem Report: evidence\FullE2E\excel_to_schedule_report.md

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1

echo [FullE2E] Start...
echo [FullE2E] repo: %CD%
echo.

python tests\smoke_e2e_excel_to_schedule.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [FullE2E] PASS
  echo [FullE2E] report: evidence\FullE2E\excel_to_schedule_report.md
) else (
  echo [FullE2E] FAIL (exit=%RC%)
  echo [FullE2E] report: evidence\FullE2E\excel_to_schedule_report.md
)

popd >nul 2>&1
endlocal & exit /b %RC%
