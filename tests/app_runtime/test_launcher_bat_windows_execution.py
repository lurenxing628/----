"""Execute the real launcher subroutines in cmd, with isolated input fixtures.

No application processes are queried, launched or stopped. Windows PowerShell
does parse the actual contract command; these host checks do not replace Win7 QA.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests._support.paths import REPO_ROOT

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires Windows cmd and Windows PowerShell")
BAT_PATH = REPO_ROOT / "assets" / "启动_排产系统_Chrome.bat"


def _section(label):
    source = BAT_PATH.read_text(encoding="utf-8")
    body = source.split("\n:" + label + "\n", 1)[1]
    following = re.search(r"^:[A-Za-z_]", body, flags=re.M)
    return ":" + label + "\n" + (body[:following.start()] if following else body)


def _write_cmd(path, text):
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


@pytest.fixture(scope="session")
def tasklist_stub(tmp_path_factory):
    folder = tmp_path_factory.mktemp("launcher-tasklist-stub")
    exe = folder / "tasklist.exe"
    source = folder / "TasklistFixture.cs"
    source.write_text(
        "using System; using System.IO; public class TasklistFixture {"
        " public static int Main() {"
        ' byte[] bytes = File.ReadAllBytes(Environment.GetEnvironmentVariable("APS_TEST_TASKLIST"));'
        " using (Stream output = Console.OpenStandardOutput()) { output.Write(bytes, 0, bytes.Length); }"
        ' return Int32.Parse(Environment.GetEnvironmentVariable("APS_TEST_TASKLIST_RC")); } }',
        encoding="ascii",
    )
    result = subprocess.run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Add-Type -Path $env:APS_STUB_SOURCE -OutputAssembly $env:APS_STUB_EXE -OutputType ConsoleApplication",
    ], env=dict(os.environ, APS_STUB_SOURCE=str(source), APS_STUB_EXE=str(exe)),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    return exe


def _run_fixture(tmp_path, body, sections, env, tasklist_stub=None, section_overrides=None):
    folder = tmp_path / "启动 验收!完整!"
    folder.mkdir()
    script = folder / "probe.cmd"
    output = folder / "result.txt"
    # This diagnostic fixture selects a legacy page before executing production
    # subroutines; the launcher itself must never change the page.
    code = "@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\nchcp 936 >nul\n"
    code += body + '\npowershell -NoProfile -NonInteractive -Command "'
    code += "$lines=@(); foreach ($item in [Environment]::GetEnvironmentVariables().GetEnumerator()) { "
    code += "if ($item.Key -match '^(CONTRACT_|LOCK_|CAN_REUSE_|BLOCKED_|BLOCK_|WAIT_|APP_|FILE_|HOST$|PORT$|CHROME_|HEALTH_|PRESENCE_)') "
    code += "{ $lines += [string]$item.Key + '=' + [string]$item.Value } }; "
    code += "$utf8=New-Object System.Text.UTF8Encoding($false); "
    code += '[IO.File]::WriteAllLines($env:APS_TEST_OUTPUT,[string[]]$lines,$utf8)"\nexit /b 0\n'
    code += "\n".join((section_overrides or {}).get(label, _section(label)) for label in sections)
    if "log" not in sections:
        code += '\n:log\n>>"%APS_TEST_LOG%" echo %*\nexit /b 0\n'
    if "probe_health" not in sections:
        code += '\n:probe_health\nset "HEALTH_OK="\nset "HEALTH_OTHER_OWNER="\n'
        code += 'if "%CONTRACT_OWNER_MATCH%"=="0" (set "HEALTH_OTHER_OWNER=1") else (set "HEALTH_OK=1")\nexit /b 0\n'
    if "probe_app_presence" not in sections:
        code += '\n:probe_app_presence\nset "HEALTH_APP_DETECTED=1"\nexit /b 0\n'
    _write_cmd(script, code)
    if tasklist_stub is not None:
        shutil.copyfile(tasklist_stub, folder / "tasklist.exe")
    process_env = dict(os.environ, **env)
    process_env.update(APS_TEST_OUTPUT=str(output), APS_TEST_LOG=str(folder / "log.txt"))
    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:on", "/c", str(script)],
        cwd=str(folder), env=process_env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert b"Cannot open >nul" not in result.stderr
    rows = output.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in rows if "=" in line)


@pytest.mark.parametrize("csv, pid, image, rc, expected, error", [
    ('"aps.exe","3424","Console","1","123 K"', "3424", "aps.exe", 0, "1", None),
    ('"APS.EXE","3424","Console","1","123 K"', "3424", "aps.exe", 0, "1", None),
    ('"排产!系统!.exe","3424","Console","1","123 K"', "3424", "排产!系统!.exe", 0, "1", None),
    ('"other.exe","3424","Console","1","123 K"', "3424", "aps.exe", 0, "0", None),
    ('"aps.exe","34240","Console","1","123 K"', "3424", "aps.exe", 0, "0", None),
    ('INFO: No tasks are running which match the specified criteria.', "3424", "aps.exe", 0, "0", None),
    ("", "3424", "aps.exe", 1, "UNKNOWN", "tasklist_failed"),
    ("", "invalid", "aps.exe", 0, "UNKNOWN", "lock_pid_invalid"),
])
def test_real_cmd_lock_checks_exact_image_and_pid(tmp_path, tasklist_stub, csv, pid, image, rc, expected, error):
    fixture = tmp_path / "tasklist.csv"
    fixture.write_bytes((csv + "\r\n").encode("gbk"))
    rows = _run_fixture(tmp_path, "call :lock_is_active", ["lock_is_active"], {
        "APS_TEST_TASKLIST": str(fixture), "APS_TEST_TASKLIST_RC": str(rc),
        "LOCK_PID": pid, "APP_EXE_NAME": image,
    }, tasklist_stub=tasklist_stub)
    assert rows["LOCK_ACTIVE"] == expected
    assert rows.get("LOCK_QUERY_ERROR") == error
    if csv.startswith('"other.exe"'):
        assert rows["LOCK_PID_IMAGE_MISMATCH"] == "1"


@pytest.mark.parametrize("owner, current_owner, version, expected", [
    (r"LOCALBOX\Administrator", r"localbox\administrator", 1, "reuse"),
    ("本机\\排产用户", "本机\\排产用户", 1, "reuse"),
    ("本机!\\排产!用户", "本机!\\排产!用户", 1, "reuse"),
    (r"LOCALBOX\other", r"LOCALBOX\Administrator", 1, "other"),
    ("", r"LOCALBOX\Administrator", 1, "invalid"),
    (r"LOCALBOX\Administrator", r"LOCALBOX\Administrator", 2, "invalid"),
])
def test_real_cmd_contract_owner_proof_is_not_lost(tmp_path, owner, current_owner, version, expected):
    contract = tmp_path / "运行 契约!完整!.json"
    contract.write_text(json.dumps({
        "owner": owner, "pid": 3424, "contract_version": version,
        "host": "127.0.0.1", "port": 5000,
    }, ensure_ascii=False), encoding="utf-8")
    rows = _run_fixture(tmp_path, "call :read_runtime_contract\ncall :try_reuse_by_contract", [
        "read_runtime_contract", "try_reuse_by_contract",
    ], {"RUNTIME_CONTRACT_FILE": str(contract), "HAS_POWERSHELL": "1", "CURRENT_OWNER": current_owner})
    if expected == "reuse":
        assert rows["CAN_REUSE_EXISTING"] == "1"
        assert rows["CONTRACT_OWNER_MATCH"] == "1"
        assert base64.b64decode(rows["CONTRACT_OWNER_BASE64"]).decode("utf-8") == owner
        assert "BLOCKED_BY_OTHER" not in rows
    elif expected == "other":
        assert rows["BLOCKED_BY_OTHER"] == "1"
        assert rows["CONTRACT_OWNER_MATCH"] == "0"
        assert "CAN_REUSE_EXISTING" not in rows
    else:
        assert "CONTRACT_VALID" not in rows
        assert "CAN_REUSE_EXISTING" not in rows
        assert "CONTRACT_READ_ERROR" in rows


@pytest.mark.parametrize("lock_owner, image, expected", [
    (r"LOCALBOX\Administrator", "aps.exe", "reuse"),
    (r"LOCALBOX\other", "aps.exe", "other"),
    ("", "aps.exe", "uncertain"),
    (r"LOCALBOX\Administrator", "unrelated.exe", "uncertain"),
    ("本机!\\排产!用户", "aps.exe", "other"),
])
def test_real_cmd_reuse_dispatch_keeps_other_and_uncertain_owner_blocked(tmp_path, tasklist_stub, lock_owner, image, expected):
    db_path = os.path.normcase(os.path.abspath(str(tmp_path / "db" / "aps.db")))
    app_exe = str(tmp_path / "aps.exe")
    lock = tmp_path / "runtime.lock"
    lock.write_text("pid=3424\nowner=" + lock_owner + "\ndb_path=" + db_path + "\nexe_path=" + app_exe + "\n", encoding="utf-8")
    host = tmp_path / "host.txt"
    host.write_text("127.0.0.1\n", encoding="ascii")
    port = tmp_path / "port.txt"
    port.write_text("5000\n", encoding="ascii")
    tasklist = tmp_path / "tasklist.csv"
    tasklist.write_text('"' + image + '","3424","Console","1","123 K"\n', encoding="ascii")
    contract = tmp_path / "contract.json"
    if expected == "reuse":
        contract.write_text(json.dumps({
            "contract_version": 1, "pid": 3424, "owner": lock_owner, "host": "127.0.0.1", "port": 5000,
        }), encoding="utf-8")
    rows = _run_fixture(tmp_path, "call :try_reuse_existing", [
        "try_reuse_existing", "try_reuse_active_lock", "try_reuse_active_endpoint", "lock_contract_pid_matches",
        "read_lock_file", "lock_is_active", "read_runtime_contract",
        "load_existing_endpoint", "read_host_file", "read_port_file", "try_reuse_by_contract", "block_uncertain",
    ], {
        "APS_TEST_TASKLIST": str(tasklist), "APS_TEST_TASKLIST_RC": "0", "APP_EXE_NAME": "aps.exe",
        "LOCK_FILE": str(lock), "HOST_FILE": str(host), "PORT_FILE": str(port),
        "RUNTIME_CONTRACT_FILE": str(contract), "APS_DB_PATH": db_path, "APP_EXE": app_exe,
        "HAS_POWERSHELL": "1", "CURRENT_OWNER": r"LOCALBOX\Administrator",
    }, tasklist_stub=tasklist_stub)
    if expected == "reuse":
        assert rows["CAN_REUSE_EXISTING"] == "1"
        assert "BLOCKED_BY_OTHER" not in rows
        assert "BLOCKED_BY_UNCERTAIN" not in rows
    else:
        assert "CAN_REUSE_EXISTING" not in rows
        assert rows["BLOCKED_BY_OTHER" if expected == "other" else "BLOCKED_BY_UNCERTAIN"] == "1"


def test_powershell2_json_fallback_emits_ascii_without_bom(tmp_path):
    section = _section("read_runtime_contract")
    line = next(row for row in section.splitlines() if row.startswith("powershell -NoProfile -Command "))
    script = line.split('-Command "', 1)[1].rsplit('" >nul 2>nul', 1)[0]
    # Execute the legacy JSON branch in installed PowerShell without changing
    # production code or requiring an unavailable PowerShell 2 engine on host.
    script = script.replace("if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    contract = tmp_path / "contract.json"
    output = tmp_path / "protocol.txt"
    contract.write_text(json.dumps({
        "owner": "本机\\排产用户", "pid": 3424, "contract_version": 1,
        "host": "127.0.0.1", "port": 5000,
    }, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=dict(os.environ, APS_RUNTIME_CONTRACT_FILE=str(contract),
                 APS_RUNTIME_CONTRACT_OUTPUT=str(output), CURRENT_OWNER="本机\\排产用户"),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    raw = output.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"owner_match=1\r\n" in raw
    assert raw.decode("ascii")


@pytest.mark.parametrize("owner, current_owner, match", [
    ("本机!\\排产!用户", "本机!\\排产!用户", "1"),
    ("本机!\\其他!用户", "本机!\\排产!用户", "0"),
])
def test_real_cmd_utf8_lock_owner_in_legacy_console(tmp_path, owner, current_owner, match):
    lock = tmp_path / "运行 !锁!.lock"
    lock.write_text("pid=3424\nowner=" + owner + "\n", encoding="utf-8")
    rows = _run_fixture(tmp_path, "call :read_lock_file", ["read_lock_file"], {
        "LOCK_FILE": str(lock), "CURRENT_OWNER": current_owner,
    })
    assert rows["LOCK_PID"] == "3424"
    assert rows["LOCK_OWNER_MATCH"] == match
    assert base64.b64decode(rows["LOCK_OWNER_BASE64"]).decode("utf-8") == owner


@pytest.mark.parametrize("missing, reason", [
    ("host", "lock_active_missing_host"), ("port", "lock_active_missing_port"),
])
def test_real_cmd_active_owner_missing_endpoint_waits(tmp_path, missing, reason):
    host = tmp_path / "host.txt"
    port = tmp_path / "port.txt"
    if missing != "host":
        host.write_text("127.0.0.1\n", encoding="ascii")
    if missing != "port":
        port.write_text("5000\n", encoding="ascii")
    rows = _run_fixture(tmp_path, "call :try_reuse_active_lock", [
        "try_reuse_active_lock", "load_existing_endpoint", "read_host_file", "read_port_file", "block_uncertain",
    ], {
        "LOCK_OWNER_BASE64": "b3duZXI=", "LOCK_OWNER_MATCH": "1",
        "LOCK_DB_MATCH": "1", "LOCK_EXE_MATCH": "1",
        "HOST_FILE": str(host), "PORT_FILE": str(port), "HAS_POWERSHELL": "1",
    })
    assert rows["WAIT_EXISTING_STARTUP"] == "1"
    assert rows["WAIT_EXISTING_REASON"] == reason
    assert "BLOCKED_BY_UNCERTAIN" not in rows


def test_real_cmd_endpoint_poll_uses_new_values_not_stale_block_expansion(tmp_path):
    host = tmp_path / "主机 !现场!.txt"
    port = tmp_path / "端口 !现场!.txt"
    host.write_text(" 127.0.0.1 \n", encoding="ascii")
    port.write_text(" 56237 \n", encoding="ascii")
    rows = _run_fixture(tmp_path, "call :poll_app_ready", [
        "poll_app_ready", "read_host_file", "read_port_file",
    ], {"HOST_FILE": str(host), "PORT_FILE": str(port), "HOST": "old", "PORT": "5000", "HAS_POWERSHELL": "1"})
    assert rows["HOST"] == "127.0.0.1"
    assert rows["PORT"] == "56237"


@pytest.mark.parametrize("port_text", ["", "abc", "5000!bad!", "5000&bad"])
def test_real_cmd_empty_host_and_invalid_port_keep_original_fallback(tmp_path, port_text):
    host = tmp_path / "host.txt"
    port = tmp_path / "port.txt"
    host.write_text("\n", encoding="ascii")
    port.write_text(port_text + "\n", encoding="ascii")
    rows = _run_fixture(tmp_path, "call :read_host_file\ncall :read_port_file", [
        "read_host_file", "read_port_file",
    ], {"HOST_FILE": str(host), "PORT_FILE": str(port)})
    assert rows["FILE_HOST"] == "127.0.0.1"
    assert "FILE_PORT" not in rows


@pytest.mark.parametrize("codepage", ["437", "936", "65001"])
def test_real_cmd_utf8_launcher_log_preserves_unicode_bang_paths(tmp_path, codepage):
    folder = tmp_path / "启动 日志!完整!"
    folder.mkdir()
    script = folder / "probe.cmd"
    log = folder / "启动 !日志!.log"
    _write_cmd(script, '@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\n'
               'chcp %APS_TEST_CODEPAGE% >nul\n'
               'call :log app_dir="%APS_TEST_PATH%"\nexit /b 0\n' + _section("log"))
    value = str(folder / "中文 !完整! 路径")
    # Match the application's long-lived append handle while BAT appends too.
    with log.open("a", encoding="utf-8") as app_log:
        app_log.write("应用日志\n")
        app_log.flush()
        result = subprocess.run([
            os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:on", "/c", str(script),
        ], env=dict(os.environ, LAUNCHER_LOG=str(log), APS_TEST_PATH=value, APS_TEST_CODEPAGE=codepage),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert 'app_dir="' + value + '"' in log.read_bytes().decode("utf-8", errors="strict")


def test_real_cmd_app_and_chrome_resolution_keep_full_bang_paths(tmp_path):
    folder = tmp_path / "安装 目录!完整!"
    folder.mkdir()
    app = folder / "排产!系统!.exe"
    chrome = folder / "App" / "chrome.exe"
    chrome.parent.mkdir()
    app.touch()
    chrome.touch()
    rows = _run_fixture(tmp_path, 'call :select_app_exe "%APS_TEST_APP%"\n'
                        'call :try_chrome_dir "%APS_TEST_CHROME%" "env_runtime"', [
        "select_app_exe", "try_chrome_dir",
    ], {"APS_TEST_APP": str(app), "APS_TEST_CHROME": str(folder)})
    assert rows["APP_EXE"] == str(app)
    assert rows["CHROME_EXE"] == str(chrome)
    assert rows["CHROME_SOURCE"] == "env_runtime\\App"


@pytest.fixture(scope="session")
def python_entry_stub(tmp_path_factory):
    folder = tmp_path_factory.mktemp("launcher-python-entry-stub")
    source = folder / "PythonEntryFixture.cs"
    exe = folder / "python.exe"
    source.write_text(
        "using System; using System.IO; using System.Text; using System.Runtime.InteropServices; "
        "public class PythonEntryFixture { "
        '[DllImport("kernel32.dll")] static extern uint GetConsoleOutputCP(); '
        "public static int Main(string[] args) { "
        'File.WriteAllLines(Environment.GetEnvironmentVariable("APS_TEST_RECEIPT"), '
        'new string[] { Directory.GetCurrentDirectory(), String.Join("|", args), '
        'Environment.GetEnvironmentVariable("APS_TEST_PATH"), GetConsoleOutputCP().ToString() }, '
        "new UTF8Encoding(false)); "
        'return Int32.Parse(Environment.GetEnvironmentVariable("APS_TEST_RC")); } }',
        encoding="ascii",
    )
    result = subprocess.run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Add-Type -Path $env:APS_STUB_SOURCE -OutputAssembly $env:APS_STUB_EXE -OutputType ConsoleApplication",
    ], env=dict(os.environ, APS_STUB_SOURCE=str(source), APS_STUB_EXE=str(exe)),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    return exe


@pytest.mark.parametrize("filename, target", [("start.bat", "app.py"), ("start_new_ui.bat", "app_new_ui.py")])
@pytest.mark.parametrize("codepage", ["437", "936"])
def test_real_development_entry_keeps_cwd_bang_paths_codepage_and_exit_code(
        tmp_path, python_entry_stub, filename, target, codepage):
    folder = tmp_path / "开发 目录!完整!"
    folder.mkdir()
    shutil.copyfile(REPO_ROOT / filename, folder / filename)
    shutil.copyfile(python_entry_stub, folder / "python.exe")
    entry = tmp_path / "invoke.cmd"
    # Disable expansion before CALL parses the target. The target cannot recover
    # exclamation marks already stripped by a caller before entering the BAT.
    _write_cmd(entry, '@echo off\nsetlocal DisableDelayedExpansion\nchcp %APS_TEST_CODEPAGE% >nul\n'
               'call "%APS_TEST_ENTRY%"\nexit /b %ERRORLEVEL%\n')
    receipt = tmp_path / "receipt.txt"
    result = subprocess.run([
        os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:on", "/c", str(entry),
    ], cwd=str(tmp_path), env=dict(os.environ, APS_TEST_ENTRY=str(folder / filename),
        APS_TEST_RECEIPT=str(receipt), APS_TEST_PATH=str(folder), APS_TEST_RC="23", APS_TEST_CODEPAGE=codepage),
        input=b"\r\n", capture_output=True, timeout=20, check=False)
    assert result.returncode == 23, (result.stdout, result.stderr)
    assert receipt.read_text(encoding="utf-8").splitlines() == [str(folder), target, str(folder), codepage]
    for line in result.stdout.splitlines():
        if line.startswith(b"[start]"):
            line.decode("ascii", errors="strict")


@pytest.mark.parametrize("app_present, expected", [(False, 1), (True, 2)])
def test_real_full_portable_launcher_failure_keeps_paths_and_status(tmp_path, app_present, expected):
    folder = tmp_path / "便携 包!完整!"
    folder.mkdir()
    launcher = folder / "启动_排产系统_Chrome.bat"
    shutil.copyfile(BAT_PATH, launcher)
    (folder / "aps-portable.txt").touch()
    if app_present:
        # A discovery fixture only: missing Chrome stops before any exe executes.
        (folder / "排产!系统!.exe").touch()
    entry = tmp_path / "invoke.cmd"
    _write_cmd(entry, '@echo off\nsetlocal DisableDelayedExpansion\nchcp 936 >nul\n'
               'call "%APS_TEST_ENTRY%"\nset "RC=%ERRORLEVEL%"\n'
               'chcp\nexit /b %RC%\n')
    result = subprocess.run([
        os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:on", "/c", str(entry),
    ], cwd=str(tmp_path), env=dict(os.environ, APS_TEST_ENTRY=str(launcher)),
        input=b"\r\n", capture_output=True, timeout=30, check=False)
    assert result.returncode == expected, (result.stdout, result.stderr)
    assert b"936" in result.stdout.splitlines()[-1]
    log = (folder / "user-data" / "logs" / "launcher.log").read_text(encoding="utf-8")
    assert 'app_dir="' + str(folder) + '"' in log
    assert 'shared_data_root="' + str(folder / "user-data") + '"' in log
    if app_present:
        assert 'app_exe="' + str(folder / "排产!系统!.exe") + '"' in log
        assert 'portable_chrome_missing="' + str(folder / "tools" / "chrome109" / "chrome.exe") + '"' in log
    else:
        assert "app_exe_not_found" in log


def test_real_cmd_unreadable_lock_stays_uncertain(tmp_path):
    rows = _run_fixture(tmp_path, "call :read_lock_file\ncall :lock_is_active", [
        "read_lock_file", "lock_is_active",
    ], {"LOCK_FILE": str(tmp_path), "CURRENT_OWNER": "owner"})
    assert rows["LOCK_ACTIVE"] == "UNKNOWN"
    assert rows["LOCK_QUERY_ERROR"] == "lock_parse_failed"


@pytest.mark.parametrize("suffix, expected", [("", 0), ("-another-profile", 2)])
def test_bat_chrome_identity_parser_uses_exact_unicode_env_profile(tmp_path, suffix, expected):
    section = _section("probe_aps_chrome_alive")
    line = next(row for row in section.splitlines() if row.startswith("powershell -NoProfile -Command "))
    script = line.split('-Command "', 1)[1].rsplit('" >nul 2>&1', 1)[0]
    # Execute the actual parser with a fixture command line, without querying
    # host browsers. CMD normally reduces the doubled percent in the modulus.
    script = script.split("$items=$null;", 1)[0].replace("%%", "%")
    script += "$cmd=[IO.File]::ReadAllText($env:APS_TEST_CHROME_CMD,[Text.Encoding]::UTF8); "
    script += "if (Test-ApsChromeCommandLine $cmd) { exit 0 }; exit 2"
    profile = str(tmp_path / "浏览器 配置!完整!")
    command = tmp_path / "command.txt"
    command.write_text('"chrome.exe" --user-data-dir="' + profile + suffix + '" --app="http://127.0.0.1:56237/"',
                       encoding="utf-8")
    result = subprocess.run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", script,
    ], env=dict(os.environ, CHROME_PROFILE_DIR=profile, APS_TEST_CHROME_CMD=str(command)),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False)
    assert result.returncode == expected, result.stderr


@pytest.fixture
def localhost_health_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.requests.append(self.path)
            body = self.server.response_body
            self.send_response(self.server.response_status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.response_body = b"{}"
    server.response_status = 200
    server.requests = []
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def _health_fixture_values(tmp_path, server):
    owner = "LOCALBOX!\\排产!USER"
    db_path = os.path.normcase(os.path.abspath(str(tmp_path / "数据库 !完整!" / "aps.db")))
    token = "instance!中文_token"
    contract = {
        "contract_version": 1, "pid": 3424, "owner": owner,
        "db_path": db_path, "shutdown_token": token,
        "host": "127.0.0.1", "port": server.server_port,
    }
    health = {
        "app": "aps", "status": "ok", "contract_version": 1,
        "pid": 3424, "owner": owner,
        "db_path_hash": hashlib.sha256(db_path.encode("utf-8")).hexdigest(),
        "instance_id": hashlib.sha256(token.encode("utf-8")).hexdigest(),
    }
    env = {
        "HAS_POWERSHELL": "1", "HOST": "127.0.0.1", "PORT": str(server.server_port),
        "APS_DB_PATH": db_path,
        "HEALTH_PATH": "/system/health", "CURRENT_OWNER": owner.lower(),
        # Deliberately stale cache: production must read the newly published file.
        "CONTRACT_PID": "9999", "CONTRACT_OWNER_MATCH": "0", "CONTRACT_HOST": "old",
    }
    return contract, health, env


def _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser, reuse=False, stale_owner=False):
    contract_path = tmp_path / "运行 契约!完整!.json"
    if contract is not None:
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    log = tmp_path / "健康 日志!完整!.log"
    section = _section("probe_health")
    if legacy_parser:
        # Select the real PowerShell 2 parser branch on the host. Only parser
        # selection changes; HTTP, contract reading and all comparisons execute.
        section = section.replace("if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    sections = ["probe_health", "log"]
    body = "call :probe_health"
    if reuse:
        sections.extend(["read_runtime_contract", "try_reuse_by_contract"])
        body = "call :read_runtime_contract\ncall :try_reuse_by_contract"
        if stale_owner:
            body = "call :try_reuse_by_contract"
    rows = _run_fixture(tmp_path, body, sections,
                        dict(env, RUNTIME_CONTRACT_FILE=str(contract_path), LAUNCHER_LOG=str(log)),
                        section_overrides={"probe_health": section})
    log_text = log.read_text(encoding="utf-8", errors="strict")
    if contract and contract.get("shutdown_token"):
        assert contract["shutdown_token"] not in log_text
    return rows


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_http_health_accepts_full_identity_and_latest_contract(tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    health["owner"] = health["owner"].lower()
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser)
    assert rows["HEALTH_OK"] == "1"
    assert rows["HEALTH_RC"] == "0"
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("case", [
    "other-pid", "other-owner", "other-db", "other-token", "other-app", "bad-status", "bad-version",
    "contract-other-owner", "current-other-owner", "contract-other-db", "contract-other-token",
    "endpoint-host", "endpoint-port", "contract-missing", "contract-empty-token", "malformed-json", "http-redirect",
    "missing-app", "missing-status", "missing-contract_version", "missing-pid", "missing-owner",
    "missing-db_path_hash", "missing-instance_id", "contract-missing-db_path", "contract-missing-pid",
])
def test_real_cmd_http_health_rejects_missing_or_wrong_identity(tmp_path, localhost_health_server, legacy_parser, case):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    if case == "other-pid":
        health["pid"] += 1
    elif case == "other-owner":
        health["owner"] = "LOCALBOX!\\another-user"
    elif case == "other-db":
        health["db_path_hash"] = hashlib.sha256(b"another-db").hexdigest()
    elif case == "other-token":
        health["instance_id"] = hashlib.sha256(b"another-token").hexdigest()
    elif case == "other-app":
        health["app"] = "another-app"
    elif case == "bad-status":
        health["status"] = "error"
    elif case == "bad-version":
        health["contract_version"] = 2
    elif case == "contract-other-owner":
        contract["owner"] = "LOCALBOX!\\another-user"
    elif case == "current-other-owner":
        env["CURRENT_OWNER"] = "LOCALBOX!\\another-user"
    elif case == "contract-other-db":
        contract["db_path"] += ".another"
    elif case == "contract-other-token":
        contract["shutdown_token"] += "another"
    elif case == "endpoint-host":
        contract["host"] = "localhost"
    elif case == "endpoint-port":
        contract["port"] = server.server_port % 65535 + 1
    elif case == "contract-missing":
        contract = None
    elif case == "contract-empty-token":
        contract["shutdown_token"] = ""
        health["instance_id"] = ""
    elif case == "http-redirect":
        server.response_status = 302
    elif case.startswith("missing-"):
        del health[case[len("missing-"):]]
    elif case.startswith("contract-missing-"):
        del contract[case[len("contract-missing-"):]]
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    if case == "malformed-json":
        # The old regex fallback could accept these status tokens in invalid JSON.
        server.response_body = b'broken {"app":"aps","status":"ok","contract_version":1}'
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser)
    assert "HEALTH_OK" not in rows
    assert rows["HEALTH_RC"] != "0"
    if case == "current-other-owner":
        assert rows["HEALTH_RC"] == "4"
        assert rows["HEALTH_OTHER_OWNER"] == "1"
    if case in {"endpoint-host", "endpoint-port", "contract-missing", "contract-empty-token",
                "contract-missing-db_path", "contract-missing-pid", "contract-other-db"}:
        assert server.requests == []
    else:
        assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_http_other_owner_is_blocked_even_with_only_contract(tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    env["CURRENT_OWNER"] = "LOCALBOX!\\another-user"
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser, reuse=True)
    assert rows["BLOCKED_BY_OTHER"] == "1"
    assert rows["HEALTH_OTHER_OWNER"] == "1"
    assert "HEALTH_OK" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_contract_reuse_obeys_live_identity_not_stale_owner_cache(tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    env.update(CONTRACT_VALID="1", CONTRACT_HOST=contract["host"], CONTRACT_PORT=str(contract["port"]))
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser, reuse=True, stale_owner=True)
    assert rows["CONTRACT_OWNER_MATCH"] == "0"
    assert rows["HEALTH_OK"] == "1"
    assert rows["CAN_REUSE_EXISTING"] == "1"
    assert "BLOCKED_BY_OTHER" not in rows
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_http_health_rejects_only_changed_expected_database(tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    env["APS_DB_PATH"] += ".database-B"
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser)
    assert "HEALTH_OK" not in rows
    assert "HEALTH_OTHER_OWNER" not in rows
    assert rows["HEALTH_RC"] == "2"
    assert server.requests == []


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("form", ["upper-forward-slashes", "relative-dot-dot"])
def test_real_cmd_expected_database_is_normalized_before_identity_comparison(
        tmp_path, localhost_health_server, legacy_parser, form):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    if form == "upper-forward-slashes":
        env["APS_DB_PATH"] = contract["db_path"].upper().replace("\\", "/")
    else:
        # The actual CMD fixture's cwd is tmp_path / "启动 验收!完整!".
        env["APS_DB_PATH"] = r"..\数据库 !完整!\unused\..\aps.db"
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser)
    assert rows["HEALTH_OK"] == "1"
    assert server.requests == ["/system/health"]


def _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, endpoints, contract_text=None, expected_db=None):
    host = tmp_path / "主机 !原始!.txt"
    port = tmp_path / "端口 !原始!.txt"
    contract_path = tmp_path / "契约 !原始!.json"
    if endpoints:
        host.write_bytes(b"127.0.0.1\n")
        port.write_bytes((str(server.server_port) + "\n").encode("ascii"))
    if contract_text is not None:
        contract_path.write_text(contract_text, encoding="utf-8")
    sections = [
        "try_reuse_existing", "try_reuse_active_lock", "try_reuse_active_endpoint", "lock_contract_pid_matches",
        "try_reuse_by_contract", "load_existing_endpoint",
        "read_host_file", "read_port_file", "read_lock_file", "lock_is_active", "read_runtime_contract",
        "probe_health", "probe_app_presence", "block_uncertain", "log",
    ]
    overrides = {}
    if legacy_parser:
        for label in ("probe_health", "probe_app_presence", "read_runtime_contract"):
            overrides[label] = _section(label).replace(
                "if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    _, _, env = _health_fixture_values(tmp_path, server)
    if expected_db is not None:
        env["APS_DB_PATH"] = expected_db
    env.update(HOST_FILE=str(host), PORT_FILE=str(port), LOCK_FILE=str(tmp_path / "absent.lock"),
               RUNTIME_CONTRACT_FILE=str(contract_path), LAUNCHER_LOG=str(tmp_path / "存在 日志!完整!.log"))
    # There is no cached contract at all in these tests.
    env.pop("CONTRACT_HOST")
    env.pop("CONTRACT_PID")
    env.pop("CONTRACT_OWNER_MATCH")
    return _run_fixture(tmp_path, "call :try_reuse_existing", sections, env, section_overrides=overrides)


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("contract_text", [None, "broken-json", '{"contract_version":2,"pid":3424}'])
def test_real_cmd_existing_aps_without_valid_contract_is_blocked_and_endpoint_files_untouched(
        tmp_path, localhost_health_server, legacy_parser, contract_text):
    server = localhost_health_server
    # Only proves APS is present; deliberately contains no reusable identity.
    server.response_body = b'{"app":"aps","status":"ok","contract_version":1}'
    rows = _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, True, contract_text)
    assert rows["BLOCKED_BY_UNCERTAIN"] == "1"
    assert rows["BLOCK_REASON"] == "healthy_without_owner_proof"
    assert rows["HEALTH_APP_DETECTED"] == "1"
    assert "HEALTH_OK" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    assert (tmp_path / "主机 !原始!.txt").read_bytes() == b"127.0.0.1\n"
    assert (tmp_path / "端口 !原始!.txt").read_bytes() == (str(server.server_port) + "\n").encode("ascii")
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_new_log_directory_does_not_probe_unpublished_default_port(tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    server.response_body = b'{"app":"aps","status":"ok","contract_version":1}'
    # HOST/PORT default to the occupied fixture's endpoint, but no endpoint files
    # have been published in this fresh log directory. Spawn/fallback remains legal.
    rows = _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, False)
    assert "CAN_REUSE_EXISTING" not in rows
    assert "BLOCKED_BY_UNCERTAIN" not in rows
    assert "BLOCKED_BY_OTHER" not in rows
    assert "HEALTH_OK" not in rows
    assert "HEALTH_APP_DETECTED" not in rows
    assert server.requests == []


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_changed_database_blocks_existing_service_without_touching_contract_or_endpoints(
        tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    contract_text = json.dumps(contract, ensure_ascii=False)
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, True, contract_text,
                                                   expected_db=env["APS_DB_PATH"] + ".database-B")
    assert rows["HEALTH_RC"] == "2"
    assert rows["BLOCKED_BY_UNCERTAIN"] == "1"
    assert rows["HEALTH_APP_DETECTED"] == "1"
    assert "HEALTH_OK" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    assert (tmp_path / "契约 !原始!.json").read_text(encoding="utf-8") == contract_text
    assert (tmp_path / "主机 !原始!.txt").read_bytes() == b"127.0.0.1\n"
    assert (tmp_path / "端口 !原始!.txt").read_bytes() == (str(server.server_port) + "\n").encode("ascii")
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("response", [b'{"app":"other","status":"ok","contract_version":1}',
                                      b'broken {"app":"aps","status":"ok","contract_version":1}'])
def test_real_cmd_presence_parser_does_not_accept_other_app_or_invalid_json(
        tmp_path, localhost_health_server, legacy_parser, response):
    server = localhost_health_server
    server.response_body = response
    rows = _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, True)
    assert "HEALTH_APP_DETECTED" not in rows
    assert "HEALTH_OK" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    assert "BLOCKED_BY_UNCERTAIN" not in rows
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("contract_text", [None, "broken-json"])
def test_real_full_launcher_keeps_endpoints_and_never_spawns_when_aps_owner_unproven(
        tmp_path, localhost_health_server, legacy_parser, contract_text):
    server = localhost_health_server
    server.response_body = b'{"app":"aps","status":"ok","contract_version":1}'
    folder = tmp_path / "便携 包!完整!"
    folder.mkdir()
    launcher = folder / "启动_排产系统_Chrome.bat"
    code = BAT_PATH.read_text(encoding="ascii")
    if legacy_parser:
        code = code.replace("if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    _write_cmd(launcher, code)
    (folder / "aps-portable.txt").touch()
    # These discovery fixtures are never executable; the correct main flow must
    # stop at BLOCKED_UNCERTAIN before either START or signal-file deletion.
    (folder / "排产!系统!.exe").touch()
    chrome = folder / "tools" / "chrome109" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()
    logs = folder / "user-data" / "logs"
    logs.mkdir(parents=True)
    original = {
        "aps_host.txt": b"127.0.0.1\r\n", "aps_port.txt": (str(server.server_port) + "\r\n").encode("ascii"),
        "aps_db_path.txt": "旧库 !完整!\n".encode(), "aps_launch_error.txt": b"previous-error\n",
    }
    for filename, raw in original.items():
        (logs / filename).write_bytes(raw)
    if contract_text is not None:
        (logs / "aps_runtime.json").write_text(contract_text, encoding="utf-8")
    entry = tmp_path / "invoke.cmd"
    _write_cmd(entry, '@echo off\nsetlocal DisableDelayedExpansion\nchcp 936 >nul\n'
               'call "%APS_TEST_ENTRY%"\nexit /b %ERRORLEVEL%\n')
    result = subprocess.run([
        os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:on", "/c", str(entry),
    ], cwd=str(tmp_path), env=dict(os.environ, APS_TEST_ENTRY=str(launcher)),
        input=b"\r\n", capture_output=True, timeout=45, check=False)
    assert result.returncode == 9, (result.stdout, result.stderr)
    for filename, raw in original.items():
        assert (logs / filename).read_bytes() == raw
    log = (logs / "launcher.log").read_text(encoding="utf-8", errors="strict")
    assert "existing_reuse_blocked=healthy_without_owner_proof" in log
    assert "app_start_required" not in log
    assert "app_spawn_probe" not in log
    assert "chrome_start_rc" not in log
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_real_cmd_503_recovery_with_complete_identity_can_open_read_only_page(
        tmp_path, localhost_health_server, legacy_parser):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    health.update(status="recovery_required", operations_available=False)
    server.response_status = 503
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser, reuse=True)
    assert rows["HEALTH_OK"] == "1"
    assert rows["HEALTH_RECOVERY_READY"] == "1"
    assert rows["CAN_REUSE_EXISTING"] == "1"
    assert rows["HEALTH_RC"] == "3"
    log = (tmp_path / "健康 日志!完整!.log").read_text(encoding="utf-8")
    assert "health_recovery_ready=" in log
    assert "health_ok=" not in log
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("case", [
    "ordinary-503", "ok-with-503", "200-recovery", "500-recovery", "missing-operations",
    "string-false", "numeric-false", "array-false", "operations-true", "missing-pid", "other-pid",
    "other-owner", "current-other-owner", "other-db", "other-token", "different-expected-db", "other-endpoint",
    "missing-owner", "missing-db_path_hash", "missing-instance_id",
])
def test_real_cmd_recovery_503_rejects_errors_mutable_or_unverified_identity(
        tmp_path, localhost_health_server, legacy_parser, case):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    health.update(status="recovery_required", operations_available=False)
    server.response_status = 503
    if case == "ordinary-503":
        health["status"] = "error"
    elif case == "ok-with-503":
        health["status"] = "ok"
    elif case == "200-recovery":
        server.response_status = 200
    elif case == "500-recovery":
        server.response_status = 500
    elif case == "missing-operations":
        del health["operations_available"]
    elif case == "string-false":
        health["operations_available"] = "false"
    elif case == "numeric-false":
        health["operations_available"] = 0
    elif case == "array-false":
        health["operations_available"] = [False]
    elif case == "operations-true":
        health["operations_available"] = True
    elif case == "missing-pid":
        del health["pid"]
    elif case == "other-pid":
        health["pid"] += 1
    elif case == "other-owner":
        health["owner"] = "another-owner"
    elif case == "current-other-owner":
        env["CURRENT_OWNER"] = "another-owner"
    elif case == "other-db":
        health["db_path_hash"] = hashlib.sha256(b"another-db").hexdigest()
    elif case == "other-token":
        health["instance_id"] = hashlib.sha256(b"another-token").hexdigest()
    elif case == "different-expected-db":
        env["APS_DB_PATH"] += ".database-B"
    elif case == "other-endpoint":
        contract["port"] = server.server_port % 65535 + 1
    elif case.startswith("missing-"):
        del health[case[len("missing-"):]]
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    rows = _run_http_health_fixture(tmp_path, server, contract, env, legacy_parser)
    assert "HEALTH_OK" not in rows
    assert "HEALTH_RECOVERY_READY" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    log = (tmp_path / "健康 日志!完整!.log").read_text(encoding="utf-8")
    assert "health_recovery_ready=" not in log
    assert "health_ok=" not in log
    assert server.requests == ([] if case in {"different-expected-db", "other-endpoint"} else ["/system/health"])


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("status", ["recovery_required", "error"])
def test_real_cmd_existing_503_aps_without_identity_proof_is_only_blocked(
        tmp_path, localhost_health_server, legacy_parser, status):
    server = localhost_health_server
    server.response_status = 503
    server.response_body = json.dumps({
        "app": "aps", "contract_version": 1, "status": status, "operations_available": False,
    }).encode("utf-8")
    rows = _run_existing_endpoint_dispatch_fixture(tmp_path, server, legacy_parser, True)
    assert rows["HEALTH_APP_DETECTED"] == "1"
    assert rows["BLOCKED_BY_UNCERTAIN"] == "1"
    assert "HEALTH_OK" not in rows
    assert "HEALTH_RECOVERY_READY" not in rows
    assert "CAN_REUSE_EXISTING" not in rows
    assert server.requests == ["/system/health"]


@pytest.mark.parametrize("cleanup, expected_success", [("Clear", True), ("Dispose", False)])
def test_actual_bat_hash_helper_handles_clr2_public_cleanup_surface(tmp_path, cleanup, expected_success):
    section = _section("probe_health")
    function = "function Get-Utf8Hash" + section.split("function Get-Utf8Hash", 1)[1].split("; try { $contract=", 1)[0]
    # Model the public method surface confirmed by the native Win7 exception:
    # ComputeHash and Clear exist, but Dispose is not publicly callable. This
    # fixture is a host regression, not a claim that host CLR equals Win7 CLR2.
    source = tmp_path / "Clr2HashAlgorithmSurface.cs"
    source.write_text(
        "using System.Security.Cryptography; namespace APSWin7Fixture { "
        "public class Clr2HashAlgorithmSurface { "
        "private readonly SHA256Managed inner = new SHA256Managed(); "
        "public static int ClearCount = 0; "
        "public byte[] ComputeHash(byte[] input) { return inner.ComputeHash(input); } "
        "public void Clear() { ClearCount++; inner.Clear(); } } }",
        encoding="ascii",
    )
    function = function.replace("[System.Security.Cryptography.SHA256]::Create()",
                                "(New-Object APSWin7Fixture.Clr2HashAlgorithmSurface)")
    if cleanup == "Dispose":
        # Negative control: the old BAT must fail on exactly that API surface.
        function = function.replace("$sha.Clear()", "$sha.Dispose()")
    output = tmp_path / "hash-result.txt"
    db_path = str(tmp_path / "数据库 !完整!" / "aps.db")
    token = "instance!中文_token"
    script = "$ErrorActionPreference='Stop'; Add-Type -Path $env:APS_TEST_HASH_SOURCE; " + function
    script += "; $dbHash=Get-Utf8Hash $env:APS_TEST_DB; $tokenHash=Get-Utf8Hash $env:APS_TEST_TOKEN; "
    script += "$lines=@($dbHash,$tokenHash,[string][APSWin7Fixture.Clr2HashAlgorithmSurface]::ClearCount); "
    script += "[IO.File]::WriteAllLines($env:APS_TEST_HASH_OUTPUT,[string[]]$lines,[Text.Encoding]::ASCII)"
    result = subprocess.run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", script,
    ], env=dict(os.environ, APS_TEST_HASH_SOURCE=str(source), APS_TEST_HASH_OUTPUT=str(output),
                 APS_TEST_DB=db_path, APS_TEST_TOKEN=token),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False)
    if expected_success:
        assert result.returncode == 0, result.stderr
        assert output.read_text(encoding="ascii").splitlines() == [
            hashlib.sha256(db_path.encode("utf-8")).hexdigest(),
            hashlib.sha256(token.encode("utf-8")).hexdigest(), "2",
        ]
    else:
        assert result.returncode != 0
        assert b"Dispose" in result.stderr
        assert not output.exists()


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
@pytest.mark.parametrize("case", [
    "same-instance", "other-owner", "other-db", "unknown-process", "unknown-process-unverified", "wrong-health",
])
def test_shared_duplicate_error_waits_then_reuses_only_verified_instance(
        tmp_path, localhost_health_server, tasklist_stub, legacy_parser, case):
    server = localhost_health_server
    contract, health, env = _health_fixture_values(tmp_path, server)
    app_exe = str(tmp_path / "aps.exe")
    lock = tmp_path / "runtime.lock"
    lock_owner = contract["owner"] if case != "other-owner" else "another-owner"
    lock_db = contract["db_path"] if case != "other-db" else contract["db_path"] + ".other"
    lock.write_text(f"pid=3424\nowner={lock_owner}\ndb_path={lock_db}\nexe_path={app_exe}\n", encoding="utf-8")
    tasklist = tmp_path / "tasklist.csv"
    tasklist.write_text('"aps.exe","3424","Console","1","123 K"\n', encoding="ascii")
    error_file = tmp_path / "aps_launch_error.txt"
    error_bytes = "duplicate launch rejected; 原始错误 !完整!\n".encode()
    error_file.write_bytes(error_bytes)
    host, port, contract_path = (tmp_path / name for name in ("host.txt", "port.txt", "contract.json"))
    published = tmp_path / "published.json"
    published.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    if case == "wrong-health":
        health["instance_id"] = "0" * 64
    elif case == "unknown-process-unverified":
        del health["instance_id"]
    server.response_body = json.dumps(health, ensure_ascii=False).encode("utf-8")
    sections = [
        "recover_launch_error", "try_reuse_existing", "try_reuse_active_lock", "try_reuse_active_endpoint",
        "lock_contract_pid_matches", "try_reuse_by_contract", "load_existing_endpoint", "read_host_file",
        "read_port_file", "read_lock_file", "lock_is_active", "read_runtime_contract", "probe_health",
        "probe_app_presence", "block_uncertain", "log",
    ]
    overrides = {}
    if legacy_parser:
        for label in ("probe_health", "probe_app_presence", "read_runtime_contract"):
            overrides[label] = _section(label).replace(
                "if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    body = "call :recover_launch_error\n"
    body += 'set "WAIT_FIRST=%WAIT_EXISTING_STARTUP%"\nset "CAN_REUSE_FIRST=%CAN_REUSE_EXISTING%"\n'
    body += 'powershell -NoProfile -NonInteractive -Command "'
    body += "[IO.File]::WriteAllText($env:HOST_FILE,'127.0.0.1'); "
    body += "[IO.File]::WriteAllText($env:PORT_FILE,$env:APS_TEST_PORT); "
    body += '[IO.File]::Copy($env:APS_TEST_PUBLISHED,$env:RUNTIME_CONTRACT_FILE)"\n'
    body += "call :recover_launch_error"
    env.update(LOCK_FILE=str(lock), HOST_FILE=str(host), PORT_FILE=str(port), APP_EXE=app_exe,
               APP_EXE_NAME="aps.exe", RUNTIME_CONTRACT_FILE=str(contract_path),
               LAUNCH_ERROR_FILE=str(error_file), LAUNCHER_LOG=str(tmp_path / "launcher.log"),
               APS_TEST_TASKLIST=str(tasklist), APS_TEST_TASKLIST_RC="1" if case.startswith("unknown-process") else "0",
               APS_TEST_PORT=str(server.server_port), APS_TEST_PUBLISHED=str(published))
    rows = _run_fixture(tmp_path, body, sections, env, tasklist_stub=tasklist_stub, section_overrides=overrides)
    assert "CAN_REUSE_FIRST" not in rows
    assert error_file.read_bytes() == error_bytes
    if case in {"same-instance", "wrong-health"}:
        assert rows["WAIT_FIRST"] == "1"
    else:
        assert "WAIT_FIRST" not in rows
    if case in {"same-instance", "unknown-process"}:
        assert rows["CAN_REUSE_EXISTING"] == "1"
        assert "WAIT_EXISTING_STARTUP" not in rows
        assert "BLOCKED_BY_UNCERTAIN" not in rows
    else:
        assert "CAN_REUSE_EXISTING" not in rows
        assert rows["BLOCKED_BY_OTHER" if case == "other-owner" else "BLOCKED_BY_UNCERTAIN"] == "1"
    probes = case in {"same-instance", "wrong-health", "unknown-process", "unknown-process-unverified"}
    assert server.requests == (["/system/health"] if probes else [])


@pytest.mark.parametrize("legacy_parser", [False, True], ids=["modern-json", "powershell2-json"])
def test_concurrent_contract_readers_are_isolated_even_with_identical_cmd_random(tmp_path, legacy_parser):
    shared_temp = tmp_path / "shared-temp"
    shared_temp.mkdir()
    section = _section("read_runtime_contract")
    if legacy_parser:
        section = section.replace("if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue)", "if ($false)")
    # Both real protocol writers finish before either reader proceeds. Without
    # a per-launch ID, identical RANDOM seeds make one reader consume the other.
    barrier = "; [IO.File]::WriteAllText($env:APS_TEST_BARRIER_SELF,'done'); "
    barrier += "$deadline=[DateTime]::UtcNow.AddSeconds(10); "
    barrier += "while (-not [IO.File]::Exists($env:APS_TEST_BARRIER_OTHER)) { "
    barrier += "if ([DateTime]::UtcNow -gt $deadline) { throw 'Writer barrier timed out' }; Start-Sleep -Milliseconds 20 }"
    section = section.replace('" >nul 2>nul', barrier + '" >nul 2>nul', 1)

    def run(index):
        root = tmp_path / str(index)
        root.mkdir()
        owner = f"LOCALBOX\\USER{index}"
        contract = root / "runtime.json"
        contract.write_text(json.dumps({
            "contract_version": 1, "pid": 3400 + index, "owner": owner, "host": "127.0.0.1", "port": 5000,
        }), encoding="utf-8")
        body = "call :initialize_launch_id\ncall :read_runtime_contract\n"
        body += 'set "APP_LAUNCH_ID=%LAUNCHER_RUN_ID%"\nset "APP_PROTOCOL_PATH=%CONTRACT_TMP%"'
        return _run_fixture(root, body, ["initialize_launch_id", "read_runtime_contract"], {
            "TEMP": str(shared_temp), "RANDOM": "7", "CURRENT_OWNER": owner, "HAS_POWERSHELL": "1",
            "RUNTIME_CONTRACT_FILE": str(contract),
            "APS_TEST_BARRIER_SELF": str(shared_temp / f"writer-{index}"),
            "APS_TEST_BARRIER_OTHER": str(shared_temp / f"writer-{3-index}"),
        }, section_overrides={"read_runtime_contract": section})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (1, 2)))
    for index, rows in enumerate(results, 1):
        assert rows["CONTRACT_VALID"] == "1"
        assert rows["CONTRACT_PID"] == str(3400 + index)
        assert rows["CONTRACT_OWNER_MATCH"] == "1"
        assert re.fullmatch("[a-f0-9]{32}", rows["APP_LAUNCH_ID"])
        assert rows["APP_LAUNCH_ID"] in rows["APP_PROTOCOL_PATH"]
    assert results[0]["APP_LAUNCH_ID"] != results[1]["APP_LAUNCH_ID"]
    assert results[0]["APP_PROTOCOL_PATH"] != results[1]["APP_PROTOCOL_PATH"]
    assert not list(shared_temp.glob("aps_contract_*.tmp"))
