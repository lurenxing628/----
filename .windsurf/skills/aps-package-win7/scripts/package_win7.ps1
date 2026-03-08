# APS Win7 packaging pipeline:
# clean -> build onedir -> stage offline Chrome109 -> build Inno Setup installer -> cold-start validate
#
# Run:
#   powershell -ExecutionPolicy Bypass -File .cursor/skills/aps-package-win7/scripts/package_win7.ps1
#
# NOTE (Windows PowerShell 5.1):
# Keep this script ASCII-only to avoid ParserError when saved as UTF-8 without BOM.

chcp 65001 | Out-Null
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    # This script lives in: <repo>/.cursor/skills/aps-package-win7/scripts/package_win7.ps1
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
    if (Test-Path $tmp) {
        Remove-Item -Recurse -Force $tmp
    }
    New-Item -ItemType Directory -Path $tmp | Out-Null

    Expand-Archive -Path $zip.FullName -DestinationPath $tmp -Force

    $found = Get-ChildItem -Path $tmp -Recurse -Filter "chrome.exe" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $found) {
        throw "chrome.exe not found inside zip: $($zip.FullName)"
    }

    $srcDir = $found.Directory.FullName
    $dstDir = Split-Path $chromeExe -Parent
    if (Test-Path $dstDir) {
        Remove-Item -Recurse -Force $dstDir
    }
    New-Item -ItemType Directory -Path $dstDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $srcDir "*") $dstDir

    if (-not (Test-Path $chromeExe)) {
        throw "Failed to prepare offline Chrome109 at: $chromeExe"
    }

    # cleanup temp folder (best-effort)
    try {
        Remove-Item -Recurse -Force $tmp
    } catch {
    }
}

$repoRoot = Resolve-RepoRoot
Push-Location $repoRoot
try {
    # Preflight: offline Chrome109 must exist (hard dependency for stage_chrome109_to_dist.bat)
    $chrome = "tools\Chrome.109.0.5414.120.x64\chrome.exe"
    Initialize-OfflineChrome109 $chrome
    Test-PathOrThrow $chrome "Missing $chrome. Provide offline Chrome109 at tools\\Chrome.109.0.5414.120.x64\\chrome.exe or tools\\ungoogled-chromium_109*.zip"

    # APS_HOST/APS_PORT override (port 5000 may be blocked by policy on some machines)
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
    } else {
        $chosen = [int]$env:APS_PORT
    }

    # Avoid dist being locked by Chrome (Chrome writes/locks dist\...\tools\chrome109\Data\...)
    cmd /c "taskkill /IM chrome.exe /F /T >nul 2>nul" | Out-Null

    # Clean old artifacts
    if (Test-Path build) { Remove-Item build -Recurse -Force }
    if (Test-Path dist) { Remove-Item dist -Recurse -Force }

    # Build onedir + stage Chrome109 into dist
    Invoke-CmdBat "build_win7_onedir.bat"
    Invoke-CmdBat "stage_chrome109_to_dist.bat"

    # Copy launchers (use wildcard to avoid hardcoding Chinese path)
    $distDir = $null
    foreach ($d in (Get-ChildItem dist -Directory -ErrorAction SilentlyContinue)) {
        $hasExe = Get-ChildItem $d.FullName -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hasExe) {
            $distDir = $d.FullName
            break
        }
    }
    if (-not $distDir) {
        throw "dist output directory not found."
    }
    Copy-Item -Force "assets\*.bat" -Destination $distDir

    # Build installer (Inno Setup)
    $iscc = $null
    if ($env:ISCC_EXE -and (Test-Path $env:ISCC_EXE)) {
        $iscc = $env:ISCC_EXE
    } elseif ($env:INNO_HOME) {
        $candidate = Join-Path $env:INNO_HOME "ISCC.exe"
        if (Test-Path $candidate) { $iscc = $candidate }
    }

    if (-not $iscc) {
        $defaultIscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
        if (Test-Path $defaultIscc) { $iscc = $defaultIscc }
    }

    if (-not $iscc) {
        throw "ISCC.exe not found. Install Inno Setup 6 or set ISCC_EXE/INNO_HOME."
    }

    & $iscc "installer\aps_win7.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compile failed (exit=$LASTEXITCODE)"
    }

    # Cold start validation
    $exe = (Get-ChildItem $distDir -Filter *.exe | Select-Object -First 1).FullName
    if (-not $exe) {
        throw "Main exe not found in $distDir."
    }

    python validate_dist_exe.py "$exe"
    if ($LASTEXITCODE -ne 0) {
        throw "validate_dist_exe.py failed (exit=$LASTEXITCODE)."
    }

    Write-Host "DONE: installer\output\APS_Win7_Setup.exe  (APS_HOST=$($env:APS_HOST) APS_PORT=$($env:APS_PORT))"
} finally {
    Pop-Location
}
