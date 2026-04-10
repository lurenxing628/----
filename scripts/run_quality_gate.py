from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any, Dict, Optional, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_support import QualityGateError  # noqa: E402
from web.bootstrap import launcher  # noqa: E402

STARTUP_REGRESSION_ARGS = [
    "tests/regression_runtime_probe_resolution.py",
    "tests/test_win7_launcher_runtime_paths.py",
    "tests/regression_runtime_contract_launcher.py",
    "tests/regression_runtime_lock_reloader_parent_skip.py",
    "tests/regression_startup_host_portfile.py",
    "tests/regression_startup_host_portfile_new_ui.py",
    "tests/regression_plugin_bootstrap_config_failure_visible.py",
    "tests/regression_plugin_bootstrap_injects_config_reader.py",
    "tests/regression_plugin_bootstrap_telemetry_failure_visible.py",
    "tests/regression_app_new_ui_secret_key_runtime_ensure.py",
    "tests/regression_app_new_ui_session_contract.py",
    "tests/regression_app_new_ui_security_hardening_enabled.py",
    "tests/test_app_factory_runtime_env_refresh.py",
    "tests/regression_runtime_stop_cli.py",
]


def _run_command(display: str, args: Sequence[str], capture_output: bool = False) -> str:
    print(f"==> {display}")
    completed = subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        errors="replace",
    )
    if capture_output:
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip(), file=sys.stderr)
    if completed.returncode != 0:
        raise QualityGateError(f"命令失败：{display}")
    return (completed.stdout or "").strip() if capture_output else ""


def _parse_ruff_version(text: str) -> Tuple[int, int, int]:
    match = re.search(r"ruff\s+([0-9]+)\.([0-9]+)(?:\.([0-9]+))?", text)
    if not match:
        raise QualityGateError(f"无法解析 ruff 版本输出：{text}")
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return major, minor, patch


def _assert_ruff_version() -> None:
    output = _run_command("python -m ruff --version", [sys.executable, "-m", "ruff", "--version"], capture_output=True)
    version = _parse_ruff_version(output)
    if version < (0, 15, 0) or version >= (0, 16, 0):
        raise QualityGateError(f"ruff 版本超出允许范围 >=0.15,<0.16：{output}")


def _state_paths() -> Dict[str, str]:
    return launcher.resolve_runtime_state_paths(REPO_ROOT)


def _load_runtime_state() -> Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]], Dict[str, str]]:
    paths = _state_paths()
    contract_exists = os.path.exists(paths["contract_path"])
    lock_exists = os.path.exists(paths["lock_path"])
    contract = launcher.read_runtime_contract(REPO_ROOT)
    lock = launcher.read_runtime_lock(REPO_ROOT)
    if contract_exists and contract is None:
        raise QualityGateError("仓库根运行时契约存在但无法解析：{}".format(paths["contract_path"]))
    if lock_exists and lock is None:
        raise QualityGateError("仓库根运行时锁存在但无法解析：{}".format(paths["lock_path"]))
    return contract, lock, paths


def _coerce_int(value: object) -> int:
    if value is None:
        return 0
    return int(cast(Any, value))


def _describe_runtime_endpoint(host: Optional[str], port: Optional[int]) -> str:
    host_text = str(host).strip() if host else "未提供"
    port_text = str(port) if port is not None else "未提供"
    return f"host={host_text} port={port_text}"


def _describe_cleanup_hint(paths: Dict[str, str]) -> str:
    return (
        "请先确认仓库根没有活动 APS 实例；若确认仅为陈旧痕迹，可手动删除后重试："
        f"contract={paths['contract_path']} lock={paths['lock_path']}"
    )


def _describe_uncertain_reason(
    pid_state: str, health_state: str, exe_path: str, port: Optional[int]
) -> str:
    reasons = []
    if pid_state == "unknown":
        reasons.append("缺少 exe_path 或无法确认 PID 对应可执行文件路径" if not exe_path else "无法确认 PID 对应可执行文件路径")
    if health_state == "absent":
        reasons.append("缺少运行时契约，无法做健康探测")
    if health_state == "unknown":
        reasons.append("缺少合法 port" if port is None or int(port) <= 0 else "健康探测前置条件不完整")
    return "；".join(reasons)


def _pid_signal(payload: Optional[Dict[str, object]]) -> Tuple[str, Optional[int], Optional[bool], str]:
    if not payload:
        return "absent", None, None, ""
    try:
        pid = _coerce_int(payload.get("pid"))
    except Exception as exc:
        raise QualityGateError(f"运行时 pid 非法：{exc}") from exc
    exe_path = str(payload.get("exe_path") or "").strip()
    if pid <= 0:
        return "stale", pid, False, exe_path
    pid_exists = bool(launcher.runtime_pid_exists(pid))
    if not pid_exists:
        return "stale", pid, False, exe_path
    if not exe_path:
        return "unknown", pid, None, exe_path
    pid_match = launcher.runtime_pid_matches_executable(pid, exe_path)
    if pid_match is False:
        return "stale", pid, False, exe_path
    if pid_match is True:
        return "active", pid, True, exe_path
    return "unknown", pid, None, exe_path


def _health_signal(contract: Optional[Dict[str, object]]) -> Tuple[str, Optional[str], Optional[int]]:
    if not contract:
        return "absent", None, None
    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = _coerce_int(contract.get("port"))
    except Exception as exc:
        raise QualityGateError(f"运行时契约 port 非法：{exc}") from exc
    if port <= 0:
        return "unknown", host, port
    healthy = bool(launcher.probe_runtime_health(host, port, timeout_s=1.0))
    return ("active" if healthy else "stale"), host, port


def _assert_no_active_runtime() -> None:
    contract, lock, paths = _load_runtime_state()
    if contract is None and lock is None:
        return

    pid_payload = contract if contract is not None else lock
    pid_state, pid, _pid_match, exe_path = _pid_signal(pid_payload)
    health_state, host, port = _health_signal(contract)
    endpoint_text = _describe_runtime_endpoint(host, port)
    cleanup_hint = _describe_cleanup_hint(paths)

    if (pid_state == "active" and health_state == "stale") or (pid_state == "stale" and health_state == "active"):
        raise QualityGateError(
            "活动实例判定出现矛盾："
            f"pid_state={pid_state} health_state={health_state} pid={pid} {endpoint_text} exe_path={exe_path}。{cleanup_hint}"
        )
    if (pid_state == "unknown" and health_state != "active") or (health_state == "unknown" and pid_state != "active"):
        reason_text = _describe_uncertain_reason(pid_state, health_state, exe_path, port)
        raise QualityGateError(
            "活动实例判定不确定："
            f"pid_state={pid_state} health_state={health_state} pid={pid} {endpoint_text} exe_path={exe_path}"
            + (f"；原因：{reason_text}" if reason_text else "")
            + f"。{cleanup_hint}"
        )

    if pid_state == "active" or health_state == "active":
        raise QualityGateError(
            f"检测到仓库根存在活动 APS 实例，请先退出后再执行门禁：pid={pid} {endpoint_text} exe_path={exe_path}"
        )

    print(
        "提示：检测到仓库根存在陈旧运行时痕迹，将继续执行；未自动删除：contract={} lock={}".format(paths["contract_path"], paths["lock_path"])
    )


def main() -> int:
    _assert_no_active_runtime()
    _assert_ruff_version()
    _run_command("python -c \"import radon\"", [sys.executable, "-c", "import radon"])  # 明确阻断缺依赖
    _run_command("python -m ruff check", [sys.executable, "-m", "ruff", "check"])
    _run_command(
        "python -m pytest -q tests/test_architecture_fitness.py",
        [sys.executable, "-m", "pytest", "-q", "tests/test_architecture_fitness.py"],
    )
    _run_command(
        "python scripts/sync_debt_ledger.py check",
        [sys.executable, "scripts/sync_debt_ledger.py", "check"],
    )
    _run_command(
        "python -m pytest -q " + " ".join(STARTUP_REGRESSION_ARGS),
        [sys.executable, "-m", "pytest", "-q"] + STARTUP_REGRESSION_ARGS,
    )
    _run_command(
        "python tests/check_quickref_vs_routes.py",
        [sys.executable, "tests/check_quickref_vs_routes.py"],
    )
    print("质量门禁通过")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
