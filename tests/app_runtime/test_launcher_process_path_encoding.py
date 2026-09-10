"""回归测试：进程路径查询编码通道（audit 2026-07-19 D02）。

Win7 PowerShell 2.0 的控制台输出编码不可控（OEM/cp936），路径查询不得走
UTF-8 + errors=ignore 文本解码——中文安装路径会被静默吞字，导致
_pid_matches_contract 误判（破锁双实例 / 停止流程拒绝强杀）。合同：
脚本端输出路径 UTF-8 字节的 base64（PS2.0/.NET2.0 即支持，纯 ASCII 不受
控制台代码页影响），Python 端严格解码；任何管道/解码失败必须留痕
（launcher.log）并返回 None（未知），让三态判定走安全侧；中文与纯 ASCII
安装路径均无损往返；bytes 通道不得携带 text/encoding/errors 解码参数。
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from web.bootstrap import launcher_processes as processes

CHINESE_EXE_PATH = "D:\\排产系统\\aps.exe"
ASCII_EXE_PATH = "C:\\APS\\aps.exe"


@pytest.fixture
def launcher_log_path(monkeypatch, tmp_path: Path):
    state_dir = tmp_path / "logs"
    processes.set_process_log_context(state_dir=str(state_dir))
    monkeypatch.setattr("web.bootstrap.launcher_processes.os.name", "nt")
    try:
        yield state_dir / "launcher.log"
    finally:
        processes.set_process_log_context()


def _read_log(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


def _stub_powershell_bytes(
    monkeypatch,
    rc: Optional[int],
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> List[str]:
    scripts: List[str] = []

    def _fake(script: str, timeout_s: float = 8.0) -> Tuple[Optional[int], bytes, bytes]:
        scripts.append(str(script))
        return rc, stdout, stderr

    monkeypatch.setattr(processes, "_run_powershell_bytes", _fake)
    return scripts


def test_chinese_path_base64_roundtrip(monkeypatch, launcher_log_path):
    payload = base64.b64encode(CHINESE_EXE_PATH.encode("utf-8")) + b"\r\n"
    _stub_powershell_bytes(monkeypatch, 0, stdout=payload)

    actual = processes._query_process_executable_path(4321)

    assert actual == os.path.normcase(os.path.abspath(CHINESE_EXE_PATH))
    assert processes._pid_matches_contract(4321, CHINESE_EXE_PATH) is True
    assert _read_log(launcher_log_path) == ""


def test_ascii_path_base64_roundtrip(monkeypatch, launcher_log_path):
    payload = base64.b64encode(ASCII_EXE_PATH.encode("utf-8")) + b"\n"
    _stub_powershell_bytes(monkeypatch, 0, stdout=payload)

    actual = processes._query_process_executable_path(100)

    assert actual == os.path.normcase(os.path.abspath(ASCII_EXE_PATH))
    assert processes._pid_matches_contract(100, ASCII_EXE_PATH) is True
    assert _read_log(launcher_log_path) == ""


def test_mismatched_path_still_returns_false(monkeypatch, launcher_log_path):
    payload = base64.b64encode(CHINESE_EXE_PATH.encode("utf-8"))
    _stub_powershell_bytes(monkeypatch, 0, stdout=payload)

    assert processes._pid_matches_contract(4321, "C:\\其他系统\\other.exe") is False


def test_gbk_bytes_on_stdout_returns_unknown_and_logs(monkeypatch, launcher_log_path):
    # 模拟 PS2.0 控制台按 cp936 输出原始中文路径字节（旧实现 UTF-8+ignore 吞字的
    # 场景）：通道要求 base64（纯 ASCII），GBK 字节必须判"身份未知"并留痕，
    # 不许吞字后拿残缺路径去比对。
    gbk_payload = CHINESE_EXE_PATH.encode("gbk") + b"\r\n"
    _stub_powershell_bytes(monkeypatch, 0, stdout=gbk_payload)

    assert processes._query_process_executable_path(4321) is None
    assert processes._pid_matches_contract(4321, CHINESE_EXE_PATH) is None
    assert "无法确认运行时身份" in _read_log(launcher_log_path)


def test_invalid_base64_ascii_output_returns_unknown_and_logs(monkeypatch, launcher_log_path):
    _stub_powershell_bytes(monkeypatch, 0, stdout=b"not-base64!!\r\n")

    assert processes._query_process_executable_path(4321) is None
    assert "base64 解码失败" in _read_log(launcher_log_path)


def test_base64_of_non_utf8_bytes_returns_unknown_and_logs(monkeypatch, launcher_log_path):
    # b"\xd6\xd0\xce\xc4" 是"中文"的 GBK 编码、非法 UTF-8：脚本端若未按 UTF-8
    # 取字节（错误编码），必须判未知留痕，不许 ignore/replace 兜底。
    payload = base64.b64encode(b"\xd6\xd0\xce\xc4") + b"\n"
    _stub_powershell_bytes(monkeypatch, 0, stdout=payload)

    assert processes._query_process_executable_path(4321) is None
    assert "UTF-8 解码失败" in _read_log(launcher_log_path)


def test_rc2_empty_path_still_returns_empty_string(monkeypatch, launcher_log_path):
    _stub_powershell_bytes(monkeypatch, 2)

    assert processes._query_process_executable_path(4321) == ""
    assert processes._pid_matches_contract(4321, CHINESE_EXE_PATH) is False
    assert "进程路径为空" in _read_log(launcher_log_path)


def test_rc_nonzero_returns_unknown_and_logs(monkeypatch, launcher_log_path):
    # stderr 以原始字节 repr 入日志（不参与任何解码），保住可查原因
    _stub_powershell_bytes(monkeypatch, 1, stderr=b"\xc4\xda\xb2\xbf\xb4\xed\xce\xf3")

    assert processes._query_process_executable_path(4321) is None
    assert "查询进程路径失败" in _read_log(launcher_log_path)


def test_rc0_with_empty_stdout_returns_unknown_and_logs(monkeypatch, launcher_log_path):
    # rc==0 却无输出属管道异常（脚本 rc==0 前必有 Write-Output）：
    # 不许沿用旧实现静默返回 ""（那会被消费端当"路径不匹配"走破锁分支）
    _stub_powershell_bytes(monkeypatch, 0, stdout=b"")

    assert processes._query_process_executable_path(4321) is None
    assert "无输出" in _read_log(launcher_log_path)


def test_query_script_uses_base64_channel_without_console_encoding_trick(monkeypatch, launcher_log_path):
    payload = base64.b64encode(ASCII_EXE_PATH.encode("utf-8"))
    scripts = _stub_powershell_bytes(monkeypatch, 0, stdout=payload)

    processes._query_process_executable_path(4321)

    assert len(scripts) == 1
    script = scripts[0]
    assert "[Console]::OutputEncoding" not in script, "PS2.0 上 OutputEncoding 技巧不可靠，路径通道禁止依赖"
    assert "ToBase64String" in script
    assert "UTF8.GetBytes" in script


def test_run_powershell_bytes_failure_returns_none_and_logs(monkeypatch, launcher_log_path):
    def _boom_run(*_args, **_kwargs):
        raise OSError("powershell missing")

    monkeypatch.setattr("web.bootstrap.launcher_processes.subprocess.run", _boom_run)

    rc, stdout_bytes, stderr_bytes = processes._run_powershell_bytes("Write-Output x")

    assert rc is None
    assert stdout_bytes == b""
    assert stderr_bytes == b""
    assert "PowerShell 运行失败" in _read_log(launcher_log_path)


def test_run_powershell_bytes_returns_raw_bytes_without_text_decode(monkeypatch, launcher_log_path):
    class _Result:
        returncode = 0
        stdout = b"QQ==\r\n"
        stderr = b"\xd6\xd0"  # 原始字节原样带回，不做任何解码

    captured_kwargs = {}

    def _fake_run(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return _Result()

    monkeypatch.setattr("web.bootstrap.launcher_processes.subprocess.run", _fake_run)

    rc, stdout_bytes, stderr_bytes = processes._run_powershell_bytes("Write-Output x")

    assert (rc, stdout_bytes, stderr_bytes) == (0, b"QQ==\r\n", b"\xd6\xd0")
    for forbidden_kwarg in ("text", "encoding", "errors", "universal_newlines"):
        assert forbidden_kwarg not in captured_kwargs, (
            f"bytes 通道不得携带文本解码参数 {forbidden_kwarg}（errors=ignore 吞字是 D02 根因）"
        )
