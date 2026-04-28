# APS Win7 packaging pipeline:
# default -> build main installer + browser runtime installer + validate dist exe
# legacy  -> build self-contained full installer for internal fallback only
#
# Run:
#   powershell -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1
#   powershell -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1 -MainOnly
#   powershell -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1 -ChromeOnly
#   powershell -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1 -Legacy
#
# NOTE (Windows PowerShell 5.1):
# Keep this script ASCII-only to avoid ParserError when saved as UTF-8 without BOM.

param(
    [switch]$MainOnly,
    [switch]$ChromeOnly,
    [switch]$Legacy
)

chcp 65001 | Out-Null
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    # This script lives in: <repo>/.limcode/skills/aps-package-win7/scripts/package_win7.ps1
    # So repo root is 4 levels up from $PSScriptRoot.
    return (Resolve-Path (Join-Path $PSScriptRoot "../../../..")).Path
}

function Test-PathOrThrow([string]$path, [string]$message) {
    if (-not (Test-Path $path)) {
        throw $message
    }
}

function Invoke-CmdBat([string]$bat) {
    cmd /c $bat
    if ($LASTEXITCODE -ne 0) {
        throw "$bat failed (exit=$LASTEXITCODE)"
    }
}

function Get-FreePort([int[]]$candidates) {
    foreach ($p in $candidates) {
        $l = New-Object System.Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $p)
        try {
            $l.Start()
            $l.Stop()
            return $p
        } catch {
            try { $l.Stop() } catch {}
        }
    }
    return $null
}

function Remove-PathWithRetry([string]$path) {
    if (-not (Test-Path $path)) {
        return
    }

    for ($i = 0; $i -lt 3; $i++) {
        try {
            Remove-Item $path -Recurse -Force
            return
        } catch {
            if ($i -ge 2) {
                throw
            }
            Start-Sleep -Seconds 2
        }
    }
}

function Remove-DistRuntimeArtifacts([string]$distDir) {
    $runtimeDirs = @(
        (Join-Path $distDir "db"),
        (Join-Path $distDir "logs"),
        (Join-Path $distDir "backups")
    )

    foreach ($path in $runtimeDirs) {
        if (Test-Path $path) {
            Remove-PathWithRetry $path
        }
    }

    $rootPatterns = @("*.maintenance.lock", "*.rollback_tmp", "*.db-wal", "*.db-shm", "*.db-journal")
    foreach ($pattern in $rootPatterns) {
        Get-ChildItem -Path $distDir -Filter $pattern -File -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-DistDir {
    foreach ($d in (Get-ChildItem dist -Directory -ErrorAction SilentlyContinue)) {
        $hasExe = Get-ChildItem $d.FullName -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hasExe) {
            return $d.FullName
        }
    }

    throw "dist output directory not found."
}

function Find-LauncherPath {
    $launcherMatches = Get-ChildItem -Path "assets" -Filter "*.bat" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*Chrome*.bat" }

    if (-not $launcherMatches -or $launcherMatches.Count -ne 1) {
        throw "Expected exactly one launcher bat in assets matching *Chrome*.bat."
    }

    return $launcherMatches[0].FullName
}

function Copy-LauncherToDist([string]$distDir) {
    $launcher = Find-LauncherPath
    Copy-Item -Force $launcher -Destination $distDir
}

function Resolve-Iscc {
    if ($env:ISCC_EXE -and (Test-Path $env:ISCC_EXE)) {
        return $env:ISCC_EXE
    }

    if ($env:INNO_HOME) {
        $candidate = Join-Path $env:INNO_HOME "ISCC.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $defaultIscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIscc) {
        return $defaultIscc
    }

    return $null
}

function Set-HostPortDefaults {
    if (-not $env:APS_HOST) {
        $env:APS_HOST = "127.0.0.1"
    }

    if (-not $env:APS_PORT) {
        $ports = @(5000, 20000, 30000, 40000, 50000)
        $chosen = Get-FreePort $ports
        if (-not $chosen) {
            throw "No free port found. Please set APS_PORT manually."
        }
        $env:APS_PORT = "$chosen"
    }
}

function Test-DistExeStartup([string]$distDir) {
    $exe = (Get-ChildItem $distDir -Filter *.exe -File | Select-Object -First 1).FullName
    if (-not $exe) {
        throw "Main exe not found in $distDir."
    }

    python validate_dist_exe.py "$exe"
    if ($LASTEXITCODE -ne 0) {
        throw "validate_dist_exe.py failed (exit=$LASTEXITCODE)."
    }
}

function Resolve-PythonExe {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    throw "python.exe not found in PATH."
}

function Wait-HttpReady([string]$url, [int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds([Math]::Max($timeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        try {
            $req = [System.Net.HttpWebRequest]::Create($url)
            $req.Timeout = 1000
            $req.ReadWriteTimeout = 1000
            $resp = $req.GetResponse()
            $resp.Close()
            return $true
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }

    return $false
}

function Get-ChromeIdsByMarker([string]$marker) {
    if ($null -eq $marker -or $marker.Trim().Length -eq 0) {
        return @()
    }

    $markerLower = $marker.ToLowerInvariant()
    $items = $null
    $prefix = "--user-data-dir="

    if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        try {
            $items = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction Stop)
        } catch {
            $items = $null
        }
    }

    if ($null -eq $items) {
        if (-not (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) {
            throw "Process enumeration unavailable for chrome smoke."
        }

        try {
            $items = @(Get-WmiObject Win32_Process -Filter "Name='chrome.exe'" -ErrorAction Stop)
        } catch {
            throw "Chrome process enumeration failed: $($_.Exception.Message)"
        }
    }

    $targetIds = New-Object System.Collections.Generic.List[int]
    foreach ($item in @($items)) {
        $cmdLine = [string]$item.CommandLine
        $matchedProfile = $false
        foreach ($arg in @(Split-CommandLineArgs $cmdLine)) {
            $argLower = $arg.ToLowerInvariant()
            if ($argLower.StartsWith($prefix) -and $argLower.Substring($prefix.Length) -eq $markerLower) {
                $matchedProfile = $true
            }
        }
        if ($matchedProfile) {
            $targetIdValue = 0
            try {
                $targetIdValue = [int]$item.ProcessId
            } catch {
                $targetIdValue = 0
            }

            if ($targetIdValue -gt 0 -and -not $targetIds.Contains($targetIdValue)) {
                $targetIds.Add($targetIdValue)
            }
        }
    }

    return $targetIds.ToArray()
}

function Split-CommandLineArgs([string]$cmdLine) {
    $tokens = @()
    if ($null -eq $cmdLine -or $cmdLine.Trim().Length -eq 0) {
        return $tokens
    }

    $buf = New-Object System.Text.StringBuilder
    $inQuotes = $false
    for ($i = 0; $i -lt $cmdLine.Length; $i++) {
        $ch = $cmdLine[$i]
        if ($ch -eq [char]34) {
            $slashCount = 0
            $j = $i - 1
            while ($j -ge 0 -and $cmdLine[$j] -eq [char]92) {
                $slashCount++
                $j--
            }
            if (($slashCount % 2) -eq 0) {
                $inQuotes = -not $inQuotes
                continue
            }
        }
        if (-not $inQuotes -and [char]::IsWhiteSpace($ch)) {
            if ($buf.Length -gt 0) {
                $tokens += $buf.ToString()
                $null = $buf.Remove(0, $buf.Length)
            }
            continue
        }
        [void]$buf.Append($ch)
    }

    if ($buf.Length -gt 0) {
        $tokens += $buf.ToString()
    }
    return $tokens
}

function Stop-ProcessTreeByIds([int[]]$targetIds) {
    foreach ($targetId in @($targetIds)) {
        if ($targetId -le 0) {
            continue
        }

        & taskkill /PID $targetId /F /T | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to stop process tree for process id=$targetId"
        }
    }
}

function Stop-ProcessTreeByIdsBestEffort([int[]]$targetIds) {
    try {
        Stop-ProcessTreeByIds $targetIds
    } catch {
    }
}

function Get-ChromeIdsByExecutablePath([string]$chromeExe) {
    if ($null -eq $chromeExe -or $chromeExe.Trim().Length -eq 0 -or -not (Test-Path $chromeExe)) {
        return @()
    }

    $targetExe = (Resolve-Path $chromeExe).Path.ToLowerInvariant()
    $items = $null
    if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        try {
            $items = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction Stop)
        } catch {
            $items = $null
        }
    }

    if ($null -eq $items) {
        if (-not (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) {
            return @()
        }

        try {
            $items = @(Get-WmiObject Win32_Process -Filter "Name='chrome.exe'" -ErrorAction Stop)
        } catch {
            return @()
        }
    }

    $targetIds = New-Object System.Collections.Generic.List[int]
    foreach ($item in @($items)) {
        $exePath = [string]$item.ExecutablePath
        if ($null -eq $exePath -or $exePath.Trim().Length -eq 0) {
            continue
        }
        if ($exePath.ToLowerInvariant() -eq $targetExe) {
            $targetIdValue = 0
            try {
                $targetIdValue = [int]$item.ProcessId
            } catch {
                $targetIdValue = 0
            }
            if ($targetIdValue -gt 0 -and -not $targetIds.Contains($targetIdValue)) {
                $targetIds.Add($targetIdValue)
            }
        }
    }

    return $targetIds.ToArray()
}

function Stop-LegacyDistChromeBestEffort {
    if (-not (Test-Path "dist")) {
        return
    }

    foreach ($distEntry in @(Get-ChildItem dist -Directory -ErrorAction SilentlyContinue)) {
        $chromeExe = Join-Path $distEntry.FullName "tools\chrome109\chrome.exe"
        $chromeIds = @(Get-ChromeIdsByExecutablePath $chromeExe)
        if ($chromeIds.Count -gt 0) {
            Stop-ProcessTreeByIdsBestEffort $chromeIds
        }
    }
}

function Invoke-ChromeRuntimeSmoke([string]$chromeExe, [string]$label) {
    Test-PathOrThrow $chromeExe "Missing Chrome executable for smoke: $chromeExe"

    $pythonExe = Resolve-PythonExe
    $smokeRoot = Join-Path $env:TEMP ("aps_chrome_smoke_" + [guid]::NewGuid().ToString("N"))
    $siteDir = Join-Path $smokeRoot "site"
    $profileDir = Join-Path $smokeRoot "profile"
    $serverProc = $null
    $marker = ""
    $port = Get-FreePort @(51380..51420)
    if (-not $port) {
        throw "No free port available for chrome smoke."
    }

    $url = "http://127.0.0.1:$port/"
    try {
        New-Item -ItemType Directory -Path $siteDir -Force | Out-Null
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        Set-Content -Path (Join-Path $siteDir "index.html") -Value "<html><body>aps chrome smoke</body></html>" -Encoding ASCII

        $marker = (Resolve-Path $profileDir).Path
        $serverArgs = @("-m", "http.server", "$port", "--bind", "127.0.0.1", "--directory", $siteDir)
        $serverProc = Start-Process -FilePath $pythonExe -ArgumentList $serverArgs -WorkingDirectory $siteDir -PassThru -WindowStyle Hidden
        if (-not (Wait-HttpReady $url 15)) {
            throw "Local smoke HTTP server did not become ready."
        }

        $chromeArgs = @(
            "--user-data-dir=$marker",
            "--app=$url",
            "--no-first-run",
            "--disable-default-apps",
            "--no-default-browser-check",
            "--disable-background-networking"
        )
        $null = Start-Process -FilePath $chromeExe -ArgumentList $chromeArgs -WorkingDirectory (Split-Path $chromeExe -Parent) -PassThru

        $deadline = (Get-Date).AddSeconds(15)
        $matchedChromeIds = @()
        while ((Get-Date) -lt $deadline) {
            $matchedChromeIds = @(Get-ChromeIdsByMarker $marker)
            if ($matchedChromeIds.Count -gt 0) {
                break
            }

            Start-Sleep -Milliseconds 500
        }

        if ($matchedChromeIds.Count -eq 0) {
            throw "Chrome smoke did not create a running chrome.exe process for $label."
        }

        Start-Sleep -Seconds 2
        $stillRunning = @(Get-ChromeIdsByMarker $marker)
        if ($stillRunning.Count -eq 0) {
            throw "Chrome smoke chrome.exe did not stay alive for $label."
        }

        Write-Host ("BROWSER SMOKE OK: " + $label + " -> " + $chromeExe)
    } finally {
        if ($marker) {
            $cleanupChromeIds = @(Get-ChromeIdsByMarker $marker)
            if ($cleanupChromeIds.Count -gt 0) {
                Stop-ProcessTreeByIdsBestEffort $cleanupChromeIds
            }
        }

        try {
            if ($serverProc -and -not $serverProc.HasExited) {
                Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }

        try {
            Remove-PathWithRetry $smokeRoot
        } catch {
        }
    }
}

function Initialize-OfflineChrome109([string]$chromeExe) {
    if (Test-Path $chromeExe) {
        return
    }

    $zip = Get-ChildItem -Path "tools" -Filter "ungoogled-chromium_109*.zip" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $zip) {
        throw "Missing offline Chrome109. Provide $chromeExe or tools\\ungoogled-chromium_109*.zip"
    }

    $tmp = "tools\\_tmp_chrome109"
    Remove-PathWithRetry $tmp
    New-Item -ItemType Directory -Path $tmp | Out-Null

    Expand-Archive -Path $zip.FullName -DestinationPath $tmp -Force

    $found = Get-ChildItem -Path $tmp -Recurse -Filter "chrome.exe" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $found) {
        throw "chrome.exe not found inside zip: $($zip.FullName)"
    }

    $srcDir = $found.Directory.FullName
    $dstDir = Split-Path $chromeExe -Parent
    Remove-PathWithRetry $dstDir
    New-Item -ItemType Directory -Path $dstDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $srcDir "*") $dstDir

    if (-not (Test-Path $chromeExe)) {
        throw "Failed to prepare offline Chrome109 at: $chromeExe"
    }

    try {
        Remove-PathWithRetry $tmp
    } catch {
    }
}

function New-ChromeRuntimePayload([string]$sourceDir, [string]$payloadDir) {
    $keptLocales = @("zh-CN.pak", "en-US.pak")
    $removedHelpers = @(
        "chrome_proxy.exe",
        "chrome_pwa_launcher.exe",
        "notification_helper.exe",
        "elevation_service.exe"
    )

    Remove-PathWithRetry $payloadDir
    New-Item -ItemType Directory -Path $payloadDir | Out-Null

    $sourceLocales = Join-Path $sourceDir "locales"
    $robocopyArgs = @(
        $sourceDir,
        $payloadDir,
        "/E",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD",
        $sourceLocales,
        "/XF"
    ) + $removedHelpers

    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy chrome runtime payload failed (exit=$LASTEXITCODE)."
    }

    $payloadLocales = Join-Path $payloadDir "locales"
    Remove-PathWithRetry $payloadLocales
    New-Item -ItemType Directory -Path $payloadLocales -Force | Out-Null

    foreach ($locale in $keptLocales) {
        $localeSource = Join-Path $sourceLocales $locale
        Test-PathOrThrow $localeSource "Missing locale file: $localeSource"
        Copy-Item -Force $localeSource -Destination (Join-Path $payloadLocales $locale)
    }

    Test-PathOrThrow (Join-Path $payloadDir "chrome.exe") "Trimmed chrome runtime payload is missing chrome.exe."
    $payloadBytes = (Get-ChildItem $payloadDir -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Host ("Prepared trimmed Chrome runtime payload: " + $payloadDir + " (" + $payloadBytes + " bytes)")
}

function Invoke-MainPackageBuild([string]$iscc) {
    Set-HostPortDefaults
    Remove-PathWithRetry "build"
    Remove-PathWithRetry "dist"

    Invoke-CmdBat "build_win7_onedir.bat"
    $distDir = Resolve-DistDir
    Copy-LauncherToDist $distDir
    Test-DistExeStartup $distDir
    Remove-DistRuntimeArtifacts $distDir

    & $iscc "installer\aps_win7.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7.iss (exit=$LASTEXITCODE)."
    }
}

function Invoke-ChromeRuntimeBuild([string]$iscc) {
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome
    Test-PathOrThrow $chrome "Missing $chrome. Provide offline Chrome109 at tools\\Chrome.109.0.5414.120.x64\\chrome.exe or tools\\ungoogled-chromium_109*.zip"
    $payloadDir = "build\chrome109_runtime_payload"
    New-ChromeRuntimePayload (Split-Path $chrome -Parent) $payloadDir
    Invoke-ChromeRuntimeSmoke (Join-Path $payloadDir "chrome.exe") "chrome runtime payload"
    $runtimeArg = "/DRuntimeDir=$((Resolve-Path $payloadDir).Path)"

    & $iscc $runtimeArg "installer\aps_win7_chrome.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7_chrome.iss (exit=$LASTEXITCODE)."
    }
}

function Invoke-LegacyPackageBuild([string]$iscc) {
    Set-HostPortDefaults
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome
    Test-PathOrThrow $chrome "Missing $chrome. Provide offline Chrome109 at tools\\Chrome.109.0.5414.120.x64\\chrome.exe or tools\\ungoogled-chromium_109*.zip"

    Stop-LegacyDistChromeBestEffort
    Remove-PathWithRetry "build"
    Remove-PathWithRetry "dist"

    Invoke-CmdBat "build_win7_onedir.bat"
    Invoke-CmdBat "stage_chrome109_to_dist.bat"

    $distDir = Resolve-DistDir
    Invoke-ChromeRuntimeSmoke (Join-Path $distDir "tools\chrome109\chrome.exe") "legacy dist chrome runtime"
    Copy-LauncherToDist $distDir
    Test-DistExeStartup $distDir
    Remove-DistRuntimeArtifacts $distDir

    & $iscc "installer\aps_win7_legacy.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7_legacy.iss (exit=$LASTEXITCODE)."
    }
}

if ($MainOnly -and $ChromeOnly) {
    throw "MainOnly and ChromeOnly cannot be used together."
}

if ($Legacy -and ($MainOnly -or $ChromeOnly)) {
    throw "Legacy cannot be combined with MainOnly or ChromeOnly."
}

$buildMain = -not $ChromeOnly
$buildChrome = -not $MainOnly
$iscc = Resolve-Iscc

if (-not $iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 or set ISCC_EXE/INNO_HOME."
}

$repoRoot = Resolve-RepoRoot
Push-Location $repoRoot
try {
    $outputs = New-Object System.Collections.Generic.List[string]

    if ($Legacy) {
        Invoke-LegacyPackageBuild $iscc
        $outputs.Add("installer\output\APS_Legacy_Full_Setup.exe") | Out-Null
        Write-Host ("DONE: " + ($outputs -join ", ") + "  (legacy fallback)")
        Write-Host ("VALIDATED: dist exe cold start OK  (APS_HOST=" + $env:APS_HOST + " APS_PORT=" + $env:APS_PORT + ")")
        return
    }

    if ($buildMain) {
        Invoke-MainPackageBuild $iscc
        $outputs.Add("installer\output\APS_Main_Setup.exe") | Out-Null
    }

    if ($buildChrome) {
        Invoke-ChromeRuntimeBuild $iscc
        $outputs.Add("installer\output\APS_Chrome109_Runtime.exe") | Out-Null
    }

    Write-Host ("DONE: " + ($outputs -join ", "))
    if ($buildMain) {
        Write-Host ("VALIDATED: dist exe cold start OK  (APS_HOST=" + $env:APS_HOST + " APS_PORT=" + $env:APS_PORT + ")")
    }
} finally {
    Pop-Location
}
