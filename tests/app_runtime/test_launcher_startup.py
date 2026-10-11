"""Execute the shipped launcher: identity, Unicode logs and elapsed-time waits.

Windows uses its native PowerShell. Other hosts can set APS_TEST_POWERSHELL to
a development-only pwsh executable; that does not prove Win7 compatibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "assets" / "aps-launcher.ps1"


@pytest.fixture
def run_ps(tmp_path):
    executable = os.environ.get("APS_TEST_POWERSHELL") or shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        pytest.skip("PowerShell runtime is needed to execute launcher behavior")

    def run(body, **environment):
        driver = tmp_path / "launcher-test.ps1"
        # Windows PowerShell recognizes non-ASCII test data only with a BOM.
        driver.write_text("$ErrorActionPreference = 'Stop'\n"
                          "[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)\n"
                          ". $env:APS_TEST_SCRIPT\n" + body,
                          encoding="utf-8-sig")
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
            env=dict(os.environ, APS_TEST_SCRIPT=str(SCRIPT), APS_TEST_ROOT=str(tmp_path), **environment),
            capture_output=True, timeout=20,
        )
        assert result.returncode == 0, result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
        return result.stdout.decode("utf-8-sig").splitlines()

    return run


@pytest.fixture
def health_server(tmp_path):
    state = {"status": 200, "patch": {}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8-sig"))
            body = dict(app="aps", status="ok", contract_version=1, owner=contract["owner"], pid=contract["pid"],
                        db_path_hash=hashlib.sha256(contract["db_path"].encode()).hexdigest(),
                        instance_id=hashlib.sha256(contract["shutdown_token"].encode()).hexdigest())
            body.update(state["patch"])
            payload = json.dumps(body).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["contract"] = dict(contract_version=1, owner="LOCAL\\operator", pid=12345,
                             db_path=str(tmp_path / "aps.db").lower(), host="127.0.0.1", port=server.server_port,
                             shutdown_token="test-instance-only")
    yield state
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def _write_contract(tmp_path, contract):
    (tmp_path / "contract.json").write_text(json.dumps(contract), encoding="utf-8")


def test_unicode_log_and_pid_queries_stay_in_one_process(run_ps, tmp_path):
    rows = run_ps(r'''
$context = @{ log = (Join-Path $env:APS_TEST_ROOT '中文 ! launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew() }
for ($i = 0; $i -lt 21; $i++) { Write-ApsLog $context ('row=' + $i + ' 中文目录 C:\APS ! & space\profile') }
$process = [Diagnostics.Process]::GetCurrentProcess()
if ((Get-ApsLockProcessState ([string]$PID) $process.MainModule.FileName) -ne 'active') { throw 'Live PID lost' }
if ((Get-ApsLockProcessState ([string]$PID) 'unrelated.exe') -ne 'absent') { throw 'Reused PID accepted' }
if ((Get-ApsLockProcessState 'not-a-pid' 'aps.exe') -ne 'unknown') { throw 'Unknown PID treated as absent' }
'OK'
''')
    assert "OK" in rows
    log = (tmp_path / "中文 ! launcher.log").read_bytes()
    assert not log.startswith(b"\xef\xbb\xbf")
    lines = log.decode("utf-8").splitlines()
    assert len(lines) == 21
    assert all("中文目录 C:\\APS ! & space\\profile" in line for line in lines)


@pytest.mark.parametrize("status,patch,owner,expected", [
    (200, {}, "LOCAL\\operator", 0),
    (503, {"status": "recovery_required", "operations_available": False}, "LOCAL\\operator", 3),
    (503, {"status": "recovery_required", "operations_available": True}, "LOCAL\\operator", 2),
    (200, {"pid": 98765}, "LOCAL\\operator", 2),
    (200, {"instance_id": "another-instance"}, "LOCAL\\operator", 2),
    (200, {"db_path_hash": "another-database"}, "LOCAL\\operator", 2),
    (200, {}, "OTHER\\operator", 4),
])
def test_health_identity_and_readonly_recovery(run_ps, tmp_path, health_server, status, patch, owner, expected):
    health_server.update(status=status, patch=patch)
    _write_contract(tmp_path, health_server["contract"])
    rows = run_ps(r'''
$contract = Read-ApsJson ([IO.File]::ReadAllText((Join-Path $env:APS_TEST_ROOT 'contract.json')))
$context = @{ db = $contract.db_path; owner = $env:APS_TEST_OWNER }
$runtime = @{ contract = $contract; hostName = $contract.host; port = $contract.port }
'CODE=' + (Test-ApsHealth $context $runtime $null)
''', APS_TEST_OWNER=owner)
    assert "CODE=" + str(expected) in rows


def test_existing_owner_and_database_are_verified_before_reuse(run_ps, tmp_path, health_server):
    _write_contract(tmp_path, health_server["contract"])
    rows = run_ps(r'''
$contract = Read-ApsJson ([IO.File]::ReadAllText((Join-Path $env:APS_TEST_ROOT 'contract.json')))
$context = @{ db = $contract.db_path; owner = $contract.owner; exe = [IO.Path]::GetFullPath((Join-Path $env:APS_TEST_ROOT 'aps.exe')) }
$script:runtime = @{ contract = $contract; hostName = $contract.host; port = $contract.port; lockState = 'active';
    lock = @{ pid = [string]$contract.pid; owner = $contract.owner; db_path = $contract.db_path; exe_path = $context.exe } }
function Read-ApsRuntime($Context) { return $script:runtime }
if ((Get-ApsExistingState $context $null).state -ne 'ready') { throw 'Healthy reuse failed' }
$script:runtime.lock.pid = '67890'
if ((Get-ApsExistingState $context $null).reason -ne 'lock_contract_pid_mismatch') { throw 'Wrong lock PID accepted' }
$script:runtime.lock.owner = 'OTHER\operator'
if ((Get-ApsExistingState $context $null).state -ne 'other') { throw 'Other owner accepted' }
$script:runtime.lock.owner = $contract.owner
$script:runtime.lock.db_path = 'another.db'
if ((Get-ApsExistingState $context $null).reason -ne 'lock_database_unproven') { throw 'Wrong DB accepted' }
$script:runtime.lock.db_path = $contract.db_path
$script:runtime.lockState = 'unknown'
if ((Get-ApsExistingState $context $null).state -ne 'ready') { throw 'Valid health proof not reused' }
$script:runtime.contract = $null
if ((Get-ApsExistingState $context $null).state -ne 'blocked') { throw 'Unknown lock allowed a spawn' }
$script:runtime.lockState = 'absent'
if ((Get-ApsExistingState $context $null).reason -ne 'healthy_without_owner_proof') { throw 'Presence accepted as proof' }
$script:runtime.contract = $contract
$script:runtime.contract.host = '127.0.0.1/path'
$script:runtime.hostName = $script:runtime.contract.host
if ((Test-ApsHealth $context $script:runtime $null) -ne 2) { throw 'Malformed endpoint accepted' }
'OK'
''')
    assert "OK" in rows


def test_wait_counts_probe_time_and_preserves_concurrent_error(run_ps, tmp_path):
    rows = run_ps(r'''
$context = @{ log = (Join-Path $env:APS_TEST_ROOT 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
    errorFile = (Join-Path $env:APS_TEST_ROOT 'aps_launch_error.txt') }
[IO.File]::WriteAllText($context.errorFile, 'duplicate start')
$script:probes = 0
function Get-ApsExistingState($Context, $Budget) {
    $script:probes++
    if ($script:probes -eq 1) { return @{ state = 'starting' } }
    return @{ state = 'ready' }
}
if ((Wait-ApsReady $context $null 2000).state -ne 'ready') { throw 'Duplicate-start error defeated healthy owner' }
if ([IO.File]::ReadAllText($context.errorFile) -ne 'duplicate start') { throw 'Owner error was changed' }
function Get-ApsExistingState($Context, $Budget) { Start-Sleep -Milliseconds 150; return @{ state = 'absent' } }
$timer = [Diagnostics.Stopwatch]::StartNew()
if ((Wait-ApsReady $context $null 100).state -ne 'timeout') { throw 'Probe duration ignored' }
if ($timer.ElapsedMilliseconds -gt 1000) { throw 'Wait counted iterations rather than elapsed time' }
function Get-ApsExistingState($Context, $Budget) { return @{ state = 'absent' } }
if ((Wait-ApsReady $context $null 1000).state -ne 'failed') { throw 'Current launch error ignored' }
'OK'
''')
    assert "OK" in rows


@pytest.mark.parametrize("reuse", [False, True])
def test_first_launch_and_reopen_preserve_portable_paths_and_owner_files(run_ps, tmp_path, health_server, reuse):
    app = tmp_path / "便携 ! APS"
    app.mkdir()
    (app / "aps-portable.txt").write_text("portable")
    (app / "aps.exe").write_bytes(b"test application")
    chrome = app / "tools" / "chrome109" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"test browser")
    logs = app / "user-data" / "logs"
    logs.mkdir(parents=True)
    contract = dict(health_server["contract"], db_path=str(app / "user-data" / "db" / "aps.db").lower())
    _write_contract(tmp_path, contract)
    if reuse:
        _write_contract(tmp_path, contract)
        shutil.copyfile(str(tmp_path / "contract.json"), str(logs / "aps_runtime.json"))
    error = logs / "aps_launch_error.txt"
    error.write_text("historical failure", encoding="utf-8")
    rows = run_ps(r'''
$script:spawned = @()
$script:browserArguments = ''
function Start-ApsProcess([string]$Executable, [string]$Arguments, [string]$Directory) {
    $script:spawned += $Executable
    if ([IO.Path]::GetFileName($Executable) -eq 'aps.exe') {
        [IO.File]::Copy((Join-Path $env:APS_TEST_ROOT 'contract.json'), (Join-Path $env:APS_LOG_DIR 'aps_runtime.json'))
        [IO.File]::WriteAllText((Join-Path $env:APS_LOG_DIR 'aps_launch_error.txt'), 'concurrent duplicate start')
    } else { $script:browserArguments = $Arguments }
}
function Start-Sleep([int]$Milliseconds) { }
$launchClock = [Diagnostics.Stopwatch]::StartNew()
$launchStarted = [DateTime]::UtcNow
[Threading.Thread]::Sleep(25)
$code = Invoke-ApsLauncher $env:APS_TEST_APP $launchClock $launchStarted
'CODE=' + $code
'SPAWNS=' + $script:spawned.Count
$profile = Join-Path $env:APS_TEST_APP 'user-data\chrome109_profile'
if (-not $script:browserArguments.Contains('--user-data-dir="' + $profile + '"')) { throw 'Browser profile argument changed' }
if ($env:APS_DB_PATH -ne (Join-Path $env:APS_TEST_APP 'user-data\db\aps.db')) { throw 'Portable DB override was not applied' }
''', APS_TEST_APP=str(app), USERNAME="operator", USERDOMAIN="LOCAL", APS_DB_PATH="must-not-use.db",
        APS_START_CMD_LOCAL_TIME="test CMD local timestamp")
    assert "CODE=0" in rows
    assert "SPAWNS=" + str(1 if reuse else 2) in rows
    assert error.read_text() == ("historical failure" if reuse else "concurrent duplicate start")
    log = (logs / "launcher.log").read_text(encoding="utf-8")
    assert "便携 ! APS" in log and "launcher_complete" in log
    assert 'cmd_started_local="test CMD local timestamp"' in log
    assert 'ps_started_utc="' in log and "ps_pid=" in log
    assert int(re.search(r"launcher_invoked_ms=(\d+)", log).group(1)) >= 25
    elapsed = [int(value) for value in re.findall(r"elapsed_ms=(\d+)", log)]
    assert elapsed == sorted(elapsed)
    phases = ["launcher_begin", "chrome_find_begin", "chrome_find_ms=", "chrome_profile_begin",
              "profile_ms=", "existing_probe_begin", "probe_ms="]
    if not reuse:
        phases.extend(["app_start_required=1", "app_spawned spawn_ms=", "wait_begin", "wait_ms="])
    phases.extend(["health_ready", "chrome_cmd=", "chrome_started spawn_ms=", "launcher_complete"])
    assert [log.index(phase) for phase in phases] == sorted(log.index(phase) for phase in phases)
    assert all(int(value) >= 0 for value in re.findall(r"(?:context|chrome_find|profile|probe|spawn|wait)_ms=(\d+)", log))


@pytest.mark.skipif(os.name != "nt", reason="Native Windows direct process creation")
def test_direct_process_preserves_unicode_arguments_working_directory_and_environment(run_ps, tmp_path):
    directory = tmp_path / "中文 ! & APS"
    directory.mkdir()
    child = directory / "child.ps1"
    child.write_text(
        "param([string]$Received)\n"
        "$rows = @([IO.Directory]::GetCurrentDirectory(), $Received, $env:APS_CHILD_SENTINEL)\n"
        "[IO.File]::WriteAllLines($env:APS_CHILD_RESULT, [string[]]$rows, (New-Object Text.UTF8Encoding($false)))\n",
        encoding="utf-8-sig",
    )
    output = directory / "result.txt"
    rows = run_ps(r'''
$executable = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
$arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $env:APS_CHILD_SCRIPT + '" "你好 ! & space"'
Start-ApsProcess $executable $arguments $env:APS_CHILD_DIRECTORY
$timer = [Diagnostics.Stopwatch]::StartNew()
while (-not [IO.File]::Exists($env:APS_CHILD_RESULT) -and $timer.ElapsedMilliseconds -lt 5000) {
    Start-Sleep -Milliseconds 50
}
if (-not [IO.File]::Exists($env:APS_CHILD_RESULT)) { throw 'Direct child process did not finish' }
'OK'
''', APS_CHILD_SCRIPT=str(child), APS_CHILD_DIRECTORY=str(directory), APS_CHILD_RESULT=str(output),
        APS_CHILD_SENTINEL="inherited APS environment")
    assert "OK" in rows
    assert output.read_text(encoding="utf-8").splitlines() == [str(directory), "你好 ! & space", "inherited APS environment"]


@pytest.mark.skipif(os.name != "nt", reason="Native CMD quoting and Windows PowerShell entry")
@pytest.mark.parametrize("entry_source,companion_name", [
    (ROOT / "assets" / "启动_排产系统_Chrome.bat", "aps-launcher.ps1"),
    (ROOT / "packaging" / "win7" / "Start.cmd", "Start.ps1"),
])
def test_cmd_entry_preserves_unicode_bang_path_without_path_search(tmp_path, entry_source, companion_name):
    app = tmp_path / "中文 ! APS"
    app.mkdir()
    entry = app / "Start.cmd"
    shutil.copyfile(str(entry_source), str(entry))
    (app / companion_name).write_text(
        "param([string]$Mode)\n"
        "[IO.File]::WriteAllText((Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'called.txt'), 'once')\nexit 0\n",
        encoding="ascii",
    )
    cmd = str(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe")
    result = subprocess.run([cmd, "/d", "/v:on", "/c", str(entry)],
                            env=dict(os.environ, PATH=str(app / "unavailable PATH")), capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (app / "called.txt").read_text() == "once"


def test_native_entry_uses_single_powershell_and_payload_requires_companion(tmp_path):
    """The launcher must be deployable together with its new required script."""
    from scripts.portable_release import REQUIRED_FILES, payload_files

    entry = (ROOT / "assets" / "启动_排产系统_Chrome.bat").read_bytes()
    assert b"DisableDelayedExpansion" in entry and b"\r\n" in entry
    assert entry.lower().count(b'powershell.exe" -noprofile') == 1
    assert SCRIPT.read_bytes().isascii()
    for relative in REQUIRED_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"payload")
    (tmp_path / "aps-launcher.ps1").unlink()
    with pytest.raises(ValueError, match="aps-launcher.ps1"):
        payload_files(tmp_path)
    shutil.copyfile(str(SCRIPT), str(tmp_path / "aps-launcher.ps1"))
    assert tmp_path / "aps-launcher.ps1" in payload_files(tmp_path)
