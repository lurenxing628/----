@echo off
rem Run the retained test suite with the project Python environment.

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
  echo [Tests] Cannot enter repository directory. >&2
  endlocal & exit /b 2
)

set "APS_TEST_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%APS_TEST_PYTHON%" (
  echo [Tests] Missing project Python: "%APS_TEST_PYTHON%" >&2
  popd >nul 2>&1
  endlocal & exit /b 2
)

"%APS_TEST_PYTHON%" -m pytest tests -q
set "RC=%ERRORLEVEL%"

popd >nul 2>&1
endlocal & exit /b %RC%
