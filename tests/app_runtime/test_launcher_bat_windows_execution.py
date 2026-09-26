"""Execute the real launcher subroutines in cmd, with isolated input fixtures.

No application processes are queried, launched or stopped. Windows PowerShell
does parse the actual contract command; these host checks do not replace Win7 QA.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
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


def _run_fixture(tmp_path, body, sections, env, tasklist_stub=None):
    folder = tmp_path / "启动 验收"
    folder.mkdir()
    script = folder / "probe.cmd"
    output = folder / "result.txt"
    code = "@echo off\nchcp 65001 >nul\nsetlocal EnableExtensions EnableDelayedExpansion\n"
    code += body + '\n>"%APS_TEST_OUTPUT%" set CONTRACT_\n'
    code += '>>"%APS_TEST_OUTPUT%" set LOCK_\n'
    code += '>>"%APS_TEST_OUTPUT%" set CAN_REUSE_\n'
    code += '>>"%APS_TEST_OUTPUT%" set BLOCKED_\nexit /b 0\n'
    code += "\n".join(_section(label) for label in sections)
    code += '\n:log\n>>"%APS_TEST_LOG%" echo %*\nexit /b 0\n'
    code += '\n:probe_health\nset "HEALTH_OK=1"\nexit /b 0\n'
    _write_cmd(script, code)
    if tasklist_stub is not None:
        shutil.copyfile(tasklist_stub, folder / "tasklist.exe")
    process_env = dict(os.environ, **env)
    process_env.update(APS_TEST_OUTPUT=str(output), APS_TEST_LOG=str(folder / "log.txt"))
    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(script)],
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
    ('"排产系统.exe","3424","Console","1","123 K"', "3424", "排产系统.exe", 0, "1", None),
    ('"other.exe","3424","Console","1","123 K"', "3424", "aps.exe", 0, "0", None),
    ('"aps.exe","34240","Console","1","123 K"', "3424", "aps.exe", 0, "0", None),
    ('INFO: No tasks are running which match the specified criteria.', "3424", "aps.exe", 0, "0", None),
    ("", "3424", "aps.exe", 1, "UNKNOWN", "tasklist_failed"),
    ("", "invalid", "aps.exe", 0, "UNKNOWN", "lock_pid_invalid"),
])
def test_real_cmd_lock_checks_exact_image_and_pid(tmp_path, tasklist_stub, csv, pid, image, rc, expected, error):
    fixture = tmp_path / "tasklist.csv"
    fixture.write_bytes((csv + "\r\n").encode("utf-8"))
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
    (r"LOCALBOX\other", r"LOCALBOX\Administrator", 1, "other"),
    ("", r"LOCALBOX\Administrator", 1, "invalid"),
    (r"LOCALBOX\Administrator", r"LOCALBOX\Administrator", 2, "invalid"),
])
def test_real_cmd_contract_owner_proof_is_not_lost(tmp_path, owner, current_owner, version, expected):
    contract = tmp_path / "运行 契约.json"
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
])
def test_real_cmd_reuse_dispatch_keeps_other_and_uncertain_owner_blocked(tmp_path, tasklist_stub, lock_owner, image, expected):
    lock = tmp_path / "runtime.lock"
    lock.write_text("pid=3424\nowner=" + lock_owner + "\n", encoding="utf-8")
    host = tmp_path / "host.txt"
    host.write_text("127.0.0.1\n", encoding="ascii")
    port = tmp_path / "port.txt"
    port.write_text("5000\n", encoding="ascii")
    tasklist = tmp_path / "tasklist.csv"
    tasklist.write_text('"' + image + '","3424","Console","1","123 K"\n', encoding="ascii")
    rows = _run_fixture(tmp_path, "call :try_reuse_existing", [
        "try_reuse_existing", "read_lock_file", "lock_is_active", "read_runtime_contract",
        "load_existing_endpoint", "read_host_file", "read_port_file", "try_reuse_by_contract", "block_uncertain",
    ], {
        "APS_TEST_TASKLIST": str(tasklist), "APS_TEST_TASKLIST_RC": "0", "APP_EXE_NAME": "aps.exe",
        "LOCK_FILE": str(lock), "HOST_FILE": str(host), "PORT_FILE": str(port),
        "RUNTIME_CONTRACT_FILE": str(tmp_path / "absent.json"),
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
