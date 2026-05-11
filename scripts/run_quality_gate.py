from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_support import (  # noqa: E402
    QUALITY_GATE_MANIFEST_REL,
    QUALITY_GATE_PYRIGHT_GATE_CONFIG,
    QUALITY_GATE_RECEIPTS_DIR_REL,
    QUALITY_GATE_SELFTEST_PATH,
    QUALITY_GATE_STARTUP_REGRESSION_ARGS,
    QUALITY_GATE_TOOL_PATHS,
    QualityGateError,
    apply_quality_gate_manifest_proof_fields,
    build_quality_gate_collection_proof,
    build_quality_gate_command_plan,
    build_quality_gate_command_receipt,
    build_quality_gate_receipt_rel_path,
    iter_quality_gate_required_tests,
    parse_pytest_collect_nodeids,
)
from web.bootstrap import launcher  # noqa: E402

STARTUP_REGRESSION_ARGS = list(QUALITY_GATE_STARTUP_REGRESSION_ARGS)
REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())
GUARD_TEST_ARGS = list(REQUIRED_TEST_ARGS)

PYRIGHT_REQUIRED_VERSION = (1, 1, 406)
PYRIGHT_GATE_CONFIG = QUALITY_GATE_PYRIGHT_GATE_CONFIG
QUALITY_GATE_SELFTEST = QUALITY_GATE_SELFTEST_PATH
GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS = [
    QUALITY_GATE_MANIFEST_REL.replace("\\", "/"),
    QUALITY_GATE_RECEIPTS_DIR_REL.replace("\\", "/") + "/",
]
HIGH_RISK_UNTRACKED_SOURCE_PREFIXES = ("core/", "web/", "data/", "tools/", "scripts/")
HIGH_RISK_UNTRACKED_SOURCE_SUFFIXES = (".py", ".js", ".ts", ".html", ".css", ".sql")


class RuntimeProbeState(str, Enum):
    ABSENT = "absent"
    ACTIVE = "active"
    STALE = "stale"
    UNKNOWN = "unknown"


def _coerce_runtime_probe_state(value: Any) -> RuntimeProbeState:
    if isinstance(value, RuntimeProbeState):
        return value
    normalized = str(value or "").strip().lower()
    for state in RuntimeProbeState:
        if state.value == normalized:
            return state
    raise QualityGateError(f"未知运行时探针状态：{value}")


def _run_command(display: str, args: Sequence[str], capture_output: bool = False) -> Dict[str, Any]:
    print(f"==> {display}")
    completed = subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if capture_output:
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip(), file=sys.stderr)
    elif completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip(), file=sys.stderr)
    return {
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "returncode": int(completed.returncode),
    }


def _coerce_command_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return {
            "stdout": str(result.get("stdout") or ""),
            "stderr": str(result.get("stderr") or ""),
            "returncode": int(result.get("returncode") or 0),
        }
    return {
        "stdout": str(result or ""),
        "stderr": "",
        "returncode": 0,
    }


def _assert_command_succeeded(display: str, result: Dict[str, Any]) -> None:
    if int(result.get("returncode") or 0) != 0:
        raise QualityGateError(f"命令失败：{display}")


def _sha256_file(abs_path: str) -> str:
    hasher = hashlib.sha256()
    with open(abs_path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _quality_gate_manifest_abs_path() -> str:
    return os.path.join(REPO_ROOT, QUALITY_GATE_MANIFEST_REL.replace("/", os.sep))


def _load_json_file(abs_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(abs_path):
        return None
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _command_identity(command: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "display": str(command.get("display") or "").strip(),
        "args": [str(arg) for arg in list(command.get("args") or [])],
        "capture_output": bool(command.get("capture_output")),
        "output_policy": str(command.get("output_policy") or "normalized").strip() or "normalized",
    }


def _commands_match(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return _command_identity(left) == _command_identity(right)


def _load_receipt_payload(receipt_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rel_path = str(receipt_entry.get("path") or "").strip()
    if not rel_path:
        return None
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return None
    if str(receipt_entry.get("sha256") or "") != _sha256_file(abs_path):
        return None
    return _load_json_file(abs_path)


def _resume_state_from_previous_failure(command_plan: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    manifest = _load_json_file(_quality_gate_manifest_abs_path())
    if not manifest or str(manifest.get("status") or "") != "failed":
        return None
    previous_commands = list(manifest.get("commands") or [])
    previous_receipts = list(manifest.get("command_receipts") or [])
    if not previous_commands or not previous_receipts:
        return None

    reusable_receipts: List[Dict[str, Any]] = []
    for index, receipt_entry in enumerate(previous_receipts, start=1):
        if index > len(command_plan) or index > len(previous_commands):
            break
        previous_command = previous_commands[index - 1]
        current_command = command_plan[index - 1]
        if not isinstance(previous_command, dict) or not isinstance(receipt_entry, dict):
            return None
        if not _commands_match(previous_command, current_command):
            return None
        receipt_payload = _load_receipt_payload(receipt_entry)
        if not receipt_payload:
            return None
        if int(receipt_payload.get("returncode") or 0) != 0:
            break
        reusable_receipts.append(receipt_entry)

    skip_count = len(reusable_receipts)
    if skip_count <= 0 or skip_count >= len(command_plan):
        return None
    return {
        "previous_run_id": str(manifest.get("run_id") or ""),
        "previous_failure_message": str(manifest.get("failure_message") or ""),
        "skip_count": skip_count,
        "start_command_index": skip_count + 1,
        "start_command_display": str(command_plan[skip_count].get("display") or ""),
        "command_receipts": reusable_receipts,
        "parsed_command_results": {
            "collection_proof": manifest.get("collection_proof"),
            "ruff_version_output": manifest.get("ruff_version"),
            "pyright_version_output": manifest.get("pyright_version"),
        },
    }


def _write_command_receipt(command: Dict[str, Any], *, run_id: str, index: int, result: Dict[str, Any]) -> Dict[str, str]:
    receipt_rel = build_quality_gate_receipt_rel_path(index, str(command.get("display") or ""))
    receipt_abs = os.path.join(REPO_ROOT, receipt_rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(receipt_abs), exist_ok=True)
    receipt_payload = build_quality_gate_command_receipt(
        command,
        run_id=run_id,
        command_index=index,
        returncode=int(result.get("returncode") or 0),
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
    )
    with open(receipt_abs, "w", encoding="utf-8") as handle:
        json.dump(receipt_payload, handle, ensure_ascii=False, indent=2)
    return {
        "path": receipt_rel,
        "sha256": _sha256_file(receipt_abs),
    }


def _clear_quality_gate_receipts() -> None:
    receipts_abs = os.path.join(REPO_ROOT, QUALITY_GATE_RECEIPTS_DIR_REL)
    if os.path.isdir(receipts_abs):
        shutil.rmtree(receipts_abs)


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
    missing = [path for path in REQUIRED_TEST_ARGS if not _guard_test_exists(path)]
    untracked = [path for path in REQUIRED_TEST_ARGS if path not in missing and not _guard_test_tracked(path)]
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


def _assert_ruff_version(output: Dict[str, Any]) -> str:
    output = _coerce_command_result(output)
    _assert_command_succeeded("python -m ruff --version", output)
    text = str(output.get("stdout") or "").strip()
    version = _parse_ruff_version(text)
    if version < (0, 15, 0) or version >= (0, 16, 0):
        raise QualityGateError(f"ruff 版本超出允许范围 >=0.15,<0.16：{text}")
    return text


def _parse_pyright_version(text: str) -> Tuple[int, int, int]:
    match = re.search(r"pyright\s+([0-9]+)\.([0-9]+)\.([0-9]+)", text)
    if not match:
        raise QualityGateError(f"Unable to parse pyright version output: {text}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _assert_pyright_version(output: Dict[str, Any]) -> str:
    output = _coerce_command_result(output)
    _assert_command_succeeded("python -m pyright --version", output)
    text = str(output.get("stdout") or "").strip()
    version = _parse_pyright_version(text)
    if version != PYRIGHT_REQUIRED_VERSION:
        expected = ".".join(str(part) for part in PYRIGHT_REQUIRED_VERSION)
        raise QualityGateError(f"pyright version must be {expected}, got: {text}")
    return text


CommandResultHandler = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def _handle_checked_quality_gate_command(display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    _assert_command_succeeded(display, result)
    return {}


def _handle_collect_quality_gate_command(_display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    _assert_command_succeeded("python -m pytest --collect-only -q tests", result)
    collect_output = str(result.get("stdout") or "").strip()
    return {"collection_proof": _build_collection_proof(_parse_collect_nodeids(collect_output))}


def _handle_ruff_version_quality_gate_command(_display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"ruff_version_output": _assert_ruff_version(result)}


def _handle_pyright_version_quality_gate_command(_display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"pyright_version_output": _assert_pyright_version(result)}


def _run_quality_gate_command_plan(
    command_plan: Sequence[Dict[str, Any]],
    *,
    run_id: str,
    commands: List[Dict[str, Any]],
    command_receipts: List[Dict[str, str]],
    parsed_command_results: Dict[str, Any],
    resume_state: Optional[Dict[str, Any]] = None,
) -> None:
    command_result_handlers: Dict[str, CommandResultHandler] = {
        str(command["display"]): _handle_checked_quality_gate_command for command in command_plan
    }
    command_result_handlers.update(
        {
            "python -m pytest --collect-only -q tests": _handle_collect_quality_gate_command,
            "python -m ruff --version": _handle_ruff_version_quality_gate_command,
            "python -m pyright --version": _handle_pyright_version_quality_gate_command,
        }
    )
    skip_count = int((resume_state or {}).get("skip_count") or 0)
    if skip_count > 0:
        for index, command in enumerate(command_plan[:skip_count], start=1):
            print(f"==> [resume-skip] {command['display']}")
            commands.append(command)
            command_receipts.append(cast(Dict[str, str], list((resume_state or {}).get("command_receipts") or [])[index - 1]))
        for key, value in dict((resume_state or {}).get("parsed_command_results") or {}).items():
            if value:
                parsed_command_results[key] = value

    for command in command_plan[skip_count:]:
        display = str(command["display"])
        result = _coerce_command_result(
            _run_command(display, _resolve_command_args(command), capture_output=bool(command.get("capture_output")))
        )
        commands.append(command)
        command_receipts.append(_write_command_receipt(command, run_id=run_id, index=len(command_receipts) + 1, result=result))
        parsed_command_results.update(command_result_handlers[display](display, result))


def _require_quality_gate_command_proofs(parsed_command_results: Dict[str, Any]) -> None:
    required_proofs = {
        "python -m pytest --collect-only -q tests": parsed_command_results.get("collection_proof"),
        "python -m ruff --version": parsed_command_results.get("ruff_version_output"),
        "python -m pyright --version": parsed_command_results.get("pyright_version_output"),
    }
    missing_display = next((display for display, value in required_proofs.items() if not value), "")
    if missing_display:
        raise QualityGateError(f"shared command plan 缺少必需证明命令或解析结果：{missing_display}")


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
    pid_state: RuntimeProbeState, health_state: RuntimeProbeState, exe_path: str, port: Optional[int]
) -> str:
    reasons = []
    if pid_state == RuntimeProbeState.UNKNOWN:
        reasons.append("缺少 exe_path 或无法确认 PID 对应可执行文件路径" if not exe_path else "无法确认 PID 对应可执行文件路径")
    if health_state == RuntimeProbeState.ABSENT:
        reasons.append("缺少运行时契约，无法做健康探测")
    if health_state == RuntimeProbeState.UNKNOWN:
        reasons.append("缺少合法 port" if port is None or int(port) <= 0 else "健康探测前置条件不完整")
    return "；".join(reasons)


def _pid_signal(payload: Optional[Dict[str, object]]) -> Tuple[RuntimeProbeState, Optional[int], Optional[bool], str]:
    if not payload:
        return RuntimeProbeState.ABSENT, None, None, ""
    try:
        pid = _coerce_int(payload.get("pid"))
    except Exception as exc:
        raise QualityGateError(f"运行时 pid 非法：{exc}") from exc
    exe_path = str(payload.get("exe_path") or "").strip()
    if pid <= 0:
        return RuntimeProbeState.STALE, pid, False, exe_path
    pid_exists = bool(launcher.runtime_pid_exists(pid))
    if not pid_exists:
        return RuntimeProbeState.STALE, pid, False, exe_path
    if not exe_path:
        return RuntimeProbeState.UNKNOWN, pid, None, exe_path
    pid_match = launcher.runtime_pid_matches_executable(pid, exe_path)
    if pid_match is False:
        return RuntimeProbeState.STALE, pid, False, exe_path
    if pid_match is True:
        return RuntimeProbeState.ACTIVE, pid, True, exe_path
    return RuntimeProbeState.UNKNOWN, pid, None, exe_path


def _health_signal(contract: Optional[Dict[str, object]]) -> Tuple[RuntimeProbeState, Optional[str], Optional[int]]:
    if not contract:
        return RuntimeProbeState.ABSENT, None, None
    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = _coerce_int(contract.get("port"))
    except Exception as exc:
        raise QualityGateError(f"运行时契约 port 非法：{exc}") from exc
    if port <= 0:
        return RuntimeProbeState.UNKNOWN, host, port
    healthy = bool(launcher.probe_runtime_health(host, port, timeout_s=1.0))
    return (RuntimeProbeState.ACTIVE if healthy else RuntimeProbeState.STALE), host, port


def _runtime_state_snapshot() -> Dict[str, Any]:
    contract, lock, paths = _load_runtime_state()
    pid_payload = contract if contract is not None else lock
    pid_state, pid, pid_match, exe_path = _pid_signal(pid_payload)
    health_state, host, port = _health_signal(contract)
    pid_state = _coerce_runtime_probe_state(pid_state)
    health_state = _coerce_runtime_probe_state(health_state)
    return {
        "contract_present": contract is not None,
        "lock_present": lock is not None,
        "pid_state": pid_state.value,
        "pid": pid,
        "pid_matches_executable": pid_match,
        "health_state": health_state.value,
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
    pid_state = _coerce_runtime_probe_state(pid_state)
    health_state = _coerce_runtime_probe_state(health_state)
    endpoint_text = _describe_runtime_endpoint(host, port)
    cleanup_hint = _describe_cleanup_hint(paths)

    if (
        pid_state == RuntimeProbeState.ACTIVE and health_state == RuntimeProbeState.STALE
    ) or (
        pid_state == RuntimeProbeState.STALE and health_state == RuntimeProbeState.ACTIVE
    ):
        raise QualityGateError(
            "活动实例判定出现矛盾："
            f"pid_state={pid_state.value} health_state={health_state.value} pid={pid} {endpoint_text} exe_path={exe_path}。{cleanup_hint}"
        )
    if (
        pid_state == RuntimeProbeState.UNKNOWN and health_state != RuntimeProbeState.ACTIVE
    ) or (
        health_state == RuntimeProbeState.UNKNOWN and pid_state != RuntimeProbeState.ACTIVE
    ):
        reason_text = _describe_uncertain_reason(pid_state, health_state, exe_path, port)
        raise QualityGateError(
            "活动实例判定不确定："
            f"pid_state={pid_state.value} health_state={health_state.value} pid={pid} {endpoint_text} exe_path={exe_path}"
            + (f"；原因：{reason_text}" if reason_text else "")
            + f"。{cleanup_hint}"
        )

    if pid_state == RuntimeProbeState.ACTIVE or health_state == RuntimeProbeState.ACTIVE:
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


def _status_untracked_path(line: str) -> str:
    text = str(line or "").rstrip()
    if not text.startswith("?? "):
        return ""
    return text[3:].strip().replace("\\", "/")


def _high_risk_untracked_source_paths(lines: Sequence[str]) -> List[str]:
    findings = []
    for line in list(lines or []):
        path = _status_untracked_path(str(line))
        if not path:
            continue
        if not path.startswith(HIGH_RISK_UNTRACKED_SOURCE_PREFIXES):
            continue
        if not path.endswith(HIGH_RISK_UNTRACKED_SOURCE_SUFFIXES):
            continue
        findings.append(path)
    return sorted(dict.fromkeys(findings))


def _dirty_worktree_message(lines: Sequence[str]) -> str:
    message = "dirty worktree: clean proof requires an empty worktree before the gate runs"
    high_risk_untracked = _high_risk_untracked_source_paths(lines)
    if high_risk_untracked:
        message += "; untracked source files: " + ", ".join(high_risk_untracked)
    return message


def _parse_collect_nodeids(output: str) -> List[str]:
    return parse_pytest_collect_nodeids(output)


def _build_collection_proof(default_collect_nodeids: Sequence[str]) -> Dict[str, Any]:
    return build_quality_gate_collection_proof(default_collect_nodeids, required_tests=REQUIRED_TEST_ARGS)


def _resolve_command_args(command: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for idx, raw_arg in enumerate(list(command.get("args") or [])):
        arg = str(raw_arg)
        if idx == 0 and arg == "python":
            args.append(sys.executable)
            continue
        args.append(arg)
    return args


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
        "run_id": f"{head_sha}:{started_at}",
        **_repo_identity(),
        "runtime_snapshot": runtime_snapshot,
        "python_version": sys.version.splitlines()[0],
        "python_executable": sys.executable,
        "ruff_version": None,
        "pyright_version": None,
        "started_at": started_at,
        "finished_at": None,
        "collection_proof": None,
        "required_tests": list(REQUIRED_TEST_ARGS),
        "commands": [],
        "gate_sources": [],
        "clean_worktree_excluded_paths": list(GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS),
        "failure_kind": None,
        "failure_message": None,
    }
    _apply_worktree_proof(manifest, git_status_short_before=git_status_short_before, git_status_short_after=None)
    apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
    return manifest


def _parse_args_legacy(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS 质量门禁")
    parser.add_argument("--require-clean-worktree", action="store_true", help="要求当前 worktree 为 clean")
    return parser.parse_args(list(argv) if argv is not None else None)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS quality gate")
    parser.add_argument("--require-clean-worktree", action="store_true", help="require a clean worktree")
    parser.add_argument("--allow-dirty-worktree", action="store_true", help="allow a dirty worktree but mark the run unbound")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="do not reuse the successful prefix from the previous failed dirty-worktree run",
    )
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    if parsed.require_clean_worktree and parsed.allow_dirty_worktree:
        parser.error("--require-clean-worktree and --allow-dirty-worktree are mutually exclusive")
    return parsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    command_plan = build_quality_gate_command_plan()
    resume_state = (
        _resume_state_from_previous_failure(command_plan)
        if bool(args.allow_dirty_worktree and not args.no_resume)
        else None
    )
    started_at = datetime.now().isoformat(timespec="seconds")
    if resume_state:
        print(
            "提示：检测到上次质量门禁失败，本次从第 {index} 个命令继续：{display}".format(
                index=resume_state["start_command_index"],
                display=resume_state["start_command_display"],
            )
        )
    else:
        _clear_quality_gate_receipts()
    head_sha = _git_head_sha()
    run_id = f"{head_sha}:{started_at}"
    git_status_short_before = _git_status_lines()
    runtime_snapshot = _runtime_state_snapshot()
    commands: List[Dict[str, Any]] = []
    command_receipts: List[Dict[str, str]] = []
    collection_proof: Optional[Dict[str, Any]] = None
    ruff_version_output: Optional[str] = None
    pyright_version_output: Optional[str] = None
    parsed_command_results: Dict[str, Any] = {}
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
    manifest["resume"] = {
        "enabled": bool(resume_state),
        "previous_run_id": None if not resume_state else resume_state["previous_run_id"],
        "skip_count": 0 if not resume_state else resume_state["skip_count"],
        "start_command_index": None if not resume_state else resume_state["start_command_index"],
        "start_command_display": None if not resume_state else resume_state["start_command_display"],
        "previous_failure_message": None if not resume_state else resume_state["previous_failure_message"],
        "proof_status": "fast_feedback_only" if resume_state else "full_command_plan",
    }
    _write_quality_gate_manifest(manifest)

    try:
        if require_clean_worktree and git_status_short_before:
            failure_kind = "dirty_before_gate"
            raise QualityGateError(_dirty_worktree_message(git_status_short_before))

        try:
            _assert_no_active_runtime()
        except QualityGateError:
            failure_kind = "environment_blocked"
            raise
        _assert_guard_tests_ready()

        _run_quality_gate_command_plan(
            command_plan,
            run_id=run_id,
            commands=commands,
            command_receipts=command_receipts,
            parsed_command_results=parsed_command_results,
            resume_state=resume_state,
        )
        collection_proof = cast(Optional[Dict[str, Any]], parsed_command_results.get("collection_proof"))
        ruff_version_output = cast(Optional[str], parsed_command_results.get("ruff_version_output"))
        pyright_version_output = cast(Optional[str], parsed_command_results.get("pyright_version_output"))
        _require_quality_gate_command_proofs(parsed_command_results)

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

        success_by_clean_contract = {
            True: ("passed", "质量门禁通过", 0),
            False: (
                "passed_but_unbound",
                "质量门禁完成，但当前证明未绑定；manifest 已标记 passed_but_unbound，不能当作通过证明。",
                2,
            ),
        }
        success_status, success_message, success_return_code = success_by_clean_contract[require_clean_worktree]
        if resume_state:
            success_message = (
                "质量门禁续跑完成；本次跳过了上次已通过的前置命令，只能当作本地快速反馈，不能当作完整通过证明。"
            )
        manifest.update(
            {
                "status": success_status,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "collection_proof": collection_proof,
                "required_tests": list(REQUIRED_TEST_ARGS),
                "commands": commands,
                "command_receipts": command_receipts,
                "ruff_version": ruff_version_output,
                "pyright_version": pyright_version_output,
                "failure_kind": None,
                "failure_message": None,
            }
        )
        apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
        _write_quality_gate_manifest(manifest)
        print(success_message)
        return success_return_code
    except Exception as exc:
        collection_proof = cast(Optional[Dict[str, Any]], parsed_command_results.get("collection_proof"))
        ruff_version_output = cast(Optional[str], parsed_command_results.get("ruff_version_output"))
        pyright_version_output = cast(Optional[str], parsed_command_results.get("pyright_version_output"))
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
                "required_tests": list(REQUIRED_TEST_ARGS),
                "commands": commands,
                "command_receipts": command_receipts,
                "ruff_version": ruff_version_output,
                "pyright_version": pyright_version_output,
                "failure_kind": failure_kind or "quality_gate_failed",
                "failure_message": str(exc),
            }
        )
        apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
        _write_quality_gate_manifest(manifest)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
