# One PowerShell process owns launch diagnostics, identity checks and readiness.
# Keep this file ASCII and compatible with Windows PowerShell 2.0 / .NET 3.5.
# Dot-sourcing loads the functions without starting the application.
$script:ApsScriptClock = [Diagnostics.Stopwatch]::StartNew()
$script:ApsScriptStartedUtc = [DateTime]::UtcNow
$ErrorActionPreference = 'Stop'
$script:ApsJsonCommand = Get-Command ConvertFrom-Json -CommandType Cmdlet -ErrorAction SilentlyContinue
$script:ApsJsonSerializer = $null

function Read-ApsJson([string]$Text) {
    if ($script:ApsJsonCommand) { return ($Text | ConvertFrom-Json) }
    if ($null -eq $script:ApsJsonSerializer) {
        Add-Type -AssemblyName System.Web.Extensions
        $script:ApsJsonSerializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    }
    return $script:ApsJsonSerializer.DeserializeObject($Text)
}

function Get-ApsValue($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) { return ,($Object[$Name]) }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return ,($property.Value) }
    return $null
}

function Write-ApsLog($Context, [string]$Message) {
    $line = '[{0}] elapsed_ms={1} {2}{3}' -f [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss.fff'),
        $Context.clock.ElapsedMilliseconds, $Message, [Environment]::NewLine
    $stream = $null
    try {
        $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($line)
        $stream = New-Object System.IO.FileStream($Context.log, [IO.FileMode]::Append,
            [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        $stream.Write($bytes, 0, $bytes.Length)
    } catch {
        Write-Host ('[launcher] Could not append the UTF-8 launcher log: ' + $_.Exception.Message)
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Get-ApsRegistryValue([string]$Key, [string]$Name) {
    $value = [Microsoft.Win32.Registry]::GetValue($Key, $Name, $null)
    if ($null -eq $value) { return '' }
    return ([string]$value).Replace('"', '')
}

function Resolve-ApsNormalizedPath([string]$Path) {
    # Lock, contract, health and context paths are compared case-insensitively in this one form.
    return [IO.Path]::GetFullPath($Path.Trim())
}

function New-ApsContext([string]$Directory, [Diagnostics.Stopwatch]$Clock) {
    if ($null -eq $Clock) { $Clock = [Diagnostics.Stopwatch]::StartNew() }
    $directory = [IO.Path]::GetFullPath($Directory)
    [IO.Directory]::SetCurrentDirectory($directory)
    $portable = [IO.File]::Exists((Join-Path $directory 'aps-portable.txt'))
    $data = $env:APS_SHARED_DATA_ROOT
    if ($data) { $data = $data.Replace('"', '') }
    if ($portable) { $data = Join-Path $directory 'user-data' }
    elseif (-not $data) { $data = Get-ApsRegistryValue 'HKEY_LOCAL_MACHINE\SOFTWARE\APS' 'SharedDataRoot' }
    if (-not $data) {
        if ($env:ProgramData) { $data = Join-Path $env:ProgramData 'APS\shared-data' }
        else { $data = Join-Path $directory 'shared-data' }
    }
    $paths = @{ APS_SHARED_DATA_ROOT = $data; APS_DB_PATH = (Join-Path $data 'db\aps.db');
        APS_LOG_DIR = (Join-Path $data 'logs'); APS_BACKUP_DIR = (Join-Path $data 'backups');
        APS_EXCEL_TEMPLATE_DIR = (Join-Path $data 'templates_excel') }
    foreach ($name in $paths.Keys) {
        if ($portable -or -not [Environment]::GetEnvironmentVariable($name)) {
            [Environment]::SetEnvironmentVariable($name, $paths[$name])
        }
    }
    [void][IO.Directory]::CreateDirectory($env:APS_LOG_DIR)
    $owner = $env:USERNAME
    $domain = $env:USERDOMAIN
    if (-not $domain) { $domain = $env:COMPUTERNAME }
    if ($domain -and $domain -ine $owner) { $owner = $domain + '\' + $owner }
    $executables = @([IO.Directory]::GetFiles($directory, '*.exe') | Sort-Object | Where-Object {
        [IO.Path]::GetFileName($_) -notmatch '^(unins.*|chrome)\.exe$'
    })
    $exe = ''
    if ($executables.Count) { $exe = Resolve-ApsNormalizedPath $executables[0] }
    $profile = Join-Path $directory 'chrome109_profile'
    if ($env:LOCALAPPDATA) { $profile = Join-Path $env:LOCALAPPDATA 'APS\Chrome109Profile' }
    if ($portable) { $profile = Join-Path $data 'chrome109_profile' }
    return @{ directory = $directory; portable = $portable; exe = $exe; owner = $owner;
        db = (Resolve-ApsNormalizedPath $env:APS_DB_PATH); profile = $profile;
        log = (Join-Path $env:APS_LOG_DIR 'launcher.log'); clock = $Clock;
        lock = (Join-Path $env:APS_LOG_DIR 'aps_runtime.lock');
        contract = (Join-Path $env:APS_LOG_DIR 'aps_runtime.json');
        hostFile = (Join-Path $env:APS_LOG_DIR 'aps_host.txt');
        portFile = (Join-Path $env:APS_LOG_DIR 'aps_port.txt');
        errorFile = (Join-Path $env:APS_LOG_DIR 'aps_launch_error.txt') }
}

function Find-ApsChrome($Context) {
    if ($Context.portable) {
        $path = Join-Path $Context.directory 'tools\chrome109\chrome.exe'
        if (-not [IO.File]::Exists($path)) { throw 'Portable browser is missing. Extract the complete portable ZIP again.' }
        return $path
    }
    if ($env:APS_CHROME_EXE) {
        $path = $env:APS_CHROME_EXE.Replace('"', '')
        if (-not [IO.File]::Exists($path)) { throw 'APS_CHROME_EXE is invalid.' }
        return $path
    }
    $directories = @($env:APS_CHROME_DIR,
        (Get-ApsRegistryValue 'HKEY_LOCAL_MACHINE\SOFTWARE\APS' 'ChromeDir'),
        (Get-ApsRegistryValue 'HKEY_CURRENT_USER\Environment' 'APS_CHROME_DIR'))
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if ($base) { $directories += Join-Path $base 'APS\Chrome109' }
    }
    if (-not $env:LOCALAPPDATA) { $directories += Join-Path $Context.directory 'chrome109_runtime' }
    $directories += Join-Path $Context.directory 'tools\chrome109'
    foreach ($directory in $directories) {
        if (-not $directory) { continue }
        foreach ($relative in @('chrome.exe', 'App\chrome.exe')) {
            $path = Join-Path $directory.Replace('"', '') $relative
            if ([IO.File]::Exists($path)) { return $path }
        }
    }
    throw 'Chrome runtime not found. Install APS_Chrome109_Runtime.exe or set APS_CHROME_EXE.'
}

function Read-ApsStateText([string]$Path) {
    # Observe the backend's files without preventing it from writing, replacing or deleting them.
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    try { $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, $share) }
    catch [IO.FileNotFoundException] { return $null }
    catch [IO.DirectoryNotFoundException] { return $null }
    try {
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8)
        try { return $reader.ReadToEnd() } finally { $reader.Close() }
    } finally { $stream.Dispose() }
}

function Read-ApsOptionalTrimmedText($Context, [string]$Path, [string]$Label) {
    try { return ([string](Read-ApsStateText $Path)).Trim() }
    catch { Write-ApsLog $Context ($Label + '_read_failed=' + $_.Exception.Message); return '' }
}

function Read-ApsRuntime($Context) {
    $result = @{ lock = $null; lockState = 'absent'; contract = $null; hostName = ''; port = 0 }
    try {
        $lockText = Read-ApsStateText $Context.lock
        if ($null -ne $lockText) {
            $lock = @{}
            # Same key=value protocol as the backend reader: keys and values are trimmed once here.
            foreach ($line in ($lockText -split '\r?\n')) {
                $index = $line.IndexOf('=')
                if ($index -lt 0) { continue }
                $key = $line.Substring(0, $index).Trim()
                if ($key) { $lock[$key] = $line.Substring($index + 1).Trim() }
            }
            $result.lock = $lock
            $normalizedExe = $lock.exe_path
            $result.lockState = Get-ApsLockProcessState $lock.pid $lock.exe_path ([ref]$normalizedExe)
            $lock.exe_path = $normalizedExe
        }
    } catch { $result.lockState = 'unknown' }
    try {
        $contractText = Read-ApsStateText $Context.contract
        if ($contractText) { $result.contract = Read-ApsJson $contractText }
    } catch { Write-ApsLog $Context ('contract_read_failed=' + $_.Exception.Message) }
    $result.hostName = [string](Get-ApsValue $result.contract 'host')
    $contractPort = 0
    [void][int]::TryParse([string](Get-ApsValue $result.contract 'port'), [ref]$contractPort)
    $result.port = $contractPort
    $value = Read-ApsOptionalTrimmedText $Context $Context.hostFile 'host_file'
    if ($value) { $result.hostName = $value }
    $value = Read-ApsOptionalTrimmedText $Context $Context.portFile 'port_file'
    $number = 0
    if ([int]::TryParse($value, [ref]$number)) { $result.port = $number }
    return $result
}

function Test-ApsActiveLock($Context, $Runtime) {
    # A live lock decides ownership before any health proof. Half-written fields are uncertain;
    # another or unreadable database path in the lock file is blocked, and so is another executable.
    # An active lock carries the executable path its process check already normalized.
    if ($Runtime.lockState -ne 'active') { return $null }
    $lock = $Runtime.lock
    if (-not $lock.owner) { return @{ state = 'uncertain'; reason = 'lock_owner_missing' } }
    if ($lock.owner -ine $Context.owner) { return @{ state = 'other'; reason = 'lock_owner_mismatch' } }
    if (-not $lock.db_path) { return @{ state = 'uncertain'; reason = 'lock_fields_incomplete' } }
    try { $lockDatabase = Resolve-ApsNormalizedPath $lock.db_path }
    catch { return @{ state = 'blocked'; reason = 'lock_database_unproven' } }
    if ($lockDatabase -ine $Context.db) { return @{ state = 'blocked'; reason = 'lock_database_unproven' } }
    if ($lock.exe_path -ine $Context.exe) { return @{ state = 'blocked'; reason = 'lock_executable_unproven' } }
    return $null
}

function Get-ApsLockProcessState([string]$ProcessId, [string]$Executable, [ref]$NormalizedExecutable) {
    # An active verdict hands back the normalized executable path; [ref] stays without a default.
    $number = 0
    if (-not [int]::TryParse($ProcessId, [ref]$number) -or $number -le 0) { return 'unknown' }
    try { $process = [Diagnostics.Process]::GetProcessById($number) }
    catch [ArgumentException] { return 'absent' }
    catch { return 'unknown' }
    try {
        if ($process.HasExited) { return 'absent' }
        if (-not $Executable) { return 'unknown' }
        $actual = $process.MainModule.FileName
        if (-not $actual) { return 'unknown' }
        $normalized = Resolve-ApsNormalizedPath $Executable
        if ((Resolve-ApsNormalizedPath $actual) -ine $normalized) { return 'absent' }
        if ($null -ne $NormalizedExecutable) { $NormalizedExecutable.Value = $normalized }
        return 'active'
    } catch { return 'unknown' }
    finally { $process.Dispose() }
}

function Get-ApsRemainingMs($Budget) {
    if ($null -eq $Budget) { return 2000 }
    return [int][Math]::Max(0, [Math]::Min(2000, $Budget.limit - $Budget.clock.ElapsedMilliseconds))
}

function Read-ApsHealth($Runtime, $Budget) {
    $timeout = Get-ApsRemainingMs $Budget
    if ($timeout -le 0) { throw 'Readiness deadline reached.' }
    $uri = New-Object System.Uri(('http://{0}:{1}/system/health' -f $Runtime.hostName, $Runtime.port))
    if ($uri.Scheme -ne 'http' -or $uri.Host -ine $Runtime.hostName -or $uri.Port -ne $Runtime.port) {
        throw (New-Object ArgumentException 'Runtime endpoint does not match the published host and port.')
    }
    $request = [Net.HttpWebRequest]::Create($uri)
    $request.Proxy = $null
    $request.Timeout = $timeout
    $request.ReadWriteTimeout = $timeout
    $request.AllowAutoRedirect = $false
    $response = $null
    $reader = $null
    try {
        try { $response = $request.GetResponse() }
        catch [Net.WebException] {
            $response = $_.Exception.Response
            if ($null -eq $response -or [int]$response.StatusCode -ne 503) { throw }
        }
        $stream = $response.GetResponseStream()
        $remaining = Get-ApsRemainingMs $Budget
        if ($remaining -le 0) { throw 'Readiness deadline reached.' }
        if ($stream.CanTimeout) { $stream.ReadTimeout = $remaining }
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8)
        $health = @{ status = [int]$response.StatusCode; body = (Read-ApsJson $reader.ReadToEnd()) }
        # Every later judgement of this response reuses the one payload verdict.
        $health.valid = Test-ApsHealthPayload $health
        return $health
    } finally {
        if ($null -ne $reader) { $reader.Close() }
        if ($null -ne $response) { $response.Close() }
    }
}

function Test-ApsHealthPayload($Response) {
    $health = $Response.body
    $healthVersion = 0
    if (-not [int]::TryParse([string](Get-ApsValue $health 'contract_version'), [ref]$healthVersion) -or $healthVersion -ne 1 -or
        (Get-ApsValue $health 'app') -cne 'aps') { return $false }
    $status = Get-ApsValue $health 'status'
    if ($Response.status -eq 503) {
        $available = Get-ApsValue $health 'operations_available'
        return ($status -ceq 'recovery_required' -and $available -is [bool] -and $available -eq $false)
    }
    return ($Response.status -eq 200 -and $status -ceq 'ok')
}

function Test-ApsHealth($Context, $Runtime, $Budget, [ref]$HealthResponse, [ref]$HealthAttempted) {
    # Codes match the former launcher: 0 ready, 1 pending, 2 invalid, 3 recovery, 4 other owner.
    # [ref] parameters stay without defaults: PowerShell rejects a $null default when the caller omits them.
    $contract = $Runtime.contract
    if ($null -eq $contract) { return 1 }
    $contractPid = 0L; $port = 0; $version = 0
    if (-not [long]::TryParse([string](Get-ApsValue $contract 'pid'), [ref]$contractPid) -or $contractPid -le 0 -or
        -not [int]::TryParse([string](Get-ApsValue $contract 'port'), [ref]$port) -or $port -lt 1 -or $port -gt 65535 -or
        -not [int]::TryParse([string](Get-ApsValue $contract 'contract_version'), [ref]$version) -or $version -ne 1) { return 2 }
    $owner = [string](Get-ApsValue $contract 'owner')
    $hostName = [string](Get-ApsValue $contract 'host')
    $database = [string](Get-ApsValue $contract 'db_path')
    $instanceId = [string](Get-ApsValue $contract 'instance_id')
    if (-not $owner -or -not $hostName -or -not $database -or -not $instanceId -or
        $Runtime.hostName -ine $hostName -or $Runtime.port -ne $port) { return 2 }
    try { $database = Resolve-ApsNormalizedPath $database } catch { return 2 }
    if ($database -ine $Context.db) { return 2 }
    $response = if ($null -ne $HealthResponse) { $HealthResponse.Value } else { $null }
    if ($null -eq $response) {
        if ($null -ne $HealthAttempted) { $HealthAttempted.Value = $true }
        try {
            $response = Read-ApsHealth $Runtime $Budget
            if ($null -ne $HealthResponse) { $HealthResponse.Value = $response }
        }
        catch [ArgumentException] { return 2 }
        catch { return 1 }
    }
    if (-not $response.valid) { return 2 }
    $health = $response.body
    $healthPid = 0L
    if (-not [long]::TryParse([string](Get-ApsValue $health 'pid'), [ref]$healthPid) -or $healthPid -ne $contractPid) { return 2 }
    $recovery = $response.status -eq 503
    $healthDatabase = [string](Get-ApsValue $health 'db_path')
    if (-not $healthDatabase) { return 2 }
    try { $healthDatabase = Resolve-ApsNormalizedPath $healthDatabase } catch { return 2 }
    if ((Get-ApsValue $health 'owner') -ine $owner -or $healthDatabase -ine $database -or
        (Get-ApsValue $health 'instance_id') -cne $instanceId) { return 2 }
    if ($owner -ine $Context.owner) { return 4 }
    if ($recovery) { return 3 }
    return 0
}

function Get-ApsSnapshotState($Runtime, [int]$Code, $HealthResponse) {
    # One snapshot of lock, contract and endpoint judged against one health response.
    $active = $Runtime.lockState -eq 'active'
    if ($Code -eq 4) { return @{ state = 'other'; reason = 'health_owner_mismatch' } }
    if ($Code -eq 0 -or $Code -eq 3) {
        if ($active -and [string]$Runtime.lock.pid -ne [string](Get-ApsValue $Runtime.contract 'pid')) {
            return @{ state = 'starting'; reason = 'lock_contract_pid_mismatch' }
        }
        return @{ state = 'ready'; recovery = ($Code -eq 3); hostName = $Runtime.hostName; port = $Runtime.port }
    }
    if ($active) {
        if ($Code -eq 2) { return @{ state = 'starting'; reason = 'lock_active_health_identity_failed' } }
        return @{ state = 'starting'; reason = 'lock_active_health_pending' }
    }
    if ($Runtime.lockState -eq 'unknown') { return @{ state = 'uncertain'; reason = 'lock_query_unknown' } }
    # Presence alone prevents another spawn; it can never authorize reuse.
    if ($null -ne $HealthResponse -and $HealthResponse.valid) {
        return @{ state = 'uncertain'; reason = 'healthy_without_owner_proof' }
    }
    return @{ state = 'absent'; reason = 'no_active_instance' }
}

function Get-ApsExistingState($Context, $Budget) {
    $runtime = Read-ApsRuntime $Context
    $lockState = Test-ApsActiveLock $Context $runtime
    if ($null -ne $lockState) { return $lockState }
    $healthResponse = $null
    $healthAttempted = $false
    $code = Test-ApsHealth $Context $runtime $Budget ([ref]$healthResponse) ([ref]$healthAttempted)
    # At most one GET per round: an endpoint that refused or timed out is not asked again.
    if (-not $healthAttempted -and $runtime.lockState -eq 'absent' -and $runtime.hostName -and
        $runtime.port -gt 0 -and $runtime.port -le 65535) {
        try { $healthResponse = Read-ApsHealth $runtime $Budget }
        catch { Write-ApsLog $Context ('app_presence_pending=' + $_.Exception.Message) }
    }
    $state = Get-ApsSnapshotState $runtime $code $healthResponse
    if ($state.state -eq 'ready' -or $state.state -eq 'other' -or $null -eq $healthResponse -or -not $healthResponse.valid) {
        return $state
    }
    # The files were read before the GET; a new owner may have published its lock and contract while the
    # GET was in flight. Judge the same response once more against a fresh file snapshot, without a new GET.
    $refreshed = Read-ApsRuntime $Context
    $lockState = Test-ApsActiveLock $Context $refreshed
    if ($null -ne $lockState) { return $lockState }
    if ($refreshed.hostName -ine $runtime.hostName -or $refreshed.port -ne $runtime.port) { return $state }
    $code = Test-ApsHealth $Context $refreshed $Budget ([ref]$healthResponse)
    return Get-ApsSnapshotState $refreshed $code $healthResponse
}

function Wait-ApsReady($Context, $IgnoredErrorTime, [int]$TimeoutMs = 45000, $SpawnedProcess) {
    $budget = @{ clock = [Diagnostics.Stopwatch]::StartNew(); limit = $TimeoutMs }
    $previous = ''
    while ((Get-ApsRemainingMs $budget) -gt 0) {
        # Sample exit and error signals before the probe, so the probe result can explain them.
        $childExited = ($null -ne $SpawnedProcess) -and $SpawnedProcess.HasExited
        $errorUpdated = [IO.File]::Exists($Context.errorFile) -and
            ([IO.File]::GetLastWriteTimeUtc($Context.errorFile) -ne $IgnoredErrorTime)
        $state = Get-ApsExistingState $Context $budget
        $description = $state.state + ':' + $state.reason
        if ($description -ne $previous) { Write-ApsLog $Context ('readiness=' + $description); $previous = $description }
        # This round's sampled verdict is judged even when the probe crossed the deadline; only a
        # non-final round waits, and the loop condition then ends an exhausted budget as timeout.
        # Ready, other account and proven other database or executable are final; uncertain is a publication race.
        if ($state.state -eq 'ready' -or $state.state -eq 'other' -or $state.state -eq 'blocked') { return $state }
        if ($null -ne $SpawnedProcess) {
            if ($childExited) {
                # A child that never owned the lock records its diagnostics in launcher.log.
                $exitCode = $SpawnedProcess.ExitCode
                if ($exitCode -eq 12) { return @{ state = 'failed'; reason = 'lock_acquisition_failed' } }
                if ($exitCode -eq 13) {
                    # 13 proves a winner of this owner, executable and DB held the lock; wait while it can publish.
                    if ($state.state -eq 'absent') { return @{ state = 'failed'; reason = 'reusable_owner_no_longer_present' } }
                } elseif ($state.state -ne 'starting') {
                    # Without a live lock of this identity nothing can still become ready for this launch.
                    if ($errorUpdated) { return @{ state = 'failed'; reason = 'see_utf8_launch_error_file' } }
                    return @{ state = 'failed'; reason = ('app_process_exited_' + $exitCode) }
                }
            }
        } elseif ($state.state -eq 'absent' -and $errorUpdated) {
            return @{ state = 'failed'; reason = 'see_utf8_launch_error_file' }
        }
        $remaining = Get-ApsRemainingMs $budget
        if ($remaining -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(200, $remaining)) }
    }
    return @{ state = 'timeout'; reason = 'readiness_deadline' }
}

function Start-ApsProcess([string]$Executable, [string]$Arguments, [string]$Directory, [ref]$ProcessOut) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = [IO.Path]::GetFullPath($Executable)
    $info.Arguments = $Arguments
    if ($Directory) { $info.WorkingDirectory = [IO.Path]::GetFullPath($Directory) }
    else { $info.WorkingDirectory = [IO.Directory]::GetCurrentDirectory() }
    $info.UseShellExecute = $false
    $process = [Diagnostics.Process]::Start($info)
    # The caller that asks for the handle owns its disposal; nothing is written to the pipeline.
    if ($null -ne $ProcessOut) { $ProcessOut.Value = $process }
    else { $process.Dispose() }
}

function Invoke-ApsLauncher([string]$Directory, [Diagnostics.Stopwatch]$LaunchClock,
    [DateTime]$PowerShellStartedUtc = [DateTime]::MinValue) {
    if ($null -eq $LaunchClock) { $LaunchClock = [Diagnostics.Stopwatch]::StartNew() }
    if ($PowerShellStartedUtc -eq [DateTime]::MinValue) { $PowerShellStartedUtc = [DateTime]::UtcNow }
    $invokedMs = $LaunchClock.ElapsedMilliseconds
    $context = $null
    try {
        $context = New-ApsContext $Directory $LaunchClock
        Write-ApsLog $context ('launcher_begin app_dir="' + $context.directory + '" owner="' + $context.owner +
            '" ps_pid=' + $PID + ' ps_started_utc="' + $PowerShellStartedUtc.ToString('o') +
            '" cmd_started_local="' + $env:APS_START_CMD_LOCAL_TIME + '" launcher_invoked_ms=' + $invokedMs +
            ' context_ms=' + ($context.clock.ElapsedMilliseconds - $invokedMs))
        if (-not $context.exe) {
            Write-ApsLog $context 'app_exe_not_found'
            Write-Host '[launcher] App exe not found.'
            return 1
        }
        Write-ApsLog $context 'chrome_find_begin'
        $phaseMs = $context.clock.ElapsedMilliseconds
        try { $chrome = Find-ApsChrome $context }
        catch {
            Write-ApsLog $context $_.Exception.Message
            Write-Host ('[launcher] ' + $_.Exception.Message)
            if (-not $context.portable -and $env:APS_CHROME_EXE) { return 4 }
            return 2
        }
        Write-ApsLog $context ('app_exe="' + $context.exe + '" chrome_exe="' + $chrome +
            '" chrome_find_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
        Write-ApsLog $context 'chrome_profile_begin'
        $phaseMs = $context.clock.ElapsedMilliseconds
        try {
            [void][IO.Directory]::CreateDirectory($context.profile)
            $probe = Join-Path $context.profile ('aps_write_probe_' + [Guid]::NewGuid().ToString('N') + '.tmp')
            [IO.File]::WriteAllText($probe, 'APS')
            [IO.File]::Delete($probe)
        }
        catch { Write-ApsLog $context ('chrome_profile_probe_failed=' + $_.Exception.Message); return 10 }
        Write-ApsLog $context ('chrome_profile_ready profile_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
        Write-ApsLog $context 'existing_probe_begin'
        $phaseMs = $context.clock.ElapsedMilliseconds
        $state = Get-ApsExistingState $context $null
        Write-ApsLog $context ('existing_instance=' + $state.state + ':' + $state.reason +
            ' probe_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
        if ($state.state -eq 'absent' -or $state.state -eq 'starting') {
            $ignoredErrorTime = $null
            $spawnedProcess = $null
            try {
                if ($state.state -eq 'absent') {
                    # The owner clears its own signals. Never erase a concurrent owner's files.
                    $ignoredErrorTime = [IO.File]::GetLastWriteTimeUtc($context.errorFile)
                    Write-Host '[launcher] Starting app...'
                    Write-ApsLog $context 'app_start_required=1'
                    $phaseMs = $context.clock.ElapsedMilliseconds
                    try { Start-ApsProcess $context.exe '' $context.directory ([ref]$spawnedProcess) }
                    catch { Write-ApsLog $context ('app_spawn_failed=' + $_.Exception.Message); return 6 }
                    Write-ApsLog $context ('app_spawned spawn_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
                }
                Write-Host '[launcher] Waiting for app readiness (up to 45s)...'
                Write-ApsLog $context 'wait_begin'
                $phaseMs = $context.clock.ElapsedMilliseconds
                $state = Wait-ApsReady $context $ignoredErrorTime -SpawnedProcess $spawnedProcess
                Write-ApsLog $context ('wait_end state=' + $state.state +
                    ' wait_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
            } finally {
                if ($null -ne $spawnedProcess) { $spawnedProcess.Dispose() }
            }
        }
        if ($state.state -ne 'ready') {
            Write-ApsLog $context ('launch_stopped=' + $state.state + ':' + $state.reason)
            switch ($state.state) {
                'other' { Write-Host '[launcher] APS is currently in use by another account.'; return 8 }
                { $_ -eq 'blocked' -or $_ -eq 'uncertain' } {
                    Write-Host '[launcher] Existing instance ownership is uncertain or blocked; startup is stopped.'
                    return 9
                }
                'timeout' { Write-Host '[launcher] App did not become ready within 45 seconds.'; return 3 }
                default {
                    $diagnostic = if ($state.reason -eq 'see_utf8_launch_error_file') { $context.errorFile } else { $context.log }
                    Write-Host ('[launcher] App startup failed. Check: ' + $diagnostic)
                    return 6
                }
            }
        }
        $url = 'http://{0}:{1}/' -f $state.hostName, $state.port
        $arguments = '--user-data-dir="{0}" --app="{1}" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking' -f $context.profile, $url
        Write-ApsLog $context ('health_ready url="' + $url + '" recovery=' + $state.recovery)
        Write-ApsLog $context ('chrome_cmd="' + $chrome + '" ' + $arguments)
        Write-Host ('[launcher] Opening: ' + $url)
        $phaseMs = $context.clock.ElapsedMilliseconds
        try { Start-ApsProcess $chrome $arguments ([IO.Path]::GetDirectoryName($chrome)) }
        catch { Write-ApsLog $context ('chrome_spawn_failed=' + $_.Exception.Message); return 5 }
        Write-ApsLog $context ('chrome_started spawn_ms=' + ($context.clock.ElapsedMilliseconds - $phaseMs))
        Write-ApsLog $context 'launcher_complete'
        return 0
    } catch {
        if ($null -ne $context) { Write-ApsLog $context ('launcher_failed=' + $_.Exception.Message) }
        Write-Host ('[launcher] Startup failed: ' + $_.Exception.Message)
        return 7
    } finally {
        if ($null -ne $context) { Write-Host ('[launcher] Log: ' + $context.log) }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    exit (Invoke-ApsLauncher (Split-Path -Parent $MyInvocation.MyCommand.Path) $script:ApsScriptClock $script:ApsScriptStartedUtc)
}
