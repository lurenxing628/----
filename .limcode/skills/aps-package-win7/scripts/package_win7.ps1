# APS Win7 packaging pipeline:
# default -> build self-contained portable ZIP, no Inno Setup required
# -Installer -> build the previous main + browser runtime installers
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
# The version guard below is the first statement and must keep parsing under PowerShell 2.0,
# so an older host reports a readable error and exit code 2 instead of a silent success.

param(
    [switch]$Installer,
    [switch]$MainOnly,
    [switch]$ChromeOnly,
    [switch]$Legacy
)

if ($PSVersionTable.PSVersion -lt [Version]"5.1") {
    [Console]::Error.WriteLine("[package_win7] ERROR: Windows PowerShell 5.1 or newer is required; this host runs " + $PSVersionTable.PSVersion + ".")
    $global:LASTEXITCODE = 2
    exit 2
}

$ErrorActionPreference = "Stop"
# Console/native-process encoding is separate from the .ps1 source encoding.
chcp 65001 | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONIOENCODING = "utf-8"

function Resolve-RepoRoot {
    # This script lives in: <repo>/.limcode/skills/aps-package-win7/scripts/package_win7.ps1
    # So repo root is 4 levels up from $PSScriptRoot.
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "../../../..")).Path
}

function Test-PathOrThrow([string]$path, [string]$message) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw $message
    }
}

function Invoke-CmdBat([string]$bat) {
    & $env:ComSpec /d /e:on /v:off /c $bat
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
    if (-not (Test-Path -LiteralPath $path)) {
        return
    }

    for ($i = 0; $i -lt 3; $i++) {
        try {
            Remove-Item -LiteralPath $path -Recurse -Force
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
        if (Test-Path -LiteralPath $path) {
            Remove-PathWithRetry $path
        }
    }

    $rootPatterns = @("*.maintenance.lock", "*.rollback_tmp", "*.db-wal", "*.db-shm", "*.db-journal")
    foreach ($pattern in $rootPatterns) {
        Get-ChildItem -LiteralPath $distDir -Filter $pattern -File -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-DistDir {
    foreach ($d in (Get-ChildItem dist -Directory -ErrorAction SilentlyContinue)) {
        $hasExe = Get-ChildItem -LiteralPath $d.FullName -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hasExe) {
            return $d.FullName
        }
    }

    throw "dist output directory not found."
}

function Resolve-Iscc {
    # An explicit ISCC_EXE or INNO_HOME must be valid; only without them are the default folders and PATH searched.
    if (-not [string]::IsNullOrWhiteSpace($env:ISCC_EXE)) {
        $explicitIscc = $env:ISCC_EXE.Trim()
        if (-not (Test-Path -LiteralPath $explicitIscc -PathType Leaf)) {
            throw ("ISCC_EXE points to a missing file: `"" + $explicitIscc + "`"")
        }
        return (Resolve-Path -LiteralPath $explicitIscc).Path
    }

    if (-not [string]::IsNullOrWhiteSpace($env:INNO_HOME)) {
        $innoCandidate = Join-Path $env:INNO_HOME.Trim() "ISCC.exe"
        if (-not (Test-Path -LiteralPath $innoCandidate -PathType Leaf)) {
            throw ("INNO_HOME does not contain ISCC.exe: `"" + $innoCandidate + "`"")
        }
        return (Resolve-Path -LiteralPath $innoCandidate).Path
    }

    $defaultCandidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $defaultCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    }
    $pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if (-not [string]::IsNullOrWhiteSpace($pf86)) {
        $defaultCandidates += (Join-Path $pf86 "Inno Setup 6\ISCC.exe")
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $defaultCandidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    }
    foreach ($candidate in $defaultCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pathCommand = Get-Command "ISCC.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pathCommand) {
        return $pathCommand.Path
    }

    throw "ISCC.exe not found. Install Inno Setup 6 or set ISCC_EXE/INNO_HOME."
}

function Test-DistExeStartup([string]$distDir) {
    $exe = (Get-ChildItem -LiteralPath $distDir -Filter *.exe -File | Select-Object -First 1).FullName
    if (-not $exe) {
        throw "Main exe not found in $distDir."
    }

    & $pythonExe validate_dist_exe.py "$exe"
    if ($LASTEXITCODE -ne 0) {
        throw "validate_dist_exe.py failed (exit=$LASTEXITCODE)."
    }
}

function Resolve-PythonExe([string]$repoRoot) {
    # The isolated build venv carries the staged JSON1 SQLite and is the only build interpreter.
    $venvPython = Join-Path $repoRoot ".venv-win7-build\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Build venv python not found: $venvPython. Run setup_win7_build.bat first."
    }
    return $venvPython
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
    if ($null -eq $chromeExe -or $chromeExe.Trim().Length -eq 0 -or -not (Test-Path -LiteralPath $chromeExe)) {
        return @()
    }

    $targetExe = (Resolve-Path -LiteralPath $chromeExe).Path.ToLowerInvariant()
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

    # Exercise non-ASCII paths and spaces in every real Windows browser smoke.
    $unicodeProbe = -join ([char[]](25490, 20135))
    $smokeRoot = Join-Path $env:TEMP ("aps chrome smoke " + $unicodeProbe + " " + [guid]::NewGuid().ToString("N"))
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
        Set-Content -LiteralPath (Join-Path $siteDir "index.html") -Value "<html><body>aps chrome smoke</body></html>" -Encoding ASCII

        $marker = (Resolve-Path -LiteralPath $profileDir).Path
        $serverArgs = '-m http.server {0} --bind 127.0.0.1 --directory "{1}"' -f $port, $siteDir
        $serverProc = Start-Process -FilePath $pythonExe -ArgumentList $serverArgs -WorkingDirectory $siteDir -PassThru -WindowStyle Hidden
        if (-not (Wait-HttpReady $url 15)) {
            throw "Local smoke HTTP server did not become ready."
        }

        # Start-Process joins arrays with spaces; quote path arguments explicitly.
        $chromeArgs = '--user-data-dir="{0}" --app="{1}" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking' -f $marker, $url
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
    if (Test-Path -LiteralPath $chromeExe -PathType Leaf) {
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

    Expand-Archive -LiteralPath $zip.FullName -DestinationPath $tmp -Force

    $found = Get-ChildItem -LiteralPath $tmp -Recurse -Filter "chrome.exe" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $found) {
        throw "chrome.exe not found inside zip: $($zip.FullName)"
    }

    $srcDir = $found.Directory.FullName
    $dstDir = Split-Path $chromeExe -Parent
    Remove-PathWithRetry $dstDir
    Copy-Item -LiteralPath $srcDir -Destination $dstDir -Recurse -Force

    if (-not (Test-Path -LiteralPath $chromeExe -PathType Leaf)) {
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

    # Robocopy reports successful copies as 1-7. Interpret its native exit code here.
    $PSNativeCommandUseErrorActionPreference = $false
    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -lt 0 -or $LASTEXITCODE -gt 7) {
        throw "robocopy chrome runtime payload failed (exit=$LASTEXITCODE)."
    }

    $payloadLocales = Join-Path $payloadDir "locales"
    Remove-PathWithRetry $payloadLocales
    New-Item -ItemType Directory -Path $payloadLocales -Force | Out-Null

    foreach ($locale in $keptLocales) {
        $localeSource = Join-Path $sourceLocales $locale
        Test-PathOrThrow $localeSource "Missing locale file: $localeSource"
        Copy-Item -Force -LiteralPath $localeSource -Destination (Join-Path $payloadLocales $locale)
    }

    Test-PathOrThrow (Join-Path $payloadDir "chrome.exe") "Trimmed chrome runtime payload is missing chrome.exe."
    $payloadBytes = (Get-ChildItem -LiteralPath $payloadDir -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Host ("Prepared trimmed Chrome runtime payload: " + $payloadDir + " (" + $payloadBytes + " bytes)")
}

function Invoke-MainPackageBuild([string]$iscc) {
    Invoke-CmdBat "build_win7_onedir.bat"
    $distDir = Resolve-DistDir
    Test-DistExeStartup $distDir
    Remove-DistRuntimeArtifacts $distDir

    & $iscc "installer\aps_win7.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7.iss (exit=$LASTEXITCODE)."
    }
}

function Invoke-PortablePackageBuild {
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome

    Invoke-CmdBat "build_win7_onedir.bat"
    $distDir = Resolve-DistDir
    $browserDir = Join-Path $distDir "tools\chrome109"
    New-Item -ItemType Directory -Path (Split-Path $browserDir -Parent) -Force | Out-Null
    New-ChromeRuntimePayload (Split-Path $chrome -Parent) $browserDir
    & $pythonExe scripts/portable_release.py prepare "$distDir"
    if ($LASTEXITCODE -ne 0) { throw "Portable payload preparation failed." }

    Test-DistExeStartup $distDir
    Invoke-ChromeRuntimeSmoke (Join-Path $browserDir "chrome.exe") "portable browser"
    # validate_dist_exe cleans its own probe. The archive rejects any subsequent user data.
    $output = "dist\APS_Portable_Win7_x64.zip"
    & $pythonExe scripts/portable_release.py archive "$distDir" "$output"
    if ($LASTEXITCODE -ne 0) { throw "Portable archive validation failed." }
    Write-Host ("DONE: " + $output)
}

function Invoke-ChromeRuntimeBuild([string]$iscc) {
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome
    $payloadDir = "build\chrome109_runtime_payload"
    New-ChromeRuntimePayload (Split-Path $chrome -Parent) $payloadDir
    Invoke-ChromeRuntimeSmoke (Join-Path $payloadDir "chrome.exe") "chrome runtime payload"
    $runtimeArg = "/DRuntimeDir=$((Resolve-Path -LiteralPath $payloadDir).Path)"

    & $iscc $runtimeArg "installer\aps_win7_chrome.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7_chrome.iss (exit=$LASTEXITCODE)."
    }
}

function Invoke-LegacyPackageBuild([string]$iscc) {
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome

    Stop-LegacyDistChromeBestEffort

    Invoke-CmdBat "build_win7_onedir.bat"
    Invoke-CmdBat "stage_chrome109_to_dist.bat"

    $distDir = Resolve-DistDir
    Invoke-ChromeRuntimeSmoke (Join-Path $distDir "tools\chrome109\chrome.exe") "legacy dist chrome runtime"
    Test-DistExeStartup $distDir
    Remove-DistRuntimeArtifacts $distDir

    & $iscc "installer\aps_win7_legacy.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed for installer\\aps_win7_legacy.iss (exit=$LASTEXITCODE)."
    }
}

try {
    if ($MainOnly -and $ChromeOnly) {
        throw "MainOnly and ChromeOnly cannot be used together."
    }

    if ($Legacy -and ($Installer -or $MainOnly -or $ChromeOnly)) {
        throw "Legacy cannot be combined with Installer, MainOnly or ChromeOnly."
    }

    $buildMain = -not $ChromeOnly
    $buildChrome = -not $MainOnly
    $repoRoot = Resolve-RepoRoot
    $pythonExe = Resolve-PythonExe $repoRoot
    $originalPath = $env:PATH
    $originalPythonHome = $env:PYTHONHOME
    Push-Location -LiteralPath $repoRoot
    try {
        $env:PATH = (Split-Path $pythonExe -Parent) + [IO.Path]::PathSeparator + $originalPath
        $env:PYTHONHOME = $null
        if (-not ($Installer -or $MainOnly -or $ChromeOnly -or $Legacy)) {
            Invoke-PortablePackageBuild
        } else {
            $iscc = Resolve-Iscc
            $outputs = New-Object System.Collections.Generic.List[string]
            if ($Legacy) {
                Invoke-LegacyPackageBuild $iscc
                $outputs.Add("installer\output\APS_Legacy_Full_Setup.exe") | Out-Null
                Write-Host ("DONE: " + ($outputs -join ", ") + "  (legacy fallback)")
                Write-Host "VALIDATED: dist exe cold start OK (isolated validate_dist_exe.py runtime)"
            } else {
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
                    Write-Host "VALIDATED: dist exe cold start OK (isolated validate_dist_exe.py runtime)"
                }
            }
        }
    } finally {
        $env:PYTHONHOME = $originalPythonHome
        $env:PATH = $originalPath
        Pop-Location
    }
    $global:LASTEXITCODE = 0
    exit 0
} catch {
    [Console]::Error.WriteLine("[package_win7] ERROR: " + $_.Exception.Message)
    $global:LASTEXITCODE = 1
    exit 1
}
