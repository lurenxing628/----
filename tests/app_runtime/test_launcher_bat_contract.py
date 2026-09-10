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
- 编码合同: 该 bat 刻意保持 UTF-8 无 BOM + LF 行尾 + 第 2 行 chcp 65001,
  任何工具链把它改成带 BOM/CRLF 都会在 Win7 cmd 下产生乱码或解析怪病。

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
        assert '\\"!APP_EXE_NAME!\\",\\"!LOCK_PID!\\",' in section, (
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
        section = _section(text, ":try_reuse_existing")
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
        assert "请稍候片刻后重试" in section
        assert "重启电脑" in section
        assert "维护人员" in section
        assert "%LAUNCHER_LOG%" in section

    def test_wait_existing_timeout_gives_safe_guidance(self) -> None:
        """等待现有实例超时的文案同样只允许安全指引,并留审计日志。"""
        text = _bat_text()
        assert "app_wait_existing_timeout" in text
        assert "等待现有实例就绪超时" in text

    def test_security_semantics_unchanged(self) -> None:
        """异 owner 拒启与 healthy_without_owner_proof 的安全语义不允许被顺手放宽。"""
        text = _bat_text()
        assert "existing_reuse_blocked=other_owner_active" in text
        assert "block_uncertain healthy_without_owner_proof" in text
        assert "block_uncertain lock_owner_missing" in text


class TestBatEncodingContract:
    def test_utf8_no_bom_lf_and_chcp65001(self) -> None:
        """bat 刻意保持 UTF-8 无 BOM + LF 行尾 + 第 2 行 chcp 65001。"""
        raw = _bat_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "bat 不允许带 UTF-8 BOM"
        assert b"\r" not in raw, "bat 必须保持 LF 行尾,不允许 CRLF"
        lines = raw.split(b"\n")
        assert lines[0] == b"@echo off"
        assert lines[1].startswith(b"chcp 65001")
