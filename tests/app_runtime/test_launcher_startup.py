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
        state["lock"] = acquire_runtime_lock(str(tmp_path), owner="LOCAL\\operator", db_path=str(database_path))
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
    contract = health_server["configure"](app / "user-data" / "db" / "aps.db")
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
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
atexit.unregister(factory._run_exit_backup)
scope = str(root / 'cold-start-lock')
payload = acquire_runtime_lock(scope, db_path=str(root / Path(os.environ['APS_DB_PATH']).name))
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
