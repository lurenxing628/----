from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_support import (  # noqa: E402
    QUALITY_GATE_GUARD_TESTS,
    QUALITY_GATE_MANIFEST_REL,
    QUALITY_GATE_SELFTEST_PATH,
    QualityGateError,
)
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

GUARD_TEST_ARGS = list(QUALITY_GATE_GUARD_TESTS)

PYRIGHT_REQUIRED_VERSION = (1, 1, 406)
PYRIGHT_GATE_CONFIG = "pyrightconfig.gate.json"
QUALITY_GATE_TOOL_PATHS = [
    "scripts/run_quality_gate.py",
    "tools/quality_gate_shared.py",
]
QUALITY_GATE_SELFTEST = QUALITY_GATE_SELFTEST_PATH


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


def _guard_test_abs_path(rel_path: str) -> str:
    return os.path.join(REPO_ROOT, rel_path)


def _guard_test_exists(rel_path: str) -> bool:
    return os.path.isfile(_guard_test_abs_path(rel_path))


def _guard_test_tracked(rel_path: str) -> bool:
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", rel_path],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def _git_rev_parse_path(*args: str, fallback: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    raw_value = str(completed.stdout or "").strip()
    if completed.returncode == 0 and raw_value:
        path_text = raw_value
        if not os.path.isabs(path_text):
            path_text = os.path.join(REPO_ROOT, path_text)
        return os.path.realpath(path_text)
    return os.path.realpath(fallback)


def _repo_identity() -> Dict[str, str]:
    return {
        "checkout_root_realpath": _git_rev_parse_path("--show-toplevel", fallback=REPO_ROOT),
        "git_common_dir_realpath": _git_rev_parse_path("--git-common-dir", fallback=os.path.join(REPO_ROOT, ".git")),
    }


def _assert_guard_tests_ready() -> None:
    missing = [path for path in GUARD_TEST_ARGS if not _guard_test_exists(path)]
    untracked = [path for path in GUARD_TEST_ARGS if path not in missing and not _guard_test_tracked(path)]
    if not missing and not untracked:
        return

    parts = []
    if missing:
        parts.append("missing=" + ", ".join(missing))
    if untracked:
        parts.append("untracked=" + ", ".join(untracked))
    raise QualityGateError("guard test preflight failed: " + "; ".join(parts))


def _parse_ruff_version(text: str) -> Tuple[int, int, int]:
    match = re.search(r"ruff\s+([0-9]+)\.([0-9]+)(?:\.([0-9]+))?", text)
    if not match:
        raise QualityGateError(f"无法解析 ruff 版本输出：{text}")
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return major, minor, patch


def _assert_ruff_version() -> str:
    output = _run_command("python -m ruff --version", [sys.executable, "-m", "ruff", "--version"], capture_output=True)
    version = _parse_ruff_version(output)
    if version < (0, 15, 0) or version >= (0, 16, 0):
        raise QualityGateError(f"ruff 版本超出允许范围 >=0.15,<0.16：{output}")
    return output


def _parse_pyright_version(text: str) -> Tuple[int, int, int]:
    match = re.search(r"pyright\s+([0-9]+)\.([0-9]+)\.([0-9]+)", text)
    if not match:
        raise QualityGateError(f"Unable to parse pyright version output: {text}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _assert_pyright_version() -> str:
    output = _run_command("python -m pyright --version", [sys.executable, "-m", "pyright", "--version"], capture_output=True)
    version = _parse_pyright_version(output)
    if version != PYRIGHT_REQUIRED_VERSION:
        expected = ".".join(str(part) for part in PYRIGHT_REQUIRED_VERSION)
        raise QualityGateError(f"pyright version must be {expected}, got: {output}")
    return output


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


def _runtime_state_snapshot() -> Dict[str, Any]:
    contract, lock, paths = _load_runtime_state()
    pid_payload = contract if contract is not None else lock
    pid_state, pid, pid_match, exe_path = _pid_signal(pid_payload)
    health_state, host, port = _health_signal(contract)
    return {
        "contract_present": contract is not None,
        "lock_present": lock is not None,
        "pid_state": pid_state,
        "pid": pid,
        "pid_matches_executable": pid_match,
        "health_state": health_state,
        "host": host,
        "port": port,
        "exe_path": exe_path,
        "paths": paths,
    }


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


def _git_head_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise QualityGateError("无法读取当前 HEAD SHA")
    return str(completed.stdout or "").strip()


def _git_status_lines() -> List[str]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise QualityGateError("无法读取 git status --short")
    return [str(line).rstrip() for line in str(completed.stdout or "").splitlines() if str(line).strip()]


def _tracked_status_lines(lines: Sequence[str]) -> List[str]:
    normalized = [str(line).rstrip() for line in list(lines or []) if str(line).strip()]
    return [line for line in normalized if not line.startswith("?? ")]


def _parse_collect_nodeids(output: str) -> List[str]:
    nodeids: List[str] = []
    seen = set()
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("="):
            continue
        if "collected " in line:
            continue
        token = line.split()[0]
        if not token.startswith("tests/"):
            continue
        if token in seen:
            continue
        seen.add(token)
        nodeids.append(token)
    return nodeids


def _build_collection_proof(default_collect_nodeids: Sequence[str]) -> Dict[str, Any]:
    collected = [str(item).strip() for item in default_collect_nodeids if str(item).strip()]
    key_tests = [QUALITY_GATE_SELFTEST] + list(GUARD_TEST_ARGS)
    key_test_rows: List[Dict[str, Any]] = []
    for path in key_tests:
        in_default_collect = any(nodeid == path or nodeid.startswith(f"{path}::") for nodeid in collected)
        key_test_rows.append(
            {
                "path": path,
                "execution_mode": "default_collect" if in_default_collect else "explicit_run",
            }
        )
    return {
        "default_collect_nodeids": collected,
        "key_tests": key_test_rows,
    }


def _write_quality_gate_manifest(manifest: Dict[str, Any]) -> None:
    manifest_path = os.path.join(REPO_ROOT, QUALITY_GATE_MANIFEST_REL)
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _apply_worktree_proof(
    manifest: Dict[str, Any],
    *,
    git_status_short_before: Sequence[str],
    git_status_short_after: Optional[Sequence[str]],
) -> None:
    before = [str(line).rstrip() for line in list(git_status_short_before or []) if str(line).strip()]
    after = None
    if git_status_short_after is not None:
        after = [str(line).rstrip() for line in list(git_status_short_after or []) if str(line).strip()]
    manifest.update(
        {
            "git_status_short_before": before,
            "is_dirty_before": bool(before),
            "git_status_short_after": after,
            "is_dirty_after": None if after is None else bool(after),
            "tracked_drift_detected": None if after is None else (_tracked_status_lines(before) != _tracked_status_lines(after)),
        }
    )


def _base_quality_gate_manifest(
    *,
    started_at: str,
    head_sha: str,
    git_status_short_before: Sequence[str],
    runtime_snapshot: Dict[str, Any],
    status: str,
) -> Dict[str, Any]:
    manifest = {
        "status": str(status or "").strip() or "running",
        "head_sha": head_sha,
        **_repo_identity(),
        "runtime_snapshot": runtime_snapshot,
        "python_version": sys.version.splitlines()[0],
        "python_executable": sys.executable,
        "ruff_version": None,
        "pyright_version": None,
        "started_at": started_at,
        "finished_at": None,
        "collection_proof": None,
        "commands": [],
        "failure_kind": None,
        "failure_message": None,
    }
    _apply_worktree_proof(manifest, git_status_short_before=git_status_short_before, git_status_short_after=None)
    return manifest


def _parse_args_legacy(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS 质量门禁")
    parser.add_argument("--require-clean-worktree", action="store_true", help="要求当前 worktree 为 clean")
    return parser.parse_args(list(argv) if argv is not None else None)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS quality gate")
    parser.add_argument("--require-clean-worktree", action="store_true", help="require a clean worktree")
    parser.add_argument("--allow-dirty-worktree", action="store_true", help="allow a dirty worktree but mark the run unbound")
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    if parsed.require_clean_worktree and parsed.allow_dirty_worktree:
        parser.error("--require-clean-worktree and --allow-dirty-worktree are mutually exclusive")
    return parsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    started_at = datetime.now().isoformat(timespec="seconds")
    head_sha = _git_head_sha()
    git_status_short_before = _git_status_lines()
    runtime_snapshot = _runtime_state_snapshot()
    commands: List[Dict[str, Any]] = []
    collection_proof: Optional[Dict[str, Any]] = None
    ruff_version_output: Optional[str] = None
    pyright_version_output: Optional[str] = None
    failure_kind: Optional[str] = None
    git_status_short_after: Optional[List[str]] = None
    require_clean_worktree = bool(args.require_clean_worktree or not args.allow_dirty_worktree)
    manifest = _base_quality_gate_manifest(
        started_at=started_at,
        head_sha=head_sha,
        git_status_short_before=git_status_short_before,
        runtime_snapshot=runtime_snapshot,
        status="running",
    )
    _write_quality_gate_manifest(manifest)

    try:
        if require_clean_worktree and git_status_short_before:
            raise QualityGateError("dirty worktree: clean proof requires an empty worktree before the gate runs")

        try:
            _assert_no_active_runtime()
        except QualityGateError:
            failure_kind = "environment_blocked"
            raise
        _assert_guard_tests_ready()

        collect_display = "python -m pytest --collect-only -q tests"
        collect_args = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"]
        collect_output = _run_command(collect_display, collect_args, capture_output=True)
        commands.append({"display": collect_display, "args": collect_args, "capture_output": True})
        collection_proof = _build_collection_proof(_parse_collect_nodeids(collect_output))

        ruff_version_output = _assert_ruff_version()
        commands.append(
            {
                "display": "python -m ruff --version",
                "args": [sys.executable, "-m", "ruff", "--version"],
                "capture_output": True,
            }
        )
        pyright_version_output = _assert_pyright_version()
        commands.append(
            {
                "display": "python -m pyright --version",
                "args": [sys.executable, "-m", "pyright", "--version"],
                "capture_output": True,
            }
        )

        run_steps = [
            ('python -c "import radon"', [sys.executable, "-c", "import radon"], False),
            ("python -m ruff check", [sys.executable, "-m", "ruff", "check"], False),
            (
                f"python -m pyright -p {PYRIGHT_GATE_CONFIG}",
                [sys.executable, "-m", "pyright", "-p", PYRIGHT_GATE_CONFIG],
                False,
            ),
            (
                "python -m pyright " + " ".join(QUALITY_GATE_TOOL_PATHS),
                [sys.executable, "-m", "pyright"] + QUALITY_GATE_TOOL_PATHS,
                False,
            ),
            (
                "python -m pytest -q tests/test_architecture_fitness.py",
                [sys.executable, "-m", "pytest", "-q", "tests/test_architecture_fitness.py"],
                False,
            ),
            (
                "python -m pytest -q " + " ".join(GUARD_TEST_ARGS),
                [sys.executable, "-m", "pytest", "-q"] + GUARD_TEST_ARGS,
                False,
            ),
            (
                f"python -m pytest -q {QUALITY_GATE_SELFTEST}",
                [sys.executable, "-m", "pytest", "-q", QUALITY_GATE_SELFTEST],
                False,
            ),
            (
                "python scripts/sync_debt_ledger.py check",
                [sys.executable, "scripts/sync_debt_ledger.py", "check"],
                False,
            ),
            (
                "python -m pytest -q " + " ".join(STARTUP_REGRESSION_ARGS),
                [sys.executable, "-m", "pytest", "-q"] + STARTUP_REGRESSION_ARGS,
                False,
            ),
            (
                "python tests/check_quickref_vs_routes.py",
                [sys.executable, "tests/check_quickref_vs_routes.py"],
                False,
            ),
        ]

        for display, cmd, capture_output in run_steps:
            _run_command(display, cmd, capture_output=capture_output)
            commands.append({"display": display, "args": cmd, "capture_output": bool(capture_output)})

        git_status_short_after = _git_status_lines()
        _apply_worktree_proof(
            manifest,
            git_status_short_before=git_status_short_before,
            git_status_short_after=git_status_short_after,
        )
        if bool(manifest.get("tracked_drift_detected")):
            failure_kind = "tracked_drift_detected"
            raise QualityGateError("tracked drift detected during quality gate execution")
        if require_clean_worktree and git_status_short_after:
            failure_kind = "dirty_after_gate"
            raise QualityGateError("dirty worktree: clean proof requires an empty worktree after the gate runs")

        manifest.update(
            {
                "status": "passed" if require_clean_worktree else "passed_but_unbound",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "collection_proof": collection_proof,
                "commands": commands,
                "ruff_version": ruff_version_output,
                "pyright_version": pyright_version_output,
                "failure_kind": None,
                "failure_message": None,
            }
        )
        _write_quality_gate_manifest(manifest)
        print("质量门禁通过")
        return 0
    except Exception as exc:
        if git_status_short_after is None:
            try:
                git_status_short_after = _git_status_lines()
            except QualityGateError:
                git_status_short_after = list(git_status_short_before or [])
        _apply_worktree_proof(
            manifest,
            git_status_short_before=git_status_short_before,
            git_status_short_after=git_status_short_after,
        )
        manifest.update(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "collection_proof": collection_proof,
                "commands": commands,
                "ruff_version": ruff_version_output,
                "pyright_version": pyright_version_output,
                "failure_kind": failure_kind or "quality_gate_failed",
                "failure_message": str(exc),
            }
        )
        _write_quality_gate_manifest(manifest)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
