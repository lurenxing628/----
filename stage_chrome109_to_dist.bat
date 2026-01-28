@echo off
rem Stage offline Chrome109 into dist\...\tools\chrome109
rem Requires: robocopy (built-in on Win7)

setlocal EnableExtensions
set "EXIT_CODE=0"

pushd "%~dp0" >nul 2>&1
if not %errorlevel%==0 (
  echo [stage] pushd failed.
  set "EXIT_CODE=1"
  goto :cleanup
)

set "SRC=%CD%\tools\Chrome.109.0.5414.120.x64"

rem Resolve dist app folder dynamically (avoid hardcoding non-ASCII names)
set "DIST_ROOT="
for /d %%D in ("%CD%\dist\*") do (
  if not defined DIST_ROOT (
    for %%E in ("%%~fD\*.exe") do (
      if exist "%%~fE" set "DIST_ROOT=%%~fD"
    )
  )
)

if not defined DIST_ROOT (
  echo [stage] dist output not found. Please run build_win7_onedir.bat first.
  set "EXIT_CODE=2"
  goto :cleanup
)

set "DST=%DIST_ROOT%\tools\chrome109"

echo [stage] repo: %CD%
echo [stage] src : %SRC%
echo [stage] dst : %DST%

if not exist "%SRC%\chrome.exe" (
  echo [stage] chrome.exe not found: %SRC%\chrome.exe
  set "EXIT_CODE=3"
  goto :cleanup
)

if not exist "%DIST_ROOT%\tools" mkdir "%DIST_ROOT%\tools" >nul 2>&1

rem Overwrite: delete old folder to avoid leftovers
if exist "%DST%" (
  echo [stage] cleanup old dst...
  rmdir /s /q "%DST%" >nul 2>&1
)

echo [stage] copying...
robocopy "%SRC%" "%DST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS /NP
set "ROBO_RC=%ERRORLEVEL%"

rem robocopy: 0-7 = success; >=8 = failure
if %ROBO_RC% GEQ 8 (
  echo [stage] robocopy failed exit=%ROBO_RC%
  set "EXIT_CODE=%ROBO_RC%"
  goto :cleanup
)

if not exist "%DST%\chrome.exe" (
  echo [stage] chrome.exe missing after copy: %DST%\chrome.exe
  set "EXIT_CODE=4"
  goto :cleanup
)

echo [stage] done.
set "EXIT_CODE=0"

:cleanup
popd >nul 2>&1
endlocal & exit /b %EXIT_CODE%
