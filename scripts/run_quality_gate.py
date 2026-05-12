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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.long_gate_cache import evaluate_reuse  # noqa: E402
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
from tools.long_gate_manifest import ENTRY_PYTEST_COLLECT_ALL, build_manifest_from_quality_gate_plan  # noqa: E402
from tools.quality_gate_support import (  # noqa: E402
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    QUALITY_GATE_LOGS_DIR_REL,
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
QUALITY_GATE_SELFTEST = QUALITY_GATE_SELFTEST_PATH
GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS = [
    QUALITY_GATE_MANIFEST_REL.replace("\\", "/"),
    QUALITY_GATE_RECEIPTS_DIR_REL.replace("\\", "/") + "/",
    QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/") + "/",
    COLLECT_NODEIDS_REL.replace("\\", "/"),
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"),
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


def _run_command(_display: str, args: Sequence[str], capture_output: bool = False) -> Dict[str, Any]:
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

    process = subprocess.Popen(
        list(args),
        cwd=REPO_ROOT,
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
        if stdout:
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


def _coerce_command_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return {
            "stdout": str(result.get("stdout") or ""),
            "stderr": str(result.get("stderr") or ""),
            "returncode": int(result.get("returncode") or 0),
            "stdout_log_path": str(result.get("stdout_log_path") or ""),
            "stderr_log_path": str(result.get("stderr_log_path") or ""),
        }
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
    result.setdefault("timed_out", False)
    result.setdefault("interrupted", False)
    result.setdefault("partial_write", False)
    return duration_s


def _clear_quality_gate_run_outputs(
    *,
    remove_manifest: bool = True,
    remove_receipts_and_logs: bool = True,
    remove_current_debt: bool = True,
) -> None:
    for rel_path in (QUALITY_GATE_RECEIPTS_DIR_REL, QUALITY_GATE_LOGS_DIR_REL):
        if not remove_receipts_and_logs:
            continue
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
    if remove_current_debt:
        _clear_quality_gate_current_full_test_debt()
    if remove_manifest:
        _remove_quality_gate_manifest()


def _clear_quality_gate_current_full_test_debt() -> None:
    current_debt_path = os.path.join(REPO_ROOT, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL)
    if os.path.isfile(current_debt_path):
        os.remove(current_debt_path)


def _remove_quality_gate_manifest() -> None:
    manifest_path = _quality_gate_manifest_abs_path()
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)


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
    resume_decision: Optional[ResumeDecision] = None,
    long_gate_cache: bool = False,
    long_gate_cache_write_success: bool = True,
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
    total = len(command_plan)
    long_gate_entries: Dict[str, Dict[str, Any]] = {}
    if long_gate_cache:
        long_manifest = build_manifest_from_quality_gate_plan(command_plan, repo_root=REPO_ROOT)
        long_gate_entries = {
            str(entry.get("display") or ""): dict(entry)
            for entry in list(long_manifest.get("entries") or [])
            if str(entry.get("entry_id") or "") == ENTRY_PYTEST_COLLECT_ALL
        }
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
        long_gate_entry = long_gate_entries.get(display)
        long_gate_fingerprint: Optional[Dict[str, Any]] = None
        if long_gate_entry is not None:
            long_gate_fingerprint = _strict_long_gate_fingerprint(long_gate_entry)
            reuse_evaluation = evaluate_reuse(long_gate_entry, long_gate_fingerprint, repo_root=REPO_ROOT)
            decision = dict(reuse_evaluation["decision"])
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
                try:
                    parsed_command_results.update(command_result_handlers[display](display, result))
                except QualityGateError as exc:
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

        result = _coerce_command_result(
            _run_command(display, _resolve_command_args(command), capture_output=bool(command.get("capture_output")))
        )
        result.update(_write_command_output_logs(index=command_index, display=display, result=result))
        result["execution_mode"] = "executed"
        elapsed = _mark_command_timing(result, started_at=command_started_at, start_monotonic=start_monotonic)
        commands.append(command)
        receipt_entry = _write_command_receipt(command, run_id=run_id, index=command_index, result=result)
        command_receipts.append(receipt_entry)
        returncode = int(result.get("returncode") or 0)
        if returncode != 0:
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
        if long_gate_entry is not None and long_gate_fingerprint is not None:
            if not bool(long_gate_cache_write_success):
                print(
                    f"==> 第 {command_index}/{total} 步：跳过 long-gate success cache 写入，"
                    "因为本次不是干净工作区的完整成功证明",
                    flush=True,
                )
            else:
                collect_payload = build_collect_nodeids_payload(
                    str(result.get("stdout") or ""),
                    pytest_version=pytest_distribution_version(strict=True),
                    collect_stdout_log_path=str(result.get("stdout_log_path") or ""),
                )
                collect_rel_path = write_collect_nodeids(collect_payload, repo_root=REPO_ROOT)
                cache_result = dict(result)
                cache_result.pop("stdout_log_path", None)
                cache_result.pop("stderr_log_path", None)
                write_long_gate_success(
                    long_gate_entry,
                    long_gate_fingerprint,
                    cache_result,
                    [os.path.join(REPO_ROOT, collect_rel_path.replace("/", os.sep))],
                    repo_root=REPO_ROOT,
                )
        print(f"==> 第 {command_index}/{total} 步结束：通过，耗时 {elapsed:.1f}s，receipt={receipt_entry['path']}", flush=True)


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


def _resolve_command_args(command: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for idx, raw_arg in enumerate(list(command.get("args") or [])):
        arg = str(raw_arg)
        if idx == 0 and arg == "python":
            args.append(sys.executable)
            continue
        args.append(arg)
    return args


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
        if args == ["python", checker_path]:
            updated = dict(command)
            updated["display"] = f"{str(command.get('display') or '').strip()} --allow-dirty-worktree-proof"
            updated["args"] = [*args, "--allow-dirty-worktree-proof"]
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
    parser.add_argument("--require-clean-worktree", action="store_true", help="require a clean worktree")
    parser.add_argument("--allow-dirty-worktree", action="store_true", help="allow a dirty worktree but mark the run unbound")
    parser.add_argument("--long-gate-cache", action="store_true", help="reuse eligible long-gate success cache entries")
    parser.add_argument("--no-long-gate-cache", action="store_true", help="disable long-gate success cache reuse")
    parser.add_argument(
        "--long-gate-cache-explain",
        action="store_true",
        help="print long-gate cache decisions without executing quality-gate commands",
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
    return parsed


def _collect_long_gate_cache_decisions(command_plan: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    manifest = build_manifest_from_quality_gate_plan(command_plan, repo_root=REPO_ROOT)
    decisions: List[Dict[str, Any]] = []
    for entry in list(manifest.get("entries") or []):
        if str(entry.get("entry_id") or "") != ENTRY_PYTEST_COLLECT_ALL:
            continue
        fingerprint = _strict_long_gate_fingerprint(dict(entry))
        evaluation = evaluate_reuse(entry, fingerprint, repo_root=REPO_ROOT)
        decision = dict(evaluation["decision"])
        decisions.append(decision)
    return decisions


def _print_long_gate_cache_decisions(decisions: Sequence[Dict[str, Any]]) -> None:
    print("Long gate cache decisions (collect-only enabled in this stage)", flush=True)
    print("note: explain mode prints decisions only; it is not a quality gate proof", flush=True)
    if not decisions:
        print("- no eligible long-gate entries", flush=True)
        return
    for decision in decisions:
        status = "REUSE" if decision.get("decision") == "reuse" else "RUN"
        print(f"- {decision.get('entry_id')}: {status}", flush=True)
        print(f"  reason: {decision.get('reason')}", flush=True)
        if decision.get("previous_completed_at"):
            print(f"  previous_success: {decision.get('previous_completed_at')}", flush=True)
        if decision.get("current_fingerprint_hash"):
            print(f"  fingerprint: {decision.get('current_fingerprint_hash')}", flush=True)
        invalidated_by = list(decision.get("invalidated_by") or [])
        if invalidated_by:
            print("  invalidated_by:", flush=True)
            for item in invalidated_by:
                print(f"    - {item}", flush=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    command_plan = _command_plan_for_worktree_mode(
        build_quality_gate_command_plan(),
        allow_dirty_worktree=bool(args.allow_dirty_worktree),
    )
    long_gate_cache_enabled = bool((args.long_gate_cache or args.long_gate_cache_explain) and not args.no_long_gate_cache)
    if bool(args.long_gate_cache_explain):
        _print_long_gate_cache_decisions(_collect_long_gate_cache_decisions(command_plan))
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
    if long_gate_cache_enabled:
        _print_long_gate_cache_decisions(_collect_long_gate_cache_decisions(command_plan))
    run_id = f"{head_sha}:{started_at}"
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
                _clear_quality_gate_run_outputs(remove_manifest=False, remove_receipts_and_logs=False)
            else:
                _clear_quality_gate_run_outputs(remove_manifest=False)
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
            long_gate_cache=long_gate_cache_enabled,
            long_gate_cache_write_success=bool(
                long_gate_cache_enabled and require_clean_worktree and not resume_decision.enabled
            ),
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
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2) from exc
