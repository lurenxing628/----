"""启动器 bat 文本合同(防倒退)——盲区清扫 B06/B11 修复钉子。

`assets/启动_排产系统_Chrome.bat` 无法在 macOS/CI 上真实执行,本测试以 UTF-8
读取脚本源码做文本级断言,钉住以下已修复行为,防止后续改动倒退:

- B06: `:lock_is_active` 不允许只按 PID 判活——必须把 tasklist CSV 的映像名列
  与 APP_EXE_NAME 比对;PID 被无关进程复用(崩溃残留锁的典型形态)时按陈旧锁
  处理,并写 `lock_pid_image_mismatch` 审计日志留痕。
- B11: 『同 owner + 锁活 + 端点缺失』是应用启动窗口期,必须走等待/复用路径
  (WAIT_EXISTING_STARTUP → :WAIT_APP_READY),不允许再落 block_uncertain;
  阻断/超时文案不允许再出现『清理运行时信号』这类教用户删活实例信号文件的
  危险指引,只给『稍候重试/重启电脑/联系维护人员并附 launcher.log』的安全指引。
  异 owner 拒启与 healthy_without_owner_proof 的安全语义保持不变。
- 编码合同: ASCII BAT、保留控制台代码页、显式 UTF-8 日志；Git 内部规范化为 LF，
  Windows checkout / 交付包使用 CRLF。真实 cmd 行为另由执行测试覆盖。

这是文本合同测试:断言的是脚本源码里的关键 token 与结构,不是运行时行为。
"""

from __future__ import annotations

import re

from tests._support.paths import REPO_ROOT

BAT_PATH = REPO_ROOT / "assets" / "启动_排产系统_Chrome.bat"


def _bat_bytes() -> bytes:
    return BAT_PATH.read_bytes()


def _bat_text() -> str:
    return BAT_PATH.read_text(encoding="utf-8")


def _section(text: str, label: str) -> str:
    """取 bat 中某个标签到下一个行首标签之间的正文。"""
    marker = "\n" + label + "\n"
    assert marker in text, f"bat 缺少标签 {label}"
    body = text[text.index(marker) + len(marker):]
    nxt = re.search(r"^:[A-Za-z_]", body, flags=re.M)
    return body[: nxt.start()] if nxt else body


class TestB06LockActivityImageNameContract:
    def test_lock_is_active_compares_image_name_not_only_pid(self) -> None:
        """锁活性判定必须包含『映像名+PID』组合匹配 token,不允许退回只查 PID。"""
        section = _section(_bat_text(), ":lock_is_active")
        assert 'if "%%~O"=="%LOCK_PID%"' in section and 'if /I "%%~N"=="%APP_EXE_NAME%"' in section, (
            ":lock_is_active 必须用 tasklist CSV 的映像名列与 APP_EXE_NAME 组合比对,"
            "防止崩溃残留锁的 PID 被无关进程复用后误判为活实例(B06)"
        )

    def test_pid_reuse_mismatch_leaves_audit_trail(self) -> None:
        """PID 命中但映像名不匹配时按陈旧锁处理,必须写审计日志留痕。"""
        section = _section(_bat_text(), ":lock_is_active")
        assert "lock_pid_image_mismatch" in section
        assert "LOCK_PID_IMAGE_MISMATCH" in section

    def test_app_exe_name_is_derived_from_app_exe(self) -> None:
        """APP_EXE_NAME 必须从既有 APP_EXE 变量派生(文件名部分),供比对使用。"""
        text = _bat_text()
        assert 'set "APP_EXE_NAME=%%~nxI"' in text


class TestB11StartupWindowContract:
    def test_no_dangerous_runtime_signal_cleanup_guidance(self) -> None:
        """全文不允许出现教用户删运行时信号文件的危险指引(B11)。"""
        assert "清理运行时信号" not in _bat_text()

    def test_lock_active_missing_endpoint_waits_instead_of_blocking(self) -> None:
        """『同 owner + 锁活 + 端点缺失』= 启动窗口期,必须等待而非 block_uncertain。"""
        text = _bat_text()
        section = _section(text, ":try_reuse_active_lock")
        assert "block_uncertain lock_active_missing_host" not in text
        assert "block_uncertain lock_active_missing_port" not in text
        for reason in ("lock_active_missing_host", "lock_active_missing_port"):
            assert "existing_reuse_wait=" + reason in section, (
                f"{reason} 分支必须记录等待日志而非 block_uncertain(B11)"
            )
        assert 'set "WAIT_EXISTING_STARTUP=1"' in section

    def test_main_flow_reenters_existing_wait_loop(self) -> None:
        """主流程必须消费 WAIT_EXISTING_STARTUP 标志并重入既有端点等待循环。"""
        text = _bat_text()
        assert "if defined WAIT_EXISTING_STARTUP" in text
        assert "goto :WAIT_APP_READY" in text
        assert "\n:WAIT_APP_READY\n" in text
        # 等待循环标签必须位于既有 readiness 循环之前(复用同一循环)
        assert text.index("\n:WAIT_APP_READY\n") < text.index("Waiting for app readiness")

    def test_blocked_uncertain_gives_safe_guidance(self) -> None:
        """block 文案只允许安全指引:稍候重试/重启电脑/联系维护人员附日志。"""
        section = _section(_bat_text(), ":BLOCKED_UNCERTAIN")
        assert "Retry later" in section
        assert "restart the computer" in section
        assert "Contact support" in section
        assert "%LAUNCHER_LOG%" in section

    def test_wait_existing_timeout_gives_safe_guidance(self) -> None:
        """等待现有实例超时的文案同样只允许安全指引,并留审计日志。"""
        text = _bat_text()
        assert "app_wait_existing_timeout" in text
        assert "Timed out waiting for the existing instance" in text

    def test_security_semantics_unchanged(self) -> None:
        """异 owner 拒启与 healthy_without_owner_proof 的安全语义不允许被顺手放宽。"""
        text = _bat_text()
        assert "existing_reuse_blocked=other_owner_active" in text
        assert "block_uncertain healthy_without_owner_proof" in text
        assert "block_uncertain lock_owner_missing" in text


class TestBatEncodingContract:
    def test_ascii_bat_preserves_console_codepage_and_bang_paths(self) -> None:
        """源码可按 Git 规范化为 LF，执行入口的 CRLF 由 Git 属性和打包保证。"""
        raw = _bat_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "bat 不允许带 UTF-8 BOM"
        raw.decode("ascii", errors="strict")
        lines = raw.splitlines()
        assert lines[0] == b"@echo off"
        assert b"chcp" not in raw.lower()
        assert b"setlocal EnableExtensions DisableDelayedExpansion" in raw
        assert b"EnableDelayedExpansion" not in raw

    def test_logs_are_written_as_utf8_independently_of_console(self) -> None:
        section = _section(_bat_text(), ":log")
        assert "System.Text.UTF8Encoding($false)" in section
        assert "System.IO.FileMode]::Append" in section
        assert "System.IO.FileShare]::ReadWrite" in section
        assert '>>"%LAUNCHER_LOG%" echo' not in section

    def test_development_entries_preserve_codepage_paths_and_exit_status(self) -> None:
        for filename in ("start.bat", "start_new_ui.bat"):
            raw = (REPO_ROOT / filename).read_bytes()
            raw.decode("ascii", errors="strict")
            assert b"chcp" not in raw.lower()
            assert b"DisableDelayedExpansion" in raw
            assert b'cd /d "%~dp0"' in raw
            assert b"exit /b %" in raw

    def test_windows_launcher_checkout_uses_crlf(self) -> None:
        attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        assert "/assets/*.bat text eol=crlf" in attributes


class TestHealthIdentityContract:
    def test_probe_uses_fresh_contract_and_complete_json_identity(self) -> None:
        section = _section(_bat_text(), ":probe_health")
        assert "$env:RUNTIME_CONTRACT_FILE" in section
        assert "JavaScriptSerializer" in section
        assert "OrdinalIgnoreCase" in section
        assert "Get-Utf8Hash $dbPath" in section
        assert "Get-Utf8Hash $token" in section
        assert "finally { $sha.Clear() }" in section
        assert "$sha.Dispose()" not in section
        assert "[System.IO.Path]::GetFullPath($env:APS_DB_PATH).ToLowerInvariant()" in section
        assert "[string]::Equals($expectedDb,$dbPath,[System.StringComparison]::Ordinal)" in section
        assert "$healthPid -ne $contractPid" in section
        assert "$uri.Port -ne $contractPort" in section
        assert "$req.AllowAutoRedirect=$false" in section
        assert "-match" not in section
        for line in section.splitlines():
            assert len(line.encode("ascii")) < 8191, "CMD command line limit"

    def test_presence_is_separate_from_identity_and_only_blocks(self) -> None:
        text = _bat_text()
        presence = _section(text, ":probe_app_presence")
        assert "JavaScriptSerializer" in presence
        assert 'set "HEALTH_APP_DETECTED=1"' in presence
        assert 'set "HEALTH_OK=1"' not in presence
        assert "-match" not in presence
        dispatch = _section(text, ":try_reuse_existing")
        assert "call :probe_app_presence" in dispatch
        assert "if defined HEALTH_APP_DETECTED" in dispatch
        assert "block_uncertain healthy_without_owner_proof" in dispatch

    def test_recovery_is_real_503_read_only_and_separately_reported(self) -> None:
        section = _section(_bat_text(), ":probe_health")
        assert "catch [System.Net.WebException]" in section
        assert "$resp=$_.Exception.Response" in section
        assert "$responseStatus -eq 503" in section
        assert "'recovery_required'" in section
        assert "$available -isnot [bool]" in section
        assert "$available -ne $false" in section
        assert 'set "HEALTH_RECOVERY_READY=1"' in section
        assert 'call :log health_recovery_ready=' in section


class TestDuplicateStartupContract:
    def test_protocol_files_are_isolated_per_launcher_not_only_cmd_random(self) -> None:
        text = _bat_text()
        assert text.index("call :initialize_launch_id") < text.index("call :probe_chrome_profile_dir")
        initialize = _section(text, ":initialize_launch_id")
        assert 'set "LAUNCHER_RUN_ID="' in initialize
        assert "[Guid]::NewGuid()" in initialize
        for line in text.splitlines():
            if line.startswith('set "') and "%RANDOM%" in line:
                assert "%LAUNCHER_RUN_ID%" in line

    def test_shared_error_never_overrides_ready_identity_or_verified_startup(self) -> None:
        text = _bat_text()
        wait = _section(text, ":WAIT_APP_READY")
        assert wait.index("call :poll_app_ready") < wait.index('if exist "%LAUNCH_ERROR_FILE%"')
        assert "call :recover_launch_error" in wait
        assert "if not defined WAIT_EXISTING_STARTUP goto :APP_START_FAILED" in wait
        assert 'del /f /q "%LAUNCH_ERROR_FILE%"' not in text
        assert 'del /f /q "%PORT_FILE%"' not in text
        assert 'del /f /q "%HOST_FILE%"' not in text
        recovery = _section(text, ":recover_launch_error")
        assert "call :try_reuse_existing" in recovery
        active = _section(text, ":try_reuse_active_lock")
        assert 'if not "%LOCK_DB_MATCH%"=="1"' in active
        assert 'if not "%LOCK_EXE_MATCH%"=="1"' in active

    def test_duplicate_recovery_preserves_original_browser_open_semantics(self) -> None:
        text = _bat_text()
        opening = _section(text, ":OPEN_CHROME")
        assert "INITIAL_OPEN_REQUEST" not in text
        assert 'start "" /D "%CHROME_RUN_DIR%" "%CHROME_EXE%"' in opening
        assert "call :probe_aps_chrome_alive" in opening
        for line in text.splitlines():
            assert len(line.encode("ascii")) < 8191
