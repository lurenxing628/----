@echo off
chcp 65001 >nul 2>&1
REM Launcher: reuse healthy APS instance or start app, then open URL.
REM Keep this script ASCII-friendly for Win7 cmd compatibility.

setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "APP_DIR=%CD%"
set "HOST=127.0.0.1"
set "PORT=5000"
if defined APS_HOST set "HOST=%APS_HOST%"
if defined APS_PORT set "PORT=%APS_PORT%"
set "MAX_WAIT=45"
set "HEALTH_PATH=/system/health"
set "CURRENT_OWNER=%USERNAME%"
if defined USERDOMAIN if /I not "%USERDOMAIN%"=="%USERNAME%" set "CURRENT_OWNER=%USERDOMAIN%\%USERNAME%"
if not defined USERDOMAIN if defined COMPUTERNAME if /I not "%COMPUTERNAME%"=="%USERNAME%" set "CURRENT_OWNER=%COMPUTERNAME%\%USERNAME%"

set "APP_EXE="
for %%F in (*.exe) do (
  set "CANDIDATE_NAME=%%~nxF"
  set "CANDIDATE_STEM=%%~nF"
  if /I not "!CANDIDATE_STEM:~0,5!"=="unins" if /I not "!CANDIDATE_NAME!"=="chrome.exe" if not defined APP_EXE set "APP_EXE=%APP_DIR%\%%~nxF"
)

call :resolve_shared_data_root
if not defined APS_SHARED_DATA_ROOT set "APS_SHARED_DATA_ROOT=%SHARED_DATA_ROOT%"
if not defined APS_DB_PATH set "APS_DB_PATH=%SHARED_DATA_ROOT%\db\aps.db"
if not defined APS_LOG_DIR set "APS_LOG_DIR=%SHARED_DATA_ROOT%\logs"
if not defined APS_BACKUP_DIR set "APS_BACKUP_DIR=%SHARED_DATA_ROOT%\backups"
if not defined APS_EXCEL_TEMPLATE_DIR set "APS_EXCEL_TEMPLATE_DIR=%SHARED_DATA_ROOT%\templates_excel"

set "LOG_DIR=%APS_LOG_DIR%"
set "LAUNCHER_LOG=%LOG_DIR%\launcher.log"
set "PORT_FILE=%LOG_DIR%\aps_port.txt"
set "HOST_FILE=%LOG_DIR%\aps_host.txt"
set "DB_FILE=%LOG_DIR%\aps_db_path.txt"
set "LOCK_FILE=%LOG_DIR%\aps_runtime.lock"
set "RUNTIME_CONTRACT_FILE=%LOG_DIR%\aps_runtime.json"
set "LAUNCH_ERROR_FILE=%LOG_DIR%\aps_launch_error.txt"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%LOG_DIR%" (
  echo [launcher] Shared log directory is not writable: %LOG_DIR%
  pause
  exit /b 7
)

set "CHROME_EXE="
set "CHROME_SOURCE="
set "CHROME_DIR="
set "CHROME_RUN_DIR="
set "ENV_CHROME_DIR="
set "REG_MACHINE_SHARED_DATA_ROOT="
set "REG_MACHINE_CHROME_DIR="
set "REG_USER_CHROME_DIR="
set "DEFAULT_MACHINE_CHROME_DIR=%ProgramFiles%\APS\Chrome109"
set "DEFAULT_MACHINE_CHROME_DIR_X86=%ProgramFiles(x86)%\APS\Chrome109"
set "DEFAULT_USER_CHROME_DIR=%LOCALAPPDATA%\APS\Chrome109"
set "CHROME_PROFILE_DIR=%LOCALAPPDATA%\APS\Chrome109Profile"
if not defined LOCALAPPDATA set "DEFAULT_USER_CHROME_DIR=%APP_DIR%\chrome109_runtime"
if not defined LOCALAPPDATA set "CHROME_PROFILE_DIR=%APP_DIR%\chrome109_profile"

call :log launcher_begin
call :log app_dir="%APP_DIR%"
call :log current_owner="%CURRENT_OWNER%"
call :log shared_data_root="%SHARED_DATA_ROOT%"
call :log log_dir="%LOG_DIR%"

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
call :read_machine_registry_shared_data_root
if defined REG_MACHINE_SHARED_DATA_ROOT call :log reg_SharedDataRoot="%REG_MACHINE_SHARED_DATA_ROOT%"
call :read_machine_registry_chrome_dir
if defined REG_MACHINE_CHROME_DIR (
  call :log reg_HKLM_ChromeDir="%REG_MACHINE_CHROME_DIR%"
) else (
  call :log reg_HKLM_ChromeDir=
)
call :read_user_registry_chrome_dir
if defined REG_USER_CHROME_DIR (
  call :log reg_HKCU_APS_CHROME_DIR="%REG_USER_CHROME_DIR%"
) else (
  call :log reg_HKCU_APS_CHROME_DIR=
)
call :log default_machine_chrome_dir="%DEFAULT_MACHINE_CHROME_DIR%"
call :log default_machine_chrome_dir_x86="%DEFAULT_MACHINE_CHROME_DIR_X86%"
call :log default_user_chrome_dir="%DEFAULT_USER_CHROME_DIR%"
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

if not defined CHROME_SOURCE if defined REG_MACHINE_CHROME_DIR call :try_chrome_dir "%REG_MACHINE_CHROME_DIR%" "HKLM\SOFTWARE\APS\ChromeDir"
if defined REG_MACHINE_CHROME_DIR if not defined CHROME_SOURCE call :log reg_HKLM_ChromeDir_not_found="%REG_MACHINE_CHROME_DIR%"

if not defined CHROME_SOURCE if defined REG_USER_CHROME_DIR call :try_chrome_dir "%REG_USER_CHROME_DIR%" "HKCU\Environment\APS_CHROME_DIR"
if defined REG_USER_CHROME_DIR if not defined CHROME_SOURCE call :log reg_HKCU_ChromeDir_not_found="%REG_USER_CHROME_DIR%"

if not defined CHROME_SOURCE call :try_chrome_dir "%DEFAULT_MACHINE_CHROME_DIR%" "default machine Chrome109 dir"
if not defined CHROME_SOURCE if defined ProgramFiles(x86) call :try_chrome_dir "%DEFAULT_MACHINE_CHROME_DIR_X86%" "default machine Chrome109 dir x86"
if not defined CHROME_SOURCE call :try_chrome_dir "%DEFAULT_USER_CHROME_DIR%" "default user Chrome109 dir"
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
call :probe_chrome_profile_dir
if not defined CHROME_PROFILE_READY (
  echo [launcher] Chrome profile directory is not writable: %CHROME_PROFILE_DIR%
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  pause
  exit /b 10
)

call :detect_powershell
call :log powershell_available=%HAS_POWERSHELL%

call :try_reuse_existing
if defined BLOCKED_BY_OTHER goto :BLOCKED
if defined BLOCKED_BY_UNCERTAIN goto :BLOCKED_UNCERTAIN
if defined CAN_REUSE_EXISTING goto :OPEN_CHROME

call :log app_start_required=1
echo [launcher] Starting app...
del /f /q "%PORT_FILE%" >nul 2>&1
del /f /q "%HOST_FILE%" >nul 2>&1
del /f /q "%DB_FILE%" >nul 2>&1
del /f /q "%LAUNCH_ERROR_FILE%" >nul 2>&1
start "" "%APP_EXE%"
set "APP_START_RC=%ERRORLEVEL%"
call :log app_spawn_probe=start rc=%APP_START_RC%
if not "%APP_START_RC%"=="0" (
  echo [launcher] App launch command failed (rc=%APP_START_RC%).
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  pause
  exit /b 6
)
timeout /t 2 /nobreak >nul
call :read_launch_error
if defined LAUNCH_ERROR (
  call :log app_spawn_probe=launch_error
  goto :APP_START_FAILED
)
call :log app_spawn_probe=wait_ready

echo [launcher] Waiting for app readiness (up to %MAX_WAIT%s)...
for /l %%i in (1,1,%MAX_WAIT%) do (
  if exist "%LAUNCH_ERROR_FILE%" (
    call :read_launch_error
    goto :APP_START_FAILED
  )
  call :read_host_file
  call :read_port_file
  if defined FILE_HOST if defined FILE_PORT (
    set "HOST=!FILE_HOST!"
    set "PORT=!FILE_PORT!"
    if defined HAS_POWERSHELL (
      call :probe_health
      if defined HEALTH_OK goto :OPEN_CHROME
    ) else (
      call :is_port_listening
      if defined PORT_READY goto :OPEN_CHROME
    )
  )
  timeout /t 1 /nobreak >nul
)

call :log app_start_timeout
echo [launcher] App did not become ready in time.
echo [launcher] Check shared logs: %LAUNCHER_LOG%
pause
exit /b 3

:APP_START_FAILED
if defined LAUNCH_ERROR (
  call :log launch_error="!LAUNCH_ERROR!"
  echo [launcher] !LAUNCH_ERROR!
) else (
  call :log launch_error=unknown
  echo [launcher] App startup failed.
)
echo [launcher] Check shared logs: %LAUNCHER_LOG%
echo [launcher] Check launch error file: %LAUNCH_ERROR_FILE%
pause
exit /b 6
:BLOCKED
call :log blocked_by_other_owner="%LOCK_OWNER%"
if defined LOCK_OWNER (
  echo [launcher] APS is currently in use by %LOCK_OWNER%.
) else (
  echo [launcher] APS is currently in use by another account.
)
echo [launcher] Please wait for the other user to exit, then try again.
pause
exit /b 8

:BLOCKED_UNCERTAIN
if defined BLOCK_REASON call :log blocked_by_uncertain=%BLOCK_REASON%
echo [launcher] 无法确认现有实例归属，已阻止新实例启动。
echo [launcher] 请先关闭现有实例或清理运行时信号后重试。
pause
exit /b 9

:OPEN_CHROME
set "URL=http://%HOST%:%PORT%/"
call :log url="%URL%"
call :log chrome_cmd="%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
echo [launcher] Chrome source: %CHROME_SOURCE%
echo [launcher] Opening: %URL%
REM 这里只能覆盖“路径校验后到执行前被移除”的极端竞态，
REM 不能证明 Chrome 启动后一定稳定运行。
start "" /D "%CHROME_RUN_DIR%" "%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
set "START_RC=%ERRORLEVEL%"
call :log chrome_start_rc=%START_RC%
if not "%START_RC%"=="0" (
  echo [launcher] Chrome start failed (rc=%START_RC%).
  echo [launcher] Check shared logs and run the logged chrome_cmd in cmd.
  pause
  exit /b 5
)
timeout /t 3 /nobreak >nul
call :probe_aps_chrome_alive
if not defined CHROME_ALIVE (
  echo [launcher] 未能确认 APS 专用浏览器已拉起。
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  echo [launcher] Profile: %CHROME_PROFILE_DIR%
  echo [launcher] Run chrome_cmd from launcher.log manually in cmd.
  pause
  exit /b 11
)
exit /b 0

:resolve_shared_data_root
set "SHARED_DATA_ROOT="
if defined APS_SHARED_DATA_ROOT set "SHARED_DATA_ROOT=%APS_SHARED_DATA_ROOT:"=%"
if defined SHARED_DATA_ROOT exit /b 0
call :read_machine_registry_shared_data_root
if defined REG_MACHINE_SHARED_DATA_ROOT set "SHARED_DATA_ROOT=%REG_MACHINE_SHARED_DATA_ROOT%"
if defined SHARED_DATA_ROOT exit /b 0
if defined ProgramData (
  set "SHARED_DATA_ROOT=%ProgramData%\APS\shared-data"
) else (
  set "SHARED_DATA_ROOT=%APP_DIR%\shared-data"
)
exit /b 0

:detect_powershell
set "HAS_POWERSHELL="
where powershell >nul 2>&1
if %errorlevel%==0 set "HAS_POWERSHELL=1"
exit /b 0

:block_uncertain
set "BLOCKED_BY_UNCERTAIN=1"
set "BLOCK_REASON=%~1"
call :log existing_reuse_blocked=%~1
exit /b 0

:try_reuse_existing
set "CAN_REUSE_EXISTING="
set "BLOCKED_BY_OTHER="
set "BLOCKED_BY_UNCERTAIN="
set "BLOCK_REASON="
set "LOCK_QUERY_ERROR="
call :read_lock_file
call :lock_is_active
call :read_runtime_contract

if /I "%LOCK_ACTIVE%"=="1" (
  if not defined LOCK_OWNER (
    call :block_uncertain lock_owner_missing
    exit /b 0
  )

  call :load_existing_endpoint
  if /I not "%LOCK_OWNER%"=="%CURRENT_OWNER%" (
    if defined ENDPOINT_HOST set "HOST=!ENDPOINT_HOST!"
    if defined ENDPOINT_PORT set "PORT=!ENDPOINT_PORT!"
    set "BLOCKED_BY_OTHER=1"
    call :log existing_reuse_blocked=other_owner_active owner="%LOCK_OWNER%"
    exit /b 0
  )

  if not defined ENDPOINT_HOST (
    call :block_uncertain lock_active_missing_host
    exit /b 0
  )
  if not defined ENDPOINT_PORT (
    call :block_uncertain lock_active_missing_port
    exit /b 0
  )

  set "HOST=!ENDPOINT_HOST!"
  set "PORT=!ENDPOINT_PORT!"
  if defined HAS_POWERSHELL (
    call :probe_health
    if defined HEALTH_OK (
      set "CAN_REUSE_EXISTING=1"
      call :log existing_reuse=lock_active_same_owner
      exit /b 0
    )
    call :block_uncertain lock_active_health_failed
    exit /b 0
  )

  call :is_port_listening
  if defined PORT_READY (
    set "CAN_REUSE_EXISTING=1"
    call :log existing_reuse=lock_active_same_owner_port
  ) else (
    call :block_uncertain lock_active_port_not_listening
  )
  exit /b 0
)

if /I "%LOCK_ACTIVE%"=="UNKNOWN" (
  call :try_reuse_by_contract
  if defined CAN_REUSE_EXISTING exit /b 0
  if defined BLOCKED_BY_OTHER exit /b 0
  if defined LOCK_QUERY_ERROR (
    call :block_uncertain %LOCK_QUERY_ERROR%
  ) else (
    call :block_uncertain lock_query_unknown
  )
  exit /b 0
)

call :try_reuse_by_contract
if defined CAN_REUSE_EXISTING exit /b 0
if defined BLOCKED_BY_OTHER exit /b 0

call :load_existing_endpoint
if defined ENDPOINT_HOST if defined ENDPOINT_PORT (
  set "HOST=%ENDPOINT_HOST%"
  set "PORT=%ENDPOINT_PORT%"
  if defined HAS_POWERSHELL (
    call :probe_health
    if defined HEALTH_OK (
      call :block_uncertain healthy_without_owner_proof
      exit /b 0
    )
  ) else (
    call :is_port_listening
    if defined PORT_READY (
      call :block_uncertain port_only_without_owner_proof
      exit /b 0
    )
  )
)

call :log existing_reuse=0
exit /b 0

:try_reuse_by_contract
if not defined CONTRACT_VALID exit /b 0
if not defined CONTRACT_HOST exit /b 0
if not defined CONTRACT_PORT exit /b 0
if not defined HAS_POWERSHELL exit /b 0

set "HOST=%CONTRACT_HOST%"
set "PORT=%CONTRACT_PORT%"
call :probe_health
if not defined HEALTH_OK exit /b 0

if /I "%CONTRACT_OWNER%"=="%CURRENT_OWNER%" (
  set "CAN_REUSE_EXISTING=1"
  call :log existing_reuse=contract_owner_match
) else (
  set "BLOCKED_BY_OTHER=1"
  set "LOCK_OWNER=%CONTRACT_OWNER%"
  call :log existing_reuse_blocked=contract_owner_mismatch owner="%CONTRACT_OWNER%"
)
exit /b 0

:load_existing_endpoint
set "ENDPOINT_HOST="
set "ENDPOINT_PORT="
call :read_host_file
if defined FILE_HOST set "ENDPOINT_HOST=%FILE_HOST%"
call :read_port_file
if defined FILE_PORT set "ENDPOINT_PORT=%FILE_PORT%"
if not defined ENDPOINT_HOST if defined CONTRACT_HOST set "ENDPOINT_HOST=%CONTRACT_HOST%"
if not defined ENDPOINT_PORT if defined CONTRACT_PORT set "ENDPOINT_PORT=%CONTRACT_PORT%"
exit /b 0



:probe_health
set "HEALTH_OK="
if not defined HAS_POWERSHELL exit /b 0
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" exit /b 0
set "HEALTH_URL=http://%HOST%:%PORT%%HEALTH_PATH%"
powershell -NoProfile -Command "$u='%HEALTH_URL%'; try { $req=[System.Net.HttpWebRequest]::Create($u); $req.Timeout=2000; $req.ReadWriteTimeout=2000; $resp=$req.GetResponse(); $sr=New-Object System.IO.StreamReader($resp.GetResponseStream()); $body=$sr.ReadToEnd(); $sr.Close(); $resp.Close(); $ok=$false; try { if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue) { $obj=$body | ConvertFrom-Json; if (($obj.app -eq 'aps') -and ($obj.status -eq 'ok') -and ([int]($obj.contract_version) -eq 1)) { $ok=$true } } } catch { $ok=$false }; if (-not $ok) { if (($body -match '\x22app\x22\s*:\s*\x22aps\x22') -and ($body -match '\x22status\x22\s*:\s*\x22ok\x22') -and ($body -match '\x22contract_version\x22\s*:\s*1')) { $ok=$true } }; if ($ok) { exit 0 } else { exit 2 } } catch { exit 1 }" >nul 2>&1
set "HEALTH_RC=%ERRORLEVEL%"
if "!HEALTH_RC!"=="0" (
  set "HEALTH_OK=1"
  call :log health_ok="%HEALTH_URL%"
) else (
  call :log health_fail="%HEALTH_URL%" rc=!HEALTH_RC!
)
exit /b 0

:read_machine_registry_shared_data_root
set "REG_MACHINE_SHARED_DATA_ROOT="
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\APS" /v SharedDataRoot 2^>nul ^| findstr /I /C:"SharedDataRoot"') do (
  if /I "%%A"=="REG_SZ" set "REG_MACHINE_SHARED_DATA_ROOT=%%B"
  if /I "%%A"=="REG_EXPAND_SZ" set "REG_MACHINE_SHARED_DATA_ROOT=%%B"
)
if defined REG_MACHINE_SHARED_DATA_ROOT set "REG_MACHINE_SHARED_DATA_ROOT=%REG_MACHINE_SHARED_DATA_ROOT:"=%"
exit /b 0

:read_machine_registry_chrome_dir
set "REG_MACHINE_CHROME_DIR="
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\APS" /v ChromeDir 2^>nul ^| findstr /I /C:"ChromeDir"') do (
  if /I "%%A"=="REG_SZ" set "REG_MACHINE_CHROME_DIR=%%B"
  if /I "%%A"=="REG_EXPAND_SZ" set "REG_MACHINE_CHROME_DIR=%%B"
)
if defined REG_MACHINE_CHROME_DIR set "REG_MACHINE_CHROME_DIR=%REG_MACHINE_CHROME_DIR:"=%"
exit /b 0

:read_user_registry_chrome_dir
set "REG_USER_CHROME_DIR="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v APS_CHROME_DIR 2^>nul ^| findstr /I /C:"APS_CHROME_DIR"') do (
  if /I "%%A"=="REG_SZ" set "REG_USER_CHROME_DIR=%%B"
  if /I "%%A"=="REG_EXPAND_SZ" set "REG_USER_CHROME_DIR=%%B"
)
if defined REG_USER_CHROME_DIR set "REG_USER_CHROME_DIR=%REG_USER_CHROME_DIR:"=%"
exit /b 0

:read_lock_file
set "LOCK_OWNER="
set "LOCK_PID="
if not exist "%LOCK_FILE%" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in ("%LOCK_FILE%") do (
  if /I "%%A"=="owner" set "LOCK_OWNER=%%B"
  if /I "%%A"=="pid" set "LOCK_PID=%%B"
)
exit /b 0

:read_runtime_contract
set "CONTRACT_OWNER="
set "CONTRACT_PID="
set "CONTRACT_VERSION="
set "CONTRACT_HOST="
set "CONTRACT_PORT="
set "CONTRACT_VALID="
set "CONTRACT_READ_ERROR="
if not exist "%RUNTIME_CONTRACT_FILE%" exit /b 0
for /f "tokens=1,* delims=:" %%A in ('findstr /R /C:"\"owner\"" "%RUNTIME_CONTRACT_FILE%"') do (
  set "RAW_VALUE=%%B"
  set "RAW_VALUE=!RAW_VALUE:,=!"
  set "RAW_VALUE=!RAW_VALUE:"=!"
  for /f "tokens=* delims= " %%V in ("!RAW_VALUE!") do if not defined CONTRACT_OWNER set "CONTRACT_OWNER=%%V"
)
for /f "tokens=1,* delims=:" %%A in ('findstr /R /C:"\"pid\"" "%RUNTIME_CONTRACT_FILE%"') do (
  set "RAW_VALUE=%%B"
  set "RAW_VALUE=!RAW_VALUE:,=!"
  set "RAW_VALUE=!RAW_VALUE:"=!"
  for /f "tokens=* delims= " %%V in ("!RAW_VALUE!") do if not defined CONTRACT_PID set "CONTRACT_PID=%%V"
)
for /f "tokens=1,* delims=:" %%A in ('findstr /R /C:"\"contract_version\"" "%RUNTIME_CONTRACT_FILE%"') do (
  set "RAW_VALUE=%%B"
  set "RAW_VALUE=!RAW_VALUE:,=!"
  set "RAW_VALUE=!RAW_VALUE:"=!"
  for /f "tokens=* delims= " %%V in ("!RAW_VALUE!") do if not defined CONTRACT_VERSION set "CONTRACT_VERSION=%%V"
)
for /f "tokens=1,* delims=:" %%A in ('findstr /R /C:"\"host\"" "%RUNTIME_CONTRACT_FILE%"') do (
  set "RAW_VALUE=%%B"
  set "RAW_VALUE=!RAW_VALUE:,=!"
  set "RAW_VALUE=!RAW_VALUE:"=!"
  for /f "tokens=* delims= " %%V in ("!RAW_VALUE!") do if not defined CONTRACT_HOST set "CONTRACT_HOST=%%V"
)
for /f "tokens=1,* delims=:" %%A in ('findstr /R /C:"\"port\"" "%RUNTIME_CONTRACT_FILE%"') do (
  set "RAW_VALUE=%%B"
  set "RAW_VALUE=!RAW_VALUE:,=!"
  set "RAW_VALUE=!RAW_VALUE:"=!"
  for /f "tokens=* delims= " %%V in ("!RAW_VALUE!") do if not defined CONTRACT_PORT set "CONTRACT_PORT=%%V"
)
call :normalize_contract_owner

if defined CONTRACT_PID (
  echo !CONTRACT_PID! | findstr /R "^[0-9][0-9]*$" >nul
  if not !errorlevel!==0 set "CONTRACT_PID="
)
if defined CONTRACT_PORT (
  echo !CONTRACT_PORT! | findstr /R "^[0-9][0-9]*$" >nul
  if not !errorlevel!==0 set "CONTRACT_PORT="
)
if not "%CONTRACT_VERSION%"=="1" (
  set "CONTRACT_READ_ERROR=contract_version_invalid"
  set "CONTRACT_OWNER="
  set "CONTRACT_PID="
  set "CONTRACT_HOST="
  set "CONTRACT_PORT="
  exit /b 0
)
if defined CONTRACT_OWNER if defined CONTRACT_PID set "CONTRACT_VALID=1"
if not defined CONTRACT_VALID set "CONTRACT_READ_ERROR=contract_missing_fields"
exit /b 0

:normalize_contract_owner
if not defined CONTRACT_OWNER (
  call :log contract_owner_normalized=
  exit /b 0
)
set "CONTRACT_OWNER=!CONTRACT_OWNER:\=\!"
call :log contract_owner_normalized="!CONTRACT_OWNER!"
exit /b 0

:lock_is_active
set "LOCK_ACTIVE="
set "LOCK_QUERY_TMP="
set "LOCK_QUERY_ERROR="
if not defined LOCK_PID exit /b 0
echo !LOCK_PID! | findstr /R "^[0-9][0-9]*$" >nul
if not !errorlevel!==0 (
  set "LOCK_ACTIVE=UNKNOWN"
  set "LOCK_QUERY_ERROR=lock_pid_invalid"
  exit /b 0
)
set "LOCK_QUERY_TMP=%TEMP%\aps_lock_query_%RANDOM%_%RANDOM%.tmp"
tasklist /FI "PID eq !LOCK_PID!" /NH /FO CSV > "%LOCK_QUERY_TMP%" 2>nul
set "LOCK_QUERY_RC=!ERRORLEVEL!"
if not "!LOCK_QUERY_RC!"=="0" (
  del /f /q "%LOCK_QUERY_TMP%" >nul 2>&1
  set "LOCK_ACTIVE=UNKNOWN"
  set "LOCK_QUERY_ERROR=tasklist_failed"
  exit /b 0
)
set "LOCK_ACTIVE=0"
for /f "usebackq delims=" %%L in ("%LOCK_QUERY_TMP%") do (
  set "LOCK_QUERY_ROW=%%L"
  if not "!LOCK_QUERY_ROW!"=="" (
    echo !LOCK_QUERY_ROW! | findstr /R /C:"^\"" >nul
    if !errorlevel!==0 (
      echo !LOCK_QUERY_ROW! | findstr /C:",\"!LOCK_PID!\"," >nul
      if !errorlevel!==0 set "LOCK_ACTIVE=1"
    )
  )
)
del /f /q "%LOCK_QUERY_TMP%" >nul 2>&1
exit /b 0

:read_launch_error
set "LAUNCH_ERROR="
if not exist "%LAUNCH_ERROR_FILE%" exit /b 0
set /p LAUNCH_ERROR=<"%LAUNCH_ERROR_FILE%"
exit /b 0

:probe_chrome_profile_dir
set "CHROME_PROFILE_READY="
set "CHROME_PROFILE_PROBE_FILE=%CHROME_PROFILE_DIR%\aps_write_probe_%RANDOM%_%RANDOM%.tmp"
if not exist "%CHROME_PROFILE_DIR%" mkdir "%CHROME_PROFILE_DIR%" >nul 2>&1
if not exist "%CHROME_PROFILE_DIR%" (
  call :log chrome_profile_probe=create_failed dir="%CHROME_PROFILE_DIR%"
  exit /b 0
)
> "%CHROME_PROFILE_PROBE_FILE%" echo APS
if not exist "%CHROME_PROFILE_PROBE_FILE%" (
  call :log chrome_profile_probe=write_failed dir="%CHROME_PROFILE_DIR%"
  exit /b 0
)
del /f /q "%CHROME_PROFILE_PROBE_FILE%" >nul 2>&1
set "CHROME_PROFILE_READY=1"
call :log chrome_profile_probe=ok dir="%CHROME_PROFILE_DIR%"
exit /b 0

:probe_aps_chrome_alive
set "CHROME_ALIVE="
if not defined HAS_POWERSHELL (
  call :log chrome_alive_probe=no_powershell
  exit /b 0
)
set "CHROME_PROFILE_MARKER=%CHROME_PROFILE_DIR:'=''%"
powershell -NoProfile -Command "$marker='%CHROME_PROFILE_MARKER%'.ToLowerInvariant(); $items=$null; if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) { try { $items=@(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) } catch { $items=$null } }; if ($null -eq $items) { if (-not (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) { exit 1 }; try { $items=@(Get-WmiObject Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) } catch { exit 1 } }; foreach ($item in @($items)) { $cmd=[string]$item.CommandLine; if ([string]::IsNullOrWhiteSpace($cmd)) { continue }; $cmdLower=$cmd.ToLowerInvariant(); if ($cmdLower.Contains('--user-data-dir') -and $cmdLower.Contains($marker)) { exit 0 } }; exit 2" >nul 2>&1
set "CHROME_QUERY_RC=%ERRORLEVEL%"
if "!CHROME_QUERY_RC!"=="0" (
  set "CHROME_ALIVE=1"
  call :log chrome_alive_probe=detected
) else (
  if "!CHROME_QUERY_RC!"=="2" (
    call :log chrome_alive_probe=missing
  ) else (
    call :log chrome_alive_probe=query_failed rc=!CHROME_QUERY_RC!
  )
)
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
set "FILE_HOST="
if exist "%HOST_FILE%" (
  set /p FILE_HOST=<"%HOST_FILE%"
  set "FILE_HOST=!FILE_HOST: =!"
  if "!FILE_HOST!"=="" set "FILE_HOST=127.0.0.1"
)
exit /b 0

:read_port_file
set "FILE_PORT="
if exist "%PORT_FILE%" (
  set /p FILE_PORT=<"%PORT_FILE%"
  set "FILE_PORT=!FILE_PORT: =!"
  echo !FILE_PORT! | findstr /R "^[0-9][0-9]*$" >nul
  if not !errorlevel!==0 (
    call :log port_file_invalid=!FILE_PORT!
    set "FILE_PORT="
  )
)
exit /b 0

:log
>>"%LAUNCHER_LOG%" echo [%date% %time%] %*
exit /b 0

