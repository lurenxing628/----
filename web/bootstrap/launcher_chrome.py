from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .launcher_observability import launcher_log_warning


@dataclass(frozen=True)
class _StopChromeResult:
    ok: bool
    status: str
    profile_dir: str
    pids: List[int]
    remaining_pids: List[int]
    failed_pids: List[int]
    reason: str = ""


def _chrome_pid_query_script(profile_dir: str) -> str:
    marker = os.path.abspath(str(profile_dir or "").strip()).replace("'", "''").lower()
    return (
        "$ErrorActionPreference='Stop';"
        f"$marker='{marker}';"
        "$items = $null;"
        "if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {"
        "  try { $items = @(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) }"
        "  catch { $items = $null }"
        "}"
        "if ($null -eq $items -and (Get-Command Get-WmiObject -ErrorAction SilentlyContinue)) {"
        "  try { $items = @(Get-WmiObject Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction Stop) }"
        "  catch { exit 1 }"
        "}"
        "if ($null -eq $items) { exit 1 }"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "$prefix='--user-data-dir=';"
        "function Split-CommandLineArgs([string]$cmd) {"
        "  $tokens = @();"
        "  if ($null -eq $cmd -or $cmd.Trim().Length -eq 0) { return $tokens };"
        "  $buf = New-Object System.Text.StringBuilder;"
        "  $inQuotes = $false;"
        "  for ($i = 0; $i -lt $cmd.Length; $i++) {"
        "    $ch = $cmd[$i];"
        "    if ($ch -eq [char]34) {"
        "      $slashCount = 0;"
        "      $j = $i - 1;"
        "      while ($j -ge 0 -and $cmd[$j] -eq [char]92) { $slashCount++; $j-- };"
        "      if (($slashCount % 2) -eq 0) { $inQuotes = -not $inQuotes; continue }"
        "    };"
        "    if (-not $inQuotes -and [char]::IsWhiteSpace($ch)) {"
        "      if ($buf.Length -gt 0) { $tokens += $buf.ToString(); $null = $buf.Remove(0, $buf.Length) };"
        "      continue"
        "    };"
        "    [void]$buf.Append($ch)"
        "  };"
        "  if ($buf.Length -gt 0) { $tokens += $buf.ToString() };"
        "  return $tokens"
        "}"
        "function Test-ApsChromeCommandLine([string]$cmd) {"
        "  foreach ($arg in @(Split-CommandLineArgs $cmd)) {"
        "    $argLower = $arg.ToLowerInvariant();"
        "    if ($argLower.StartsWith($prefix)) {"
        "      if ($argLower.Substring($prefix.Length) -eq $marker) { return $true }"
        "    }"
        "  };"
        "  return $false"
        "}"
        "foreach ($item in $items) {"
        "  $cmd = [string]$item.CommandLine;"
        "  if (Test-ApsChromeCommandLine $cmd) {"
        "    Write-Output ([string][int]$item.ProcessId)"
        "  }"
        "}"
        "exit 0"
    )


def _parse_chrome_pid_output(output: str) -> List[int]:
    pids: List[int] = []
    for line in str(output or "").splitlines():
        value = str(line or "").strip()
        if not value:
            continue
        if value.startswith("ProcessId="):
            value = value.split("=", 1)[1].strip()
        if value.isdigit():
            pid_i = int(value)
            if pid_i > 0 and pid_i not in pids:
                pids.append(pid_i)
    return pids


def _list_aps_chrome_pids(
    profile_dir: str,
    *,
    run_powershell_text: Callable[[str, float], Tuple[Optional[int], str]],
) -> Optional[List[int]]:
    target_profile = os.path.abspath(str(profile_dir or "").strip()) if str(profile_dir or "").strip() else ""
    if os.name != "nt":
        return []
    if not target_profile:
        return []
    rc, output = run_powershell_text(_chrome_pid_query_script(target_profile), 8.0)
    if rc is None or rc != 0:
        return None
    return _parse_chrome_pid_output(output)


def _stop_aps_chrome_with_result(
    profile_dir: Optional[str],
    *,
    list_pids: Callable[[str], Optional[List[int]]],
    kill_pid: Callable[[int], bool],
) -> _StopChromeResult:
    target_profile = str(profile_dir or "").strip()
    if not target_profile:
        return _StopChromeResult(True, "profile_missing", target_profile, [], [], [])
    pids = list_pids(target_profile)
    if pids is None:
        return _StopChromeResult(False, "process_list_unavailable", target_profile, [], [], [], "list_failed")
    failed_pids = [int(pid) for pid in pids if not kill_pid(pid)]
    remaining_pids = list_pids(target_profile)
    if remaining_pids is None:
        return _StopChromeResult(False, "final_recheck_unavailable", target_profile, list(pids), [], failed_pids, "recheck_failed")
    if remaining_pids:
        return _StopChromeResult(False, "profile_processes_still_running", target_profile, list(pids), list(remaining_pids), failed_pids)
    return _StopChromeResult(True, "stopped", target_profile, list(pids), [], failed_pids)


def _log_chrome_stop_failure(result: _StopChromeResult, *, logger: Optional[logging.Logger], state_dir: str = "") -> None:
    message = (
        f"chrome_stop_failed status={result.status} profile={result.profile_dir} "
        f"pids={result.pids} failed_pids={result.failed_pids} remaining_pids={result.remaining_pids}"
    )
    launcher_log_warning(logger, message, state_dir=state_dir)
