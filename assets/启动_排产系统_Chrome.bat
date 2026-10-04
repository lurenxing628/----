@echo off
REM Launcher: reuse healthy APS instance or start app, then open URL.
REM Keep this script ASCII-friendly for Win7 cmd compatibility.

REM Disable expansion even when inherited from cmd /V:ON; preserve literal ! paths.
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"
set "APP_DIR=%CD%"
set "PORTABLE="
if exist "%APP_DIR%\aps-portable.txt" set "PORTABLE=1"
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
for %%F in (*.exe) do call :select_app_exe "%%~fF"

if defined PORTABLE call :configure_portable_data
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
if defined PORTABLE set "CHROME_PROFILE_DIR=%APP_DIR%\user-data\chrome109_profile"

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
for %%I in ("%APP_EXE%") do set "APP_EXE_NAME=%%~nxI"
call :log app_exe_name="%APP_EXE_NAME%"

if defined PORTABLE (
  set "CHROME_EXE=%APP_DIR%\tools\chrome109\chrome.exe"
  set "CHROME_SOURCE=portable tools\chrome109"
  goto :CHROME_RESOLVED
)

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

if defined APS_CHROME_EXE set "CHROME_EXE=%APS_CHROME_EXE:"=%"
if defined APS_CHROME_EXE (
  if exist "%CHROME_EXE%" (
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

:CHROME_RESOLVED
if defined PORTABLE if not exist "%CHROME_EXE%" (
  call :log portable_chrome_missing="%CHROME_EXE%"
  echo [launcher] Portable browser is missing. Extract the complete APS portable ZIP again.
  pause
  exit /b 2
)
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
call :detect_powershell
call :log powershell_available=%HAS_POWERSHELL%
if not defined HAS_POWERSHELL (
  call :log launcher_blocked=no_powershell
  echo [launcher] PowerShell is required to verify the APS runtime owner and health.
  echo [launcher] Install or enable PowerShell before launching APS.
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  pause
  exit /b 12
)

call :initialize_launch_id
if errorlevel 1 (
  call :log launcher_blocked=unique_id_failed
  echo [launcher] Could not create an isolated startup identifier.
  pause
  exit /b 12
)
call :log launcher_run_id=%LAUNCHER_RUN_ID%
call :probe_chrome_profile_dir
if not defined CHROME_PROFILE_READY (
  echo [launcher] Chrome profile directory is not writable: %CHROME_PROFILE_DIR%
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  pause
  exit /b 10
)

call :try_reuse_existing
if defined BLOCKED_BY_OTHER goto :BLOCKED
if defined BLOCKED_BY_UNCERTAIN goto :BLOCKED_UNCERTAIN
if defined CAN_REUSE_EXISTING goto :OPEN_CHROME
if defined WAIT_EXISTING_STARTUP (
  call :log app_wait_existing_startup=%WAIT_EXISTING_REASON%
  echo [launcher] This account's app is starting; waiting for readiness...
  goto :WAIT_APP_READY
)

call :log app_start_required=1
echo [launcher] Starting app...
REM The owner publishes/cleans its signals. A second launcher must not erase them.
start "" "%APP_EXE%"
set "APP_START_RC=%ERRORLEVEL%"
call :log app_spawn_probe=start rc=%APP_START_RC%
if not "%APP_START_RC%"=="0" (
  echo [launcher] App launch command failed, rc=%APP_START_RC%.
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  pause
  exit /b 6
)
timeout /t 2 /nobreak >nul
call :read_launch_error
if defined LAUNCH_ERROR (
  call :log app_spawn_probe=launch_error
  call :recover_launch_error
  if defined BLOCKED_BY_OTHER goto :BLOCKED
  if defined BLOCKED_BY_UNCERTAIN goto :BLOCKED_UNCERTAIN
  if defined CAN_REUSE_EXISTING goto :OPEN_CHROME
  if not defined WAIT_EXISTING_STARTUP goto :APP_START_FAILED
)
call :log app_spawn_probe=wait_ready

:WAIT_APP_READY
echo [launcher] Waiting for app readiness (up to %MAX_WAIT%s)...
for /l %%i in (1,1,%MAX_WAIT%) do (
  call :poll_app_ready
  if defined HEALTH_OK if not exist "%LAUNCH_ERROR_FILE%" goto :OPEN_CHROME
  if exist "%LAUNCH_ERROR_FILE%" (
    call :read_launch_error
    call :recover_launch_error
    if defined BLOCKED_BY_OTHER goto :BLOCKED
    if defined BLOCKED_BY_UNCERTAIN goto :BLOCKED_UNCERTAIN
    if defined CAN_REUSE_EXISTING goto :OPEN_CHROME
    if not defined WAIT_EXISTING_STARTUP goto :APP_START_FAILED
  )
  timeout /t 1 /nobreak >nul
)

if defined WAIT_EXISTING_STARTUP (
  call :log app_wait_existing_timeout=%WAIT_EXISTING_REASON%
  echo [launcher] Timed out waiting for the existing instance.
  echo [launcher] Retry later; if startup keeps failing, restart the computer.
  echo [launcher] Contact support with the launcher log: %LAUNCHER_LOG%
) else (
  call :log app_start_timeout
  echo [launcher] App did not become ready in time.
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
)
pause
exit /b 3

:APP_START_FAILED
if defined LAUNCH_ERROR (
  call :log launch_error=see_utf8_error_file
  echo [launcher] App startup failed; see the UTF-8 launch error file below.
) else (
  call :log launch_error=unknown
  echo [launcher] App startup failed.
)
echo [launcher] Check shared logs: %LAUNCHER_LOG%
echo [launcher] Check launch error file: %LAUNCH_ERROR_FILE%
pause
exit /b 6
:BLOCKED
call :log blocked_by_other_owner_utf8_base64="%LOCK_OWNER_BASE64%"
echo [launcher] APS is currently in use by another account.
echo [launcher] Please wait for the other user to exit, then try again.
pause
exit /b 8

:BLOCKED_UNCERTAIN
if defined BLOCK_REASON call :log blocked_by_uncertain=%BLOCK_REASON%
echo [launcher] Existing instance ownership is uncertain; startup is blocked.
echo [launcher] Retry later; if startup keeps failing, restart the computer.
echo [launcher] Contact support with the launcher log: %LAUNCHER_LOG%
pause
exit /b 9

:OPEN_CHROME
set "URL=http://%HOST%:%PORT%/"
call :log url="%URL%"
call :log chrome_cmd="%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
echo [launcher] Chrome source: %CHROME_SOURCE%
if defined HEALTH_RECOVERY_READY echo [launcher] Opening the read-only recovery page.
echo [launcher] Opening: %URL%
REM The start return code only covers immediate command failure.
start "" /D "%CHROME_RUN_DIR%" "%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
set "START_RC=%ERRORLEVEL%"
call :log chrome_start_rc=%START_RC%
if not "%START_RC%"=="0" (
  echo [launcher] Chrome start failed, rc=%START_RC%.
  echo [launcher] Check shared logs and run the logged chrome_cmd in cmd.
  pause
  exit /b 5
)
timeout /t 3 /nobreak >nul
call :probe_aps_chrome_alive
if not defined CHROME_ALIVE (
  echo [launcher] Could not confirm the APS browser process.
  echo [launcher] Check shared logs: %LAUNCHER_LOG%
  echo [launcher] Profile: %CHROME_PROFILE_DIR%
  echo [launcher] Run chrome_cmd from launcher.log manually in cmd.
  pause
  exit /b 11
)
exit /b 0


:select_app_exe
if defined APP_EXE exit /b 0
set "CANDIDATE_NAME=%~nx1"
set "CANDIDATE_STEM=%~n1"
if /I "%CANDIDATE_STEM:~0,5%"=="unins" exit /b 0
if /I "%CANDIDATE_NAME%"=="chrome.exe" exit /b 0
set "APP_EXE=%~1"
exit /b 0

:initialize_launch_id
REM CMD RANDOM can have the same seed in two concurrent launcher processes.
set "LAUNCHER_RUN_ID="
for /f "delims=" %%G in ('powershell -NoProfile -NonInteractive -Command "[Guid]::NewGuid().ToString('N')" 2^>nul') do set "LAUNCHER_RUN_ID=%%G"
if not defined LAUNCHER_RUN_ID exit /b 1
set LAUNCHER_RUN_ID | findstr /R "^LAUNCHER_RUN_ID=[a-f0-9][a-f0-9]*$" >nul
if errorlevel 1 exit /b 1
if not "%LAUNCHER_RUN_ID:~32,1%"=="" exit /b 1
if "%LAUNCHER_RUN_ID:~31,1%"=="" exit /b 1
exit /b 0

:recover_launch_error
REM A shared duplicate-start error is not proof that the actual owner failed.
REM Recheck the live DB/owner/lock/contract; never remove or rewrite the error.
call :try_reuse_existing
if defined CAN_REUSE_EXISTING call :log launch_error_recovered=verified_ready
if defined WAIT_EXISTING_STARTUP call :log launch_error_recovered=verified_starting
exit /b 0

:poll_app_ready
set "HEALTH_OK="
set "PORT_READY="
call :read_host_file
call :read_port_file
if not defined FILE_HOST exit /b 0
if not defined FILE_PORT exit /b 0
set "HOST=%FILE_HOST%"
set "PORT=%FILE_PORT%"
if defined HAS_POWERSHELL (call :probe_health) else (call :is_port_listening)
exit /b 0

:configure_portable_data
set "APS_SHARED_DATA_ROOT=%APP_DIR%\user-data"
set "APS_DB_PATH=%APP_DIR%\user-data\db\aps.db"
set "APS_LOG_DIR=%APP_DIR%\user-data\logs"
set "APS_BACKUP_DIR=%APP_DIR%\user-data\backups"
set "APS_EXCEL_TEMPLATE_DIR=%APP_DIR%\user-data\templates_excel"
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
set "HEALTH_OK="
set "HEALTH_RECOVERY_READY="
set "HEALTH_APP_DETECTED="
set "BLOCKED_BY_OTHER="
set "BLOCKED_BY_UNCERTAIN="
set "BLOCK_REASON="
set "LOCK_QUERY_ERROR="
set "WAIT_EXISTING_STARTUP="
set "WAIT_EXISTING_REASON="
call :read_lock_file
call :lock_is_active
call :read_runtime_contract

if /I "%LOCK_ACTIVE%"=="1" (
  call :try_reuse_active_lock
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
    call :probe_app_presence
    if defined HEALTH_APP_DETECTED (
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

:try_reuse_active_lock
  if not defined LOCK_OWNER_BASE64 (
    call :block_uncertain lock_owner_missing
    exit /b 0
  )

  call :load_existing_endpoint
  if not "%LOCK_OWNER_MATCH%"=="1" (
    if defined ENDPOINT_HOST set "HOST=%ENDPOINT_HOST%"
    if defined ENDPOINT_PORT set "PORT=%ENDPOINT_PORT%"
    set "BLOCKED_BY_OTHER=1"
    call :log existing_reuse_blocked=other_owner_active owner_utf8_base64="%LOCK_OWNER_BASE64%"
    exit /b 0
  )
  if not "%LOCK_DB_MATCH%"=="1" (
    call :block_uncertain lock_database_unproven
    exit /b 0
  )
  if not "%LOCK_EXE_MATCH%"=="1" (
    call :block_uncertain lock_executable_unproven
    exit /b 0
  )

  REM B11: same owner + verified-active lock + endpoint not published yet means
  REM the app is still starting - the lock is written before host/port files.
  REM Wait for the endpoint instead of blocking as uncertain.
  if not defined ENDPOINT_HOST (
    set "WAIT_EXISTING_STARTUP=1"
    set "WAIT_EXISTING_REASON=lock_active_missing_host"
    call :log existing_reuse_wait=lock_active_missing_host
    exit /b 0
  )
  if not defined ENDPOINT_PORT (
    set "WAIT_EXISTING_STARTUP=1"
    set "WAIT_EXISTING_REASON=lock_active_missing_port"
    call :log existing_reuse_wait=lock_active_missing_port
    exit /b 0
  )

  set "HOST=%ENDPOINT_HOST%"
  set "PORT=%ENDPOINT_PORT%"
  if defined HAS_POWERSHELL (
    call :try_reuse_active_endpoint
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

:try_reuse_active_endpoint
call :probe_health
if defined HEALTH_OK (
  call :read_runtime_contract
  call :lock_contract_pid_matches
  if not defined LOCK_CONTRACT_PID_MATCH (
    call :block_uncertain lock_contract_pid_mismatch
    exit /b 0
  )
  set "CAN_REUSE_EXISTING=1"
  call :log existing_reuse=lock_active_same_owner
  exit /b 0
)
if defined HEALTH_OTHER_OWNER (
  set "BLOCKED_BY_OTHER=1"
  exit /b 0
)
if "%HEALTH_RC%"=="2" (
  call :block_uncertain lock_active_health_identity_failed
  exit /b 0
)
set "WAIT_EXISTING_STARTUP=1"
set "WAIT_EXISTING_REASON=lock_active_health_pending"
call :log existing_reuse_wait=lock_active_health_pending
exit /b 0

:lock_contract_pid_matches
set "LOCK_CONTRACT_PID_MATCH="
if defined CONTRACT_VALID if "%LOCK_PID%"=="%CONTRACT_PID%" set "LOCK_CONTRACT_PID_MATCH=1"
exit /b 0

:try_reuse_by_contract
if not defined CONTRACT_VALID exit /b 0
if not defined CONTRACT_HOST exit /b 0
if not defined CONTRACT_PORT exit /b 0
if not defined HAS_POWERSHELL exit /b 0

set "HOST=%CONTRACT_HOST%"
set "PORT=%CONTRACT_PORT%"
call :probe_health
if defined HEALTH_OTHER_OWNER (
  set "BLOCKED_BY_OTHER=1"
  call :log existing_reuse_blocked=health_owner_mismatch
  exit /b 0
)
if not defined HEALTH_OK exit /b 0

REM HEALTH_OK already proves the latest contract's owner, DB and instance.
REM Do not override that proof with the earlier cached owner comparison.
set "CAN_REUSE_EXISTING=1"
call :log existing_reuse=contract_owner_match
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
set "HEALTH_RECOVERY_READY="
set "HEALTH_OTHER_OWNER="
set "HEALTH_RC="
if not defined HAS_POWERSHELL exit /b 0
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" exit /b 0
set "HEALTH_URL=http://%HOST%:%PORT%%HEALTH_PATH%"
REM Read the latest contract on every probe, including the first-start wait loop.
REM Both JSON parsers must prove the full identity; never trust status-only text.
powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; function Read-IdentityJson([string]$text) { if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue) { return ($text | ConvertFrom-Json) }; Add-Type -AssemblyName System.Web.Extensions; return (New-Object System.Web.Script.Serialization.JavaScriptSerializer).DeserializeObject($text) }; function Get-IdentityValue($obj,[string]$name) { if ($obj -is [System.Collections.IDictionary]) { return ,($obj[$name]) }; if ($null -eq $obj) { return $null }; $prop=$obj.PSObject.Properties[$name]; if ($null -ne $prop) { return ,($prop.Value) }; return $null }; function Get-Utf8Hash([string]$text) { $sha=[System.Security.Cryptography.SHA256]::Create(); try { return [BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text))).Replace('-','').ToLowerInvariant() } finally { $sha.Clear() } }; try { $contract=Read-IdentityJson ([System.IO.File]::ReadAllText($env:RUNTIME_CONTRACT_FILE,[System.Text.Encoding]::UTF8)); $contractPid=[long]0; $contractPort=[int]0; $contractVersion=[int]0; if (-not [long]::TryParse([string](Get-IdentityValue $contract 'pid'),[ref]$contractPid) -or $contractPid -le 0) { exit 2 }; if (-not [int]::TryParse([string](Get-IdentityValue $contract 'port'),[ref]$contractPort) -or $contractPort -lt 1 -or $contractPort -gt 65535) { exit 2 }; if (-not [int]::TryParse([string](Get-IdentityValue $contract 'contract_version'),[ref]$contractVersion) -or $contractVersion -ne 1) { exit 2 }; $contractOwner=[string](Get-IdentityValue $contract 'owner'); $contractHost=[string](Get-IdentityValue $contract 'host'); $dbPath=[string](Get-IdentityValue $contract 'db_path'); $token=[string](Get-IdentityValue $contract 'shutdown_token'); if ([string]::IsNullOrEmpty($contractOwner) -or [string]::IsNullOrEmpty($contractHost) -or [string]::IsNullOrEmpty($dbPath) -or [string]::IsNullOrEmpty($token)) { exit 2 }; if ([string]::IsNullOrEmpty($env:APS_DB_PATH)) { exit 2 }; $expectedDb=[System.IO.Path]::GetFullPath($env:APS_DB_PATH).ToLowerInvariant(); if (-not [string]::Equals($expectedDb,$dbPath,[System.StringComparison]::Ordinal)) { exit 2 }; $uri=New-Object System.Uri($env:HEALTH_URL); if ($uri.Scheme -ne 'http' -or -not [string]::Equals($uri.Host,$contractHost,[System.StringComparison]::OrdinalIgnoreCase) -or $uri.Port -ne $contractPort -or -not [string]::Equals($env:HOST,$contractHost,[System.StringComparison]::OrdinalIgnoreCase)) { exit 2 }; $req=[System.Net.HttpWebRequest]::Create($uri); $req.Timeout=2000; $req.ReadWriteTimeout=2000; $req.AllowAutoRedirect=$false; $resp=$null; $sr=$null; try { try { $resp=$req.GetResponse() } catch [System.Net.WebException] { $resp=$_.Exception.Response; if ($null -eq $resp -or [int]$resp.StatusCode -ne 503) { throw } }; $responseStatus=[int]$resp.StatusCode; if ($responseStatus -ne 200 -and $responseStatus -ne 503) { exit 2 }; $sr=New-Object System.IO.StreamReader($resp.GetResponseStream(),[System.Text.Encoding]::UTF8); $body=$sr.ReadToEnd() } finally { if ($null -ne $sr) { $sr.Close() }; if ($null -ne $resp) { $resp.Close() } }; $health=Read-IdentityJson $body; $healthPid=[long]0; $healthVersion=[int]0; if (-not [long]::TryParse([string](Get-IdentityValue $health 'pid'),[ref]$healthPid) -or $healthPid -ne $contractPid) { exit 2 }; if (-not [int]::TryParse([string](Get-IdentityValue $health 'contract_version'),[ref]$healthVersion) -or $healthVersion -ne 1) { exit 2 }; if (-not [string]::Equals([string](Get-IdentityValue $health 'app'),'aps',[System.StringComparison]::Ordinal)) { exit 2 }; $isRecovery=$false; $status=[string](Get-IdentityValue $health 'status'); if ($responseStatus -eq 503) { $available=Get-IdentityValue $health 'operations_available'; if (-not [string]::Equals($status,'recovery_required',[System.StringComparison]::Ordinal) -or $available -isnot [bool] -or $available -ne $false) { exit 2 }; $isRecovery=$true } elseif (-not [string]::Equals($status,'ok',[System.StringComparison]::Ordinal)) { exit 2 }; $healthOwner=[string](Get-IdentityValue $health 'owner'); if (-not [string]::Equals($healthOwner,$contractOwner,[System.StringComparison]::OrdinalIgnoreCase)) { exit 2 }; if (-not [string]::Equals([string](Get-IdentityValue $health 'db_path_hash'),(Get-Utf8Hash $dbPath),[System.StringComparison]::Ordinal) -or -not [string]::Equals([string](Get-IdentityValue $health 'instance_id'),(Get-Utf8Hash $token),[System.StringComparison]::Ordinal)) { exit 2 }; if (-not [string]::Equals($healthOwner,$env:CURRENT_OWNER,[System.StringComparison]::OrdinalIgnoreCase) -or -not [string]::Equals($contractOwner,$env:CURRENT_OWNER,[System.StringComparison]::OrdinalIgnoreCase)) { exit 4 }; if ($isRecovery) { exit 3 }; exit 0 } catch { exit 1 }" >nul 2>nul
set "HEALTH_RC=%ERRORLEVEL%"
if "%HEALTH_RC%"=="3" (
  set "HEALTH_OK=1"
  set "HEALTH_RECOVERY_READY=1"
  call :log health_recovery_ready="%HEALTH_URL%"
  exit /b 0
)
if "%HEALTH_RC%"=="0" (
  set "HEALTH_OK=1"
  call :log health_ok="%HEALTH_URL%"
) else (
  REM Code 4 proves a live contract identity owned by another account, not reuse.
  if "%HEALTH_RC%"=="4" set "HEALTH_OTHER_OWNER=1"
  call :log health_fail="%HEALTH_URL%" rc=%HEALTH_RC%
)
exit /b 0

:probe_app_presence
REM Read-only existence evidence from a published endpoint is never reuse proof.
REM APS error/recovery responses also block a new spawn until ownership is known.
set "HEALTH_APP_DETECTED="
set "PRESENCE_RC="
if not defined HAS_POWERSHELL exit /b 0
if not defined HOST exit /b 0
if not defined PORT exit /b 0
set "PRESENCE_URL=http://%HOST%:%PORT%%HEALTH_PATH%"
powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; function Read-PresenceJson([string]$text) { if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue) { return ($text | ConvertFrom-Json) }; Add-Type -AssemblyName System.Web.Extensions; return (New-Object System.Web.Script.Serialization.JavaScriptSerializer).DeserializeObject($text) }; function Get-PresenceValue($obj,[string]$name) { if ($obj -is [System.Collections.IDictionary]) { return $obj[$name] }; if ($null -eq $obj) { return $null }; $prop=$obj.PSObject.Properties[$name]; if ($null -ne $prop) { return $prop.Value }; return $null }; try { $req=[System.Net.HttpWebRequest]::Create($env:PRESENCE_URL); $req.Timeout=2000; $req.ReadWriteTimeout=2000; $req.AllowAutoRedirect=$false; $resp=$null; $sr=$null; try { try { $resp=$req.GetResponse() } catch [System.Net.WebException] { $resp=$_.Exception.Response; if ($null -eq $resp -or [int]$resp.StatusCode -ne 503) { throw } }; $responseStatus=[int]$resp.StatusCode; if ($responseStatus -ne 200 -and $responseStatus -ne 503) { exit 2 }; $sr=New-Object System.IO.StreamReader($resp.GetResponseStream(),[System.Text.Encoding]::UTF8); $body=$sr.ReadToEnd() } finally { if ($null -ne $sr) { $sr.Close() }; if ($null -ne $resp) { $resp.Close() } }; $obj=Read-PresenceJson $body; $version=[int]0; if (-not [int]::TryParse([string](Get-PresenceValue $obj 'contract_version'),[ref]$version) -or $version -ne 1) { exit 2 }; if (-not [string]::Equals([string](Get-PresenceValue $obj 'app'),'aps',[System.StringComparison]::Ordinal)) { exit 2 }; exit 0 } catch { exit 1 }" >nul 2>nul
set "PRESENCE_RC=%ERRORLEVEL%"
if "%PRESENCE_RC%"=="0" (
  set "HEALTH_APP_DETECTED=1"
  call :log app_presence_detected="%PRESENCE_URL%"
) else (
  call :log app_presence_failed="%PRESENCE_URL%" rc=%PRESENCE_RC%
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
set "LOCK_OWNER_BASE64="
set "LOCK_OWNER_MATCH="
set "LOCK_DB_MATCH="
set "LOCK_EXE_MATCH="
set "LOCK_PID="
set "LOCK_READ_ERROR="
if not exist "%LOCK_FILE%" exit /b 0
set "LOCK_READ_TMP=%TEMP%\aps_lock_read_%LAUNCHER_RUN_ID%_%RANDOM%_%RANDOM%.tmp"
REM Runtime lock files are UTF-8, not console text. Compare Unicode owners in PS.
powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $owner=''; $pidText=''; $dbPath=''; $exePath=''; foreach ($line in [System.IO.File]::ReadAllLines($env:LOCK_FILE,[System.Text.Encoding]::UTF8)) { $i=$line.IndexOf('='); if ($i -lt 0) { continue }; $key=$line.Substring(0,$i); $value=$line.Substring($i+1); if ($key -eq 'owner') { $owner=$value }; if ($key -eq 'pid') { $pidText=$value }; if ($key -eq 'db_path') { $dbPath=$value }; if ($key -eq 'exe_path') { $exePath=$value } }; if ($pidText -notmatch '^[0-9]*$') { $pidText='invalid' }; $owner64=[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($owner)); $match=0; if ($owner.Length -gt 0 -and [string]::Equals($owner,$env:CURRENT_OWNER,[System.StringComparison]::OrdinalIgnoreCase)) { $match=1 }; $dbMatch=0; $exeMatch=0; if ($dbPath.Length -gt 0 -and -not [string]::IsNullOrEmpty($env:APS_DB_PATH)) { $expectedDb=[IO.Path]::GetFullPath($env:APS_DB_PATH).ToLowerInvariant(); if ([string]::Equals($dbPath,$expectedDb,[StringComparison]::Ordinal)) { $dbMatch=1 } }; if ($exePath.Length -gt 0 -and -not [string]::IsNullOrEmpty($env:APP_EXE)) { if ([string]::Equals([IO.Path]::GetFullPath($exePath),[IO.Path]::GetFullPath($env:APP_EXE),[StringComparison]::OrdinalIgnoreCase)) { $exeMatch=1 } }; $lines=@(('db_match=' + $dbMatch),('exe_match=' + $exeMatch),('owner_utf8_base64=' + $owner64),('owner_match=' + $match),('pid=' + $pidText)); [System.IO.File]::WriteAllLines($env:LOCK_READ_TMP,[string[]]$lines,[System.Text.Encoding]::ASCII)" >nul 2>nul
if errorlevel 1 (
  del /f /q "%LOCK_READ_TMP%" >nul 2>&1
  set "LOCK_READ_ERROR=lock_parse_failed"
  exit /b 0
)
for /f "usebackq tokens=1,* delims==" %%A in ("%LOCK_READ_TMP%") do (
  if /I "%%A"=="owner_utf8_base64" set "LOCK_OWNER_BASE64=%%B"
  if /I "%%A"=="owner_match" set "LOCK_OWNER_MATCH=%%B"
  if /I "%%A"=="db_match" set "LOCK_DB_MATCH=%%B"
  if /I "%%A"=="exe_match" set "LOCK_EXE_MATCH=%%B"
  if /I "%%A"=="pid" set "LOCK_PID=%%B"
)
del /f /q "%LOCK_READ_TMP%" >nul 2>&1
exit /b 0

:read_runtime_contract
set "CONTRACT_OWNER_BASE64="
set "CONTRACT_OWNER_MATCH="
set "CONTRACT_PID="
set "CONTRACT_VERSION="
set "CONTRACT_HOST="
set "CONTRACT_PORT="
set "CONTRACT_VALID="
set "CONTRACT_READ_ERROR="
if not exist "%RUNTIME_CONTRACT_FILE%" exit /b 0
if not defined HAS_POWERSHELL (
  set "CONTRACT_READ_ERROR=contract_parser_unavailable"
  exit /b 0
)
set "CONTRACT_TMP=%TEMP%\aps_contract_%LAUNCHER_RUN_ID%_%RANDOM%_%RANDOM%.tmp"
set "APS_RUNTIME_CONTRACT_FILE=%RUNTIME_CONTRACT_FILE%"
set "APS_RUNTIME_CONTRACT_OUTPUT=%CONTRACT_TMP%"
REM Keep owner comparison inside PowerShell; emit an ASCII-only file directly.
REM Win7 console encoding/BOM cannot corrupt the account used as identity proof.
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $path=$env:APS_RUNTIME_CONTRACT_FILE; $json=[System.IO.File]::ReadAllText($path,[System.Text.Encoding]::UTF8); $obj=$null; if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue) { $obj=$json | ConvertFrom-Json } else { Add-Type -AssemblyName System.Web.Extensions; $obj=(New-Object System.Web.Script.Serialization.JavaScriptSerializer).DeserializeObject($json) }; function Get-ContractValue([string]$name) { if ($obj -is [System.Collections.IDictionary]) { return $obj[$name] }; $prop=$obj.PSObject.Properties[$name]; if ($null -ne $prop) { return $prop.Value }; return $null }; $owner=[string](Get-ContractValue 'owner'); $owner64=[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($owner)); $ownerMatch=0; if ($owner.Length -gt 0 -and [string]::Equals($owner,$env:CURRENT_OWNER,[System.StringComparison]::OrdinalIgnoreCase)) { $ownerMatch=1 }; $lines=@(('owner_utf8_base64=' + $owner64),('owner_match=' + $ownerMatch),('pid=' + [string](Get-ContractValue 'pid')),('contract_version=' + [string](Get-ContractValue 'contract_version')),('host=' + [string](Get-ContractValue 'host')),('port=' + [string](Get-ContractValue 'port'))); foreach ($line in $lines) { if ($line -match '[^\x20-\x7e]') { throw 'Invalid contract protocol value' } }; [System.IO.File]::WriteAllLines($env:APS_RUNTIME_CONTRACT_OUTPUT,[string[]]$lines,[System.Text.Encoding]::ASCII)" >nul 2>nul
set "CONTRACT_RC=%ERRORLEVEL%"
if not "%CONTRACT_RC%"=="0" (
  del /f /q "%CONTRACT_TMP%" >nul 2>&1
  set "CONTRACT_READ_ERROR=contract_parse_failed"
  exit /b 0
)
for /f "usebackq tokens=1,* delims==" %%A in ("%CONTRACT_TMP%") do (
  if /I "%%A"=="owner_utf8_base64" set "CONTRACT_OWNER_BASE64=%%B"
  if /I "%%A"=="owner_match" set "CONTRACT_OWNER_MATCH=%%B"
  if /I "%%A"=="pid" set "CONTRACT_PID=%%B"
  if /I "%%A"=="contract_version" set "CONTRACT_VERSION=%%B"
  if /I "%%A"=="host" set "CONTRACT_HOST=%%B"
  if /I "%%A"=="port" set "CONTRACT_PORT=%%B"
)
del /f /q "%CONTRACT_TMP%" >nul 2>&1
call :log contract_owner_match="%CONTRACT_OWNER_MATCH%" owner_utf8_base64="%CONTRACT_OWNER_BASE64%"

if defined CONTRACT_PID (
  set CONTRACT_PID | findstr /R "^CONTRACT_PID=[0-9][0-9]*$" >nul
  if errorlevel 1 set "CONTRACT_PID="
)
if defined CONTRACT_PORT (
  set CONTRACT_PORT | findstr /R "^CONTRACT_PORT=[0-9][0-9]*$" >nul
  if errorlevel 1 set "CONTRACT_PORT="
)
if not "%CONTRACT_VERSION%"=="1" (
  set "CONTRACT_READ_ERROR=contract_version_invalid"
  set "CONTRACT_OWNER_BASE64="
  set "CONTRACT_OWNER_MATCH="
  set "CONTRACT_PID="
  set "CONTRACT_HOST="
  set "CONTRACT_PORT="
  exit /b 0
)
if defined CONTRACT_OWNER_BASE64 if defined CONTRACT_PID if "%CONTRACT_OWNER_MATCH%"=="0" set "CONTRACT_VALID=1"
if defined CONTRACT_OWNER_BASE64 if defined CONTRACT_PID if "%CONTRACT_OWNER_MATCH%"=="1" set "CONTRACT_VALID=1"
if not defined CONTRACT_VALID set "CONTRACT_READ_ERROR=contract_missing_fields"
exit /b 0

:lock_is_active
set "LOCK_ACTIVE="
set "LOCK_QUERY_TMP="
set "LOCK_QUERY_ERROR="
if defined LOCK_READ_ERROR (
  set "LOCK_ACTIVE=UNKNOWN"
  set "LOCK_QUERY_ERROR=%LOCK_READ_ERROR%"
  exit /b 0
)
if not defined LOCK_PID exit /b 0
set LOCK_PID | findstr /R "^LOCK_PID=[0-9][0-9]*$" >nul
if errorlevel 1 (
  set "LOCK_ACTIVE=UNKNOWN"
  set "LOCK_QUERY_ERROR=lock_pid_invalid"
  exit /b 0
)
set "LOCK_QUERY_TMP=%TEMP%\aps_lock_query_%LAUNCHER_RUN_ID%_%RANDOM%_%RANDOM%.tmp"
tasklist /FI "PID eq %LOCK_PID%" /NH /FO CSV > "%LOCK_QUERY_TMP%" 2>nul
set "LOCK_QUERY_RC=%ERRORLEVEL%"
if not "%LOCK_QUERY_RC%"=="0" (
  del /f /q "%LOCK_QUERY_TMP%" >nul 2>&1
  set "LOCK_ACTIVE=UNKNOWN"
  set "LOCK_QUERY_ERROR=tasklist_failed"
  exit /b 0
)
set "LOCK_ACTIVE=0"
set "LOCK_PID_IMAGE_MISMATCH="
set "LOCK_ROW_IMAGE="
REM B06: PID existing is not enough. A crash-leftover lock PID can be reused by
REM an unrelated process, so the CSV image-name column must match APP_EXE_NAME.
REM PID found but image mismatch => treat as stale lock (LOCK_ACTIVE stays 0).
REM Parse CSV columns instead of passing backslash-escaped quotes to FINDSTR:
REM cmd does not use C-style quote escaping and can turn >nul into a filename.
for /f "usebackq tokens=1,2 delims=," %%N in ("%LOCK_QUERY_TMP%") do (
  if "%%~O"=="%LOCK_PID%" (
    if /I "%%~N"=="%APP_EXE_NAME%" (
      set "LOCK_ACTIVE=1"
    ) else (
      set "LOCK_PID_IMAGE_MISMATCH=1"
      set "LOCK_ROW_IMAGE=%%~N"
    )
  )
)
if defined LOCK_PID_IMAGE_MISMATCH if not "%LOCK_ACTIVE%"=="1" (
  call :log lock_pid_image_mismatch=stale pid=%LOCK_PID% image="%LOCK_ROW_IMAGE%" expected="%APP_EXE_NAME%"
)
del /f /q "%LOCK_QUERY_TMP%" >nul 2>&1
exit /b 0

:read_launch_error
set "LAUNCH_ERROR="
if not exist "%LAUNCH_ERROR_FILE%" exit /b 0
REM Never decode a UTF-8 exception through SET /P and the console code page.
set "LAUNCH_ERROR=1"
exit /b 0

:probe_chrome_profile_dir
set "CHROME_PROFILE_READY="
set "CHROME_PROFILE_PROBE_FILE=%CHROME_PROFILE_DIR%\aps_write_probe_%LAUNCHER_RUN_ID%_%RANDOM%_%RANDOM%.tmp"
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
powershell -NoProfile -Command "$marker=$env:CHROME_PROFILE_DIR.ToLowerInvariant(); $prefix='--user-data-dir='; function Split-CommandLineArgs([string]$cmd) { $tokens=@(); if ($null -eq $cmd -or $cmd.Trim().Length -eq 0) { return $tokens }; $buf=New-Object System.Text.StringBuilder; $inQuotes=$false; for ($i=0; $i -lt $cmd.Length; $i++) { $ch=$cmd[$i]; if ($ch -eq [char]34) { $slashCount=0; $j=$i-1; while ($j -ge 0 -and $cmd[$j] -eq [char]92) { $slashCount++; $j-- }; if (($slashCount %% 2) -eq 0) { $inQuotes=-not $inQuotes; continue } }; if (-not $inQuotes -and [char]::IsWhiteSpace($ch)) { if ($buf.Length -gt 0) { $tokens += $buf.ToString(); $null=$buf.Remove(0,$buf.Length) }; continue }; [void]$buf.Append($ch) }; if ($buf.Length -gt 0) { $tokens += $buf.ToString() }; return $tokens }; function Test-ApsChromeCommandLine([string]$cmd) { foreach ($arg in @(Split-CommandLineArgs $cmd)) { $argLower=$arg.ToLowerInvariant(); if ($argLower.StartsWith($prefix) -and $argLower.Substring($prefix.Length) -eq $marker) { return $true } }; return $false }; $items=$null; if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) { try { $items=@(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) } catch { $items=$null } }; if ($null -eq $items) { if (-not (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) { exit 1 }; try { $items=@(Get-WmiObject Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) } catch { exit 1 } }; foreach ($item in @($items)) { $cmd=[string]$item.CommandLine; if (Test-ApsChromeCommandLine $cmd) { exit 0 } }; exit 2" >nul 2>&1
set "CHROME_QUERY_RC=%ERRORLEVEL%"
if "%CHROME_QUERY_RC%"=="0" (
  set "CHROME_ALIVE=1"
  call :log chrome_alive_probe=detected
) else (
  if "%CHROME_QUERY_RC%"=="2" (
    call :log chrome_alive_probe=missing
  ) else (
    call :log chrome_alive_probe=query_failed rc=%CHROME_QUERY_RC%
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
if not exist "%HOST_FILE%" exit /b 0
set /p FILE_HOST=<"%HOST_FILE%"
if defined FILE_HOST set "FILE_HOST=%FILE_HOST: =%"
if not defined FILE_HOST set "FILE_HOST=127.0.0.1"
exit /b 0

:read_port_file
set "FILE_PORT="
if not exist "%PORT_FILE%" exit /b 0
set /p FILE_PORT=<"%PORT_FILE%"
if not defined FILE_PORT exit /b 0
set "FILE_PORT=%FILE_PORT: =%"
set FILE_PORT | findstr /R "^FILE_PORT=[0-9][0-9]*$" >nul
if errorlevel 1 (
    call :log port_file_invalid="%FILE_PORT%"
    set "FILE_PORT="
)
exit /b 0

:log
REM CMD redirection uses the console code page. Write Unicode environment data
REM through .NET instead; supported by Windows PowerShell 2.0 on Win7.
set "APS_LAUNCHER_MESSAGE=%*"
powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $line='[' + [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss.fff') + '] ' + $env:APS_LAUNCHER_MESSAGE + [Environment]::NewLine; $utf8=New-Object System.Text.UTF8Encoding($false); $bytes=$utf8.GetBytes($line); $stream=New-Object System.IO.FileStream($env:LAUNCHER_LOG,[System.IO.FileMode]::Append,[System.IO.FileAccess]::Write,[System.IO.FileShare]::ReadWrite); try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }" >nul 2>nul
if errorlevel 1 echo [launcher] Could not append the UTF-8 launcher log.
exit /b 0
