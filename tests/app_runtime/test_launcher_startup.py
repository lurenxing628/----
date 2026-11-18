"""Execute the shipped launcher: identity, Unicode logs and elapsed-time waits.

Windows uses its native PowerShell. Other hosts can set APS_TEST_POWERSHELL to
a development-only pwsh executable; that does not prove Win7 compatibility.
"""
from __future__ import annotations

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
    import sys

    from flask import Flask
    from werkzeug.test import Client
    from werkzeug.wrappers import Response

    from web.bootstrap.entrypoint import _default_deps, configure_runtime_contract
    from web.bootstrap.launcher_contracts import read_runtime_contract_result
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.launcher_shutdown import RuntimeHostStopTransport
    from web.routes.workbench.system_runtime import health

    app = Flask("launcher-runtime-contract")
    app.config.update(LOG_DIR=str(tmp_path / "logs"), BACKUP_DIR=str(tmp_path / "backups"),
                      EXCEL_TEMPLATE_DIR=str(tmp_path / "templates"))
    app.add_url_rule("/system/health", view_func=health)
    client = Client(RuntimeHostStopTransport(app), Response)
    state = {"status": 200, "patch": {}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            app.extensions["workbench_system_restore_recovery"] = state["status"] == 503
            response = client.get("/system/health")
            body = response.get_json()
            body.update(state["patch"])
            payload = json.dumps(body).encode()
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def configure(database_path):
        app.config["DATABASE_PATH"] = str(database_path)
        previous = state.get("lock")
        if previous is not None:
            assert release_runtime_lock(str(tmp_path), expected_payload=previous)
        state["lock"] = acquire_runtime_lock(str(tmp_path), owner="LOCAL\\operator", exe_path=sys.executable,
                                             db_path=str(database_path))
        configure_runtime_contract(app, str(tmp_path), "127.0.0.1", server.server_port, "LOCAL\\operator",
                                   deps=_default_deps(), runtime_lock=state["lock"])
        result = read_runtime_contract_result(str(tmp_path))
        assert result.ok
        state["contract"] = result.payload
        state["contract_path"] = Path(result.path)
        return result.payload

    state.update(app=app, client=client, configure=configure)
    configure(tmp_path / "aps.db")
    yield state
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    assert release_runtime_lock(str(tmp_path), expected_payload=state["lock"])


def _write_contract(tmp_path, contract):
    (tmp_path / "contract.json").write_text(json.dumps(contract), encoding="utf-8")


def test_runtime_contract_producer_and_health_share_instance_identity(health_server):
    from web.bootstrap.launcher_contracts import read_runtime_contract_result
    from web.bootstrap.launcher_health import probe_runtime_health_result
    from web.runtime_host import normalize_runtime_db_path, runtime_identity

    app, client, contract = health_server["app"], health_server["client"], health_server["contract"]
    response = client.get("/system/health")
    assert response.status_code == 200
    body = response.get_json()
    probed = probe_runtime_health_result(f"http://127.0.0.1:{contract['port']}", timeout_s=0.75)
    assert probed.ok and probed.status == 200
    assert probed.payload is not None
    for key in ("owner", "pid", "db_path", "instance_id"):
        assert body[key] == contract[key]
        assert probed.payload[key] == contract[key]
    assert body["db_path"] == normalize_runtime_db_path(app.config["DATABASE_PATH"])
    assert not {"db_path_hash", "shutdown_token"}.intersection(body)
    assert contract["shutdown_token"] not in response.get_data(as_text=True)
    app.extensions["workbench_system_restore_recovery"] = True
    recovery = client.get("/system/health")
    assert recovery.status_code == 503 and recovery.get_json()["operations_available"] is False
    assert recovery.get_json()["instance_id"] == contract["instance_id"] == runtime_identity(app)["instance_id"]
    assert not {"db_path_hash", "shutdown_token"}.intersection(recovery.get_json())
    legacy = dict(contract)
    del legacy["instance_id"]
    health_server["contract_path"].write_text(json.dumps(legacy), encoding="utf-8")
    result = read_runtime_contract_result(app.config["APS_RUNTIME_DIR"])
    assert result.status == "invalid" and result.reason == "missing_instance_id" and result.payload is None


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
    (200, {"db_path": "another-database"}, "LOCAL\\operator", 2),
    (200, {}, "OTHER\\operator", 4),
])
def test_health_identity_and_readonly_recovery(run_ps, tmp_path, health_server, status, patch, owner, expected):
    if "pid" in patch:
        patch = dict(patch, pid=os.getpid() + 1)
    health_server.update(status=status, patch=patch)
    _write_contract(tmp_path, health_server["contract"])
    rows = run_ps(r'''
$contract = Read-ApsJson ([IO.File]::ReadAllText((Join-Path $env:APS_TEST_ROOT 'contract.json')))
$context = @{ db = $contract.db_path; owner = $env:APS_TEST_OWNER }
$runtime = @{ contract = $contract; hostName = $contract.host; port = $contract.port }
'CODE=' + (Test-ApsHealth $context $runtime $null)
if ($env:APS_TEST_EXPECTED -eq '0') {
    $contract.instance_id = ''
    if ((Test-ApsHealth $context $runtime $null) -ne 2) { throw 'Missing instance identity accepted' }
}
''', APS_TEST_OWNER=owner, APS_TEST_EXPECTED=str(expected))
    assert "CODE=" + str(expected) in rows


def test_existing_owner_and_database_are_verified_before_reuse(run_ps, tmp_path, health_server):
    _write_contract(tmp_path, health_server["contract"])
    rows = run_ps(r'''
$contract = Read-ApsJson ([IO.File]::ReadAllText((Join-Path $env:APS_TEST_ROOT 'contract.json')))
$context = @{ db = $contract.db_path; owner = $contract.owner; exe = [IO.Path]::GetFullPath((Join-Path $env:APS_TEST_ROOT 'aps.exe')) }
$script:runtime = @{ contract = $contract; hostName = $contract.host; port = $contract.port; lockState = 'active';
    lock = @{ pid = [string]$contract.pid; owner = $contract.owner; db_path = $contract.db_path; exe_path = $context.exe } }
# The real parser trims a padded owner and leaves a blank DB field incomplete, never another account or a crash.
$lockDir = Join-Path $env:APS_TEST_ROOT 'lock-parse'
[void][IO.Directory]::CreateDirectory($lockDir)
$lockFiles = @{ lock = (Join-Path $lockDir 'aps_runtime.lock'); contract = (Join-Path $lockDir 'aps_runtime.json');
    hostFile = (Join-Path $lockDir 'aps_host.txt'); portFile = (Join-Path $lockDir 'aps_port.txt');
    log = (Join-Path $lockDir 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
    db = $context.db; owner = $context.owner; exe = $context.exe }
$self = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
[IO.File]::WriteAllText($lockFiles.lock, ('pid=' + $PID + "`r`nowner=  " + $contract.owner + "  `r`ndb_path=   `r`nexe_path=" + $self + "`r`n"))
$parsed = Read-ApsRuntime $lockFiles
if ($parsed.lockState -ne 'active') { throw 'Live lock owner was not recognized' }
$state = Test-ApsActiveLock $context $parsed
if ($state.state + ':' + $state.reason -ne 'uncertain:lock_fields_incomplete') { throw ('Blank lock field judged as ' + $state.state + ':' + $state.reason) }
# A live PID whose lock names an unreadable executable stays unknown: no active verdict, no crash.
[IO.File]::WriteAllText($lockFiles.lock, ('pid=' + $PID + "`r`nowner=" + $contract.owner + "`r`ndb_path=" + $contract.db_path +
    "`r`n" + 'exe_path=bad' + [char]0 + 'aps.exe' + "`r`n"))
$state = Get-ApsExistingState $lockFiles $null
if ($state.state + ':' + $state.reason -ne 'uncertain:lock_query_unknown') { throw ('Unreadable live lock executable judged as ' + $state.state + ':' + $state.reason) }
function Read-ApsRuntime($Context) { return $script:runtime }
if ((Get-ApsExistingState $context $null).state -ne 'ready') { throw 'Healthy reuse failed' }
$script:runtime.lock.pid = '67890'
if ((Get-ApsExistingState $context $null).reason -ne 'lock_contract_pid_mismatch') { throw 'Wrong lock PID accepted' }
$script:runtime.lock.owner = 'OTHER\operator'
if ((Get-ApsExistingState $context $null).state -ne 'other') { throw 'Other owner accepted' }
$script:runtime.lock.owner = $contract.owner
$script:runtime.lock.db_path = 'another.db'
if ((Get-ApsExistingState $context $null).reason -ne 'lock_database_unproven') { throw 'Wrong DB accepted' }
$script:runtime.lock.db_path = ''
if ((Get-ApsExistingState $context $null).reason -ne 'lock_fields_incomplete') { throw 'Half-written lock judged as another DB' }
$script:runtime.lock.db_path = 'bad' + [char]0 + 'path.db'
$state = Get-ApsExistingState $context $null
if ($state.state + ':' + $state.reason -ne 'blocked:lock_database_unproven') { throw 'Unreadable lock DB path was not blocked' }
$script:runtime.lock.db_path = $contract.db_path
$script:runtime.lock.exe_path = [IO.Path]::GetFullPath((Join-Path $env:APS_TEST_ROOT 'other-aps.exe'))
$state = Get-ApsExistingState $context $null
if ($state.state + ':' + $state.reason -ne 'blocked:lock_executable_unproven') { throw 'Another lock executable was not blocked' }
$script:runtime.lock.exe_path = $context.exe
$script:runtime.lockState = 'unknown'
if ((Get-ApsExistingState $context $null).state -ne 'ready') { throw 'Valid health proof not reused' }
$script:runtime.contract = $null
if ((Get-ApsExistingState $context $null).state -ne 'uncertain') { throw 'Unknown lock allowed a spawn' }
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
$script:probes = 0
if ((Wait-ApsReady $context $null).state -ne 'ready') { throw 'Two-argument wait lost its default deadline' }
function Get-ApsExistingState($Context, $Budget) { Start-Sleep -Milliseconds 150; return @{ state = 'starting' } }
$timer = [Diagnostics.Stopwatch]::StartNew()
if ((Wait-ApsReady $context $null 100).state -ne 'timeout') { throw 'Probe duration ignored' }
if ($timer.ElapsedMilliseconds -ge 1000) { throw 'Wait counted iterations rather than elapsed time' }
# A final verdict sampled by a probe that crossed the deadline is still reported, never as timeout.
$child = @{ HasExited = $true; ExitCode = 14 }
function Get-ApsExistingState($Context, $Budget) {
    Start-Sleep -Milliseconds 80
    return @{ state = 'uncertain'; reason = 'healthy_without_owner_proof' }
}
$state = Wait-ApsReady $context ([IO.File]::GetLastWriteTimeUtc($context.errorFile)) 50 $child
if ($state.state + ':' + $state.reason -ne 'failed:app_process_exited_14') { throw ('Exit 14 across the deadline judged as ' + $state.state + ':' + $state.reason) }
function Get-ApsExistingState($Context, $Budget) { return @{ state = 'absent' } }
if ((Wait-ApsReady $context $null 1000).state -ne 'failed') { throw 'Current launch error ignored' }
'OK'
''')
    assert "OK" in rows


def _unused_local_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_restart_over_old_contract_reaches_new_instance_with_one_get_per_round(run_ps, tmp_path, health_server):
    """Win7 实测时序：旧快照（无活跃锁 + 旧契约）遇上新后台的健康响应。

    端口未监听时一轮只发一次 GET；新后台在 GET 途中发布锁和契约时，同一份响应对照刷新后的快照判定 ready，
    不再停在 healthy_without_owner_proof，也不追加第二次 GET。
    """
    fresh = health_server["contract"]
    _write_contract(tmp_path, fresh)
    old = dict(fresh, pid=fresh["pid"] + 1, instance_id="instance-before-restart")
    (tmp_path / "old-closed.json").write_text(json.dumps(dict(old, port=_unused_local_port())), encoding="utf-8")
    (tmp_path / "old-live.json").write_text(json.dumps(old), encoding="utf-8")
    (tmp_path / "launcher-logs").mkdir()
    rows = run_ps(r'''
$logs = Join-Path $env:APS_TEST_ROOT 'launcher-logs'
$fresh = Read-ApsJson ([IO.File]::ReadAllText((Join-Path $env:APS_TEST_ROOT 'contract.json')))
$appExe = [Diagnostics.Process]::GetProcessById([int]$fresh.pid).MainModule.FileName
$context = @{ db = $fresh.db_path; owner = $fresh.owner; exe = $appExe;
    log = (Join-Path $logs 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
    lock = (Join-Path $logs 'aps_runtime.lock'); contract = (Join-Path $logs 'aps_runtime.json');
    hostFile = (Join-Path $logs 'aps_host.txt'); portFile = (Join-Path $logs 'aps_port.txt');
    errorFile = (Join-Path $logs 'aps_launch_error.txt') }
function Set-TestFile([string]$Path, [string]$Text) { [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false))) }
function Copy-TestContract([string]$Name) { [IO.File]::Copy((Join-Path $env:APS_TEST_ROOT $Name), $context.contract, $true) }
$script:realReadHealth = ${function:Read-ApsHealth}
$script:healthReads = 0
$script:publishDuringGet = $false
function Read-ApsHealth($Runtime, $Budget) {
    $script:healthReads++
    if ($script:publishDuringGet) {
        $script:publishDuringGet = $false
        Set-TestFile $context.lock ((('pid=' + $fresh.pid), ('owner=' + $fresh.owner), ('db_path=' + $context.db),
            ('exe_path=' + $context.exe)) -join "`n")
        Copy-TestContract 'contract.json'
    }
    return (& $script:realReadHealth $Runtime $Budget)
}
$script:realExistingState = ${function:Get-ApsExistingState}
$script:rounds = 0
function Get-ApsExistingState($Context, $Budget) { $script:rounds++; return (& $script:realExistingState $Context $Budget) }

Copy-TestContract 'old-closed.json'
$closed = Read-ApsJson ([IO.File]::ReadAllText($context.contract))
Set-TestFile $context.hostFile $closed.host
Set-TestFile $context.portFile ([string]$closed.port)
$state = Get-ApsExistingState $context $null
'CLOSED=' + $state.state + ':' + $state.reason + ' reads=' + $script:healthReads

Copy-TestContract 'old-live.json'
Set-TestFile $context.portFile ([string]$fresh.port)
$script:healthReads = 0
$script:rounds = 0
$script:publishDuringGet = $true
$state = Wait-ApsReady $context $null 5000
'RESTART=' + $state.state + ':' + $state.port + ' rounds=' + $script:rounds + ' reads=' + $script:healthReads
# A writer still holding the newly published lock must not prevent the launcher from reading it on Windows.
$writer = [IO.File]::Open($context.lock, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
try {
    $context.exe = Join-Path $env:APS_TEST_ROOT 'different-app.exe'
    $state = Get-ApsExistingState $context $null
    'WRONG_EXE=' + $state.state + ':' + $state.reason
} finally { $writer.Dispose() }
''')
    assert "CLOSED=absent:no_active_instance reads=1" in rows
    assert f"RESTART=ready:{fresh['port']} rounds=1 reads=1" in rows
    assert "WRONG_EXE=blocked:lock_executable_unproven" in rows
    log = (tmp_path / "launcher-logs" / "launcher.log").read_text(encoding="utf-8")
    assert "readiness=ready:" in log and "healthy_without_owner_proof" not in log


def test_wait_polls_through_publication_races_until_ready(run_ps, tmp_path):
    """就绪等待：uncertain 与 starting 只记日志继续轮询，并发败选者的错误文件不提前判失败。"""
    races = ["uncertain:healthy_without_owner_proof", "uncertain:lock_query_unknown",
             "starting:lock_active_health_identity_failed", "starting:lock_contract_pid_mismatch",
             "uncertain:lock_owner_missing", "uncertain:lock_fields_incomplete"]
    rows = run_ps(r'''
$context = @{ log = (Join-Path $env:APS_TEST_ROOT 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
    errorFile = (Join-Path $env:APS_TEST_ROOT 'aps_launch_error.txt') }
[IO.File]::WriteAllText($context.errorFile, 'concurrent duplicate start')
$script:sequence = @($env:APS_TEST_RACES.Split(',')) + 'ready:'
$script:probes = 0
function Get-ApsExistingState($Context, $Budget) {
    $parts = $script:sequence[$script:probes].Split(':')
    $script:probes++
    return @{ state = $parts[0]; reason = $parts[1] }
}
function Start-Sleep([int]$Milliseconds) { }
$state = Wait-ApsReady $context $null 5000
'STATE=' + $state.state + ' probes=' + $script:probes
''', APS_TEST_RACES=",".join(races))
    assert f"STATE=ready probes={len(races) + 1}" in rows
    log = (tmp_path / "launcher.log").read_text(encoding="utf-8")
    assert re.findall(r"readiness=(\S+)", log) == races + ["ready:"]


def test_wait_stops_on_final_states_and_judges_spawned_child_by_exit_code(run_ps, tmp_path):
    """异账户、异库与异程序锁立即返回；真实子进程退出码 13（锁竞争败选）在 starting/uncertain 下继续等胜者，
    其他退出码（14 启动失败）只在 starting 下继续等，absent/uncertain 下立即失败。"""
    rows = run_ps(r'''
$context = @{ log = (Join-Path $env:APS_TEST_ROOT 'launcher.log'); clock = [Diagnostics.Stopwatch]::StartNew();
    errorFile = (Join-Path $env:APS_TEST_ROOT 'aps_launch_error.txt') }
$shell = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
function Start-ExitedChild([int]$Code) {
    $child = $null
    $output = Start-ApsProcess $shell ('-NoProfile -NonInteractive -Command "exit ' + $Code + '"') $env:APS_TEST_ROOT ([ref]$child)
    if ($null -ne $output) { throw 'Start-ApsProcess wrote to the pipeline' }
    if (-not $child.WaitForExit(15000)) { throw 'Test child did not exit' }
    return $child
}
$output = Start-ApsProcess $shell '-NoProfile -NonInteractive -Command "exit 0"' $env:APS_TEST_ROOT
if ($null -ne $output) { throw 'Start-ApsProcess without a handle wrote to the pipeline' }
$script:states = @()
$script:probes = 0
function Get-ApsExistingState($Context, $Budget) {
    $parts = $script:states[[Math]::Min($script:probes, $script:states.Count - 1)].Split(':')
    $script:probes++
    return @{ state = $parts[0]; reason = $parts[1] }
}
function Start-Sleep([int]$Milliseconds) { }
function Show-Wait([string]$Name, [string]$States, $IgnoredErrorTime, $Child) {
    $script:states = $States.Split(',')
    $script:probes = 0
    $state = Wait-ApsReady $context $IgnoredErrorTime 5000 $Child
    $Name + '=' + $state.state + ':' + $state.reason + '@' + $script:probes
}
Show-Wait 'OTHER' 'other:lock_owner_mismatch,ready:' $null $null
Show-Wait 'DATABASE' 'blocked:lock_database_unproven,ready:' $null $null
Show-Wait 'EXECUTABLE' 'blocked:lock_executable_unproven,ready:' $null $null
$lost = Start-ExitedChild 13
$lockFailed = Start-ExitedChild 12
$failed = Start-ExitedChild 14
$beforeError = [IO.File]::GetLastWriteTimeUtc($context.errorFile)
[IO.File]::WriteAllText($context.errorFile, 'runtime lock is held by another instance')
Show-Wait 'LOST13' 'starting:lock_active_health_pending,starting:lock_contract_pid_mismatch,ready:' $beforeError $lost
Show-Wait 'UNCERTAIN13' 'uncertain:lock_query_unknown,uncertain:healthy_without_owner_proof,ready:' $beforeError $lost
Show-Wait 'GONE13' 'absent:no_active_instance' $beforeError $lost
Show-Wait 'LOCK12' 'absent:no_active_instance' $beforeError $lockFailed
Show-Wait 'FAILED14' 'absent:no_active_instance,ready:' $beforeError $failed
Show-Wait 'EXITED14' 'absent:no_active_instance,ready:' ([IO.File]::GetLastWriteTimeUtc($context.errorFile)) $failed
Show-Wait 'UNCERTAIN14' 'uncertain:lock_query_unknown,ready:' $beforeError $failed
Show-Wait 'WINNER14' 'starting:lock_active_health_pending,starting:lock_contract_pid_mismatch,ready:' $beforeError $failed
Show-Wait 'RUNNING' 'absent:no_active_instance,absent:no_active_instance,ready:' $beforeError ([Diagnostics.Process]::GetCurrentProcess())
$lost.Dispose()
$lockFailed.Dispose()
$failed.Dispose()
''')
    assert {row.split("=", 1)[0]: row.split("=", 1)[1] for row in rows if "=" in row} == {
        "OTHER": "other:lock_owner_mismatch@1",
        "DATABASE": "blocked:lock_database_unproven@1",
        "EXECUTABLE": "blocked:lock_executable_unproven@1",
        "LOST13": "ready:@3",
        "UNCERTAIN13": "ready:@3",
        "GONE13": "failed:reusable_owner_no_longer_present@1",
        "LOCK12": "failed:lock_acquisition_failed@1",
        "FAILED14": "failed:see_utf8_launch_error_file@1",
        "EXITED14": "failed:app_process_exited_14@1",
        "UNCERTAIN14": "failed:see_utf8_launch_error_file@1",
        "WINNER14": "ready:@3",
        "RUNNING": "ready:@3",
    }


@pytest.mark.parametrize("reuse", [False, True, "publishing"])
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
    contract = health_server["configure"](app / "user-data" / "db" / "aps.db")
    _write_contract(tmp_path, contract)
    if reuse == "publishing":
        (logs / "aps_runtime.json").write_text(json.dumps(dict(contract, instance_id="old-instance")), encoding="utf-8")
        (logs / "aps_runtime.lock").write_text(
            f"pid={contract['pid']}\nowner={contract['owner']}\ndb_path={contract['db_path']}\nexe_path={app / 'aps.exe'}\n",
            encoding="utf-8",
        )
    elif reuse:
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
if ($env:APS_TEST_PUBLISHING) {
    # The HTTP fixture stands in for the frozen process, whose executable is empty in this test.
    function Get-ApsLockProcessState($ProcessId, $Executable) { return 'active' }
}
function Start-Sleep([int]$Milliseconds) {
    if ($env:APS_TEST_PUBLISHING) {
        [IO.File]::Copy((Join-Path $env:APS_TEST_ROOT 'contract.json'), (Join-Path $env:APS_LOG_DIR 'aps_runtime.json'), $true)
    }
}
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
        APS_START_CMD_LOCAL_TIME="test CMD local timestamp", APS_TEST_PUBLISHING="1" if reuse == "publishing" else "")
    assert "CODE=0" in rows
    assert "SPAWNS=" + str(1 if reuse else 2) in rows
    assert error.read_text() == ("historical failure" if reuse else "concurrent duplicate start")
    log = (logs / "launcher.log").read_text(encoding="utf-8")
    assert "便携 ! APS" in log and "launcher_complete" in log
    if reuse == "publishing":
        assert "existing_instance=starting:lock_active_health_identity_failed" in log
        assert "app_start_required=1" not in log
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


def test_static_probe_of_healthy_instance_without_owner_proof_stops_with_exit_9(run_ps, tmp_path, health_server):
    """启动前探测：无活跃锁、旧契约对不上健康身份时归为 uncertain，不拉起后台、不开浏览器，退出码 9。"""
    app = tmp_path / "APS"
    app.mkdir()
    (app / "aps-portable.txt").write_text("portable")
    (app / "aps.exe").write_bytes(b"test application")
    chrome = app / "tools" / "chrome109" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"test browser")
    logs = app / "user-data" / "logs"
    logs.mkdir(parents=True)
    contract = health_server["configure"](app / "user-data" / "db" / "aps.db")
    (logs / "aps_runtime.json").write_text(json.dumps(dict(contract, instance_id="old-instance")), encoding="utf-8")
    rows = run_ps(r'''
$script:spawned = 0
function Start-ApsProcess([string]$Executable, [string]$Arguments, [string]$Directory) { $script:spawned++ }
'CODE=' + (Invoke-ApsLauncher $env:APS_TEST_APP)
'SPAWNS=' + $script:spawned
''', APS_TEST_APP=str(app), USERNAME="operator", USERDOMAIN="LOCAL")
    assert "CODE=9" in rows and "SPAWNS=0" in rows
    log = (logs / "launcher.log").read_text(encoding="utf-8")
    assert "existing_instance=uncertain:healthy_without_owner_proof" in log
    assert "app_start_required=1" not in log


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


def test_launcher_strict_bounded_integers_across_endpoint_contract_health_and_chrome_pids(tmp_path, health_server, monkeypatch):
    import io
    import urllib.request

    from web.bootstrap.launcher_chrome import _parse_chrome_pid_output
    from web.bootstrap.launcher_contract_result import read_runtime_contract_result
    from web.bootstrap.launcher_endpoint_result import read_runtime_endpoint_files_result
    from web.bootstrap.launcher_health import probe_runtime_health_result

    endpoint_dir = tmp_path / "endpoint-state"
    endpoint_dir.mkdir()
    (endpoint_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    port_file = endpoint_dir / "aps_port.txt"
    port_file.write_text("65535\n", encoding="utf-8")
    valid_ep = read_runtime_endpoint_files_result(str(endpoint_dir))
    assert (valid_ep.port, valid_ep.port_status, valid_ep.port_error) == (65535, "valid", "")

    for raw_port, expected_reason in (
        ("８０８０", "port_not_integer"),
        ("08080", "port_not_integer"),
        ("-1", "port_not_integer"),
        ("0", "port_not_positive"),
        ("000", "port_not_positive"),
        ("65536", "port_out_of_range"),
        ("9" * 6000, "port_out_of_range"),
    ):
        port_file.write_text(raw_port, encoding="utf-8")
        bad_ep = read_runtime_endpoint_files_result(str(endpoint_dir))
        assert (bad_ep.port, bad_ep.port_status, bad_ep.port_error) == (0, "invalid", expected_reason)

    contract_dir = tmp_path / "contract-state"
    contract_dir.mkdir()
    contract_file = contract_dir / "aps_runtime.json"
    base_contract = dict(health_server["contract"])

    max_dword_contract = dict(base_contract, pid=0xFFFFFFFF, port=65535)
    contract_file.write_text(json.dumps(max_dword_contract), encoding="utf-8")
    ok_contract = read_runtime_contract_result(str(contract_dir))
    assert ok_contract.ok and ok_contract.payload is not None
    assert (ok_contract.payload["pid"], ok_contract.payload["port"]) == (0xFFFFFFFF, 65535)

    for patch, expected_reason in (
        ({"contract_version": True}, "invalid_contract_version"),
        ({"contract_version": 1.0}, "invalid_contract_version"),
        ({"contract_version": 1.9}, "invalid_contract_version"),
        ({"contract_version": "1"}, "invalid_contract_version"),
        ({"contract_version": None}, "invalid_contract_version"),
        ({"contract_version": 2}, "contract_version_mismatch"),
        ({"pid": True}, "invalid_pid"),
        ({"pid": 123.0}, "invalid_pid"),
        ({"pid": "123"}, "invalid_pid"),
        ({"pid": 0}, "invalid_pid"),
        ({"pid": 0xFFFFFFFF + 1}, "invalid_pid"),
        ({"port": True}, "invalid_port"),
        ({"port": 6322.0}, "invalid_port"),
        ({"port": "6322"}, "invalid_port"),
        ({"port": 0}, "invalid_port"),
        ({"port": 65536}, "invalid_port"),
    ):
        contract_file.write_text(json.dumps({**base_contract, **patch}), encoding="utf-8")
        bad_contract = read_runtime_contract_result(str(contract_dir))
        assert bad_contract.status == "invalid" and bad_contract.reason == expected_reason
        assert bad_contract.payload is None

    base_url = f"http://127.0.0.1:{base_contract['port']}"
    try:
        for bad_version in (True, 1.9, "1", None):
            health_server.update(status=200, patch={"contract_version": bad_version})
            probed = probe_runtime_health_result(base_url, timeout_s=0.75)
            assert not probed.ok and probed.reason == "invalid_contract_version"
            assert isinstance(probed.payload, dict)
        health_server.update(status=200, patch={"contract_version": 2})
        mismatch = probe_runtime_health_result(base_url, timeout_s=0.75)
        assert not mismatch.ok and mismatch.reason == "unexpected_health_payload"
    finally:
        health_server.update(status=200, patch={})

    class _ArrayResponse(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    with monkeypatch.context() as patch_http:
        patch_http.setattr(urllib.request, "urlopen", lambda req, timeout=None: _ArrayResponse(b"[1]"))
        non_dict = probe_runtime_health_result("http://127.0.0.1:9", timeout_s=0.5)
    assert not non_dict.ok and non_dict.reason == "invalid_contract_version" and non_dict.payload is None

    chrome_out = (
        "\ufeff1234\r\n"
        "ProcessId=4294967295\r\n"
        "ProcessId=4294967296\r\n"
        "0\r\n"
        "0123\r\n"
        "１２３４\r\n"
        + ("9" * 6000)
        + "\r\n1234\r\n\ufeff5678\r\n"
    )
    assert _parse_chrome_pid_output(chrome_out) == [1234, 0xFFFFFFFF]


def test_app_create_app_smoke(db_env, monkeypatch) -> None:
    import importlib
    import sys
    from urllib.parse import unquote, urlparse

    from core.infrastructure import database as database_mod
    from tests._support.workbench_web_contract import boot_payload
    from web.bootstrap import entrypoint, factory

    monkeypatch.setenv("SECRET_KEY", "aps-smoke-app-key")
    create_calls = []
    original_create_app = entrypoint.create_app
    monkeypatch.setattr(entrypoint, "create_app", lambda: (create_calls.append(1), original_create_app())[1])
    db_connect_calls = []
    original_get_connection = factory.get_connection
    monkeypatch.setattr(
        factory,
        "get_connection",
        lambda path: (db_connect_calls.append(path), original_get_connection(path))[1],
    )
    sqlite_connect_targets = []
    original_sqlite_connect = database_mod.sqlite3.connect
    monkeypatch.setattr(
        database_mod.sqlite3,
        "connect",
        lambda database, *args, **kwargs: (
            sqlite_connect_targets.append(str(database)),
            original_sqlite_connect(database, *args, **kwargs),
        )[1],
    )
    monkeypatch.delitem(sys.modules, "app", raising=False)
    mod = importlib.import_module("app")
    assert not hasattr(mod, "app")
    assert create_calls == []
    assert db_connect_calls == []
    assert sqlite_connect_targets == []

    app = mod.create_app()
    expected_db = os.path.abspath(app.config["DATABASE_PATH"])
    business_db_connects = [
        target for target in sqlite_connect_targets
        if target.strip() != ":memory:"
        and os.path.abspath(unquote(urlparse(target).path) if target.startswith("file:") else target) == expected_db
    ]
    assert len(create_calls) == 1
    assert len(db_connect_calls) == 1
    assert len(business_db_connects) == 1

    client = app.test_client()
    root = client.get("/")
    assert root.status_code == 302 and root.headers["Location"] == "/workbench"
    boot = boot_payload(client.get(root.headers["Location"]))
    assert boot["view"] == "dashboard" and "dashboard" in boot["enabled_views"]

    r2 = client.get("/excel-demo/")
    assert r2.status_code == 404


@pytest.mark.parametrize(("configured", "expected"), [(None, 43200), (0, 0)])
def test_static_cache_age_defaults_only_when_not_configured(db_env, monkeypatch, configured, expected) -> None:
    from web.bootstrap import app_config
    from web.bootstrap.entrypoint import create_app

    monkeypatch.setenv("SECRET_KEY", "aps-static-cache-age-key")
    monkeypatch.setattr(app_config.Config, "SEND_FILE_MAX_AGE_DEFAULT", configured, raising=False)
    assert create_app().config["SEND_FILE_MAX_AGE_DEFAULT"] == expected


def test_cold_start_defers_computation_and_excel_until_used(db_env, monkeypatch):
    import sys

    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "cold-start-contract-key")
    script = """
import atexit, importlib, json, os, sqlite3, sys
from pathlib import Path
from urllib.parse import unquote, urlparse
original_connect = sqlite3.connect
root = Path(os.environ['APS_DB_PATH']).resolve().parent
def connect(database, *args, **kwargs):
    raw = os.fspath(database)
    if raw != ':memory:':
        path = unquote(urlparse(raw).path) if raw.startswith('file:') else raw
        Path(path).resolve().relative_to(root)
    return original_connect(database, *args, **kwargs)
sqlite3.connect = connect
mod = importlib.import_module('app')
assert not hasattr(mod, 'app')
app = mod.create_app()
from web.bootstrap import factory
from web.bootstrap.entrypoint import _default_deps
from web.bootstrap.workbench_run_lifecycle import install_run_lifecycle, stop_run_runtime
from web.bootstrap.launcher_paths import current_runtime_owner
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
atexit.unregister(factory._run_exit_backup)
scope = str(root / 'cold-start-lock')
payload = acquire_runtime_lock(scope, owner=current_runtime_owner(), exe_path=sys.executable,
                               db_path=str(root / Path(os.environ['APS_DB_PATH']).name))
runtime = install_run_lifecycle(_default_deps(), app, {'payload': payload})
try:
    assert runtime.ready and app.extensions['workbench_system_restore_host'].status['operations_available']
    for name in ('openpyxl', 'core.services.workbench.run.worker',
                 'core.services.workbench.run.compute'):
        assert name not in sys.modules, name
    response = app.test_client().get('/api/workbench/v1/entities/batch/template', buffered=True)
    assert response.status_code == 200 and response.data.startswith(b'PK')
    response.close()
    assert 'openpyxl' in sys.modules
    from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
    from core.services.workbench.run.worker import RUN_SCHEDULE_LOCK as worker_lock
    from core.services.workbench.run.worker_recovery import RUN_SCHEDULE_LOCK as recovery_lock
    from core.services.workbench.run.adoption_host import RUN_SCHEDULE_LOCK as adoption_lock
    from web.bootstrap.workbench_system_restore import RUN_SCHEDULE_LOCK as restore_lock
    assert all(lock is RUN_SCHEDULE_LOCK for lock in
               (worker_lock, recovery_lock, adoption_lock, restore_lock))
    print(json.dumps({'ready': runtime.ready, 'xlsx': response.status_code, 'shared_lock': True}))
finally:
    stop_run_runtime(runtime)
    release_runtime_lock(scope, expected_payload=payload)
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT),
                            env=os.environ.copy(), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"ready": True, "xlsx": 200, "shared_lock": True}
    log = (Path(os.environ["APS_LOG_DIR"]) / "launcher.log").read_text(encoding="utf-8")
    assert "python_entry" in log and "application_import_complete" in log and "schema_complete" in log


@pytest.mark.parametrize("launcher_log_writable", [True, False], ids=["both-files", "error-file-without-log"])
def test_entry_import_failure_leaves_launch_error_without_database_or_stderr(tmp_path, launcher_log_writable):
    """入口模块链在事务模块处导入失败：退出码 14，启动日志写原因、错误文件写公开提示，两份各自尝试。"""
    import sys

    from app import PRELAUNCH_PUBLIC_MESSAGE

    logs = tmp_path / "logs"
    logs.mkdir()
    if not launcher_log_writable:
        (logs / "launcher.log").mkdir()
    script = """
import importlib.abc, sqlite3, sys
class BlockTransaction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "core.infrastructure.transaction":
            raise ImportError("blocked core.infrastructure.transaction")
        return None
sys.meta_path.insert(0, BlockTransaction())
connects = []
def deny_connect(*args, **kwargs):
    connects.append(args)
    raise AssertionError("sqlite connection during prelaunch failure")
sqlite3.connect = deny_connect
sys.stderr = None
import app
rc = app.main([])
sys.exit(99 if connects else rc)
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT), capture_output=True, timeout=60,
                            env={**os.environ, "APS_LOG_DIR": str(logs), "PYTHONIOENCODING": "utf-8"})
    assert result.returncode == 14, result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    assert (logs / "aps_launch_error.txt").read_text(encoding="utf-8") == PRELAUNCH_PUBLIC_MESSAGE + "\n"
    if launcher_log_writable:
        log = (logs / "launcher.log").read_text(encoding="utf-8")
        assert "python_entry" in log
        assert "[ERROR] 应用启动前加载失败：blocked core.infrastructure.transaction" in log
