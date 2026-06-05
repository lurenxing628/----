from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared  # noqa: E402
from tools.architecture_scan_cache import architecture_scan_cache_metadata  # noqa: E402
from tools.long_gate_cache import evaluate_failure_reuse, evaluate_reuse  # noqa: E402
from tools.long_gate_cache import resolve_cache_dir as resolve_long_gate_cache_dir
from tools.long_gate_cache import write_failure as write_long_gate_failure
from tools.long_gate_cache import write_success as write_long_gate_success
from tools.long_gate_collect import (  # noqa: E402
    COLLECT_NODEIDS_REL,
    build_collect_nodeids_payload,
    write_collect_nodeids,
)
from tools.long_gate_fingerprint import (  # noqa: E402
    LongGateFingerprintError,
    fingerprint_entry,
    pytest_distribution_version,
)
from tools.long_gate_manifest import (  # noqa: E402
    ENTRY_DEBT_LEDGER_SYNC,
    ENTRY_FULL_TEST_DEBT,
    ENTRY_PYRIGHT_GATE_FULL,
    ENTRY_PYRIGHT_TOOLS_FULL,
    ENTRY_PYTEST_COLLECT_ALL,
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_RUFF_CHECK_FULL,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    build_manifest_from_quality_gate_plan,
    explain_long_gate_impact,
)
from tools.long_gate_schema import stable_json_hash  # noqa: E402
from tools.long_gate_summary import (  # noqa: E402
    build_long_gate_summary,
    build_summary_entry,
    extract_copyable_failure,
    write_long_gate_summary,
)
from tools.quality_gate_support import (  # noqa: E402
    LEDGER_PATH,
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    QUALITY_GATE_DEBT_LEDGER_SYNC_REL,
    QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL,
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
    QUALITY_GATE_LOGS_DIR_REL,
    QUALITY_GATE_MANIFEST_REL,
    QUALITY_GATE_PYRIGHT_GATE_CONFIG,
    QUALITY_GATE_PYRIGHT_GATE_FULL_REL,
    QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
    QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL,
    QUALITY_GATE_QUICKREF_VS_ROUTES_REL,
    QUALITY_GATE_RECEIPTS_DIR_REL,
    QUALITY_GATE_REQUIRED_REGRESSIONS_REL,
    QUALITY_GATE_RUFF_CHECK_FULL_REL,
    QUALITY_GATE_SELFTEST_PATH,
    QUALITY_GATE_STARTUP_REGRESSION_ARGS,
    QUALITY_GATE_STARTUP_RUNTIME_REGRESSIONS_REL,
    QUALITY_GATE_TOOL_PATHS,
    QualityGateError,
    apply_quality_gate_manifest_proof_fields,
    build_quality_gate_collection_proof,
    build_quality_gate_command_plan,
    build_quality_gate_command_receipt,
    build_quality_gate_receipt_rel_path,
    hash_quality_gate_commands,
    iter_quality_gate_required_tests,
    parse_pytest_collect_nodeids,
)
from web.bootstrap import launcher  # noqa: E402

STARTUP_REGRESSION_ARGS = list(QUALITY_GATE_STARTUP_REGRESSION_ARGS)
REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())
GUARD_TEST_ARGS = list(REQUIRED_TEST_ARGS)

PYRIGHT_REQUIRED_VERSION = (1, 1, 406)
PYRIGHT_GATE_CONFIG = QUALITY_GATE_PYRIGHT_GATE_CONFIG
PYRIGHT_TOOLS_CONFIG = QUALITY_GATE_PYRIGHT_TOOLS_CONFIG
QUALITY_GATE_SELFTEST = QUALITY_GATE_SELFTEST_PATH
PYTEST_COLLECT_ALL_DISPLAY = "python -m pytest --collect-only -q tests"
STARTUP_RUNTIME_REGRESSIONS_PROOF_SCHEMA_VERSION = 1
REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION = 4
STATIC_CHECK_PROOF_SCHEMA_VERSION = 1
DEBT_LEDGER_SYNC_PROOF_SCHEMA_VERSION = 1
GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS = [
    QUALITY_GATE_MANIFEST_REL.replace("\\", "/"),
    QUALITY_GATE_RECEIPTS_DIR_REL.replace("\\", "/") + "/",
    QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/") + "/",
    COLLECT_NODEIDS_REL.replace("\\", "/"),
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"),
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL.replace("\\", "/"),
    QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL.replace("\\", "/"),
    "evidence/QualityGate/architecture_scan_cache.json",
    QUALITY_GATE_STARTUP_RUNTIME_REGRESSIONS_REL.replace("\\", "/"),
    QUALITY_GATE_REQUIRED_REGRESSIONS_REL.replace("\\", "/"),
    "evidence/QualityGate/required_regressions/",
    QUALITY_GATE_DEBT_LEDGER_SYNC_REL.replace("\\", "/"),
    QUALITY_GATE_RUFF_CHECK_FULL_REL.replace("\\", "/"),
    QUALITY_GATE_PYRIGHT_GATE_FULL_REL.replace("\\", "/"),
    QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL.replace("\\", "/"),
    QUALITY_GATE_QUICKREF_VS_ROUTES_REL.replace("\\", "/"),
]
HIGH_RISK_UNTRACKED_SOURCE_PREFIXES = ("core/", "web/", "data/", "tools/", "scripts/")
HIGH_RISK_UNTRACKED_SOURCE_SUFFIXES = (".py", ".js", ".ts", ".html", ".css", ".sql")


@dataclass(frozen=True)
class LoadedJsonFile:
    payload: Optional[Dict[str, Any]]
    error: str = ""


@dataclass(frozen=True)
class ResumeDecision:
    enabled: bool
    reason: str
    previous_run_id: str = ""
    previous_failure_message: str = ""
    skip_count: int = 0
    start_command_index: int = 0
    start_command_display: str = ""
    reusable_receipts: Tuple[Dict[str, str], ...] = ()
    reusable_receipt_payloads: Tuple[Dict[str, Any], ...] = ()
    validated_dirty_fingerprint: Optional[Dict[str, Any]] = None



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


def _run_command(
    _display: str,
    args: Sequence[str],
    capture_output: bool = False,
    env_overlay: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []

    def pump_stream(stream, chunks: List[str], *, sink: Optional[Any]) -> None:
        try:
            for chunk in iter(stream.readline, ""):
                chunks.append(str(chunk))
                if sink is not None:
                    print(str(chunk), end="", file=sink, flush=True)
        finally:
            stream.close()

    env = os.environ.copy()
    if env_overlay:
        env.update({str(key): str(value) for key, value in dict(env_overlay).items()})

    process = subprocess.Popen(
        list(args),
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None or process.stderr is None:  # pragma: no cover
        raise QualityGateError("无法捕获子命令 stdout/stderr")
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=pump_stream,
        args=(process.stdout, stdout_chunks),
        kwargs={"sink": None if capture_output else sys.stdout},
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=pump_stream,
        args=(process.stderr, stderr_chunks),
        kwargs={"sink": sys.stderr},
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    returncode = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if capture_output:
        if _display == PYTEST_COLLECT_ALL_DISPLAY:
            if returncode == 0:
                print(_format_collect_only_success(stdout), flush=True)
        elif stdout:
            print(stdout.rstrip(), flush=True)
    elif returncode != 0:
        if stdout and not stdout.endswith("\n"):
            print(flush=True)
        if stderr and not stderr.endswith("\n"):
            print(file=sys.stderr, flush=True)
    return {
        "stdout": stdout,
        "stderr": stderr,
        "returncode": int(returncode),
    }


def _run_command_with_env_overlay(
    display: str,
    args: Sequence[str],
    *,
    capture_output: bool,
    env_overlay: Mapping[str, str],
) -> Dict[str, Any]:
    return _run_command(
        display,
        args,
        capture_output=capture_output,
        env_overlay=env_overlay,
    )


def _coerce_command_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        coerced = {
            "stdout": str(result.get("stdout") or ""),
            "stderr": str(result.get("stderr") or ""),
            "returncode": int(result.get("returncode") or 0),
            "stdout_log_path": str(result.get("stdout_log_path") or ""),
            "stderr_log_path": str(result.get("stderr_log_path") or ""),
        }
        for field_name in ("timed_out", "interrupted", "partial_write"):
            if field_name in result:
                coerced[field_name] = bool(result.get(field_name))
        return coerced
    return {
        "stdout": str(result or ""),
        "stderr": "",
        "returncode": 0,
        "stdout_log_path": "",
        "stderr_log_path": "",
    }


def _assert_command_succeeded(display: str, result: Dict[str, Any]) -> None:
    if int(result.get("returncode") or 0) != 0:
        raise QualityGateError(f"命令失败：{display}")


def _format_collect_only_success(stdout: str) -> str:
    return f"collected_count={len(_parse_collect_nodeids(stdout))}"


def _collect_nodeids_or_raise(stdout: str) -> List[str]:
    nodeids = _parse_collect_nodeids(stdout)
    if not nodeids:
        raise QualityGateError("pytest collect-only 输出没有任何 test nodeid，不能生成 collection proof")
    return nodeids


def _tail_lines(text: str, limit: int = 80) -> str:
    lines = str(text or "").splitlines()
    if not lines:
        return "<空>"
    return "\n".join(lines[-limit:])


def _print_command_log_tail(result: Dict[str, Any], *, limit: int = 80) -> None:
    stdout_log_rel = str(result.get("stdout_log_path") or "")
    stderr_log_rel = str(result.get("stderr_log_path") or "")
    print(f"--- stdout 最后 {limit} 行：{stdout_log_rel or '<未落盘>'} ---", flush=True)
    print(_tail_lines(str(result.get("stdout") or ""), limit=limit), flush=True)
    print(f"--- stderr 最后 {limit} 行：{stderr_log_rel or '<未落盘>'} ---", file=sys.stderr, flush=True)
    print(_tail_lines(str(result.get("stderr") or ""), limit=limit), file=sys.stderr, flush=True)


def _raise_command_failure(
    *,
    index: int,
    total: int,
    display: str,
    receipt_rel: str,
    result: Dict[str, Any],
    detail: str = "",
) -> None:
    _print_command_log_tail(result)
    returncode = int(result.get("returncode") or 0)
    message = (
        f"质量门禁第 {index}/{total} 步失败：\n"
        f"命令：{display}\n"
        f"returncode：{returncode}\n"
        f"receipt：{receipt_rel}\n"
        f"stdout 日志：{result.get('stdout_log_path') or '<未落盘>'}\n"
        f"stderr 日志：{result.get('stderr_log_path') or '<未落盘>'}"
    )
    if detail:
        message += f"\n原因：{detail}"
    raise QualityGateError(message)


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


def _load_json_file(abs_path: str) -> LoadedJsonFile:
    if not os.path.isfile(abs_path):
        return LoadedJsonFile(None, "文件不存在")
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except JSONDecodeError as exc:
        return LoadedJsonFile(None, f"JSON 解析失败：{exc}")
    except OSError as exc:
        return LoadedJsonFile(None, f"读取失败：{exc}")
    if not isinstance(payload, dict):
        return LoadedJsonFile(None, "JSON 顶层不是对象")
    return LoadedJsonFile(cast(Dict[str, Any], payload), "")


def _command_identity(command: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "display": str(command.get("display") or "").strip(),
        "args": [str(arg) for arg in list(command.get("args") or [])],
        "capture_output": bool(command.get("capture_output")),
        "output_policy": str(command.get("output_policy") or "normalized").strip() or "normalized",
        "env_overlay": quality_gate_shared._normalize_env_overlay(command.get("env_overlay")),
    }


def _commands_match(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return _command_identity(left) == _command_identity(right)


def _read_repo_text(rel_path: str) -> str:
    abs_path = os.path.join(REPO_ROOT, str(rel_path or "").replace("/", os.sep))
    with open(abs_path, encoding="utf-8") as handle:
        return handle.read()


def _worktree_status_lines(status_lines: Sequence[str]) -> List[str]:
    return [str(line) for line in list(status_lines or []) if str(line)]


def _run_git_bytes(args: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=REPO_ROOT,
        text=False,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = bytes(completed.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = bytes(completed.stdout or b"").decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or "git diff failed"
        raise QualityGateError(f"无法生成脏工作区指纹：{' '.join(['git', *list(args)])}: {detail}")
    return bytes(completed.stdout or b"")


def _decode_status_path(path_text: str) -> str:
    text = str(path_text or "")
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            decoded = ast.literal_eval(text)
        except (SyntaxError, ValueError) as exc:
            raise QualityGateError(f"无法解析 git status 路径：{text}") from exc
        if not isinstance(decoded, str):
            raise QualityGateError(f"无法解析 git status 路径：{text}")
        return decoded
    return text


def _status_line_path(line: str) -> str:
    text = str(line or "")
    if len(text) < 4:
        return ""
    status_code = text[:2]
    path_text = text[3:]
    if ("R" in status_code or "C" in status_code) and " -> " in path_text:
        path_text = path_text.rsplit(" -> ", 1)[-1]
    return _decode_status_path(path_text)


def _dirty_worktree_fingerprint(status_lines: Sequence[str]) -> Dict[str, Any]:
    normalized_lines = _worktree_status_lines(status_lines)
    hasher = hashlib.sha256()
    for line in normalized_lines:
        hasher.update(line.encode("utf-8", errors="replace"))
        hasher.update(b"\0")
    if not normalized_lines:
        return {
            "status_lines": normalized_lines,
            "content_sha256": hasher.hexdigest(),
        }
    for diff_kind, diff_args in (
        ("unstaged", ["diff", "--no-ext-diff", "--binary"]),
        ("staged", ["diff", "--cached", "--no-ext-diff", "--binary"]),
    ):
        hasher.update(diff_kind.encode("ascii"))
        hasher.update(b"\0")
        hasher.update(_run_git_bytes(diff_args))
        hasher.update(b"\0")
    for line in normalized_lines:
        rel_path = _status_line_path(line)
        if not rel_path:
            continue
        abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
        hasher.update(rel_path.encode("utf-8", errors="replace"))
        hasher.update(b"\0")
        if os.path.islink(abs_path):
            hasher.update(b"symlink\0")
            try:
                hasher.update(os.readlink(abs_path).encode("utf-8", errors="replace"))
            except OSError as exc:
                raise QualityGateError(f"无法读取符号链接目标：{rel_path}: {exc}") from exc
        elif os.path.isfile(abs_path):
            hasher.update(_sha256_file(abs_path).encode("ascii"))
        elif os.path.isdir(abs_path):
            for dirpath, dirnames, filenames in os.walk(abs_path):
                dirnames.sort()
                filenames.sort()
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    rel_file = os.path.relpath(file_path, REPO_ROOT).replace(os.sep, "/")
                    hasher.update(rel_file.encode("utf-8", errors="replace"))
                    hasher.update(b"\0")
                    hasher.update(_sha256_file(file_path).encode("ascii"))
                    hasher.update(b"\0")
        else:
            hasher.update(b"<not-a-file>")
        hasher.update(b"\0")
    return {
        "status_lines": normalized_lines,
        "content_sha256": hasher.hexdigest(),
    }


def _expected_command_log_rel_paths(index: int, display: str) -> Dict[str, str]:
    receipt_rel = build_quality_gate_receipt_rel_path(index, display)
    stem = os.path.splitext(os.path.basename(receipt_rel))[0]
    logs_dir = QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/")
    return {
        "stdout_log_path": f"{logs_dir}/{stem}.stdout.log",
        "stderr_log_path": f"{logs_dir}/{stem}.stderr.log",
    }


def _write_command_output_logs(*, index: int, display: str, result: Dict[str, Any]) -> Dict[str, str]:
    log_paths = _expected_command_log_rel_paths(index, display)
    for result_key, path_key in (("stdout", "stdout_log_path"), ("stderr", "stderr_log_path")):
        rel_path = log_paths[path_key]
        abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(str(result.get(result_key) or ""))
    return log_paths


def _load_resume_receipt_payload(
    receipt_entry: Dict[str, Any],
    command: Dict[str, Any],
    *,
    index: int,
    previous_run_id: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    display = str(command.get("display") or "")
    expected_path = build_quality_gate_receipt_rel_path(index, display)
    rel_path = str(receipt_entry.get("path") or "").strip().replace("\\", "/")
    if not rel_path:
        return None, f"旧 receipt 缺失：第 {index} 步"
    if rel_path != expected_path:
        return None, f"旧 receipt 命令身份不一致：第 {index} 步"
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return None, f"旧 receipt 缺失：{rel_path}"
    if str(receipt_entry.get("sha256") or "") != _sha256_file(abs_path):
        return None, f"旧 receipt hash 不一致：{rel_path}"

    loaded = _load_json_file(abs_path)
    if loaded.error:
        return None, f"旧 receipt 不是合法 JSON：{rel_path}: {loaded.error}"
    receipt_payload = dict(loaded.payload or {})

    stdout_log_rel = str(receipt_payload.get("stdout_log_path") or "").replace("\\", "/")
    stderr_log_rel = str(receipt_payload.get("stderr_log_path") or "").replace("\\", "/")
    if not stdout_log_rel or not stderr_log_rel:
        return None, f"旧 receipt 缺少日志路径：{rel_path}"
    expected_logs = _expected_command_log_rel_paths(index, display)
    if stdout_log_rel != expected_logs["stdout_log_path"] or stderr_log_rel != expected_logs["stderr_log_path"]:
        return None, f"旧 receipt 日志路径不匹配：第 {index} 步"
    for log_rel in (stdout_log_rel, stderr_log_rel):
        log_abs = os.path.join(REPO_ROOT, log_rel.replace("/", os.sep))
        if not os.path.isfile(log_abs):
            return None, f"旧 receipt 日志缺失：{log_rel}"
    try:
        stdout_text = _read_repo_text(stdout_log_rel)
        stderr_text = _read_repo_text(stderr_log_rel)
        returncode = int(receipt_payload.get("returncode") or 0)
    except (OSError, ValueError) as exc:
        return None, f"旧 receipt 证据不可读：{rel_path}: {exc}"

    expected_payload = build_quality_gate_command_receipt(
        command,
        run_id=previous_run_id,
        command_index=index,
        returncode=returncode,
        stdout=stdout_text,
        stderr=stderr_text,
        stdout_log_path=stdout_log_rel,
        stderr_log_path=stderr_log_rel,
    )
    identity_fields = (
        "schema_version",
        "run_id",
        "command_index",
        "command_hash",
        "display",
        "args",
        "capture_output",
        "output_policy",
        "env_overlay",
        "stdout_log_path",
        "stderr_log_path",
    )
    for field_name in identity_fields:
        if receipt_payload.get(field_name) != expected_payload.get(field_name):
            return None, f"旧 receipt 命令身份不一致：第 {index} 步"
    if int(receipt_payload.get("returncode") or 0) != returncode:
        return None, f"旧 receipt returncode 不一致：第 {index} 步"
    for field_name in ("stdout_sha256", "stderr_sha256"):
        if receipt_payload.get(field_name) != expected_payload.get(field_name):
            return None, f"旧 receipt 输出日志 hash 不一致：第 {index} 步"
    return receipt_payload, ""


def _result_from_receipt_logs(receipt_payload: Dict[str, Any]) -> Dict[str, Any]:
    stdout_log_rel = str(receipt_payload.get("stdout_log_path") or "").replace("\\", "/")
    stderr_log_rel = str(receipt_payload.get("stderr_log_path") or "").replace("\\", "/")
    if not stdout_log_rel or not stderr_log_rel:
        raise QualityGateError("旧 receipt 缺少 stdout/stderr 日志路径，不能续跑")
    return {
        "stdout": _read_repo_text(stdout_log_rel),
        "stderr": _read_repo_text(stderr_log_rel),
        "returncode": int(receipt_payload.get("returncode") or 0),
    }


def _strict_long_gate_fingerprint(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return fingerprint_entry(entry, REPO_ROOT, strict=True)
    except LongGateFingerprintError as exc:
        raise QualityGateError(str(exc)) from exc


def _decide_resume_from_previous_failure(
    command_plan: Sequence[Dict[str, Any]],
    *,
    current_head_sha: str,
    current_git_status_short: Sequence[str],
) -> ResumeDecision:
    manifest_path = _quality_gate_manifest_abs_path()
    if not os.path.isfile(manifest_path):
        return ResumeDecision(False, "旧 manifest 不存在")
    loaded_manifest = _load_json_file(manifest_path)
    if loaded_manifest.error:
        if loaded_manifest.error == "文件不存在":
            return ResumeDecision(False, "旧 manifest 不存在")
        return ResumeDecision(False, f"旧 manifest 不是合法 JSON：{loaded_manifest.error}")
    manifest = dict(loaded_manifest.payload or {})
    if str(manifest.get("status") or "") != "failed":
        return ResumeDecision(False, "上次不是失败记录")

    previous_head_sha = str(manifest.get("head_sha") or "").strip()
    if not previous_head_sha:
        return ResumeDecision(False, "旧 manifest 缺少 head_sha，不能续跑")
    if previous_head_sha != str(current_head_sha or "").strip():
        return ResumeDecision(
            False, f"旧 manifest head_sha 与当前 HEAD 不一致，不能续跑：previous={previous_head_sha} current={current_head_sha}"
        )

    current_identity = _repo_identity()
    for field_name in ("checkout_root_realpath", "git_common_dir_realpath"):
        previous_value = str(manifest.get(field_name) or "").strip()
        current_value = str(current_identity.get(field_name) or "").strip()
        if not previous_value or previous_value != current_value:
            return ResumeDecision(False, f"旧 manifest 仓库身份不一致，不能续跑：{field_name}")
    previous_python_executable = str(manifest.get("python_executable") or "").strip()
    current_python_executable = str(sys.executable or "").strip()
    if not previous_python_executable:
        return ResumeDecision(False, "旧 manifest 缺少 python_executable，不能续跑")
    previous_python_realpath = os.path.normcase(os.path.realpath(previous_python_executable))
    current_python_realpath = os.path.normcase(os.path.realpath(current_python_executable))
    if previous_python_realpath != current_python_realpath:
        return ResumeDecision(False, "旧 manifest 使用的 Python 解释器与当前不一致，不能续跑")
    previous_python_version = str(manifest.get("python_version") or "").strip()
    current_python_version = sys.version.splitlines()[0].strip()
    if not previous_python_version:
        return ResumeDecision(False, "旧 manifest 缺少 python_version，不能续跑")
    if previous_python_version != current_python_version:
        return ResumeDecision(False, "旧 manifest 使用的 Python 版本与当前不一致，不能续跑")

    previous_dirty_fingerprint = manifest.get("dirty_worktree_fingerprint_before")
    current_dirty_fingerprint = _dirty_worktree_fingerprint(current_git_status_short)
    if not isinstance(previous_dirty_fingerprint, dict):
        return ResumeDecision(False, "旧 manifest 缺少脏工作区指纹，不能续跑")
    if previous_dirty_fingerprint != current_dirty_fingerprint:
        return ResumeDecision(False, "脏工作区内容已变化，本次完整重跑")

    previous_run_id = str(manifest.get("run_id") or "").strip()
    if not previous_run_id:
        return ResumeDecision(False, "旧 manifest 缺少 run_id，不能续跑")
    previous_planned_commands = manifest.get("planned_commands")
    previous_planned_hash = str(manifest.get("planned_commands_hash") or "").strip()
    if not isinstance(previous_planned_commands, list) or not previous_planned_hash:
        return ResumeDecision(False, "旧 manifest 没有完整命令计划，不能续跑")

    current_planned_commands = [_command_identity(command) for command in command_plan]
    normalized_previous_plan = [
        _command_identity(command) for command in previous_planned_commands if isinstance(command, dict)
    ]
    current_plan_hash = hash_quality_gate_commands(command_plan)
    if normalized_previous_plan != current_planned_commands or previous_planned_hash != current_plan_hash:
        return ResumeDecision(False, "命令计划已变化，本次完整重跑")

    previous_commands = list(manifest.get("commands") or [])
    previous_receipts = list(manifest.get("command_receipts") or [])
    reusable_receipts: List[Dict[str, str]] = []
    reusable_payloads: List[Dict[str, Any]] = []
    if not previous_receipts:
        return ResumeDecision(False, "旧 receipt 缺失：manifest 中没有 command_receipts")
    for index, command in enumerate(command_plan, start=1):
        if index > len(previous_commands) or not isinstance(previous_commands[index - 1], dict):
            return ResumeDecision(False, f"旧 manifest.commands 缺少第 {index} 步，不能续跑")
        if not _commands_match(cast(Dict[str, Any], previous_commands[index - 1]), command):
            return ResumeDecision(False, f"旧 receipt 命令身份不一致：第 {index} 步")
        if index > len(previous_receipts) or not isinstance(previous_receipts[index - 1], dict):
            return ResumeDecision(False, f"旧 receipt 缺失：第 {index} 步")
        receipt_entry = cast(Dict[str, Any], previous_receipts[index - 1])
        receipt_payload, receipt_error = _load_resume_receipt_payload(
            receipt_entry,
            command,
            index=index,
            previous_run_id=previous_run_id,
        )
        if receipt_error:
            return ResumeDecision(False, receipt_error)
        returncode = int((receipt_payload or {}).get("returncode") or 0)
        if returncode != 0:
            skip_count = len(reusable_receipts)
            if skip_count <= 0:
                return ResumeDecision(False, "上次失败发生在第 1 步，没有可跳过的成功前缀")
            return ResumeDecision(
                True,
                "找到可复用的成功前缀",
                previous_run_id=previous_run_id,
                previous_failure_message=str(manifest.get("failure_message") or ""),
                skip_count=skip_count,
                start_command_index=index,
                start_command_display=str(command.get("display") or ""),
                reusable_receipts=tuple(dict(item) for item in reusable_receipts),
                reusable_receipt_payloads=tuple(dict(item) for item in reusable_payloads),
                validated_dirty_fingerprint=dict(current_dirty_fingerprint),
            )
        reusable_receipts.append(
            {"path": str(receipt_entry.get("path") or ""), "sha256": str(receipt_entry.get("sha256") or "")}
        )
        reusable_payloads.append(dict(receipt_payload or {}))
    return ResumeDecision(False, "旧记录没有可定位的失败命令 receipt")


def _write_command_receipt(command: Dict[str, Any], *, run_id: str, index: int, result: Dict[str, Any]) -> Dict[str, str]:
    display = str(command.get("display") or "")
    if not str(result.get("stdout_log_path") or "") or not str(result.get("stderr_log_path") or ""):
        result.update(_write_command_output_logs(index=index, display=display, result=result))
    receipt_rel = build_quality_gate_receipt_rel_path(index, display)
    receipt_abs = os.path.join(REPO_ROOT, receipt_rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(receipt_abs), exist_ok=True)
    receipt_payload = build_quality_gate_command_receipt(
        command,
        run_id=run_id,
        command_index=index,
        returncode=int(result.get("returncode") or 0),
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
        stdout_log_path=str(result.get("stdout_log_path") or ""),
        stderr_log_path=str(result.get("stderr_log_path") or ""),
    )
    receipt_payload["execution_mode"] = str(result.get("execution_mode") or "executed")
    reused_from = result.get("reused_from")
    if isinstance(reused_from, dict):
        receipt_payload["reused_from"] = dict(reused_from)
    if result.get("started_at"):
        receipt_payload["started_at"] = str(result.get("started_at") or "")
    if result.get("ended_at"):
        receipt_payload["ended_at"] = str(result.get("ended_at") or "")
    if "duration_s" in result:
        receipt_payload["duration_s"] = float(result.get("duration_s") or 0.0)
    duration_kind = str(result.get("duration_kind") or "").strip()
    if duration_kind:
        receipt_payload["duration_kind"] = duration_kind
    if "original_duration_s" in result:
        receipt_payload["original_duration_s"] = float(result.get("original_duration_s") or 0.0)
    receipt_payload["timed_out"] = bool(result.get("timed_out"))
    receipt_payload["interrupted"] = bool(result.get("interrupted"))
    receipt_payload["partial_write"] = bool(result.get("partial_write"))
    with open(receipt_abs, "w", encoding="utf-8") as handle:
        json.dump(receipt_payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {
        "path": receipt_rel,
        "sha256": _sha256_file(receipt_abs),
    }


def _mark_command_timing(result: Dict[str, Any], *, started_at: str, start_monotonic: float) -> float:
    duration_s = time.monotonic() - start_monotonic
    result["started_at"] = started_at
    result["ended_at"] = datetime.now().isoformat(timespec="seconds")
    result["duration_s"] = duration_s
    result.setdefault("duration_kind", "executed")
    result.setdefault("timed_out", False)
    result.setdefault("interrupted", False)
    result.setdefault("partial_write", False)
    return duration_s


def _clear_quality_gate_run_outputs(
    *,
    remove_manifest: bool = True,
    remove_receipts_and_logs: bool = True,
    remove_current_debt: bool = True,
    remove_full_test_debt_summary: bool = True,
) -> None:
    for rel_path in (QUALITY_GATE_RECEIPTS_DIR_REL, QUALITY_GATE_LOGS_DIR_REL):
        if not remove_receipts_and_logs:
            continue
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
    if remove_current_debt:
        _clear_quality_gate_current_full_test_debt()
    if remove_full_test_debt_summary:
        _clear_quality_gate_full_test_debt_summary()
    if remove_manifest:
        _remove_quality_gate_manifest()


def _clear_quality_gate_current_full_test_debt() -> None:
    current_debt_path = os.path.join(REPO_ROOT, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL)
    if os.path.isfile(current_debt_path):
        os.remove(current_debt_path)


def _clear_quality_gate_full_test_debt_summary() -> None:
    summary_path = os.path.join(REPO_ROOT, QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL)
    if os.path.isfile(summary_path):
        os.remove(summary_path)


def _clear_full_test_debt_current_outputs_after_failure(runtime_entry: Optional[Mapping[str, Any]]) -> None:
    if not isinstance(runtime_entry, Mapping):
        return
    entry = dict(runtime_entry.get("entry") or {})
    if str(entry.get("entry_id") or "") != ENTRY_FULL_TEST_DEBT:
        return
    _clear_quality_gate_current_full_test_debt()
    _clear_quality_gate_full_test_debt_summary()


def _remove_quality_gate_manifest() -> None:
    manifest_path = _quality_gate_manifest_abs_path()
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)


def _remove_quality_gate_run_output_path(rel_path: str) -> None:
    normalized = str(rel_path or "").replace("\\", "/").strip()
    if not normalized:
        return
    abs_path = os.path.join(REPO_ROOT, normalized.replace("/", os.sep))
    if os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
    elif os.path.isfile(abs_path):
        os.remove(abs_path)


def _clear_stale_long_gate_output_files(
    runtime_entries: Mapping[str, Dict[str, Any]],
    *,
    preserve_full_test_debt_outputs: bool,
) -> None:
    for runtime_entry in list(runtime_entries.values()):
        entry = dict((runtime_entry or {}).get("entry") or {})
        decision = dict((runtime_entry or {}).get("decision") or {})
        entry_id = str(entry.get("entry_id") or "")
        if str(decision.get("decision") or "") == "reuse":
            continue
        if entry_id == ENTRY_FULL_TEST_DEBT and preserve_full_test_debt_outputs:
            continue
        for rel_path in list(entry.get("output_result_files") or []):
            _remove_quality_gate_run_output_path(str(rel_path))
        if entry_id == ENTRY_REQUIRED_REGRESSIONS:
            _remove_quality_gate_run_output_path("evidence/QualityGate/required_regressions")


def _clear_quality_gate_receipts() -> None:
    _clear_quality_gate_run_outputs()


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


def _git_rev_parse_path(*args: str) -> str:
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
    detail = str(completed.stderr or completed.stdout or "").strip() or "git rev-parse failed"
    raise QualityGateError(f"无法确认仓库身份：git rev-parse {' '.join(args)}: {detail}")


def _repo_identity() -> Dict[str, str]:
    return {
        "checkout_root_realpath": _git_rev_parse_path("--show-toplevel"),
        "git_common_dir_realpath": _git_rev_parse_path("--git-common-dir"),
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
    _assert_command_succeeded(PYTEST_COLLECT_ALL_DISPLAY, result)
    collect_output = str(result.get("stdout") or "").strip()
    return {"collection_proof": _build_collection_proof(_collect_nodeids_or_raise(collect_output))}


def _handle_ruff_version_quality_gate_command(_display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"ruff_version_output": _assert_ruff_version(result)}


def _handle_pyright_version_quality_gate_command(_display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"pyright_version_output": _assert_pyright_version(result)}


def _parse_pyright_json_summary(stdout: str) -> Dict[str, Any]:
    try:
        payload = json.loads(str(stdout or "{}"))
    except json.JSONDecodeError as exc:
        raise QualityGateError("无法解析 pyright JSON 输出") from exc
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        raise QualityGateError("pyright JSON 输出缺少 summary")
    return summary


def _load_pyright_tools_config_include() -> List[str]:
    config_path = os.path.join(REPO_ROOT, PYRIGHT_TOOLS_CONFIG.replace("/", os.sep))
    try:
        with open(config_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise QualityGateError(f"无法读取 pyright tools 配置：{PYRIGHT_TOOLS_CONFIG}") from exc
    if not isinstance(payload, dict):
        raise QualityGateError(f"pyright tools 配置格式不正确：{PYRIGHT_TOOLS_CONFIG}")
    include = payload.get("include")
    if not isinstance(include, list):
        raise QualityGateError(f"pyright tools 配置缺少 include：{PYRIGHT_TOOLS_CONFIG}")
    return [str(item).replace("\\", "/").strip() for item in include if str(item).strip()]


def _assert_pyright_tools_config_matches_tool_paths() -> None:
    configured = _load_pyright_tools_config_include()
    expected = [str(path).replace("\\", "/").strip() for path in QUALITY_GATE_TOOL_PATHS]
    if configured == expected:
        return
    configured_set = set(configured)
    expected_set = set(expected)
    missing = [path for path in expected if path not in configured_set]
    extra = [path for path in configured if path not in expected_set]
    raise QualityGateError(
        "pyright tools 配置 include 与 QUALITY_GATE_TOOL_PATHS 不一致："
        f"missing={missing[:5]} extra={extra[:5]}"
    )


def _assert_pyright_tools_coverage() -> None:
    _assert_pyright_tools_config_matches_tool_paths()
    args = [
        sys.executable,
        "-m",
        "pyright",
        "-p",
        PYRIGHT_TOOLS_CONFIG,
        "--outputjson",
    ]
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    summary = _parse_pyright_json_summary(str(completed.stdout or ""))
    files_analyzed = summary.get("filesAnalyzed")
    expected_count = len(QUALITY_GATE_TOOL_PATHS)
    if not isinstance(files_analyzed, int) or isinstance(files_analyzed, bool) or int(files_analyzed) < expected_count:
        raise QualityGateError(
            f"pyright tools 覆盖不足：预期至少分析 {expected_count} 个工具路径，实际 filesAnalyzed={files_analyzed}"
        )
    if int(completed.returncode) != 0:
        detail = str(completed.stdout or "").strip()
        stderr = str(completed.stderr or "").strip()
        if stderr:
            detail += "\n" + stderr
        raise QualityGateError("pyright tools 覆盖自检失败：" + detail)


def _handle_pyright_tools_quality_gate_command(display: str, result: Dict[str, Any]) -> Dict[str, Any]:
    _assert_command_succeeded(display, result)
    if str(result.get("execution_mode") or "") == "reused_success_cache":
        _assert_pyright_tools_config_matches_tool_paths()
    else:
        _assert_pyright_tools_coverage()
    return {}


def _should_prepare_long_gate_output_files(entry: Mapping[str, Any]) -> bool:
    entry_id = str(entry.get("entry_id") or "")
    return bool(entry.get("reuse_allowed")) or entry_id == ENTRY_DEBT_LEDGER_SYNC


def _run_quality_gate_command_plan(
    command_plan: Sequence[Dict[str, Any]],
    *,
    run_id: str,
    commands: List[Dict[str, Any]],
    command_receipts: List[Dict[str, str]],
    parsed_command_results: Dict[str, Any],
    resume_decision: Optional[ResumeDecision] = None,
    long_gate_cache: bool = False,
    long_gate_cache_write_success: bool = True,
    long_gate_cache_dir: str = "",
    long_gate_runtime_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    long_gate_failure: Optional[Dict[str, Any]] = None,
    pending_long_gate_successes: Optional[List[Dict[str, Any]]] = None,
) -> None:
    command_result_handlers: Dict[str, CommandResultHandler] = {
        str(command["display"]): _handle_checked_quality_gate_command for command in command_plan
    }
    command_result_handlers.update(
        {
            PYTEST_COLLECT_ALL_DISPLAY: _handle_collect_quality_gate_command,
            "python -m ruff --version": _handle_ruff_version_quality_gate_command,
            "python -m pyright --version": _handle_pyright_version_quality_gate_command,
            f"python -m pyright -p {PYRIGHT_TOOLS_CONFIG}": _handle_pyright_tools_quality_gate_command,
        }
    )
    total = len(command_plan)
    long_gate_entries = dict(long_gate_runtime_entries or {}) if long_gate_cache else {}
    skip_count = int(resume_decision.skip_count if resume_decision and resume_decision.enabled else 0)
    if skip_count > 0:
        reusable_receipts = list(resume_decision.reusable_receipts if resume_decision else ())
        reusable_payloads = list(resume_decision.reusable_receipt_payloads if resume_decision else ())
        for index, command in enumerate(command_plan[:skip_count], start=1):
            display = str(command["display"])
            print(f"==> 第 {index}/{total} 步：[resume-skip] {display}", flush=True)
            command_started_at = datetime.now().isoformat(timespec="seconds")
            start_monotonic = time.monotonic()
            result = _result_from_receipt_logs(reusable_payloads[index - 1])
            result["execution_mode"] = "resumed_success_prefix"
            result["reused_from"] = {
                "receipt_path": str(reusable_receipts[index - 1].get("path") or ""),
                "receipt_sha256": str(reusable_receipts[index - 1].get("sha256") or ""),
                "run_id": str(reusable_payloads[index - 1].get("run_id") or ""),
                "completed_at": str(reusable_payloads[index - 1].get("ended_at") or ""),
            }
            _mark_command_timing(result, started_at=command_started_at, start_monotonic=start_monotonic)
            result["duration_kind"] = "resume_overhead"
            result["original_duration_s"] = float(reusable_payloads[index - 1].get("duration_s") or 0.0)
            commands.append(command)
            receipt_entry = _write_command_receipt(command, run_id=run_id, index=index, result=result)
            command_receipts.append(receipt_entry)
            try:
                parsed_command_results.update(command_result_handlers[display](display, result))
            except QualityGateError as exc:
                _raise_command_failure(
                    index=index,
                    total=total,
                    display=display,
                    receipt_rel=receipt_entry["path"],
                    result=result,
                    detail=str(exc),
                )

    for zero_based_index, command in enumerate(command_plan[skip_count:], start=skip_count):
        command_index = zero_based_index + 1
        display = str(command["display"])
        print(f"==> 第 {command_index}/{total} 步开始：{display}", flush=True)
        command_started_at = datetime.now().isoformat(timespec="seconds")
        start_monotonic = time.monotonic()
        long_gate_runtime_entry = long_gate_entries.get(display)
        long_gate_entry = dict((long_gate_runtime_entry or {}).get("entry") or {})
        long_gate_fingerprint: Optional[Dict[str, Any]] = None
        if long_gate_runtime_entry is not None:
            _refresh_full_test_debt_reuse_decision(long_gate_runtime_entry, cache_dir=long_gate_cache_dir)
            long_gate_fingerprint = dict(long_gate_runtime_entry.get("fingerprint") or {})
            reuse_evaluation = dict(long_gate_runtime_entry.get("evaluation") or {})
            decision = dict(long_gate_runtime_entry.get("decision") or {})
            if decision["decision"] == "reuse":
                previous = reuse_evaluation["validated_success"]
                if not isinstance(previous, dict):
                    raise QualityGateError("long gate success cache 判定可复用，但缺少已验证结果")
                cached_result = {
                    "stdout": str(reuse_evaluation.get("stdout") or ""),
                    "stderr": str(reuse_evaluation.get("stderr") or ""),
                    "returncode": int(previous.get("returncode") or 0),
                    "execution_mode": "reused_success_cache",
                    "reused_from": {
                        "result_path": str(decision.get("previous_result_path") or ""),
                        "completed_at": str(previous.get("completed_at") or ""),
                        "fingerprint_hash": str(previous.get("fingerprint_hash") or ""),
                        "duration_s": float(previous.get("duration_s") or 0.0),
                    },
                }
                result = _coerce_command_result(cached_result)
                result["execution_mode"] = "reused_success_cache"
                result["reused_from"] = dict(cached_result.get("reused_from") or {})
                elapsed = _mark_command_timing(result, started_at=command_started_at, start_monotonic=start_monotonic)
                result["duration_kind"] = "reuse_overhead"
                if isinstance(result.get("reused_from"), dict):
                    result["original_duration_s"] = float(result["reused_from"].get("duration_s") or 0.0)
                commands.append(command)
                receipt_entry = _write_command_receipt(command, run_id=run_id, index=command_index, result=result)
                command_receipts.append(receipt_entry)
                _refresh_summary_entry(
                    long_gate_runtime_entry,
                    result=result,
                    receipt_path=receipt_entry["path"],
                    output_file_paths=[
                        str(row.get("path") or "")
                        for row in list(previous.get("output_files") or [])
                        if isinstance(row, dict)
                    ],
                )
                try:
                    parsed_command_results.update(command_result_handlers[display](display, result))
                except QualityGateError as exc:
                    if long_gate_failure is not None:
                        long_gate_failure.clear()
                        long_gate_failure.update(
                            extract_copyable_failure(
                                entry_id=str(long_gate_entry.get("entry_id") or ""),
                                display=display,
                                result=result,
                                receipt_path=receipt_entry["path"],
                            )
                        )
                        _refresh_summary_entry(
                            long_gate_runtime_entry,
                            result=result,
                            receipt_path=receipt_entry["path"],
                            failed=True,
                        )
                        _print_long_gate_failure(long_gate_failure)
                    _raise_command_failure(
                        index=command_index,
                        total=total,
                        display=display,
                        receipt_rel=receipt_entry["path"],
                        result=result,
                        detail=str(exc),
                    )
                print(
                    f"==> 第 {command_index}/{total} 步结束：[long-gate-reuse] 通过，"
                    f"耗时 {elapsed:.1f}s，receipt={receipt_entry['path']}",
                    flush=True,
                )
                continue
            cached_failure = None
            if long_gate_cache_write_success:
                cached_failure = _cached_full_test_debt_failure_result(
                    long_gate_runtime_entry,
                    cache_dir=long_gate_cache_dir,
                )
            if cached_failure is not None:
                result = _coerce_command_result(cached_failure)
                result["execution_mode"] = "cached_failure"
                result["reused_from"] = dict(cached_failure.get("reused_from") or {})
                elapsed = _mark_command_timing(result, started_at=command_started_at, start_monotonic=start_monotonic)
                result["duration_kind"] = "reuse_overhead"
                if isinstance(result.get("reused_from"), dict):
                    result["original_duration_s"] = float(result["reused_from"].get("duration_s") or 0.0)
                commands.append(command)
                receipt_entry = _write_command_receipt(command, run_id=run_id, index=command_index, result=result)
                command_receipts.append(receipt_entry)
                if long_gate_failure is not None:
                    long_gate_failure.clear()
                    long_gate_failure.update(
                        extract_copyable_failure(
                            entry_id=str(long_gate_entry.get("entry_id") or ""),
                            display=display,
                            result=result,
                            receipt_path=receipt_entry["path"],
                        )
                    )
                    _refresh_summary_entry(
                        long_gate_runtime_entry,
                        result=result,
                        receipt_path=receipt_entry["path"],
                        failed=True,
                    )
                    _print_long_gate_failure(long_gate_failure)
                    _clear_full_test_debt_current_outputs_after_failure(long_gate_runtime_entry)
                print(
                    f"==> 第 {command_index}/{total} 步结束：[long-gate-cached-failure] "
                    f"失败(returncode={int(result.get('returncode') or 0)})，耗时 {elapsed:.1f}s，"
                    f"receipt={receipt_entry['path']}",
                    flush=True,
                )
                _raise_command_failure(
                    index=command_index,
                    total=total,
                    display=display,
                    receipt_rel=receipt_entry["path"],
                    result=result,
                )

        raw_result: Any = None
        if raw_result is None:
            raw_result = _run_command_with_env_overlay(
                display,
                _resolve_command_args(command),
                capture_output=bool(command.get("capture_output")),
                env_overlay=quality_gate_shared._normalize_env_overlay(command.get("env_overlay")),
            )
        result = _coerce_command_result(raw_result)
        result.update(_write_command_output_logs(index=command_index, display=display, result=result))
        if isinstance(raw_result, dict):
            result["execution_mode"] = str(raw_result.get("execution_mode") or "executed")
            if isinstance(raw_result.get("reused_from"), dict):
                result["reused_from"] = dict(raw_result.get("reused_from") or {})
        else:
            result["execution_mode"] = "executed"
        elapsed = _mark_command_timing(result, started_at=command_started_at, start_monotonic=start_monotonic)
        commands.append(command)
        receipt_entry = _write_command_receipt(command, run_id=run_id, index=command_index, result=result)
        command_receipts.append(receipt_entry)
        returncode = int(result.get("returncode") or 0)
        if returncode != 0:
            if long_gate_runtime_entry is not None and long_gate_failure is not None:
                long_gate_failure.clear()
                long_gate_failure.update(
                    extract_copyable_failure(
                        entry_id=str(long_gate_entry.get("entry_id") or ""),
                        display=display,
                        result=result,
                        receipt_path=receipt_entry["path"],
                    )
                )
                _refresh_summary_entry(
                    long_gate_runtime_entry,
                    result=result,
                    receipt_path=receipt_entry["path"],
                    failed=True,
                )
                _print_long_gate_failure(long_gate_failure)
                _clear_full_test_debt_current_outputs_after_failure(long_gate_runtime_entry)
                _maybe_write_full_test_debt_failure_cache(
                    long_gate_runtime_entry,
                    result=result,
                    receipt_path=receipt_entry["path"],
                    cache_dir=long_gate_cache_dir,
                    long_gate_cache_write_success=long_gate_cache_write_success,
                )
            print(
                f"==> 第 {command_index}/{total} 步结束：失败(returncode={returncode})，"
                f"耗时 {elapsed:.1f}s，receipt={receipt_entry['path']}",
                flush=True,
            )
            _raise_command_failure(
                index=command_index,
                total=total,
                display=display,
                receipt_rel=receipt_entry["path"],
                result=result,
            )
        try:
            parsed_command_results.update(command_result_handlers[display](display, result))
        except QualityGateError as exc:
            if long_gate_runtime_entry is not None and long_gate_failure is not None:
                long_gate_failure.clear()
                long_gate_failure.update(
                    extract_copyable_failure(
                        entry_id=str(long_gate_entry.get("entry_id") or ""),
                        display=display,
                        result=result,
                        receipt_path=receipt_entry["path"],
                    )
                )
                _refresh_summary_entry(
                    long_gate_runtime_entry,
                    result=result,
                    receipt_path=receipt_entry["path"],
                    failed=True,
                )
                _print_long_gate_failure(long_gate_failure)
            print(
                f"==> 第 {command_index}/{total} 步结束：失败(returncode={returncode})，"
                f"耗时 {elapsed:.1f}s，receipt={receipt_entry['path']}",
                flush=True,
            )
            _raise_command_failure(
                index=command_index,
                total=total,
                display=display,
                receipt_rel=receipt_entry["path"],
                result=result,
                detail=str(exc),
            )
        output_file_paths: List[str] = []
        if long_gate_runtime_entry is not None and _should_prepare_long_gate_output_files(long_gate_entry):
            current_decision = dict(long_gate_runtime_entry.get("decision") or {})
            if _decision_cache_unavailable(current_decision):
                print(
                    f"==> 第 {command_index}/{total} 步：跳过 long-gate success cache 写入，"
                    "因为 strict fingerprint 失败，该 entry 当前 cache unavailable",
                    flush=True,
                )
            elif not bool(long_gate_cache_write_success):
                print(
                    f"==> 第 {command_index}/{total} 步：跳过 long-gate success cache 写入，"
                    "因为本次不是干净工作区的完整成功证明",
                    flush=True,
                )
            else:
                if not long_gate_fingerprint:
                    long_gate_fingerprint = _strict_long_gate_fingerprint(long_gate_entry)
                output_file_paths = _prepare_long_gate_success_output_files(
                    long_gate_entry,
                    result,
                    cache_dir=long_gate_cache_dir,
                    run_id=run_id,
                    command_index=command_index,
                    command_plan=command_plan,
                    fingerprint=dict(long_gate_fingerprint or {}),
                )
                if bool(long_gate_entry.get("reuse_allowed")):
                    long_gate_fingerprint = _fingerprint_for_success_cache(
                        long_gate_entry,
                        dict(long_gate_fingerprint or {}),
                    )
                    long_gate_runtime_entry["fingerprint"] = dict(long_gate_fingerprint)
                    decision_for_summary = long_gate_runtime_entry.get("decision")
                    if isinstance(decision_for_summary, dict):
                        decision_for_summary["current_fingerprint_hash"] = str(long_gate_fingerprint.get("hash") or "")
                    cache_result = dict(result)
                    cache_result.pop("stdout_log_path", None)
                    cache_result.pop("stderr_log_path", None)
                    if pending_long_gate_successes is not None:
                        pending_long_gate_successes.append(
                            {
                                "entry": dict(long_gate_entry),
                                "fingerprint": dict(long_gate_fingerprint),
                                "command_result": cache_result,
                                "output_files": _abs_output_paths(output_file_paths),
                            }
                        )
            _refresh_summary_entry(
                long_gate_runtime_entry,
                result=result,
                receipt_path=receipt_entry["path"],
                output_file_paths=output_file_paths,
            )
        print(f"==> 第 {command_index}/{total} 步结束：通过，耗时 {elapsed:.1f}s，receipt={receipt_entry['path']}", flush=True)


def _require_quality_gate_command_proofs(parsed_command_results: Dict[str, Any]) -> None:
    required_proofs = {
        PYTEST_COLLECT_ALL_DISPLAY: parsed_command_results.get("collection_proof"),
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
    pid_state = launcher.runtime_pid_state(pid)
    if pid_state is False:
        return RuntimeProbeState.STALE, pid, False, exe_path
    if pid_state is None:
        return RuntimeProbeState.UNKNOWN, pid, None, exe_path
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
        "提示：检测到仓库根存在陈旧运行时痕迹，将继续执行；未自动删除：contract={} lock={}".format(
            paths["contract_path"], paths["lock_path"]
        ),
        flush=True,
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
        ["git", "-c", "core.quotepath=false", "status", "--short", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise QualityGateError("无法读取 git status --short")
    return [str(line) for line in str(completed.stdout or "").splitlines() if str(line)]


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


def _long_gate_declared_output_paths(entry: Dict[str, Any]) -> List[str]:
    return list(dict.fromkeys(str(path).replace("\\", "/") for path in list(entry.get("output_result_files") or [])))


def _long_gate_success_log_row(result: Dict[str, Any], *, stream: str, rel_path: str) -> Dict[str, Any]:
    text = str(result.get(stream) or "")
    encoded = text.encode("utf-8")
    return {
        "path": str(rel_path or "").replace("\\", "/"),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }


def _is_required_regressions_verifier_args(args: Sequence[str]) -> bool:
    return list(args)[:2] == ["python", "tools/verify_required_regressions_from_full_test_debt.py"]


def _write_startup_runtime_regressions_proof(
    entry: Dict[str, Any],
    result: Dict[str, Any],
    *,
    run_id: str,
    command_index: int,
    command_plan: Sequence[Dict[str, Any]],
    fingerprint: Dict[str, Any],
    cache_dir: str,
) -> str:
    rel_path = QUALITY_GATE_STARTUP_RUNTIME_REGRESSIONS_REL.replace("\\", "/")
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    args = [str(arg) for arg in list(entry.get("args") or [])]
    startup_target_paths = list(args[4:]) if args[:4] == ["python", "-m", "pytest", "-q"] else []
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    safe_entry_id = ENTRY_STARTUP_RUNTIME_REGRESSIONS.replace("\\", "_").replace("/", "_")
    stdout_log_path = f"{cache_root}/logs/{safe_entry_id}.stdout.log"
    stderr_log_path = f"{cache_root}/logs/{safe_entry_id}.stderr.log"
    stdout_log_row = _long_gate_success_log_row(result, stream="stdout", rel_path=stdout_log_path)
    stderr_log_row = _long_gate_success_log_row(result, stream="stderr", rel_path=stderr_log_path)
    if not str(result.get("stdout") or "").strip():
        raise QualityGateError("startup runtime regressions stdout 为空，无法证明 pytest 实际执行结果")
    payload = {
        "schema_version": STARTUP_RUNTIME_REGRESSIONS_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "entry_id": str(entry.get("entry_id") or ""),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "head_sha": _git_head_sha(),
        "run_id": str(run_id or ""),
        "quality_gate_plan_hash": hash_quality_gate_commands(command_plan),
        "command_index": int(command_index),
        "display": str(entry.get("display") or ""),
        "args": args,
        "command_hash": str(entry.get("command_hash") or ""),
        "capture_output": bool(entry.get("capture_output")),
        "output_policy": str(entry.get("output_policy") or ""),
        "startup_target_count": len(startup_target_paths),
        "test_count": len(startup_target_paths),
        "startup_target_paths": startup_target_paths,
        "startup_target_hash": stable_json_hash(startup_target_paths),
        "fingerprint_schema_version": int(entry.get("fingerprint_schema_version") or 0),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "returncode": int(result.get("returncode") or 0),
        "pytest_exit_code": int(result.get("returncode") or 0),
        "execution_mode": str(result.get("execution_mode") or "executed"),
        "duration_s": float(result.get("duration_s") or 0.0),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_sha256": str(stdout_log_row["sha256"]),
        "stderr_sha256": str(stderr_log_row["sha256"]),
        "timed_out": bool(result.get("timed_out")),
        "interrupted": bool(result.get("interrupted")),
        "partial_write": bool(result.get("partial_write")),
        "does_not_claim": "clean_worktree_proof",
        "logs": {
            "stdout": stdout_log_row,
            "stderr": stderr_log_row,
        },
    }
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return rel_path


def _write_required_regressions_proof(
    entry: Dict[str, Any],
    result: Dict[str, Any],
    *,
    run_id: str,
    command_index: int,
    command_plan: Sequence[Dict[str, Any]],
    fingerprint: Dict[str, Any],
    cache_dir: str,
) -> List[str]:
    rel_path = QUALITY_GATE_REQUIRED_REGRESSIONS_REL.replace("\\", "/")
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    args = [str(arg) for arg in list(entry.get("args") or [])]
    required_target_paths = (
        list(args[4:])
        if args[:4] == ["python", "-m", "pytest", "-q"]
        else list(iter_quality_gate_required_tests())
    )
    uses_full_test_debt_verifier = _is_required_regressions_verifier_args(args)
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    safe_entry_id = ENTRY_REQUIRED_REGRESSIONS.replace("\\", "_").replace("/", "_")
    stdout_log_path = f"{cache_root}/logs/{safe_entry_id}.stdout.log"
    stderr_log_path = f"{cache_root}/logs/{safe_entry_id}.stderr.log"
    stdout_log_row = _long_gate_success_log_row(result, stream="stdout", rel_path=stdout_log_path)
    stderr_log_row = _long_gate_success_log_row(result, stream="stderr", rel_path=stderr_log_path)
    payload = {
        "schema_version": REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "entry_id": str(entry.get("entry_id") or ""),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "head_sha": _git_head_sha(),
        "run_id": str(run_id or ""),
        "quality_gate_plan_hash": hash_quality_gate_commands(command_plan),
        "command_index": int(command_index),
        "display": str(entry.get("display") or ""),
        "args": args,
        "command_hash": str(entry.get("command_hash") or ""),
        "capture_output": bool(entry.get("capture_output")),
        "output_policy": str(entry.get("output_policy") or ""),
        "required_target_count": len(required_target_paths),
        "test_count": len(required_target_paths),
        "required_target_paths": required_target_paths,
        "required_target_hash": stable_json_hash(required_target_paths),
        "fingerprint_schema_version": int(entry.get("fingerprint_schema_version") or 0),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "returncode": int(result.get("returncode") or 0),
        "pytest_exit_code": int(result.get("returncode") or 0),
        "verification_exit_code": int(result.get("returncode") or 0),
        "verification_method": (
            "full_test_debt_payload_required_coverage"
            if uses_full_test_debt_verifier
            else "direct_pytest_required_targets"
        ),
        "execution_mode": str(result.get("execution_mode") or "executed"),
        "duration_s": float(result.get("duration_s") or 0.0),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_sha256": str(stdout_log_row["sha256"]),
        "stderr_sha256": str(stderr_log_row["sha256"]),
        "timed_out": bool(result.get("timed_out")),
        "interrupted": bool(result.get("interrupted")),
        "partial_write": bool(result.get("partial_write")),
        "does_not_claim": "clean_worktree_proof",
        "logs": {
            "stdout": stdout_log_row,
            "stderr": stderr_log_row,
        },
    }
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return [rel_path]


def _parse_debt_ledger_check_stdout(stdout: str) -> Dict[str, Any]:
    marker = "治理台账校验通过"
    text = str(stdout or "")
    marker_index = text.find(marker)
    if marker_index < 0:
        raise QualityGateError("debt_ledger_sync stdout 缺少通过标题")
    json_text = text[marker_index + len(marker) :].strip()
    if not json_text:
        raise QualityGateError("debt_ledger_sync stdout 缺少 summary JSON")
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise QualityGateError("debt_ledger_sync stdout summary JSON 无法解析") from exc
    if not isinstance(payload, dict):
        raise QualityGateError("debt_ledger_sync stdout summary JSON 必须是 object")
    return dict(payload)


def _write_debt_ledger_sync_proof(
    entry: Dict[str, Any],
    result: Dict[str, Any],
    *,
    run_id: str,
    command_index: int,
    command_plan: Sequence[Dict[str, Any]],
    fingerprint: Dict[str, Any],
    cache_dir: str,
) -> str:
    rel_path = QUALITY_GATE_DEBT_LEDGER_SYNC_REL.replace("\\", "/")
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    args = [str(arg) for arg in list(entry.get("args") or [])]
    summary = _parse_debt_ledger_check_stdout(str(result.get("stdout") or ""))
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    safe_entry_id = ENTRY_DEBT_LEDGER_SYNC.replace("\\", "_").replace("/", "_")
    stdout_log_path = f"{cache_root}/logs/{safe_entry_id}.stdout.log"
    stderr_log_path = f"{cache_root}/logs/{safe_entry_id}.stderr.log"
    stdout_log_row = _long_gate_success_log_row(result, stream="stdout", rel_path=stdout_log_path)
    stderr_log_row = _long_gate_success_log_row(result, stream="stderr", rel_path=stderr_log_path)
    ledger_counts = {
        "oversize_count": int(summary.get("oversize_count") or 0),
        "complexity_count": int(summary.get("complexity_count") or 0),
        "silent_fallback_count": int(summary.get("silent_fallback_count") or 0),
        "test_debt_count": int(summary.get("test_debt_count") or 0),
        "accepted_risk_count": int(summary.get("accepted_risk_count") or 0),
    }
    payload = {
        "schema_version": DEBT_LEDGER_SYNC_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "entry_id": str(entry.get("entry_id") or ""),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "head_sha": _git_head_sha(),
        "run_id": str(run_id or ""),
        "quality_gate_plan_hash": hash_quality_gate_commands(command_plan),
        "command_index": int(command_index),
        "display": str(entry.get("display") or ""),
        "args": args,
        "command_hash": str(entry.get("command_hash") or ""),
        "capture_output": bool(entry.get("capture_output")),
        "output_policy": str(entry.get("output_policy") or ""),
        "fingerprint_schema_version": int(entry.get("fingerprint_schema_version") or 0),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "returncode": int(result.get("returncode") or 0),
        "execution_mode": str(result.get("execution_mode") or "executed"),
        "duration_s": float(result.get("duration_s") or 0.0),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_sha256": str(stdout_log_row["sha256"]),
        "stderr_sha256": str(stderr_log_row["sha256"]),
        "timed_out": bool(result.get("timed_out")),
        "interrupted": bool(result.get("interrupted")),
        "partial_write": bool(result.get("partial_write")),
        "ledger_path": os.path.relpath(LEDGER_PATH, REPO_ROOT).replace("\\", "/"),
        "ledger_schema_version": int(summary.get("schema_version") or 0),
        "ledger_checked_at": str(summary.get("checked_at") or ""),
        "ledger_counts": ledger_counts,
        "samples_hash": stable_json_hash(summary.get("samples") or {}),
        "architecture_scan_cache": architecture_scan_cache_metadata(REPO_ROOT),
        "does_not_claim": "clean_worktree_proof",
        "logs": {
            "stdout": stdout_log_row,
            "stderr": stderr_log_row,
        },
    }
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return rel_path


def _static_check_proof_rel_path(entry_id: str) -> str:
    if entry_id == ENTRY_RUFF_CHECK_FULL:
        return QUALITY_GATE_RUFF_CHECK_FULL_REL.replace("\\", "/")
    if entry_id == ENTRY_PYRIGHT_GATE_FULL:
        return QUALITY_GATE_PYRIGHT_GATE_FULL_REL.replace("\\", "/")
    if entry_id == ENTRY_PYRIGHT_TOOLS_FULL:
        return QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL.replace("\\", "/")
    raise QualityGateError(f"未知 static long-gate entry：{entry_id}")


def _option_value(args: Sequence[str], option: str) -> str:
    try:
        index = list(args).index(option)
    except ValueError:
        return ""
    if index + 1 >= len(args):
        return ""
    return str(args[index + 1])


def _write_static_check_proof(
    entry: Dict[str, Any],
    result: Dict[str, Any],
    *,
    run_id: str,
    command_index: int,
    command_plan: Sequence[Dict[str, Any]],
    fingerprint: Dict[str, Any],
    cache_dir: str,
) -> str:
    entry_id = str(entry.get("entry_id") or "")
    rel_path = _static_check_proof_rel_path(entry_id)
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    args = [str(arg) for arg in list(entry.get("args") or [])]
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    safe_entry_id = entry_id.replace("\\", "_").replace("/", "_").strip() or "unknown"
    stdout_log_path = f"{cache_root}/logs/{safe_entry_id}.stdout.log"
    stderr_log_path = f"{cache_root}/logs/{safe_entry_id}.stderr.log"
    stdout_log_row = _long_gate_success_log_row(result, stream="stdout", rel_path=stdout_log_path)
    stderr_log_row = _long_gate_success_log_row(result, stream="stderr", rel_path=stderr_log_path)
    if entry_id == ENTRY_PYRIGHT_TOOLS_FULL:
        tool_paths = list(QUALITY_GATE_TOOL_PATHS)
    else:
        tool_paths = [path for path in QUALITY_GATE_TOOL_PATHS if path in args]
    payload = {
        "schema_version": STATIC_CHECK_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "entry_id": entry_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "head_sha": _git_head_sha(),
        "run_id": str(run_id or ""),
        "quality_gate_plan_hash": hash_quality_gate_commands(command_plan),
        "command_index": int(command_index),
        "display": str(entry.get("display") or ""),
        "args": args,
        "command_hash": str(entry.get("command_hash") or ""),
        "capture_output": bool(entry.get("capture_output")),
        "output_policy": str(entry.get("output_policy") or ""),
        "config_path": _option_value(args, "-p"),
        "tool_path_count": len(tool_paths),
        "tool_paths": tool_paths,
        "tool_paths_hash": stable_json_hash(tool_paths),
        "fingerprint_schema_version": int(entry.get("fingerprint_schema_version") or 0),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "returncode": int(result.get("returncode") or 0),
        "execution_mode": str(result.get("execution_mode") or "executed"),
        "duration_s": float(result.get("duration_s") or 0.0),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_sha256": str(stdout_log_row["sha256"]),
        "stderr_sha256": str(stderr_log_row["sha256"]),
        "timed_out": bool(result.get("timed_out")),
        "interrupted": bool(result.get("interrupted")),
        "partial_write": bool(result.get("partial_write")),
        "does_not_claim": "clean_worktree_proof",
        "logs": {
            "stdout": stdout_log_row,
            "stderr": stderr_log_row,
        },
    }
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return rel_path


def _full_test_debt_failure_cache_is_allowed(
    runtime_entry: Optional[Mapping[str, Any]],
    *,
    long_gate_cache_write_success: bool,
) -> bool:
    if not long_gate_cache_write_success or not isinstance(runtime_entry, Mapping):
        return False
    entry = dict(runtime_entry.get("entry") or {})
    if str(entry.get("entry_id") or "") != ENTRY_FULL_TEST_DEBT:
        return False
    decision = dict(runtime_entry.get("decision") or {})
    if _decision_cache_unavailable(decision):
        return False
    reason = str(decision.get("reason") or "")
    if reason.startswith("forced by --long-gate-force-rerun"):
        return False
    return str(decision.get("decision") or "") == "run"


def _maybe_write_full_test_debt_failure_cache(
    runtime_entry: Optional[Mapping[str, Any]],
    *,
    result: Mapping[str, Any],
    receipt_path: str,
    cache_dir: str,
    long_gate_cache_write_success: bool,
) -> None:
    if not _full_test_debt_failure_cache_is_allowed(
        runtime_entry,
        long_gate_cache_write_success=long_gate_cache_write_success,
    ):
        return
    if str(result.get("execution_mode") or "executed") != "executed":
        return
    assert runtime_entry is not None
    cache_result = dict(result)
    cache_result["receipt_path"] = str(receipt_path or "")
    write_long_gate_failure(
        dict(runtime_entry.get("entry") or {}),
        dict(runtime_entry.get("fingerprint") or {}),
        cache_result,
        repo_root=REPO_ROOT,
        cache_dir=cache_dir,
    )


def _cached_full_test_debt_failure_result(
    runtime_entry: Dict[str, Any],
    *,
    cache_dir: str,
) -> Optional[Dict[str, Any]]:
    if not _full_test_debt_failure_cache_is_allowed(runtime_entry, long_gate_cache_write_success=True):
        return None
    evaluation = evaluate_failure_reuse(
        dict(runtime_entry.get("entry") or {}),
        dict(runtime_entry.get("fingerprint") or {}),
        repo_root=REPO_ROOT,
        cache_dir=cache_dir,
    )
    decision = dict(evaluation["decision"])
    runtime_entry["failure_evaluation"] = dict(evaluation)
    runtime_entry["failure_decision"] = decision
    if str(decision.get("decision") or "") != "cached_failure":
        return None
    previous = evaluation["validated_failure"]
    if not isinstance(previous, dict):
        raise QualityGateError("long gate failure cache 判定可复用，但缺少已验证失败结果")
    return {
        "stdout": str(evaluation.get("stdout") or ""),
        "stderr": str(evaluation.get("stderr") or ""),
        "returncode": int(previous.get("returncode") or 1),
        "execution_mode": "cached_failure",
        "reused_from": {
            "result_path": str(decision.get("previous_result_path") or ""),
            "completed_at": str(previous.get("completed_at") or ""),
            "fingerprint_hash": str(previous.get("fingerprint_hash") or ""),
            "duration_s": float(previous.get("duration_s") or 0.0),
        },
        "stdout_log_path": str(previous.get("stdout_log_path") or ""),
        "stderr_log_path": str(previous.get("stderr_log_path") or ""),
    }


def _long_gate_success_result_rel_path(entry_id: str, *, cache_dir: str) -> str:
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    safe_entry_id = str(entry_id or "").replace("\\", "_").replace("/", "_").strip() or "unknown"
    return f"{cache_root}/results/{safe_entry_id}.success.json"


def _prepare_long_gate_success_output_files(
    entry: Dict[str, Any],
    result: Dict[str, Any],
    *,
    cache_dir: str = "evidence/QualityGate/long_gate",
    run_id: str = "",
    command_index: int = 0,
    command_plan: Sequence[Dict[str, Any]] = (),
    fingerprint: Optional[Dict[str, Any]] = None,
) -> List[str]:
    entry_id = str(entry.get("entry_id") or "")
    if entry_id == ENTRY_PYTEST_COLLECT_ALL:
        collect_payload = build_collect_nodeids_payload(
            str(result.get("stdout") or ""),
            pytest_version=pytest_distribution_version(strict=True),
            collect_stdout_log_path=str(result.get("stdout_log_path") or ""),
        )
        return [write_collect_nodeids(collect_payload, repo_root=REPO_ROOT)]
    if entry_id == ENTRY_STARTUP_RUNTIME_REGRESSIONS:
        return [
            _write_startup_runtime_regressions_proof(
                entry,
                result,
                run_id=run_id,
                command_index=command_index,
                command_plan=command_plan,
                fingerprint=dict(fingerprint or {}),
                cache_dir=cache_dir,
            )
        ]
    if entry_id == ENTRY_REQUIRED_REGRESSIONS:
        return _write_required_regressions_proof(
            entry,
            result,
            run_id=run_id,
            command_index=command_index,
            command_plan=command_plan,
            fingerprint=dict(fingerprint or {}),
            cache_dir=cache_dir,
        )
    if entry_id == ENTRY_DEBT_LEDGER_SYNC:
        return [
            _write_debt_ledger_sync_proof(
                entry,
                result,
                run_id=run_id,
                command_index=command_index,
                command_plan=command_plan,
                fingerprint=dict(fingerprint or {}),
                cache_dir=cache_dir,
            )
        ]
    if entry_id in {ENTRY_RUFF_CHECK_FULL, ENTRY_PYRIGHT_GATE_FULL, ENTRY_PYRIGHT_TOOLS_FULL}:
        return [
            _write_static_check_proof(
                entry,
                result,
                run_id=run_id,
                command_index=command_index,
                command_plan=command_plan,
                fingerprint=dict(fingerprint or {}),
                cache_dir=cache_dir,
            )
        ]
    return _long_gate_declared_output_paths(entry)


def _fingerprint_for_success_cache(entry: Dict[str, Any], fingerprint: Dict[str, Any]) -> Dict[str, Any]:
    if str(entry.get("entry_id") or "") == ENTRY_FULL_TEST_DEBT:
        return _strict_long_gate_fingerprint(entry)
    return dict(fingerprint)


def _abs_output_paths(rel_paths: Sequence[str]) -> List[str]:
    return [os.path.join(REPO_ROOT, str(path).replace("\\", "/").replace("/", os.sep)) for path in list(rel_paths or [])]


def _long_gate_success_cache_exists(entry_id: str, *, cache_dir: str) -> bool:
    safe_entry_id = str(entry_id or "").replace("\\", "_").replace("/", "_").strip() or "unknown"
    result_path = os.path.join(
        REPO_ROOT,
        str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/").replace("/", os.sep),
        "results",
        f"{safe_entry_id}.success.json",
    )
    return os.path.isfile(result_path)


def _should_preserve_full_test_debt_outputs(
    runtime_entry: Dict[str, Any],
    *,
    cache_enabled: bool,
    cache_dir: str,
) -> bool:
    if not cache_enabled:
        return False
    entry = dict(runtime_entry.get("entry") or {})
    if str(entry.get("entry_id") or "") != ENTRY_FULL_TEST_DEBT:
        return False
    decision = dict(runtime_entry.get("decision") or {})
    if str(decision.get("decision") or "") == "reuse":
        return True
    if str(decision.get("reason") or "") != "collect nodeids proof is invalid":
        return False
    return _long_gate_success_cache_exists(ENTRY_FULL_TEST_DEBT, cache_dir=cache_dir)


def _resolve_command_args(command: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for idx, raw_arg in enumerate(list(command.get("args") or [])):
        arg = str(raw_arg)
        if idx == 0 and arg == "python":
            args.append(sys.executable)
            continue
        args.append(arg)
    return args


def _runtime_entry_by_entry_id(
    runtime_entries: Mapping[str, Dict[str, Any]],
    entry_id: str,
) -> Dict[str, Any]:
    for runtime_entry in runtime_entries.values():
        entry = dict((runtime_entry or {}).get("entry") or {})
        if str(entry.get("entry_id") or "") == str(entry_id):
            return dict(runtime_entry or {})
    return {}


def _command_plan_for_worktree_mode(
    command_plan: Sequence[Dict[str, Any]],
    *,
    allow_dirty_worktree: bool,
) -> List[Dict[str, Any]]:
    if not allow_dirty_worktree:
        return [dict(command) for command in command_plan]

    checker_path = "/".join(["tools", "check_full_test_debt.py"])
    out: List[Dict[str, Any]] = []
    for command in command_plan:
        args = [str(arg) for arg in list(command.get("args") or [])]
        if args[:2] == ["python", checker_path]:
            updated = dict(command)
            updated["display"] = f"{str(command.get('display') or '').strip()} --allow-dirty-worktree-proof"
            updated["args"] = [*args[:2], "--allow-dirty-worktree-proof", *args[2:]]
            out.append(updated)
            continue
        out.append(dict(command))
    return out


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
    before = _worktree_status_lines(git_status_short_before)
    after = None
    if git_status_short_after is not None:
        after = _worktree_status_lines(git_status_short_after)
    previous_before_fingerprint = manifest.get("dirty_worktree_fingerprint_before")
    if isinstance(previous_before_fingerprint, dict) and previous_before_fingerprint.get("status_lines") == before:
        before_fingerprint = previous_before_fingerprint
    else:
        before_fingerprint = _dirty_worktree_fingerprint(before)
    after_fingerprint = _dirty_worktree_fingerprint(after) if after is not None else None
    manifest.update(
        {
            "git_status_short_before": before,
            "dirty_worktree_fingerprint_before": before_fingerprint,
            "is_dirty_before": bool(before),
            "git_status_short_after": after,
            "dirty_worktree_fingerprint_after": after_fingerprint,
            "is_dirty_after": None if after is None else bool(after),
            "tracked_drift_detected": None if after is None else (before_fingerprint != after_fingerprint),
        }
    )


def _assert_resume_dirty_fingerprint_still_current(
    resume_decision: ResumeDecision,
    *,
    git_status_short_before: Sequence[str],
) -> None:
    if not resume_decision.enabled:
        return
    expected = resume_decision.validated_dirty_fingerprint
    if not isinstance(expected, dict):
        raise QualityGateError("续跑缺少已校验的脏工作区指纹")
    current = _dirty_worktree_fingerprint(git_status_short_before)
    if current != expected:
        raise QualityGateError("脏工作区内容在续跑判定后又发生变化，本次不能跳过前置命令")


def _base_quality_gate_manifest(
    *,
    started_at: str,
    head_sha: str,
    git_status_short_before: Sequence[str],
    runtime_snapshot: Dict[str, Any],
    status: str,
    command_plan: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    manifest = {
        "status": str(status or "").strip() or "running",
        "head_sha": head_sha,
        "run_id": f"{head_sha}:{started_at}",
        **_repo_identity(),
        "runtime_snapshot": runtime_snapshot,
        "python_version": sys.version.splitlines()[0].strip(),
        "python_executable": sys.executable,
        "ruff_version": None,
        "pyright_version": None,
        "started_at": started_at,
        "finished_at": None,
        "collection_proof": None,
        "required_tests": list(REQUIRED_TEST_ARGS),
        "planned_commands": [_command_identity(command) for command in command_plan],
        "planned_commands_hash": hash_quality_gate_commands(command_plan),
        "commands": [],
        "gate_sources": [],
        "clean_worktree_excluded_paths": list(GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS),
        "failure_kind": None,
        "failure_message": None,
    }
    _apply_worktree_proof(manifest, git_status_short_before=git_status_short_before, git_status_short_after=None)
    apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
    return manifest


def _mark_manifest_unbound(manifest: Dict[str, Any]) -> None:
    manifest["proof_scope"] = {
        "claim": "diagnostic_run_completed_in_dirty_worktree",
        "does_not_claim": "required_registry_bound_to_clean_worktree",
    }


def _parse_args_legacy(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS 质量门禁")
    parser.add_argument("--require-clean-worktree", action="store_true", help="要求当前 worktree 为 clean")
    return parser.parse_args(list(argv) if argv is not None else None)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS quality gate")
    parser.add_argument(
        "--fast-precheck",
        action="store_true",
        help="run fast static precheck only; this is not a full quality gate proof",
    )
    parser.add_argument("--require-clean-worktree", action="store_true", help="require a clean worktree")
    parser.add_argument("--allow-dirty-worktree", action="store_true", help="allow a dirty worktree but mark the run unbound")
    parser.add_argument("--long-gate-cache", action="store_true", help="reuse eligible long-gate success cache entries")
    parser.add_argument("--no-long-gate-cache", action="store_true", help="disable long-gate success cache reuse")
    parser.add_argument(
        "--long-gate-cache-dir",
        help="success cache directory under evidence/QualityGate/long_gate",
    )
    parser.add_argument(
        "--long-gate-force-rerun",
        action="append",
        default=[],
        metavar="ENTRY_ID",
        help="force one enabled long-gate cache entry to execute instead of reusing success cache",
    )
    parser.add_argument(
        "--long-gate-force-rerun-all",
        action="store_true",
        help="force all enabled long-gate cache entries to execute instead of reusing success cache",
    )
    parser.add_argument(
        "--long-gate-cache-explain",
        action="store_true",
        help="print long-gate cache decisions without executing quality-gate commands",
    )
    parser.add_argument(
        "--long-gate-impact-explain",
        action="store_true",
        help="print JSON explaining which long-gate entries are affected by changed paths",
    )
    parser.add_argument(
        "--long-gate-impact-path",
        action="append",
        default=[],
        metavar="PATH",
        help="changed path to explain; may be repeated; defaults to current git changed paths",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="do not reuse the successful prefix from the previous failed dirty-worktree run",
    )
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    if parsed.require_clean_worktree and parsed.allow_dirty_worktree:
        parser.error("--require-clean-worktree and --allow-dirty-worktree are mutually exclusive")
    if (parsed.long_gate_cache or parsed.long_gate_cache_explain) and parsed.no_long_gate_cache:
        parser.error("--long-gate-cache/--long-gate-cache-explain and --no-long-gate-cache are mutually exclusive")
    if parsed.long_gate_impact_path and not parsed.long_gate_impact_explain:
        parser.error("--long-gate-impact-path requires --long-gate-impact-explain")
    if parsed.long_gate_impact_explain:
        incompatible = []
        if parsed.fast_precheck:
            incompatible.append("--fast-precheck")
        if parsed.require_clean_worktree:
            incompatible.append("--require-clean-worktree")
        if parsed.allow_dirty_worktree:
            incompatible.append("--allow-dirty-worktree")
        if parsed.long_gate_cache:
            incompatible.append("--long-gate-cache")
        if parsed.no_long_gate_cache:
            incompatible.append("--no-long-gate-cache")
        if parsed.long_gate_cache_dir:
            incompatible.append("--long-gate-cache-dir")
        if parsed.long_gate_force_rerun:
            incompatible.append("--long-gate-force-rerun")
        if parsed.long_gate_force_rerun_all:
            incompatible.append("--long-gate-force-rerun-all")
        if parsed.long_gate_cache_explain:
            incompatible.append("--long-gate-cache-explain")
        if parsed.no_resume:
            incompatible.append("--no-resume")
        if incompatible:
            parser.error("--long-gate-impact-explain cannot be combined with " + ", ".join(incompatible))
    if parsed.fast_precheck:
        incompatible = []
        if parsed.require_clean_worktree:
            incompatible.append("--require-clean-worktree")
        if parsed.allow_dirty_worktree:
            incompatible.append("--allow-dirty-worktree")
        if parsed.long_gate_cache:
            incompatible.append("--long-gate-cache")
        if parsed.no_long_gate_cache:
            incompatible.append("--no-long-gate-cache")
        if parsed.long_gate_cache_dir:
            incompatible.append("--long-gate-cache-dir")
        if parsed.long_gate_force_rerun:
            incompatible.append("--long-gate-force-rerun")
        if parsed.long_gate_force_rerun_all:
            incompatible.append("--long-gate-force-rerun-all")
        if parsed.long_gate_cache_explain:
            incompatible.append("--long-gate-cache-explain")
        if parsed.long_gate_impact_explain:
            incompatible.append("--long-gate-impact-explain")
        if parsed.long_gate_impact_path:
            incompatible.append("--long-gate-impact-path")
        if parsed.no_resume:
            incompatible.append("--no-resume")
        if incompatible:
            parser.error("--fast-precheck cannot be combined with " + ", ".join(incompatible))
    return parsed


def _planned_long_gate_decision(entry: Dict[str, Any]) -> Dict[str, Any]:
    return _planned_long_gate_decision_forced(entry, force_requested=False)


def _planned_long_gate_decision_forced(entry: Dict[str, Any], *, force_requested: bool) -> Dict[str, Any]:
    reason = "long gate cache for this entry is not enabled yet"
    invalidated_by: List[str] = []
    if force_requested:
        reason = f"{reason}; force rerun ignored because planned entries are not enabled"
        invalidated_by.append("force rerun ignored for planned entry")
    return {
        "entry_id": str(entry.get("entry_id") or ""),
        "decision": "planned_only",
        "reuse_allowed": False,
        "reason": reason,
        "invalidated_by": invalidated_by,
        "previous_completed_at": "",
        "previous_result_path": "",
        "current_fingerprint_hash": "",
    }


def _disabled_long_gate_decision(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entry_id": str(entry.get("entry_id") or ""),
        "decision": "disabled",
        "reuse_allowed": False,
        "reason": "long gate cache is disabled for this run",
        "invalidated_by": [],
        "previous_completed_at": "",
        "previous_result_path": "",
        "current_fingerprint_hash": "",
    }


def _unwrap_fingerprint_error(error: BaseException) -> Optional[LongGateFingerprintError]:
    if isinstance(error, LongGateFingerprintError):
        return error
    cause = getattr(error, "__cause__", None)
    if isinstance(cause, LongGateFingerprintError):
        return cause
    return None


def _fingerprint_error_details(error: LongGateFingerprintError) -> Dict[str, Any]:
    details = getattr(error, "details", {})
    if isinstance(details, Mapping):
        return dict(details)
    return {}


def _fingerprint_error_long_gate_decision(entry: Dict[str, Any], error: LongGateFingerprintError) -> Dict[str, Any]:
    details = _fingerprint_error_details(error)
    runtime_key = str(details.get("runtime_key") or "")
    failure_kind = str(details.get("failure_kind") or "")
    invalidated_by = ["strict fingerprint failed"]
    if runtime_key:
        invalidated_by.append("runtime_key=" + runtime_key)
    if failure_kind:
        invalidated_by.append("failure_kind=" + failure_kind)
    fingerprint_error = {
        "message": str(error),
        "runtime_key": runtime_key,
        "failure_kind": failure_kind,
        "details": details,
    }
    return {
        "entry_id": str(entry.get("entry_id") or ""),
        "decision": "run",
        "reuse_allowed": False,
        "reason": "strict fingerprint failed; cache unavailable; executing command without read/write cache",
        "invalidated_by": invalidated_by,
        "previous_completed_at": "",
        "previous_result_path": "",
        "current_fingerprint_hash": "",
        "cache_unavailable": True,
        "fingerprint_error": fingerprint_error,
    }


def _decision_cache_unavailable(decision: Mapping[str, Any]) -> bool:
    return bool(decision.get("cache_unavailable")) or bool(decision.get("fingerprint_error"))


def _force_long_gate_decision(entry: Dict[str, Any], decision: Dict[str, Any], *, force_reason: str) -> Dict[str, Any]:
    invalidated_by = list(decision.get("invalidated_by") or [])
    if force_reason not in invalidated_by:
        invalidated_by.append(force_reason)
    return {
        "entry_id": str(entry.get("entry_id") or decision.get("entry_id") or ""),
        "decision": "run",
        "reuse_allowed": False,
        "reason": force_reason,
        "invalidated_by": invalidated_by,
        "previous_completed_at": str(decision.get("previous_completed_at") or ""),
        "previous_result_path": str(decision.get("previous_result_path") or ""),
        "current_fingerprint_hash": str(decision.get("current_fingerprint_hash") or ""),
    }


def _refresh_full_test_debt_reuse_decision(runtime_entry: Dict[str, Any], *, cache_dir: str) -> None:
    entry = dict(runtime_entry.get("entry") or {})
    if str(entry.get("entry_id") or "") != ENTRY_FULL_TEST_DEBT:
        return
    current_decision = dict(runtime_entry.get("decision") or {})
    if not _full_test_debt_decision_can_refresh(current_decision):
        return
    fingerprint = _strict_long_gate_fingerprint(entry)
    evaluation = evaluate_reuse(entry, fingerprint, repo_root=REPO_ROOT, cache_dir=cache_dir)
    runtime_entry["fingerprint"] = dict(fingerprint)
    runtime_entry["evaluation"] = dict(evaluation)
    refreshed_decision = dict(cast(Mapping[str, Any], evaluation["decision"]))
    runtime_entry["decision"] = refreshed_decision
    if str(refreshed_decision.get("decision") or "") != "reuse":
        for rel_path in list(entry.get("output_result_files") or []):
            abs_path = os.path.join(REPO_ROOT, str(rel_path).replace("\\", "/").replace("/", os.sep))
            if os.path.isfile(abs_path):
                os.remove(abs_path)


def _full_test_debt_decision_can_refresh(decision: Dict[str, Any]) -> bool:
    if _decision_cache_unavailable(decision):
        return False
    decision_kind = str(decision.get("decision") or "")
    if decision_kind == "reuse":
        return True
    if decision_kind != "run":
        return False
    reason = str(decision.get("reason") or "")
    invalidated_by = [str(item) for item in list(decision.get("invalidated_by") or [])]
    if reason.startswith("forced by --long-gate-force-rerun") or any(
        item.startswith("forced by --long-gate-force-rerun") for item in invalidated_by
    ):
        return False
    return True


def _prepare_long_gate_cache_decisions(
    command_plan: Sequence[Dict[str, Any]],
    *,
    cache_enabled: bool,
    cache_dir: str,
    force_rerun_entry_ids: Optional[Sequence[str]] = None,
    force_rerun_all: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    resolved_cache_dir = resolve_long_gate_cache_dir(REPO_ROOT, cache_dir)
    forced_entry_ids: Set[str] = {
        str(entry_id or "").strip() for entry_id in list(force_rerun_entry_ids or []) if str(entry_id or "").strip()
    }
    manifest = build_manifest_from_quality_gate_plan(command_plan, repo_root=REPO_ROOT)
    known_long_gate_entry_ids = {
        str(entry.get("entry_id") or "")
        for entry in list(manifest.get("entries") or [])
        if bool(entry.get("long_gate_candidate")) or bool(entry.get("reuse_allowed"))
    }
    unknown_forced = sorted(forced_entry_ids - known_long_gate_entry_ids)
    if unknown_forced:
        raise QualityGateError(
            "--long-gate-force-rerun 指定了未知的 long gate entry_id: " + ", ".join(unknown_forced)
        )
    summary_entries: List[Dict[str, Any]] = []
    runtime_entries: Dict[str, Dict[str, Any]] = {}
    for index, raw_entry in enumerate(list(manifest.get("entries") or []), start=1):
        entry = dict(raw_entry)
        if not bool(entry.get("long_gate_candidate")) and not bool(entry.get("reuse_allowed")):
            continue
        entry_id = str(entry.get("entry_id") or "")
        force_requested = entry_id in forced_entry_ids
        fingerprint: Optional[Dict[str, Any]] = None
        evaluation: Optional[Dict[str, Any]] = None
        if not cache_enabled:
            decision = _disabled_long_gate_decision(entry)
        elif bool(entry.get("reuse_allowed")):
            try:
                fingerprint = _strict_long_gate_fingerprint(entry)
            except (LongGateFingerprintError, QualityGateError) as exc:
                fingerprint_error = _unwrap_fingerprint_error(exc)
                if fingerprint_error is None:
                    raise
                decision = _fingerprint_error_long_gate_decision(entry, fingerprint_error)
                evaluation = {}
                entry["cache_status"] = "cache_unavailable"
            else:
                evaluation = dict(evaluate_reuse(entry, fingerprint, repo_root=REPO_ROOT, cache_dir=resolved_cache_dir))
                decision = dict(evaluation["decision"])
                if force_rerun_all:
                    decision = _force_long_gate_decision(
                        entry,
                        decision,
                        force_reason="forced by --long-gate-force-rerun-all",
                    )
                    evaluation = {}
                elif force_requested:
                    decision = _force_long_gate_decision(
                        entry,
                        decision,
                        force_reason=f"forced by --long-gate-force-rerun {entry_id}",
                    )
                    evaluation = {}
        else:
            decision = _planned_long_gate_decision_forced(entry, force_requested=force_requested)
        summary_entry = build_summary_entry(index=index, entry=entry, decision=decision)
        summary_entries.append(summary_entry)
        if cache_enabled:
            runtime_entries[str(entry.get("display") or "")] = {
                "entry": entry,
                "fingerprint": fingerprint or {},
                "evaluation": evaluation or {},
                "decision": decision,
                "summary_entry": summary_entry,
            }
    return summary_entries, runtime_entries


def _collect_long_gate_cache_decisions(command_plan: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary_entries, _runtime_entries = _prepare_long_gate_cache_decisions(
        command_plan,
        cache_enabled=True,
        cache_dir="",
    )
    return summary_entries


def _print_long_gate_cache_decisions(entries: Sequence[Dict[str, Any]], *, cache_dir: str) -> None:
    print("Long gate cache decisions", flush=True)
    print("note: explain mode prints decisions only; it is not a quality gate proof", flush=True)
    print(f"cache_dir: {cache_dir}", flush=True)
    if not entries:
        print("- no eligible long-gate entries", flush=True)
        return
    for entry in entries:
        decision = str(entry.get("decision") or "")
        status = {
            "reuse": "REUSE",
            "run": "RUN",
            "planned_only": "PLANNED_ONLY",
            "disabled": "DISABLED",
        }.get(decision, decision.upper() or "UNKNOWN")
        print(f"- {entry.get('entry_id')}: {status}", flush=True)
        print(f"  cache: {entry.get('cache_status')}", flush=True)
        print(f"  reason: {entry.get('reason')}", flush=True)
        fingerprint_error = entry.get("fingerprint_error")
        if isinstance(fingerprint_error, Mapping) and fingerprint_error:
            runtime_key = str(fingerprint_error.get("runtime_key") or "")
            failure_kind = str(fingerprint_error.get("failure_kind") or "")
            if runtime_key:
                print(f"  runtime_key: {runtime_key}", flush=True)
            if failure_kind:
                print(f"  failure_kind: {failure_kind}", flush=True)
            print("  note: cache unavailable for this entry; old success cache will not be reused", flush=True)
            details = fingerprint_error.get("details")
            if isinstance(details, Mapping):
                for key in ("chrome_path", "chrome_source", "chrome_exit_code", "stderr_tail"):
                    if key in details and str(details.get(key) or ""):
                        print(f"  {key}: {details.get(key)}", flush=True)
        if entry.get("previous_result_path"):
            print(f"  previous_result: {entry.get('previous_result_path')}", flush=True)
        if entry.get("current_fingerprint_hash"):
            print(f"  fingerprint: {entry.get('current_fingerprint_hash')}", flush=True)
        _print_long_gate_cache_decision_hint(entry)
        invalidated_by = list(entry.get("invalidated_by") or [])
        if invalidated_by:
            print("  invalidated_by:", flush=True)
            for item in invalidated_by[:10]:
                print(f"    - {item}", flush=True)
            if len(invalidated_by) > 10:
                print(f"    - ... {len(invalidated_by) - 10} more", flush=True)
        _print_fingerprint_diff(entry)


def _format_fingerprint_component(change: Mapping[str, Any]) -> str:
    component = str(change.get("component") or "fingerprint")
    reason = str(change.get("reason") or "input fingerprint changed")
    details: List[str] = []
    for key in ("path", "key", "field"):
        if change.get(key):
            details.append(f"{key}={change.get(key)}")
    if not details:
        for key in ("previous", "current"):
            if key in change:
                details.append(f"{key}={change.get(key)!r}")
    suffix = " " + " ".join(details) if details else ""
    return f"{component}: {reason}{suffix}"


def _print_fingerprint_diff(entry: Mapping[str, Any]) -> None:
    changes = [dict(item) for item in list(entry.get("fingerprint_diff") or []) if isinstance(item, dict)]
    if not changes:
        return
    print("  fingerprint_changed_components:", flush=True)
    for change in changes[:20]:
        print(f"    - {_format_fingerprint_component(change)}", flush=True)
    if len(changes) > 20:
        print(f"    - ... {len(changes) - 20} more", flush=True)


def _normalize_impact_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _dedupe_impact_paths(paths: Sequence[str]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for raw_path in list(paths or []):
        path = _normalize_impact_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        rows.append(path)
    return rows


def _git_impact_paths(args: Sequence[str]) -> List[str]:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if int(completed.returncode) != 0:
        detail = str(completed.stderr or completed.stdout or "git command failed").strip()
        raise QualityGateError("long-gate impact explain 无法读取 git 变更路径：git " + " ".join(args) + "：" + detail)
    return _dedupe_impact_paths(str(completed.stdout or "").splitlines())


def _current_impact_paths() -> List[str]:
    paths: List[str] = []
    for args in (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        paths.extend(_git_impact_paths(args))
    return _dedupe_impact_paths(paths)


def _print_long_gate_impact_explain(command_plan: Sequence[Dict[str, Any]], paths: Sequence[str]) -> None:
    impact = explain_long_gate_impact(command_plan, paths, repo_root=REPO_ROOT)
    print(json.dumps(impact, ensure_ascii=False, sort_keys=True, indent=2), flush=True)


def _quality_gate_rel_exists(rel_path: str) -> bool:
    return os.path.isfile(os.path.join(REPO_ROOT, str(rel_path).replace("\\", "/").replace("/", os.sep)))


def _print_long_gate_cache_decision_hint(entry: Dict[str, Any]) -> None:
    if str(entry.get("decision") or "") != "run":
        return
    entry_id = str(entry.get("entry_id") or "")
    reason = str(entry.get("reason") or "")
    if reason == "no previous success cache":
        print("  cache_state: missing", flush=True)
    elif entry_id != ENTRY_FULL_TEST_DEBT:
        return
    if entry_id != ENTRY_FULL_TEST_DEBT:
        return
    direct_outputs = [
        rel_path
        for rel_path in [
            QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
            QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
        ]
        if _quality_gate_rel_exists(rel_path)
    ]
    if direct_outputs:
        print("  direct_check_outputs:", flush=True)
        for rel_path in direct_outputs:
            print(f"    - {rel_path}", flush=True)
        print(
            "  hint: tools/check_full_test_debt.py writes current/summary proof, but it does not create long gate success cache.",
            flush=True,
        )
        print(
            "  warmup_command: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
            flush=True,
        )


def _print_long_gate_summary(summary: Dict[str, Any], summary_paths: Dict[str, str]) -> None:
    counts = dict(summary.get("counts") or {})
    print("Long gate summary", flush=True)
    for key in ("executed", "reused", "failed", "planned_only", "disabled"):
        print(f"- {key}: {int(counts.get(key) or 0)}", flush=True)
    print(f"- summary_json: {summary_paths.get('summary_json') or ''}", flush=True)
    print(f"- summary_md: {summary_paths.get('summary_md') or ''}", flush=True)


def _write_and_print_long_gate_summary(
    *,
    run_id: str,
    head_sha: str,
    worktree_clean: bool,
    cache_enabled: bool,
    entries: Sequence[Dict[str, Any]],
    failure: Optional[Dict[str, Any]],
    cache_dir: str,
) -> Dict[str, Any]:
    summary = build_long_gate_summary(
        run_id=run_id,
        repo_root=REPO_ROOT,
        head_sha=head_sha,
        worktree_clean=worktree_clean,
        cache_enabled=cache_enabled,
        mode="run",
        entries=entries,
        failure=failure,
        cache_dir=cache_dir,
    )
    summary_paths = write_long_gate_summary(summary, REPO_ROOT)
    _print_long_gate_summary(summary, summary_paths)
    return summary


def _write_pending_long_gate_successes(pending_successes: Sequence[Dict[str, Any]], *, cache_dir: str) -> None:
    for pending in list(pending_successes or []):
        write_long_gate_success(
            dict(pending.get("entry") or {}),
            dict(pending.get("fingerprint") or {}),
            dict(pending.get("command_result") or {}),
            [str(path) for path in list(pending.get("output_files") or [])],
            repo_root=REPO_ROOT,
            cache_dir=cache_dir,
        )


def _print_long_gate_failure(failure: Dict[str, Any]) -> None:
    print(f"FAILED: {failure.get('entry_id') or failure.get('display') or 'unknown'}", flush=True)
    print("command:", flush=True)
    print(f"  {failure.get('display') or ''}", flush=True)
    print("copyable rerun:", flush=True)
    print(f"  {failure.get('copyable_command') or ''}", flush=True)
    print("receipt:", flush=True)
    print(f"  {failure.get('receipt_path') or ''}", flush=True)
    print("stdout log:", flush=True)
    print(f"  {failure.get('stdout_log_path') or ''}", flush=True)
    print("stderr log:", flush=True)
    print(f"  {failure.get('stderr_log_path') or ''}", flush=True)
    print("stdout tail:", flush=True)
    print(str(failure.get("stdout_tail") or ""), flush=True)
    print("stderr tail:", file=sys.stderr, flush=True)
    print(str(failure.get("stderr_tail") or ""), file=sys.stderr, flush=True)


def _output_file_rows(paths: Sequence[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for rel_path in list(paths or []):
        normalized = str(rel_path or "").replace("\\", "/")
        if not normalized:
            continue
        abs_path = os.path.join(REPO_ROOT, normalized.replace("/", os.sep))
        if os.path.isfile(abs_path):
            rows.append({"path": normalized, "sha256": _sha256_file(abs_path)})
    return rows


def _refresh_summary_entry(
    runtime_entry: Dict[str, Any],
    *,
    result: Dict[str, Any],
    receipt_path: str,
    output_file_paths: Optional[Sequence[str]] = None,
    failed: bool = False,
) -> None:
    summary_entry = runtime_entry.get("summary_entry")
    if not isinstance(summary_entry, dict):
        return
    output_files = _output_file_rows(list(output_file_paths or []))
    updated = build_summary_entry(
        index=int(summary_entry.get("index") or 0),
        entry=dict(runtime_entry.get("entry") or {}),
        decision=dict(runtime_entry.get("decision") or {}),
        result=result,
        receipt_path=receipt_path,
        output_files=output_files,
        failed=failed,
    )
    summary_entry.clear()
    summary_entry.update(updated)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if bool(args.fast_precheck):
        from tools import fast_static_precheck

        return int(fast_static_precheck.main([]))
    command_plan = _command_plan_for_worktree_mode(
        build_quality_gate_command_plan(),
        allow_dirty_worktree=bool(args.allow_dirty_worktree),
    )
    if bool(args.long_gate_impact_explain):
        impact_paths = (
            _dedupe_impact_paths(list(args.long_gate_impact_path or []))
            if list(args.long_gate_impact_path or [])
            else _current_impact_paths()
        )
        _print_long_gate_impact_explain(command_plan, impact_paths)
        return 0
    long_gate_cache_enabled = bool((args.long_gate_cache or args.long_gate_cache_explain) and not args.no_long_gate_cache)
    resolved_long_gate_cache_dir = "evidence/QualityGate/long_gate"
    if long_gate_cache_enabled:
        try:
            resolved_long_gate_cache_dir = resolve_long_gate_cache_dir(REPO_ROOT, args.long_gate_cache_dir)
        except ValueError as exc:
            raise QualityGateError(str(exc)) from exc
    if bool(args.long_gate_cache_explain):
        long_gate_summary_entries, _long_gate_runtime_entries = _prepare_long_gate_cache_decisions(
            command_plan,
            cache_enabled=True,
            cache_dir=resolved_long_gate_cache_dir,
            force_rerun_entry_ids=list(args.long_gate_force_rerun or []),
            force_rerun_all=bool(args.long_gate_force_rerun_all),
        )
        _print_long_gate_cache_decisions(long_gate_summary_entries, cache_dir=resolved_long_gate_cache_dir)
        return 0
    started_at = datetime.now().isoformat(timespec="seconds")
    head_sha = _git_head_sha()
    git_status_short_before = _git_status_lines()
    if bool(args.allow_dirty_worktree and not args.no_resume):
        resume_decision = _decide_resume_from_previous_failure(
            command_plan,
            current_head_sha=head_sha,
            current_git_status_short=git_status_short_before,
        )
    elif bool(args.allow_dirty_worktree and args.no_resume):
        resume_decision = ResumeDecision(False, "--no-resume 已指定")
    else:
        resume_decision = ResumeDecision(False, "当前不是 allow-dirty-worktree 模式")
    if resume_decision.enabled:
        print(
            f"提示：检测到上次质量门禁失败，本次从第 {resume_decision.start_command_index}/{len(command_plan)} "
            f"步继续：{resume_decision.start_command_display}",
            flush=True,
        )
    else:
        print(f"提示：未使用续跑：{resume_decision.reason}。本次完整重跑。", flush=True)
    effective_long_gate_cache_enabled = bool(long_gate_cache_enabled and not resume_decision.enabled)
    long_gate_summary_entries, long_gate_runtime_entries = _prepare_long_gate_cache_decisions(
        command_plan,
        cache_enabled=effective_long_gate_cache_enabled,
        cache_dir=resolved_long_gate_cache_dir,
        force_rerun_entry_ids=list(args.long_gate_force_rerun or []) if effective_long_gate_cache_enabled else [],
        force_rerun_all=bool(args.long_gate_force_rerun_all and effective_long_gate_cache_enabled),
    )
    if long_gate_cache_enabled:
        _print_long_gate_cache_decisions(long_gate_summary_entries, cache_dir=resolved_long_gate_cache_dir)
    run_id = f"{head_sha}:{started_at}"
    runtime_snapshot = _runtime_state_snapshot()
    commands: List[Dict[str, Any]] = []
    command_receipts: List[Dict[str, str]] = []
    collection_proof: Optional[Dict[str, Any]] = None
    ruff_version_output: Optional[str] = None
    pyright_version_output: Optional[str] = None
    parsed_command_results: Dict[str, Any] = {}
    long_gate_failure: Dict[str, Any] = {}
    pending_long_gate_successes: List[Dict[str, Any]] = []
    failure_kind: Optional[str] = None
    git_status_short_after: Optional[List[str]] = None
    full_test_debt_runtime_entry = _runtime_entry_by_entry_id(long_gate_runtime_entries, ENTRY_FULL_TEST_DEBT)
    preserve_full_test_debt_outputs = _should_preserve_full_test_debt_outputs(
        full_test_debt_runtime_entry,
        cache_enabled=effective_long_gate_cache_enabled,
        cache_dir=resolved_long_gate_cache_dir,
    )
    require_clean_worktree = bool(args.require_clean_worktree or not args.allow_dirty_worktree)
    manifest = _base_quality_gate_manifest(
        started_at=started_at,
        head_sha=head_sha,
        git_status_short_before=git_status_short_before,
        runtime_snapshot=runtime_snapshot,
        status="running",
        command_plan=command_plan,
    )
    manifest["resume"] = {
        "enabled": bool(resume_decision.enabled),
        "reason": resume_decision.reason,
        "previous_run_id": resume_decision.previous_run_id or None,
        "skip_count": int(resume_decision.skip_count),
        "start_command_index": resume_decision.start_command_index or None,
        "start_command_display": resume_decision.start_command_display or None,
        "previous_failure_message": resume_decision.previous_failure_message or None,
        "proof_status": "pending",
    }
    if not require_clean_worktree:
        _mark_manifest_unbound(manifest)
    _write_quality_gate_manifest(manifest)

    try:
        try:
            if resume_decision.enabled:
                _clear_quality_gate_run_outputs(
                    remove_manifest=False,
                    remove_receipts_and_logs=False,
                    remove_current_debt=not preserve_full_test_debt_outputs,
                    remove_full_test_debt_summary=not preserve_full_test_debt_outputs,
                )
            else:
                _clear_quality_gate_run_outputs(
                    remove_manifest=False,
                    remove_current_debt=not preserve_full_test_debt_outputs,
                    remove_full_test_debt_summary=not preserve_full_test_debt_outputs,
                )
            _clear_stale_long_gate_output_files(
                long_gate_runtime_entries,
                preserve_full_test_debt_outputs=preserve_full_test_debt_outputs,
            )
        except Exception:
            failure_kind = "quality_gate_cleanup_failed"
            raise

        if require_clean_worktree and git_status_short_before:
            failure_kind = "dirty_before_gate"
            raise QualityGateError(_dirty_worktree_message(git_status_short_before))

        try:
            _assert_no_active_runtime()
        except QualityGateError:
            failure_kind = "environment_blocked"
            raise
        _assert_guard_tests_ready()
        try:
            _assert_resume_dirty_fingerprint_still_current(
                resume_decision,
                git_status_short_before=git_status_short_before,
            )
        except QualityGateError:
            failure_kind = "resume_dirty_fingerprint_changed"
            raise

        _run_quality_gate_command_plan(
            command_plan,
            run_id=run_id,
            commands=commands,
            command_receipts=command_receipts,
            parsed_command_results=parsed_command_results,
            resume_decision=resume_decision,
            long_gate_cache=effective_long_gate_cache_enabled,
            long_gate_cache_write_success=bool(
                effective_long_gate_cache_enabled and require_clean_worktree and not resume_decision.enabled
            ),
            long_gate_cache_dir=resolved_long_gate_cache_dir,
            long_gate_runtime_entries=long_gate_runtime_entries,
            long_gate_failure=long_gate_failure,
            pending_long_gate_successes=pending_long_gate_successes,
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

        if long_gate_cache_enabled:
            _write_and_print_long_gate_summary(
                run_id=run_id,
                head_sha=head_sha,
                worktree_clean=not bool(git_status_short_before or git_status_short_after),
                cache_enabled=effective_long_gate_cache_enabled,
                entries=long_gate_summary_entries,
                failure=long_gate_failure or None,
                cache_dir=resolved_long_gate_cache_dir,
            )
            _write_pending_long_gate_successes(pending_long_gate_successes, cache_dir=resolved_long_gate_cache_dir)

        success_by_clean_contract = {
            True: ("passed", "质量门禁通过", 0),
            False: (
                "passed_but_unbound",
                "质量门禁完成，但当前证明未绑定；manifest 已标记 passed_but_unbound，不能当作通过证明。",
                2,
            ),
        }
        success_status, success_message, success_return_code = success_by_clean_contract[require_clean_worktree]
        if resume_decision.enabled:
            success_message = (
                "质量门禁续跑完成；本次跳过了上次已通过的前置命令，只能当作本地快速反馈，不能当作完整通过证明。"
            )
        resume_info = dict(manifest.get("resume") or {})
        resume_info["proof_status"] = (
            "fast_feedback_only"
            if resume_decision.enabled
            else ("full_command_plan_bound" if require_clean_worktree else "full_command_plan_unbound")
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
                "resume": resume_info,
            }
        )
        apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
        if not require_clean_worktree:
            _mark_manifest_unbound(manifest)
        _write_quality_gate_manifest(manifest)
        print(success_message, flush=True)
        return success_return_code
    except Exception as exc:
        collection_proof = cast(Optional[Dict[str, Any]], parsed_command_results.get("collection_proof"))
        ruff_version_output = cast(Optional[str], parsed_command_results.get("ruff_version_output"))
        pyright_version_output = cast(Optional[str], parsed_command_results.get("pyright_version_output"))
        worktree_proof_errors: List[str] = []
        if git_status_short_after is None:
            try:
                git_status_short_after = _git_status_lines()
            except (QualityGateError, OSError) as status_exc:
                git_status_short_after = None
                worktree_proof_errors.append(f"git_status_after: {status_exc}")
        try:
            _apply_worktree_proof(
                manifest,
                git_status_short_before=git_status_short_before,
                git_status_short_after=git_status_short_after,
            )
        except (QualityGateError, OSError) as proof_exc:
            worktree_proof_errors.append(f"worktree_fingerprint: {proof_exc}")
        resume_info = dict(manifest.get("resume") or {})
        resume_info["proof_status"] = "failed"
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
                "resume": resume_info,
            }
        )
        if worktree_proof_errors:
            manifest["worktree_proof_error"] = "；".join(worktree_proof_errors)
        try:
            apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)
            if not require_clean_worktree:
                _mark_manifest_unbound(manifest)
        except Exception as manifest_proof_exc:
            manifest["manifest_proof_error"] = str(manifest_proof_exc)
        try:
            _write_quality_gate_manifest(manifest)
        except Exception as manifest_write_exc:
            print(f"ERROR: 无法写入失败质量门禁 manifest：{manifest_write_exc}", file=sys.stderr, flush=True)
        if long_gate_cache_enabled:
            try:
                _write_and_print_long_gate_summary(
                    run_id=run_id,
                    head_sha=head_sha,
                    worktree_clean=not bool(git_status_short_before or (git_status_short_after or [])),
                    cache_enabled=effective_long_gate_cache_enabled,
                    entries=long_gate_summary_entries,
                    failure=long_gate_failure or None,
                    cache_dir=resolved_long_gate_cache_dir,
                )
            except Exception as summary_write_exc:
                print(f"ERROR: 无法写入 long gate summary：{summary_write_exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2) from exc
