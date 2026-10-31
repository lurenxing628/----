#Requires -Version 5.1
# Shared Inno Setup compiler (ISCC.exe) resolver for Win7 packaging scripts.
# Keep this script ASCII-only for Windows PowerShell 5.1 compatibility.

$ErrorActionPreference = "Stop"

function Fail-ResolveIscc([string]$message) {
    [Console]::Error.WriteLine($message)
    $global:LASTEXITCODE = 1
    exit 1
}

if (-not [string]::IsNullOrWhiteSpace($env:ISCC_EXE)) {
    $explicitIscc = $env:ISCC_EXE.Trim()
    if (Test-Path -LiteralPath $explicitIscc -PathType Leaf) {
        Write-Output ((Resolve-Path -LiteralPath $explicitIscc).Path)
        $global:LASTEXITCODE = 0
        exit 0
    }
    Fail-ResolveIscc ("[ERROR] ISCC_EXE points to a missing file: `"" + $explicitIscc + "`"")
}

if (-not [string]::IsNullOrWhiteSpace($env:INNO_HOME)) {
    $innoHome = $env:INNO_HOME.Trim()
    $innoCandidate = Join-Path $innoHome "ISCC.exe"
    if (Test-Path -LiteralPath $innoCandidate -PathType Leaf) {
        Write-Output ((Resolve-Path -LiteralPath $innoCandidate).Path)
        $global:LASTEXITCODE = 0
        exit 0
    }
    Fail-ResolveIscc ("[ERROR] INNO_HOME does not contain ISCC.exe: `"" + $innoCandidate + "`"")
}

$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$defaultCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    $defaultCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
}
if (-not [string]::IsNullOrWhiteSpace($pf86)) {
    $defaultCandidates += (Join-Path $pf86 "Inno Setup 6\ISCC.exe")
}
if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
    $defaultCandidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
}

foreach ($candidate in $defaultCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        Write-Output ((Resolve-Path -LiteralPath $candidate).Path)
        $global:LASTEXITCODE = 0
        exit 0
    }
}

$pathCommand = Get-Command "ISCC.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pathCommand -and -not [string]::IsNullOrWhiteSpace($pathCommand.Source) -and (Test-Path -LiteralPath $pathCommand.Source -PathType Leaf)) {
    Write-Output ((Resolve-Path -LiteralPath $pathCommand.Source).Path)
    $global:LASTEXITCODE = 0
    exit 0
}

Fail-ResolveIscc "[ERROR] ISCC.exe not found. Install Inno Setup 6 or set ISCC_EXE/INNO_HOME."
