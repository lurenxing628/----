@echo off
REM Launcher: start app first, then open URL with APS browser runtime.
REM Keep this script ASCII-friendly for Win7 cmd compatibility.

setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "APP_DIR=%CD%"
set "HOST=127.0.0.1"
set "PORT=5000"
if defined APS_HOST set "HOST=%APS_HOST%"
if defined APS_PORT set "PORT=%APS_PORT%"
set "MAX_WAIT=45"

set "LOG_DIR=%APP_DIR%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LAUNCHER_LOG=%LOG_DIR%\launcher.log"
set "PORT_FILE=%LOG_DIR%\aps_port.txt"
set "HOST_FILE=%LOG_DIR%\aps_host.txt"

set "APP_EXE="
for %%F in (*.exe) do (
  set "CANDIDATE_NAME=%%~nxF"
  set "CANDIDATE_STEM=%%~nF"
  if /I not "!CANDIDATE_STEM:~0,5!"=="unins" if /I not "!CANDIDATE_NAME!"=="chrome.exe" if not defined APP_EXE set "APP_EXE=%APP_DIR%\%%~nxF"
)

set "CHROME_EXE="
set "CHROME_SOURCE="
set "CHROME_DIR="
set "CHROME_RUN_DIR="
set "ENV_CHROME_DIR="
set "REG_CHROME_DIR="
set "DEFAULT_CHROME_DIR=%LOCALAPPDATA%\APS\Chrome109"
set "CHROME_PROFILE_DIR=%LOCALAPPDATA%\APS\Chrome109Profile"
if not defined LOCALAPPDATA set "DEFAULT_CHROME_DIR=%APP_DIR%\chrome109_runtime"
if not defined LOCALAPPDATA set "CHROME_PROFILE_DIR=%APP_DIR%\chrome109_profile"

call :log launcher_begin
call :log app_dir="%APP_DIR%"

if not defined APP_EXE (
  call :log app_exe_not_found
  echo [launcher] App exe not found.
  pause
  exit /b 1
)
call :log app_exe="%APP_EXE%"

if defined APS_CHROME_DIR set "ENV_CHROME_DIR=%APS_CHROME_DIR:"=%"
if defined ENV_CHROME_DIR (
  call :log env_APS_CHROME_DIR="%ENV_CHROME_DIR%"
) else (
  call :log env_APS_CHROME_DIR=
)
call :read_registry_chrome_dir
if defined REG_CHROME_DIR (
  call :log reg_APS_CHROME_DIR="%REG_CHROME_DIR%"
) else (
  call :log reg_APS_CHROME_DIR=
)
call :log default_chrome_dir="%DEFAULT_CHROME_DIR%"
call :log legacy_chrome_dir="%APP_DIR%\tools\chrome109"

if defined APS_CHROME_EXE (
  set "CHROME_EXE=%APS_CHROME_EXE:"=%"
  if exist "!CHROME_EXE!" (
    set "CHROME_SOURCE=APS_CHROME_EXE"
  ) else (
    call :log invalid_APS_CHROME_EXE="%APS_CHROME_EXE%"
    echo [launcher] APS_CHROME_EXE is invalid.
    echo [launcher] Fix APS_CHROME_EXE or install APS_Chrome109_Runtime.exe.
    pause
    exit /b 4
  )
)

if not defined CHROME_SOURCE if defined ENV_CHROME_DIR call :try_chrome_dir "%ENV_CHROME_DIR%" "APS_CHROME_DIR"
if defined ENV_CHROME_DIR if not defined CHROME_SOURCE call :log env_APS_CHROME_DIR_not_found="%ENV_CHROME_DIR%"

if not defined CHROME_SOURCE if defined REG_CHROME_DIR call :try_chrome_dir "%REG_CHROME_DIR%" "HKCU\Environment\APS_CHROME_DIR"
if defined REG_CHROME_DIR if not defined CHROME_SOURCE call :log reg_APS_CHROME_DIR_not_found="%REG_CHROME_DIR%"

if not defined CHROME_SOURCE call :try_chrome_dir "%DEFAULT_CHROME_DIR%" "default Chrome109 dir"
if not defined CHROME_SOURCE call :try_chrome_dir "%APP_DIR%\tools\chrome109" "legacy tools\chrome109"

if not defined CHROME_SOURCE (
  call :log chrome_runtime_not_found
  echo [launcher] Chrome runtime not found.
  echo [launcher] Install APS_Chrome109_Runtime.exe or set APS_CHROME_EXE.
  pause
  exit /b 2
)

if not exist "%CHROME_PROFILE_DIR%" mkdir "%CHROME_PROFILE_DIR%" >nul 2>&1
for %%I in ("%CHROME_EXE%") do set "CHROME_RUN_DIR=%%~dpI"

call :log chrome_source="%CHROME_SOURCE%"
call :log chrome_exe="%CHROME_EXE%"
call :log chrome_run_dir="%CHROME_RUN_DIR%"
call :log chrome_profile_dir="%CHROME_PROFILE_DIR%"

call :read_host_file
call :read_port_file
call :is_port_listening
if defined PORT_READY goto :OPEN_CHROME

call :log app_start_required=1
echo [launcher] Starting app...
del /f /q "%PORT_FILE%" >nul 2>&1
del /f /q "%HOST_FILE%" >nul 2>&1
start "" "%APP_EXE%"

echo [launcher] Waiting for app readiness (up to %MAX_WAIT%s)...
for /l %%i in (1,1,%MAX_WAIT%) do (
  call :read_host_file
  call :read_port_file
  call :is_port_listening
  if defined PORT_READY goto :OPEN_CHROME
  timeout /t 1 /nobreak >nul
)

call :log app_start_timeout
echo [launcher] App did not become ready in time.
echo [launcher] Check logs\aps_error.log
pause
exit /b 3

:OPEN_CHROME
set "URL=http://%HOST%:%PORT%/"
call :log url="%URL%"
call :log chrome_cmd="%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
echo [launcher] Chrome source: %CHROME_SOURCE%
echo [launcher] Opening: %URL%
start "" /D "%CHROME_RUN_DIR%" "%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
set "START_RC=%ERRORLEVEL%"
call :log chrome_start_rc=%START_RC%
if not "%START_RC%"=="0" (
  echo [launcher] Chrome start failed (rc=%START_RC%).
  echo [launcher] Check logs\launcher.log and run the logged chrome_cmd in cmd.
  pause
  exit /b 5
)
exit /b 0

:read_registry_chrome_dir
set "REG_CHROME_DIR="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v APS_CHROME_DIR 2^>nul ^| findstr /I /C:"APS_CHROME_DIR"') do (
  if /I "%%A"=="REG_SZ" set "REG_CHROME_DIR=%%B"
  if /I "%%A"=="REG_EXPAND_SZ" set "REG_CHROME_DIR=%%B"
)
if defined REG_CHROME_DIR set "REG_CHROME_DIR=%REG_CHROME_DIR:"=%"
exit /b 0

:try_chrome_dir
set "CHROME_DIR=%~1"
set "CHROME_SOURCE_LABEL=%~2"
if "%CHROME_DIR%"=="" exit /b 0
if exist "%CHROME_DIR%\chrome.exe" (
  set "CHROME_EXE=%CHROME_DIR%\chrome.exe"
  set "CHROME_SOURCE=%CHROME_SOURCE_LABEL%"
  exit /b 0
)
if exist "%CHROME_DIR%\App\chrome.exe" (
  set "CHROME_EXE=%CHROME_DIR%\App\chrome.exe"
  set "CHROME_SOURCE=%CHROME_SOURCE_LABEL%\App"
  exit /b 0
)
exit /b 0

:is_port_listening
set "PORT_READY="
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%PORT% " >nul
if %errorlevel%==0 set "PORT_READY=1"
exit /b 0

:read_host_file
if exist "%HOST_FILE%" (
  set /p HOST=<"%HOST_FILE%"
  set "HOST=!HOST: =!"
  if "!HOST!"=="" set "HOST=127.0.0.1"
)
exit /b 0

:read_port_file
if exist "%PORT_FILE%" (
  set /p PORT=<"%PORT_FILE%"
  set "PORT=!PORT: =!"
)
exit /b 0

:log
>>"%LAUNCHER_LOG%" echo [%date% %time%] %*
exit /b 0

