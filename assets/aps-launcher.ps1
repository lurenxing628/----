# One PowerShell process owns launch diagnostics, identity checks and readiness.
# Keep this file ASCII and compatible with Windows PowerShell 2.0 / .NET 3.5.
# Dot-sourcing loads the functions without starting the application.
$ErrorActionPreference = 'Stop'
$script:ApsJsonCommand = Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue
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

function New-ApsContext([string]$Directory) {
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
    if ($executables.Count) { $exe = $executables[0] }
    $profile = Join-Path $directory 'chrome109_profile'
    if ($env:LOCALAPPDATA) { $profile = Join-Path $env:LOCALAPPDATA 'APS\Chrome109Profile' }
    if ($portable) { $profile = Join-Path $data 'chrome109_profile' }
    return @{ directory = $directory; portable = $portable; exe = $exe; owner = $owner;
        db = [IO.Path]::GetFullPath($env:APS_DB_PATH).ToLowerInvariant(); profile = $profile;
        log = (Join-Path $env:APS_LOG_DIR 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
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

function Read-ApsRuntime($Context) {
    $result = @{ lock = $null; lockState = 'absent'; contract = $null; hostName = ''; port = 0 }
    if ([IO.File]::Exists($Context.lock)) {
        try {
            $lock = @{}
            foreach ($line in [IO.File]::ReadAllLines($Context.lock, [Text.Encoding]::UTF8)) {
                $index = $line.IndexOf('=')
                if ($index -ge 0) { $lock[$line.Substring(0, $index)] = $line.Substring($index + 1) }
            }
            $result.lock = $lock
            $result.lockState = Get-ApsLockProcessState $lock.pid $Context.exe
        } catch { $result.lockState = 'unknown' }
    }
    if ([IO.File]::Exists($Context.contract)) {
        try { $result.contract = Read-ApsJson ([IO.File]::ReadAllText($Context.contract, [Text.Encoding]::UTF8)) }
        catch { Write-ApsLog $Context ('contract_read_failed=' + $_.Exception.Message) }
    }
    $result.hostName = [string](Get-ApsValue $result.contract 'host')
    $contractPort = 0
    [void][int]::TryParse([string](Get-ApsValue $result.contract 'port'), [ref]$contractPort)
    $result.port = $contractPort
    if ([IO.File]::Exists($Context.hostFile)) {
        $value = [IO.File]::ReadAllText($Context.hostFile, [Text.Encoding]::UTF8).Trim()
        if ($value) { $result.hostName = $value }
    }
    if ([IO.File]::Exists($Context.portFile)) {
        $value = [IO.File]::ReadAllText($Context.portFile, [Text.Encoding]::UTF8).Trim()
        $number = 0
        if ([int]::TryParse($value, [ref]$number)) { $result.port = $number }
    }
    return $result
}

function Get-ApsLockProcessState([string]$ProcessId, [string]$Executable) {
    $number = 0
    if (-not [int]::TryParse($ProcessId, [ref]$number) -or $number -le 0) { return 'unknown' }
    $process = $null
    try {
        $process = [Diagnostics.Process]::GetProcessById($number)
        if ($process.HasExited) { return 'absent' }
        if ($process.ProcessName -ine [IO.Path]::GetFileNameWithoutExtension($Executable)) { return 'absent' }
        return 'active'
    } catch [ArgumentException] { return 'absent' }
    catch { return 'unknown' }
    finally { if ($null -ne $process) { $process.Dispose() } }
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
        return @{ status = [int]$response.StatusCode; body = (Read-ApsJson $reader.ReadToEnd()) }
    } finally {
        if ($null -ne $reader) { $reader.Close() }
        if ($null -ne $response) { $response.Close() }
    }
}

function Get-ApsIdentityHash([string]$Text) {
    # Existing runtime health protocol: DB scope and per-instance shutdown token.
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Clear() }
}

function Test-ApsHealth($Context, $Runtime, $Budget) {
    # Codes match the former launcher: 0 ready, 1 pending, 2 invalid, 3 recovery, 4 other owner.
    $contract = $Runtime.contract
    if ($null -eq $contract) { return 1 }
    $contractPid = 0L; $port = 0; $version = 0
    if (-not [long]::TryParse([string](Get-ApsValue $contract 'pid'), [ref]$contractPid) -or $contractPid -le 0 -or
        -not [int]::TryParse([string](Get-ApsValue $contract 'port'), [ref]$port) -or $port -lt 1 -or $port -gt 65535 -or
        -not [int]::TryParse([string](Get-ApsValue $contract 'contract_version'), [ref]$version) -or $version -ne 1) { return 2 }
    $owner = [string](Get-ApsValue $contract 'owner')
    $hostName = [string](Get-ApsValue $contract 'host')
    $database = [string](Get-ApsValue $contract 'db_path')
    $token = [string](Get-ApsValue $contract 'shutdown_token')
    if (-not $owner -or -not $hostName -or -not $database -or -not $token -or
        $database -cne $Context.db -or $Runtime.hostName -ine $hostName -or $Runtime.port -ne $port) { return 2 }
    try { $response = Read-ApsHealth $Runtime $Budget }
    catch [ArgumentException] { return 2 }
    catch { return 1 }
    $health = $response.body
    $healthPid = 0L; $healthVersion = 0
    if (-not [long]::TryParse([string](Get-ApsValue $health 'pid'), [ref]$healthPid) -or $healthPid -ne $contractPid -or
        -not [int]::TryParse([string](Get-ApsValue $health 'contract_version'), [ref]$healthVersion) -or $healthVersion -ne 1 -or
        (Get-ApsValue $health 'app') -cne 'aps') { return 2 }
    $status = Get-ApsValue $health 'status'
    $recovery = $response.status -eq 503
    if ($recovery) {
        $available = Get-ApsValue $health 'operations_available'
        if ($status -cne 'recovery_required' -or $available -isnot [bool] -or $available -ne $false) { return 2 }
    } elseif ($response.status -ne 200 -or $status -cne 'ok') { return 2 }
    if ((Get-ApsValue $health 'owner') -ine $owner -or
        (Get-ApsValue $health 'db_path_hash') -cne (Get-ApsIdentityHash $database) -or
        (Get-ApsValue $health 'instance_id') -cne (Get-ApsIdentityHash $token)) { return 2 }
    if ($owner -ine $Context.owner) { return 4 }
    if ($recovery) { return 3 }
    return 0
}

function Get-ApsExistingState($Context, $Budget) {
    $runtime = Read-ApsRuntime $Context
    $active = $runtime.lockState -eq 'active'
    if ($active) {
        $lock = $runtime.lock
        if (-not $lock.owner) { return @{ state = 'blocked'; reason = 'lock_owner_missing' } }
        if ($lock.owner -ine $Context.owner) { return @{ state = 'other'; reason = 'lock_owner_mismatch' } }
        if ($lock.db_path -cne $Context.db) { return @{ state = 'blocked'; reason = 'lock_database_unproven' } }
        if (-not $lock.exe_path -or [IO.Path]::GetFullPath($lock.exe_path) -ine $Context.exe) {
            return @{ state = 'blocked'; reason = 'lock_executable_unproven' }
        }
    }
    $code = Test-ApsHealth $Context $runtime $Budget
    if ($code -eq 4) { return @{ state = 'other'; reason = 'health_owner_mismatch' } }
    if ($code -eq 0 -or $code -eq 3) {
        if ($active -and [string]$runtime.lock.pid -ne [string](Get-ApsValue $runtime.contract 'pid')) {
            return @{ state = 'blocked'; reason = 'lock_contract_pid_mismatch' }
        }
        return @{ state = 'ready'; recovery = ($code -eq 3); hostName = $runtime.hostName; port = $runtime.port }
    }
    if ($active) {
        if ($code -eq 2) { return @{ state = 'blocked'; reason = 'lock_active_health_identity_failed' } }
        return @{ state = 'starting'; reason = 'lock_active_health_pending' }
    }
    if ($runtime.lockState -eq 'unknown') { return @{ state = 'blocked'; reason = 'lock_query_unknown' } }
    # Presence alone blocks another spawn; it can never authorize reuse.
    if ($runtime.hostName -and $runtime.port -gt 0 -and $runtime.port -le 65535) {
        try {
            $presence = Read-ApsHealth $runtime $Budget
            if (($presence.status -eq 200 -or $presence.status -eq 503) -and
                (Get-ApsValue $presence.body 'app') -ceq 'aps' -and (Get-ApsValue $presence.body 'contract_version') -eq 1) {
                return @{ state = 'blocked'; reason = 'healthy_without_owner_proof' }
            }
        } catch { Write-ApsLog $Context ('app_presence_pending=' + $_.Exception.Message) }
    }
    return @{ state = 'absent'; reason = 'no_active_instance' }
}

function Wait-ApsReady($Context, $IgnoredErrorTime, [int]$TimeoutMs = 45000) {
    $budget = @{ clock = [Diagnostics.Stopwatch]::StartNew(); limit = $TimeoutMs }
    $previous = ''
    while ((Get-ApsRemainingMs $budget) -gt 0) {
        $state = Get-ApsExistingState $Context $budget
        $description = $state.state + ':' + $state.reason
        if ($description -ne $previous) { Write-ApsLog $Context ('readiness=' + $description); $previous = $description }
        if ($budget.clock.ElapsedMilliseconds -ge $budget.limit) { break }
        if (@('ready', 'blocked', 'other') -contains $state.state) { return $state }
        if ($state.state -ne 'starting' -and [IO.File]::Exists($Context.errorFile) -and
            [IO.File]::GetLastWriteTimeUtc($Context.errorFile) -ne $IgnoredErrorTime) {
            return @{ state = 'failed'; reason = 'see_utf8_launch_error_file' }
        }
        $remaining = Get-ApsRemainingMs $budget
        if ($remaining -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(200, $remaining)) }
    }
    return @{ state = 'timeout'; reason = 'readiness_deadline' }
}

function Start-ApsProcess([string]$Executable, [string]$Arguments, [string]$Directory) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.Arguments = $Arguments
    $info.WorkingDirectory = $Directory
    $info.UseShellExecute = $true
    $process = [Diagnostics.Process]::Start($info)
    if ($null -ne $process) { $process.Dispose() }
}

function Invoke-ApsLauncher([string]$Directory) {
    $context = $null
    try {
        $context = New-ApsContext $Directory
        Write-ApsLog $context ('launcher_begin app_dir="' + $context.directory + '" owner="' + $context.owner + '"')
        if (-not $context.exe) {
            Write-ApsLog $context 'app_exe_not_found'
            Write-Host '[launcher] App exe not found.'
            return 1
        }
        try { $chrome = Find-ApsChrome $context }
        catch {
            Write-ApsLog $context $_.Exception.Message
            Write-Host ('[launcher] ' + $_.Exception.Message)
            if (-not $context.portable -and $env:APS_CHROME_EXE) { return 4 }
            return 2
        }
        Write-ApsLog $context ('app_exe="' + $context.exe + '" chrome_exe="' + $chrome + '"')
        try {
            [void][IO.Directory]::CreateDirectory($context.profile)
            $probe = Join-Path $context.profile ('aps_write_probe_' + [Guid]::NewGuid().ToString('N') + '.tmp')
            [IO.File]::WriteAllText($probe, 'APS')
            [IO.File]::Delete($probe)
        }
        catch { Write-ApsLog $context ('chrome_profile_probe_failed=' + $_.Exception.Message); return 10 }
        $state = Get-ApsExistingState $context $null
        Write-ApsLog $context ('existing_instance=' + $state.state + ':' + $state.reason)
        if ($state.state -eq 'absent' -or $state.state -eq 'starting') {
            $ignoredErrorTime = $null
            if ($state.state -eq 'absent') {
                # The owner clears its own signals. Never erase a concurrent owner's files.
                $ignoredErrorTime = [IO.File]::GetLastWriteTimeUtc($context.errorFile)
                Write-Host '[launcher] Starting app...'
                Write-ApsLog $context 'app_start_required=1'
                try { Start-ApsProcess $context.exe '' $context.directory }
                catch { Write-ApsLog $context ('app_spawn_failed=' + $_.Exception.Message); return 6 }
                Write-ApsLog $context 'app_spawned'
            }
            Write-Host '[launcher] Waiting for app readiness (up to 45s)...'
            $state = Wait-ApsReady $context $ignoredErrorTime
        }
        if ($state.state -ne 'ready') {
            Write-ApsLog $context ('launch_stopped=' + $state.state + ':' + $state.reason)
            switch ($state.state) {
                'other' { Write-Host '[launcher] APS is currently in use by another account.'; return 8 }
                'blocked' { Write-Host '[launcher] Existing instance ownership is uncertain; startup is blocked.'; return 9 }
                'timeout' { Write-Host '[launcher] App did not become ready within 45 seconds.'; return 3 }
                default { Write-Host ('[launcher] App startup failed. Check: ' + $context.errorFile); return 6 }
            }
        }
        $url = 'http://{0}:{1}/' -f $state.hostName, $state.port
        $arguments = '--user-data-dir="{0}" --app="{1}" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking' -f $context.profile, $url
        Write-ApsLog $context ('health_ready url="' + $url + '" recovery=' + $state.recovery)
        Write-ApsLog $context ('chrome_cmd="' + $chrome + '" ' + $arguments)
        Write-Host ('[launcher] Opening: ' + $url)
        try { Start-ApsProcess $chrome $arguments ([IO.Path]::GetDirectoryName($chrome)) }
        catch { Write-ApsLog $context ('chrome_spawn_failed=' + $_.Exception.Message); return 5 }
        Write-ApsLog $context 'chrome_started'
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
    exit (Invoke-ApsLauncher (Split-Path -Parent $MyInvocation.MyCommand.Path))
}
