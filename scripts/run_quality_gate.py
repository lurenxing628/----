from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, NoReturn, Optional, Sequence, Set, Tuple, Union, cast

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import quality_gate_shared
from tools.long_gate_cache import (
    PreparedSuccessWrite,
    cache_log_rel_paths,
    cache_result_rel_path,
    cache_unavailable_decision,
    commit_prepared_success_write,
    evaluate_cache,
    prepare_success_write,
    resolve_cache_dir,
    write_failure,
)
from tools.long_gate_collect import build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_fingerprint import (
    FingerprintFileSnapshot,
    LongGateFingerprintError,
    command_environment,
    fingerprint_entry,
    fingerprint_environment,
    pytest_distribution_version,
)
from tools.long_gate_manifest import explain_long_gate_impact, normalize_repo_path
from tools.long_gate_paths import LEDGER_REL, LONG_GATE_CACHE_DIR_REL, GateContext, resolve_repo_root
from tools.long_gate_records import (
    CacheDecision,
    CacheRecord,
    CommandResult,
    DecisionCause,
    GateEntry,
    Receipt,
    ReceiptRow,
    Rejection,
    RuntimeEntry,
    StepOutcome,
    admit_manifest,
    admit_receipt,
    build_receipt,
    gate_entries,
)
from tools.long_gate_schema import (
    SensitiveSourceError,
    content_equal,
    decode_nul_paths,
    long_gate_cache_metadata,
    read_file_content,
    repo_identity,
)
from tools.long_gate_summary import (
    SUMMARY_COUNT_KEYS,
    TAIL_LINES,
    build_long_gate_summary,
    copyable_failure,
    summary_entry,
    tail_text,
    write_long_gate_summary,
)
from tools.quality_gate_shared import (
    QUALITY_GATE_COLLECT_NODEIDS_REL,
    QUALITY_GATE_COMMAND_KEYS,
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    QUALITY_GATE_DEBT_LEDGER_SYNC_REL,
    QUALITY_GATE_FAILED_FULL_TEST_DEBT_REL,
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
    QUALITY_GATE_LOGS_DIR_REL,
    QUALITY_GATE_MANIFEST_REL,
    QUALITY_GATE_PROOF_SCHEMA_VERSION,
    QUALITY_GATE_PROOF_SCOPE,
    QUALITY_GATE_PYRIGHT_GATE_CONFIG,
    QUALITY_GATE_PYRIGHT_GATE_FULL_REL,
    QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
    QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL,
    QUALITY_GATE_QUICKREF_VS_ROUTES_REL,
    QUALITY_GATE_RECEIPTS_DIR_REL,
    QUALITY_GATE_REQUIRED_REGRESSIONS_REL,
    QUALITY_GATE_RUFF_CHECK_FULL_REL,
    QUALITY_GATE_TOOL_PATHS,
    GateCheckSpec,
    QualityGateError,
    build_quality_gate_collection_proof,
    build_quality_gate_receipt_rel_path,
    build_quality_gate_source_proof,
    iter_quality_gate_required_tests,
    normalize_command_output_for_policy,
    parse_pytest_collect_nodeids,
)
from web.bootstrap.launcher_contract_result import read_runtime_contract_result
from web.bootstrap.launcher_health import probe_runtime_health_result
from web.bootstrap.launcher_lock_result import read_runtime_lock_result
from web.bootstrap.launcher_paths import resolve_runtime_state_paths
from web.bootstrap.launcher_processes import pid_matches_contract, query_pid_state

REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())

PYRIGHT_REQUIRED_VERSION = (1, 1, 406)
PYRIGHT_GATE_CONFIG = QUALITY_GATE_PYRIGHT_GATE_CONFIG
PYRIGHT_TOOLS_CONFIG = QUALITY_GATE_PYRIGHT_TOOLS_CONFIG
# long-gate 专题证明（随成功缓存作为输出文件保存，供人查看）的形状版本。
REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION = 6
STATIC_CHECK_PROOF_SCHEMA_VERSION = 3
DEBT_LEDGER_SYNC_PROOF_SCHEMA_VERSION = 3
GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS = [
    QUALITY_GATE_MANIFEST_REL.replace("\\", "/"),
    QUALITY_GATE_RECEIPTS_DIR_REL.replace("\\", "/") + "/",
    QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/") + "/",
    QUALITY_GATE_COLLECT_NODEIDS_REL.replace("\\", "/"),
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"),
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL.replace("\\", "/"),
    "evidence/QualityGate/architecture_scan_cache.json",
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
# 这两类条目的输入含本次前序步骤的产物（collect 收集结果、full_test_debt payload）：
# 执行前按当时的输入重新判定复用，成功后按命令完成时的输入写成功缓存。
_INPUTS_FROM_EARLIER_STEPS = frozenset({"full_test_debt", "required_regressions"})


@dataclass(frozen=True)
class ResumedStep:
    """续跑可复用的一步：已绑定本次计划的旧 receipt，以及它两份日志的原文。"""

    receipt: Receipt
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ResumeDecision:
    """续跑判定；resumed_steps 是旧失败位置之前、已校验成功的非 none 步骤，按原序号排列。"""

    enabled: bool
    reason: str
    previous_run_id: str = ""
    previous_failure_message: Optional[str] = None
    failed_command_index: int = 0
    failed_command_display: str = ""
    resumed_steps: Tuple[ResumedStep, ...] = ()
    validated_dirty_content: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class LongGateCacheContext:
    """本次生效的 long-gate 缓存：缓存目录、缓存元数据、是否写入缓存。

    metadata 为 None 表示元数据含敏感内容、不可用；此时每个条目的决策都是 cache unavailable，
    执行中不读写缓存。
    """

    cache_dir: str
    metadata: Optional[Mapping[str, Any]]
    write_success: bool


@dataclass(frozen=True)
class PendingSuccess:
    """命令已通过、等 summary 写成功后再落盘的成功缓存。"""

    entry: GateEntry
    fingerprint: Mapping[str, Any]
    result: CommandResult
    receipt_path: str
    output_files: Tuple[str, ...]
    metadata: Mapping[str, Any]


@dataclass
class PlanProgress:
    """命令计划执行中逐步更新的状态与产物；失败路径也要读到它们，所以由调用方持有。

    `running_command_index` 是正在执行的步骤序号，步骤开始前与全部步骤结束后为 None；
    失败收尾把它写成 manifest 的 `failure_command_index`，续跑按它划定可复用的步骤。
    """

    run_id: str
    total: int
    commands: List[Mapping[str, Any]]
    command_receipts: List[Dict[str, Any]]
    parsed_command_results: Dict[str, Any]
    pending_successes: List[PendingSuccess]
    running_command_index: Optional[int] = None


class RuntimeProbeState(str, Enum):
    ABSENT = "absent"
    ACTIVE = "active"
    STALE = "stale"
    UNKNOWN = "unknown"


#: 父进程收到中断后等子命令自行退出的秒数（终端 Ctrl+C 已同时发给子命令），超时才终止它。
_INTERRUPT_GRACE_S = 10.0
#: 等待子命令的轮询间隔：Windows 上无超时的 wait 停在原生等待里，主线程处理不了 Ctrl+C，带超时的 wait 每轮回到 Python 层。
_WAIT_POLL_S = 0.2


def _wait_polling(process: subprocess.Popen[str]) -> int:
    while True:
        try:
            return process.wait(timeout=_WAIT_POLL_S)
        except subprocess.TimeoutExpired:
            continue


def _run_command(
    ctx: GateContext,
    check_id: str,
    args: Sequence[str],
    capture_output: bool = False,
    *,
    environment: Mapping[str, str],
) -> Dict[str, Any]:
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []

    def pump_stream(stream, chunks: List[str], *, sink: Optional[Any]) -> None:
        try:
            for chunk in iter(stream.readline, ""):
                chunks.append(str(chunk))
                if sink is not None:
                    print(quality_gate_shared.sanitize_quality_gate_output(str(chunk)), end="", file=sink, flush=True)
        finally:
            stream.close()

    process = subprocess.Popen(
        list(args),
        cwd=ctx.repo_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None or process.stderr is None:  # pragma: no cover
        raise QualityGateError("无法捕获子命令 stdout/stderr")
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
    # 父进程在等待时收到中断：先等子命令退出（超时则终止），把管道读到结尾，如实返回已取得的输出与退出码，
    # 由执行边界登记本步后继续传播中断。
    interrupted = False
    try:
        returncode = _wait_polling(process)
    except KeyboardInterrupt:
        interrupted = True
        try:
            returncode = process.wait(timeout=_INTERRUPT_GRACE_S)
        except subprocess.TimeoutExpired:
            process.terminate()
            returncode = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if capture_output:
        if check_id == quality_gate_shared.ENTRY_PYTEST_COLLECT_ALL:
            if returncode == 0:
                print(_format_collect_only_success(stdout), flush=True)
        elif stdout:
            print(quality_gate_shared.sanitize_quality_gate_output(stdout).rstrip(), flush=True)
    elif returncode != 0:
        if stdout and not stdout.endswith("\n"):
            print(flush=True)
        if stderr and not stderr.endswith("\n"):
            print(file=sys.stderr, flush=True)
    return {
        "stdout": stdout,
        "stderr": stderr,
        "returncode": int(returncode),
        "interrupted": interrupted,
    }


def _format_collect_only_success(stdout: str) -> str:
    return f"collected_count={len(_parse_collect_nodeids(stdout))}"


def _collect_nodeids_or_raise(stdout: str) -> List[str]:
    nodeids = _parse_collect_nodeids(stdout)
    if not nodeids:
        raise QualityGateError("pytest collect-only 输出没有任何 test nodeid，不能生成 collection proof")
    return nodeids


def _print_command_log_tail(result: CommandResult) -> None:
    print(f"--- stdout 最后 {TAIL_LINES} 行：{result.stdout_log_path} ---", flush=True)
    print(tail_text(quality_gate_shared.sanitize_quality_gate_output(result.stdout)), flush=True)
    print(f"--- stderr 最后 {TAIL_LINES} 行：{result.stderr_log_path} ---", file=sys.stderr, flush=True)
    print(tail_text(quality_gate_shared.sanitize_quality_gate_output(result.stderr)), file=sys.stderr, flush=True)


def _raise_command_failure(
    entry: GateEntry,
    *,
    total: int,
    receipt_path: str,
    result: CommandResult,
    detail: str = "",
) -> NoReturn:
    _print_command_log_tail(result)
    message = (
        f"质量门禁第 {entry.index}/{total} 步失败：\n"
        f"命令：{entry.spec.display}\n"
        f"returncode：{result.returncode}\n"
        f"receipt：{receipt_path}\n"
        f"stdout 日志：{result.stdout_log_path}\n"
        f"stderr 日志：{result.stderr_log_path}"
    )
    if detail:
        message += f"\n原因：{detail}"
    raise QualityGateError(message)


def _print_step_end(
    entry: GateEntry, *, total: int, result: CommandResult, receipt_path: str, failed: bool, label: str = ""
) -> None:
    status = f"失败(returncode={result.returncode})" if failed else "通过"
    print(
        f"==> 第 {entry.index}/{total} 步结束：{label}{status}，耗时 {result.duration_s:.1f}s，receipt={receipt_path}",
        flush=True,
    )


def _quality_gate_manifest_abs_path(ctx: GateContext) -> str:
    return os.path.join(ctx.repo_root, QUALITY_GATE_MANIFEST_REL.replace("/", os.sep))


def _read_repo_text(ctx: GateContext, rel_path: str) -> str:
    abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
    with open(abs_path, encoding="utf-8", newline="") as handle:
        return handle.read()


def _worktree_status_lines(status_lines: Sequence[str]) -> List[str]:
    return [str(line) for line in list(status_lines or []) if str(line)]


def _run_git_bytes(ctx: GateContext, args: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=ctx.repo_root,
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


def _dirty_worktree_content(ctx: GateContext, status_lines: Sequence[str]) -> Dict[str, Any]:
    normalized_lines = _worktree_status_lines(status_lines)
    diffs: Dict[str, str] = {}
    if normalized_lines:
        for kind, args in (
            ("unstaged", ["diff", "--no-ext-diff", "--binary"]),
            ("staged", ["diff", "--cached", "--no-ext-diff", "--binary"]),
        ):
            raw = _run_git_bytes(ctx, args)
            text = raw.decode("utf-8", errors="replace")
            if quality_gate_shared.sanitize_quality_gate_output(text) != text:
                raise QualityGateError("脏工作区差异包含敏感环境值，未保存来源内容。")
            diffs[kind] = base64.b64encode(raw).decode("ascii")
    rows: List[Dict[str, Any]] = []
    for line in normalized_lines:
        rel_path = _status_line_path(line)
        if not rel_path:
            continue
        abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
        row: Dict[str, Any] = {"path": rel_path}
        try:
            if os.path.islink(abs_path):
                row.update(kind="symlink", target=os.readlink(abs_path))
            elif os.path.isfile(abs_path):
                row.update(kind="file", content_base64=read_file_content(abs_path))
            elif os.path.isdir(abs_path):
                files: List[Dict[str, str]] = []
                for dirpath, dirnames, filenames in os.walk(abs_path):
                    dirnames.sort()
                    filenames.sort()
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        files.append({"path": os.path.relpath(file_path, ctx.repo_root).replace(os.sep, "/"),
                                      "content_base64": read_file_content(file_path)})
                row.update(kind="directory", files=files)
            else:
                row.update(kind="missing")
        except SensitiveSourceError as exc:
            raise QualityGateError(f"脏工作区包含敏感来源内容，未保存来源证明：{exc}") from exc
        rows.append(row)
    return {"status_lines": normalized_lines, "diffs_base64": diffs, "paths": rows}


def _expected_command_log_rel_paths(index: int, display: str) -> Tuple[str, str]:
    """第 index 步命令日志的唯一路径规则：(stdout, stderr)。"""
    receipt_rel = build_quality_gate_receipt_rel_path(index, display)
    stem = os.path.splitext(os.path.basename(receipt_rel))[0]
    logs_dir = QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/")
    return f"{logs_dir}/{stem}.stdout.log", f"{logs_dir}/{stem}.stderr.log"


def _write_command_output_logs(ctx: GateContext, entry: GateEntry, *, stdout: str, stderr: str) -> Tuple[str, str]:
    log_paths = _expected_command_log_rel_paths(entry.index, entry.spec.display)
    for rel_path, text in zip(log_paths, (stdout, stderr)):
        abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(quality_gate_shared.sanitize_quality_gate_output(text))
    return log_paths


def _step_start() -> Tuple[str, float]:
    # 用 perf_counter 而非 monotonic：Windows 上 monotonic 分辨率粗（~15ms），瞬时返回的
    # 命令会量到 duration_s=0.0；perf_counter 为高分辨率计时，快操作也能得到正时长。
    return datetime.now().isoformat(timespec="seconds"), time.perf_counter()


def _command_result(
    started: Tuple[str, float],
    *,
    stdout: str,
    stderr: str,
    returncode: int,
    log_paths: Tuple[str, str],
    execution_mode: str,
    reused_from: Mapping[str, Any],
    duration_kind: str,
    original_duration_s: Optional[float],
) -> CommandResult:
    started_at, start_perf = started
    return CommandResult(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        stdout_log_path=log_paths[0],
        stderr_log_path=log_paths[1],
        execution_mode=execution_mode,
        reused_from=reused_from,
        started_at=started_at,
        ended_at=datetime.now().isoformat(timespec="seconds"),
        duration_s=time.perf_counter() - start_perf,
        duration_kind=duration_kind,
        original_duration_s=original_duration_s,
    )


def _execute_step(
    ctx: GateContext,
    entry: GateEntry,
    progress: PlanProgress,
    runtime_entries: Dict[str, RuntimeEntry],
    *,
    started: Tuple[str, float],
    environment: Mapping[str, str],
    environment_fingerprint: Mapping[str, Any],
) -> Tuple[CommandResult, str]:
    """实际执行一步并写 receipt，返回结果与 receipt 路径。

    等待子命令时被中断：按已取得的输出照常写日志与 receipt、登记本步失败，再继续向外传播中断。
    """
    raw = _run_command(
        ctx,
        entry.spec.check_id,
        _resolve_command_args(entry.command["args"]),
        capture_output=entry.command["capture_output"],
        environment=environment,
    )
    result = _command_result(
        started,
        stdout=raw["stdout"],
        stderr=raw["stderr"],
        returncode=raw["returncode"],
        log_paths=_write_command_output_logs(ctx, entry, stdout=raw["stdout"], stderr=raw["stderr"]),
        execution_mode="executed",
        reused_from={},
        duration_kind="executed",
        original_duration_s=None,
    )
    receipt_path = _record_step(ctx, progress, entry, result, environment_fingerprint)
    if raw["interrupted"]:
        _record_outcome(runtime_entries, entry, result, receipt_path, failed=True)
        _print_step_end(entry, total=progress.total, result=result, receipt_path=receipt_path, failed=True, label="[interrupted] ")
        raise KeyboardInterrupt(
            f"质量门禁第 {entry.index}/{progress.total} 步被中断：{entry.spec.display}；receipt：{receipt_path}"
        )
    return result, receipt_path


def _resumed_result(ctx: GateContext, entry: GateEntry, step: ResumedStep, started: Tuple[str, float]) -> CommandResult:
    receipt = step.receipt
    return _command_result(
        started,
        stdout=step.stdout,
        stderr=step.stderr,
        returncode=receipt.returncode,
        log_paths=_write_command_output_logs(ctx, entry, stdout=step.stdout, stderr=step.stderr),
        execution_mode="resumed_success",
        reused_from={
            "receipt_path": receipt.path,
            "receipt_content": receipt.payload,
            "run_id": receipt.run_id,
            "completed_at": receipt.ended_at,
        },
        duration_kind="resume_overhead",
        original_duration_s=receipt.duration_s,
    )


def _cache_reused_from(record: CacheRecord) -> Dict[str, Any]:
    return {
        "result_path": record.result_path,
        "completed_at": record.completed_at,
        "fingerprint": record.fingerprint,
        "duration_s": record.duration_s,
    }


def _reused_success_result(
    ctx: GateContext, entry: GateEntry, record: CacheRecord, started: Tuple[str, float]
) -> CommandResult:
    return _command_result(
        started,
        stdout=record.stdout_content,
        stderr=record.stderr_content,
        returncode=record.returncode,
        log_paths=_write_command_output_logs(ctx, entry, stdout=record.stdout_content, stderr=record.stderr_content),
        execution_mode="reused_success_cache",
        reused_from=_cache_reused_from(record),
        duration_kind="reuse_overhead",
        original_duration_s=record.duration_s,
    )


def _cached_failure_result(record: CacheRecord, started: Tuple[str, float]) -> CommandResult:
    # 缓存失败的 receipt 指向 long-gate 日志；续跑按命令日志目录绑定 receipt，因此这类失败步骤不会被续跑复用。
    return _command_result(
        started,
        stdout=record.stdout_content,
        stderr=record.stderr_content,
        returncode=record.returncode,
        log_paths=(record.stdout_log_path, record.stderr_log_path),
        execution_mode="cached_failure",
        reused_from=_cache_reused_from(record),
        duration_kind="reuse_overhead",
        original_duration_s=record.duration_s,
    )


def _strict_long_gate_fingerprint(
    ctx: GateContext, entry: GateEntry, *, file_snapshot: Optional[FingerprintFileSnapshot] = None
) -> Dict[str, Any]:
    try:
        return fingerprint_entry(entry, ctx.repo_root, strict=True, file_snapshot=file_snapshot)
    except LongGateFingerprintError as exc:
        raise QualityGateError(str(exc)) from exc


def _fingerprint_failure_kind(error: QualityGateError) -> str:
    """_strict_long_gate_fingerprint 总是把带 failure_kind 的 LongGateFingerprintError 链在 __cause__ 上。"""
    cause = cast(LongGateFingerprintError, error.__cause__)
    return cause.details.get("failure_kind", "")


def _changed_environment_keys(previous: Mapping[str, Any], current: Mapping[str, Any]) -> List[str]:
    return [key for key in current["keys"] if not content_equal(previous["values"][key], current["values"][key])]


def _bind_previous_receipt(
    ctx: GateContext, row: ReceiptRow, entry: GateEntry, *, previous_run_id: str
) -> Union[ResumedStep, str]:
    """把旧 manifest 第 entry.index 步的 receipt 绑定到本次计划；返回可复用的步骤，或不能续跑的理由。"""
    index = entry.index
    if row.path != build_quality_gate_receipt_rel_path(index, entry.spec.display):
        return "UNBOUND: quality gate command receipt path mismatch"
    admitted = admit_receipt(ctx.repo_root, row.path)
    if isinstance(admitted, Rejection):
        return admitted.reason
    if not content_equal(admitted.payload, row.content):
        return "UNBOUND: quality gate command receipt content mismatch"
    if admitted.run_id != previous_run_id:
        return "UNBOUND: quality gate command receipt run_id mismatch"
    if admitted.command_index != index:
        return "UNBOUND: quality gate command receipt command_index mismatch"
    for key in QUALITY_GATE_COMMAND_KEYS:
        if not content_equal(admitted.command[key], entry.command[key]):
            return f"UNBOUND: quality gate command receipt {key} mismatch"
    # 准入已保证 values 恰好以 keys 为键；这里再绑定 keys 就是本步规格的 env_keys，环境比较才能逐键直接对照。
    if admitted.environment["keys"] != list(entry.spec.env_keys):
        return "UNBOUND: quality gate command receipt environment keys mismatch"
    texts: List[str] = []
    for rel_path, expected_rel_path, content in zip(
        (admitted.stdout_log_path, admitted.stderr_log_path),
        _expected_command_log_rel_paths(index, entry.spec.display),
        (admitted.stdout_content, admitted.stderr_content),
    ):
        if rel_path != expected_rel_path:
            return f"旧 receipt 日志路径不匹配：第 {index} 步"
        try:
            text = _read_repo_text(ctx, rel_path)
        except (OSError, UnicodeDecodeError):
            return f"旧 receipt 日志缺失或不可读：{rel_path}"
        if normalize_command_output_for_policy(text, policy=admitted.command["output_policy"]) != content:
            return f"旧 receipt 输出原文不一致：{rel_path}"
        texts.append(text)
    return ResumedStep(admitted, texts[0], texts[1])


def _decide_resume_from_previous_failure(
    ctx: GateContext,
    plan: Sequence[GateEntry],
    *,
    current_head_sha: str,
    current_git_status_short: Sequence[str],
) -> ResumeDecision:
    admitted = admit_manifest(_quality_gate_manifest_abs_path(ctx))
    if isinstance(admitted, Rejection):
        return ResumeDecision(False, admitted.reason)
    manifest = admitted
    if manifest.status != "failed":
        return ResumeDecision(False, "上次不是失败记录")
    if manifest.head_sha != current_head_sha:
        return ResumeDecision(
            False, f"旧 manifest head_sha 与当前 HEAD 不一致，不能续跑：previous={manifest.head_sha} current={current_head_sha}"
        )
    current_identity = _repo_identity(ctx)
    for field_name, previous_value in (
        ("checkout_root_realpath", manifest.checkout_root_realpath),
        ("git_common_dir_realpath", manifest.git_common_dir_realpath),
    ):
        if previous_value != current_identity[field_name]:
            return ResumeDecision(False, f"旧 manifest 仓库身份不一致，不能续跑：{field_name}")
    current_dirty_content = _dirty_worktree_content(ctx, current_git_status_short)
    if not content_equal(manifest.dirty_worktree_content_before, current_dirty_content):
        return ResumeDecision(False, "脏工作区内容已变化，本次完整重跑")
    if not content_equal(list(manifest.planned_commands), [entry.command for entry in plan]):
        return ResumeDecision(False, "命令计划已变化，本次完整重跑")

    # 失败位置取 manifest 记录的失败步骤，不按退出码反推：中断后的子命令可能以 0 退出，
    # 结果解析或写证明失败时退出码也是 0。只复用失败位置之前、已校验成功的非 none 步骤。
    failed_index = manifest.failure_command_index
    if failed_index is None:
        return ResumeDecision(False, "上次失败不在某个命令步骤上，没有可复用的步骤")
    if not 1 <= failed_index <= len(plan):
        return ResumeDecision(False, f"旧 manifest 的失败步骤不在本次命令计划内：第 {failed_index} 步")
    resumed_steps: List[ResumedStep] = []
    for entry in plan[: failed_index - 1]:
        index = entry.index
        if index > len(manifest.command_receipts):
            return ResumeDecision(False, f"旧 receipt 缺失：第 {index} 步")
        bound = _bind_previous_receipt(
            ctx, manifest.command_receipts[index - 1], entry, previous_run_id=manifest.run_id
        )
        if isinstance(bound, str):
            return ResumeDecision(False, bound)
        if bound.receipt.returncode != 0:
            return ResumeDecision(False, f"旧 receipt 在失败步骤之前就已失败：第 {index} 步")
        if entry.spec.reuse_policy == "none":
            # 版本与环境探针等 none 步骤每次都重新执行，不复用。
            continue
        current_environment = fingerprint_environment(
            entry.spec.env_keys, environment=command_environment(entry.command["env_overlay"]), repo_root=ctx.repo_root
        )
        if not content_equal(bound.receipt.environment, current_environment):
            changed_keys = _changed_environment_keys(bound.receipt.environment, current_environment)
            return ResumeDecision(False, f"环境与上次不一致：第 {index} 步（{'、'.join(changed_keys)}）")
        # 指纹相等时两边的私有键清单相同。私有键只记“是否存在”，取值换了也看不出来，
        # 与 long-gate 缓存同一条规则：带私有键的步骤一律不复用。
        private_keys = current_environment["non_reusable_env_keys"]
        if private_keys:
            return ResumeDecision(
                False, f"环境含私有键，只能确认存在、核对不了取值：第 {index} 步（{'、'.join(private_keys)}）"
            )
        resumed_steps.append(bound)
    if not resumed_steps:
        return ResumeDecision(False, f"上次失败在第 {failed_index} 步，之前没有可复用的成功步骤")
    return ResumeDecision(
        True,
        "找到可复用的成功步骤",
        previous_run_id=manifest.run_id,
        previous_failure_message=manifest.failure_message,
        failed_command_index=failed_index,
        failed_command_display=plan[failed_index - 1].spec.display,
        resumed_steps=tuple(resumed_steps),
        validated_dirty_content=current_dirty_content,
    )


def _write_command_receipt(
    ctx: GateContext, entry: GateEntry, *, run_id: str, result: CommandResult, environment: Mapping[str, Any]
) -> Dict[str, Any]:
    receipt_rel = build_quality_gate_receipt_rel_path(entry.index, entry.spec.display)
    receipt_abs = os.path.join(ctx.repo_root, receipt_rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(receipt_abs), exist_ok=True)
    payload = build_receipt(
        entry.command, run_id=run_id, command_index=entry.index, result=result, environment=environment
    )
    with open(receipt_abs, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"path": receipt_rel, "content": payload}


def _record_step(
    ctx: GateContext, progress: PlanProgress, entry: GateEntry, result: CommandResult, environment: Mapping[str, Any]
) -> str:
    progress.commands.append(entry.command)
    receipt = _write_command_receipt(ctx, entry, run_id=progress.run_id, result=result, environment=environment)
    progress.command_receipts.append(receipt)
    return receipt["path"]


def _clear_quality_gate_run_outputs(
    ctx: GateContext, *, keep_receipts_and_logs: bool, keep_full_test_debt_outputs: bool
) -> None:
    if not keep_receipts_and_logs:
        for rel_path in (QUALITY_GATE_RECEIPTS_DIR_REL, QUALITY_GATE_LOGS_DIR_REL):
            abs_path = os.path.join(ctx.repo_root, rel_path)
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
    if not keep_full_test_debt_outputs:
        _clear_quality_gate_current_full_test_debt(ctx)
        _clear_quality_gate_full_test_debt_summary(ctx)


def _clear_quality_gate_current_full_test_debt(ctx: GateContext) -> None:
    current_debt_path = os.path.join(ctx.repo_root, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL)
    if os.path.isfile(current_debt_path):
        os.remove(current_debt_path)


def _clear_quality_gate_full_test_debt_summary(ctx: GateContext) -> None:
    summary_path = os.path.join(ctx.repo_root, QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL)
    if os.path.isfile(summary_path):
        os.remove(summary_path)


def _preserve_failed_full_test_debt_payload(ctx: GateContext) -> Optional[str]:
    """把失败的 current 明细改名留存供事后排错；返回留存相对路径（无文件则 None）。

    改名（而非保留原名）是刻意为之：原名一旦消失，下一轮 long-gate 指纹就走「文件不存在＝
    干净」分支，不会被这份带失败的 payload 污染；同时内容改名留住，省去为看一眼 traceback
    重跑整轮全量。.failed.json 已纳入 .gitignore 与禁提交名单，os.replace 单文件覆盖（最多常驻
    一份、不跨次堆积），且不计入 git status，因此也不会判脏工作区。
    """
    current_debt_path = os.path.join(ctx.repo_root, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL)
    if not os.path.isfile(current_debt_path):
        return None
    preserved_path = os.path.join(ctx.repo_root, QUALITY_GATE_FAILED_FULL_TEST_DEBT_REL)
    try:
        os.replace(current_debt_path, preserved_path)
    except OSError:
        return None
    return QUALITY_GATE_FAILED_FULL_TEST_DEBT_REL.replace("\\", "/")


def _clear_full_test_debt_current_outputs_after_failure(ctx: GateContext, entry: GateEntry) -> None:
    if entry.spec.proof_kind != "full_test_debt":
        return
    preserved_rel = _preserve_failed_full_test_debt_payload(ctx)
    _clear_quality_gate_full_test_debt_summary(ctx)
    if preserved_rel:
        print(
            f"==> 失败明细已留存：{preserved_rel}"
            "（含逐用例 traceback/分类，事后排错可直接看，无需重跑全量）",
            flush=True,
        )


def _remove_quality_gate_run_output_path(ctx: GateContext, rel_path: str) -> None:
    abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
    if os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
    elif os.path.isfile(abs_path):
        os.remove(abs_path)


def _clear_stale_long_gate_output_files(
    ctx: GateContext,
    runtime_entries: Mapping[str, RuntimeEntry],
    *,
    preserve_full_test_debt_outputs: bool,
) -> None:
    for rt in runtime_entries.values():
        if rt.record is not None:
            continue
        proof_kind = rt.entry.spec.proof_kind
        if proof_kind == "full_test_debt" and preserve_full_test_debt_outputs:
            continue
        for rel_path in rt.entry.spec.output_result_files:
            _remove_quality_gate_run_output_path(ctx, rel_path)
        if proof_kind == "required_regressions":
            _remove_quality_gate_run_output_path(ctx, "evidence/QualityGate/required_regressions")


def _guard_test_exists(ctx: GateContext, rel_path: str) -> bool:
    return os.path.isfile(os.path.join(ctx.repo_root, rel_path))


def _guard_test_tracked(ctx: GateContext, rel_path: str) -> bool:
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", rel_path],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def _repo_identity(ctx: GateContext) -> Dict[str, str]:
    try:
        return repo_identity(ctx.repo_root)
    except RuntimeError as exc:
        raise QualityGateError(f"无法确认仓库身份：{exc}") from exc


def _assert_guard_tests_ready(ctx: GateContext, *, require_tracked: bool) -> None:
    missing = [path for path in REQUIRED_TEST_ARGS if not _guard_test_exists(ctx, path)]
    untracked = ([path for path in REQUIRED_TEST_ARGS if path not in missing and not _guard_test_tracked(ctx, path)]
                 if require_tracked else [])
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


def _assert_ruff_version(output: str) -> str:
    text = output.strip()
    version = _parse_ruff_version(text)
    if version < (0, 15, 0) or version >= (0, 16, 0):
        raise QualityGateError(f"ruff 版本超出允许范围 >=0.15,<0.16：{text}")
    return text


def _parse_pyright_version(text: str) -> Tuple[int, int, int]:
    match = re.search(r"pyright\s+([0-9]+)\.([0-9]+)\.([0-9]+)", text)
    if not match:
        raise QualityGateError(f"Unable to parse pyright version output: {text}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _assert_pyright_version(output: str) -> str:
    text = output.strip()
    version = _parse_pyright_version(text)
    if version != PYRIGHT_REQUIRED_VERSION:
        expected = ".".join(str(part) for part in PYRIGHT_REQUIRED_VERSION)
        raise QualityGateError(f"pyright version must be {expected}, got: {text}")
    return text


# 结果处理器只在命令返回 0 后调用，产出 manifest 需要的解析结果；不通过时抛 QualityGateError。
CommandResultHandler = Callable[[GateContext, CommandResult], Dict[str, Any]]


def _handle_checked_quality_gate_command(_ctx: GateContext, _result: CommandResult) -> Dict[str, Any]:
    return {}


def _handle_collect_quality_gate_command(_ctx: GateContext, result: CommandResult) -> Dict[str, Any]:
    nodeids = _collect_nodeids_or_raise(result.stdout.strip())
    collected_paths = {nodeid.split("::", 1)[0].replace("\\", "/") for nodeid in nodeids}
    missing = [path for path in REQUIRED_TEST_ARGS if path.replace("\\", "/") not in collected_paths]
    if missing:
        raise QualityGateError("required 文件没有被实际 collect 覆盖：" + ", ".join(missing))
    return {"collection_proof": build_quality_gate_collection_proof(nodeids, required_tests=REQUIRED_TEST_ARGS)}


def _handle_ruff_version_quality_gate_command(_ctx: GateContext, result: CommandResult) -> Dict[str, Any]:
    return {"ruff_version_output": _assert_ruff_version(result.stdout)}


def _handle_pyright_version_quality_gate_command(_ctx: GateContext, result: CommandResult) -> Dict[str, Any]:
    return {"pyright_version_output": _assert_pyright_version(result.stdout)}


def _load_pyright_tools_config_include(ctx: GateContext) -> List[str]:
    config_path = os.path.join(ctx.repo_root, PYRIGHT_TOOLS_CONFIG.replace("/", os.sep))
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


def _assert_pyright_tools_config_matches_tool_paths(ctx: GateContext) -> None:
    configured = _load_pyright_tools_config_include(ctx)
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


def _handle_pyright_tools_quality_gate_command(ctx: GateContext, _result: CommandResult) -> Dict[str, Any]:
    _assert_pyright_tools_config_matches_tool_paths(ctx)
    return {}


def _handle_import_cycle_production_quality_gate_command(_ctx: GateContext, _result: CommandResult) -> Dict[str, Any]:
    return {"import_cycle_production_proof": True}


def _handle_import_cycle_with_tests_quality_gate_command(_ctx: GateContext, _result: CommandResult) -> Dict[str, Any]:
    return {"import_cycle_with_tests_proof": True}


RUNNER_HANDLERS: Dict[str, CommandResultHandler] = {
    "default": _handle_checked_quality_gate_command,
    "pytest_collect_all": _handle_collect_quality_gate_command,
    "ruff_version": _handle_ruff_version_quality_gate_command,
    "pyright_version": _handle_pyright_version_quality_gate_command,
    "pyright_tools": _handle_pyright_tools_quality_gate_command,
    "import_cycle_production": _handle_import_cycle_production_quality_gate_command,
    "import_cycle_with_tests": _handle_import_cycle_with_tests_quality_gate_command,
}


def _run_quality_gate_command_plan(
    ctx: GateContext,
    plan: Sequence[GateEntry],
    progress: PlanProgress,
    *,
    resume_decision: ResumeDecision,
    long_gate_runtime_entries: Dict[str, RuntimeEntry],
    long_gate_context: Optional[LongGateCacheContext],
) -> None:
    """按命令序号逐步执行：同一个循环里逐步决定续跑复用、long-gate 复用、缓存失败复用或实际执行。

    每条路径都经 `_record_outcome` 把可复用条目换成带结果的条目，summary（含失败）由它生成；
    long_gate_context 为 None 表示本次缓存未生效（未启用或续跑），不读写缓存。
    """
    resumed_steps = {step.receipt.command_index: step for step in resume_decision.resumed_steps}
    for entry in plan:
        progress.running_command_index = entry.index
        if entry.index in resumed_steps:
            _run_resumed_step(ctx, entry, resumed_steps[entry.index], progress, long_gate_runtime_entries)
            continue
        environment = command_environment(entry.command["env_overlay"])
        environment_fingerprint = fingerprint_environment(
            entry.spec.env_keys, environment=environment, repo_root=ctx.repo_root
        )
        print(f"==> 第 {entry.index}/{progress.total} 步开始：{entry.spec.display}", flush=True)
        started = _step_start()
        if long_gate_context is not None and entry.spec.check_id in long_gate_runtime_entries:
            _run_long_gate_step(
                ctx,
                entry,
                progress,
                long_gate_runtime_entries,
                long_gate_context,
                started=started,
                environment=environment,
                environment_fingerprint=environment_fingerprint,
            )
            continue
        result, receipt_path = _execute_step(
            ctx,
            entry,
            progress,
            long_gate_runtime_entries,
            started=started,
            environment=environment,
            environment_fingerprint=environment_fingerprint,
        )
        if result.returncode != 0:
            _record_outcome(long_gate_runtime_entries, entry, result, receipt_path, failed=True)
            _print_step_end(entry, total=progress.total, result=result, receipt_path=receipt_path, failed=True)
            _raise_command_failure(entry, total=progress.total, receipt_path=receipt_path, result=result)
        try:
            progress.parsed_command_results.update(RUNNER_HANDLERS[entry.spec.runner_handler](ctx, result))
        except QualityGateError as exc:
            _record_outcome(long_gate_runtime_entries, entry, result, receipt_path, failed=True)
            _print_step_end(entry, total=progress.total, result=result, receipt_path=receipt_path, failed=True)
            _raise_command_failure(entry, total=progress.total, receipt_path=receipt_path, result=result, detail=str(exc))
        _record_outcome(long_gate_runtime_entries, entry, result, receipt_path, failed=False)
        _print_step_end(entry, total=progress.total, result=result, receipt_path=receipt_path, failed=False)
    progress.running_command_index = None


def _run_resumed_step(
    ctx: GateContext,
    entry: GateEntry,
    step: ResumedStep,
    progress: PlanProgress,
    runtime_entries: Dict[str, RuntimeEntry],
) -> None:
    print(f"==> 第 {entry.index}/{progress.total} 步：[resume-skip] {entry.spec.display}", flush=True)
    result = _resumed_result(ctx, entry, step, _step_start())
    # 续跑判定已核过这份环境指纹与当前环境逐项相等，直接沿用。
    receipt_path = _record_step(ctx, progress, entry, result, step.receipt.environment)
    try:
        progress.parsed_command_results.update(RUNNER_HANDLERS[entry.spec.runner_handler](ctx, result))
    except QualityGateError as exc:
        _record_outcome(runtime_entries, entry, result, receipt_path, failed=True)
        _raise_command_failure(entry, total=progress.total, receipt_path=receipt_path, result=result, detail=str(exc))
    _record_outcome(runtime_entries, entry, result, receipt_path, failed=False)


def _record_outcome(
    runtime_entries: Dict[str, RuntimeEntry],
    entry: GateEntry,
    result: CommandResult,
    receipt_path: str,
    *,
    failed: bool,
    output_files: Tuple[str, ...] = (),
) -> StepOutcome:
    """登记一步的结果；执行、long-gate 复用、缓存失败复用与续跑复用都经这里。

    只有可复用条目（runtime_entries 里有它）进 long-gate summary；output_files 是随成功缓存保存的输出文件。
    """
    outcome = StepOutcome(result, receipt_path, output_files, failed)
    check_id = entry.spec.check_id
    if check_id in runtime_entries:
        runtime_entries[check_id] = replace(runtime_entries[check_id], outcome=outcome)
    return outcome


def _record_long_gate_failure(
    runtime_entries: Dict[str, RuntimeEntry], entry: GateEntry, result: CommandResult, receipt_path: str
) -> None:
    outcome = _record_outcome(runtime_entries, entry, result, receipt_path, failed=True)
    _print_long_gate_failure(copyable_failure(entry, outcome))


def _run_long_gate_step(
    ctx: GateContext,
    entry: GateEntry,
    progress: PlanProgress,
    runtime_entries: Dict[str, RuntimeEntry],
    context: LongGateCacheContext,
    *,
    started: Tuple[str, float],
    environment: Mapping[str, str],
    environment_fingerprint: Mapping[str, Any],
) -> None:
    total = progress.total
    rt = _refresh_long_gate_decision(ctx, runtime_entries[entry.spec.check_id], context)
    runtime_entries[entry.spec.check_id] = rt
    handler = RUNNER_HANDLERS[entry.spec.runner_handler]
    if rt.record is not None:
        # 决策为复用成功缓存。
        result = _reused_success_result(ctx, entry, rt.record, started)
        receipt_path = _record_step(ctx, progress, entry, result, environment_fingerprint)
        try:
            progress.parsed_command_results.update(handler(ctx, result))
        except QualityGateError as exc:
            _record_long_gate_failure(runtime_entries, entry, result, receipt_path)
            _raise_command_failure(entry, total=total, receipt_path=receipt_path, result=result, detail=str(exc))
        output_files = tuple(row["path"] for row in rt.record.output_files)
        _record_outcome(runtime_entries, entry, result, receipt_path, failed=False, output_files=output_files)
        _print_step_end(entry, total=total, result=result, receipt_path=receipt_path, failed=False, label="[long-gate-reuse] ")
        return

    cached_failure = _cached_failure_record(ctx, rt, context)
    if cached_failure is not None:
        result = _cached_failure_result(cached_failure, started)
        receipt_path = _record_step(ctx, progress, entry, result, environment_fingerprint)
        _record_long_gate_failure(runtime_entries, entry, result, receipt_path)
        _clear_full_test_debt_current_outputs_after_failure(ctx, entry)
        label = "[long-gate-cached-failure] "
        _print_step_end(entry, total=total, result=result, receipt_path=receipt_path, failed=True, label=label)
        _raise_command_failure(entry, total=total, receipt_path=receipt_path, result=result)

    result, receipt_path = _execute_step(
        ctx,
        entry,
        progress,
        runtime_entries,
        started=started,
        environment=environment,
        environment_fingerprint=environment_fingerprint,
    )
    if result.returncode != 0:
        _record_long_gate_failure(runtime_entries, entry, result, receipt_path)
        _clear_full_test_debt_current_outputs_after_failure(ctx, entry)
        _write_failure_cache(ctx, rt, result, receipt_path=receipt_path, context=context, run_id=progress.run_id)
        _print_step_end(entry, total=total, result=result, receipt_path=receipt_path, failed=True)
        _raise_command_failure(entry, total=total, receipt_path=receipt_path, result=result)
    try:
        progress.parsed_command_results.update(handler(ctx, result))
    except QualityGateError as exc:
        _record_long_gate_failure(runtime_entries, entry, result, receipt_path)
        _print_step_end(entry, total=total, result=result, receipt_path=receipt_path, failed=True)
        _raise_command_failure(entry, total=total, receipt_path=receipt_path, result=result, detail=str(exc))
    # 输出文件与专题证明写出可能失败（磁盘、权限）：写之前先按失败登记已取得的结果与 receipt，写完才改记为通过，
    # 写出失败时本步状态与已取得的信息都留在 summary 里。
    _record_outcome(runtime_entries, entry, result, receipt_path, failed=True)
    rt, output_files = _stage_long_gate_success(ctx, rt, context, result, receipt_path=receipt_path, progress=progress)
    runtime_entries[entry.spec.check_id] = rt
    _record_outcome(runtime_entries, entry, result, receipt_path, failed=False, output_files=output_files)
    _print_step_end(entry, total=total, result=result, receipt_path=receipt_path, failed=False)


def _require_quality_gate_command_proofs(
    command_specs: Sequence[GateCheckSpec],
    parsed_command_results: Dict[str, Any],
) -> None:
    check_ids = {spec.check_id for spec in command_specs}
    required_proofs = {
        quality_gate_shared.ENTRY_PYTEST_COLLECT_ALL: parsed_command_results.get("collection_proof"),
        "ruff_version_probe": parsed_command_results.get("ruff_version_output"),
        "pyright_version_probe": parsed_command_results.get("pyright_version_output"),
    }
    cycle_check_ids = (
        quality_gate_shared.ENTRY_IMPORT_CYCLES_PRODUCTION,
        quality_gate_shared.ENTRY_IMPORT_CYCLES_WITH_TESTS,
    )
    if check_ids & {quality_gate_shared.ENTRY_RUFF_CHECK_FULL, *cycle_check_ids}:
        missing_cycle_id = next((cid for cid in cycle_check_ids if cid not in check_ids), "")
        if missing_cycle_id:
            raise QualityGateError(f"shared command plan 缺少循环门禁检查：{missing_cycle_id}")
        required_proofs.update(
            {
                quality_gate_shared.ENTRY_IMPORT_CYCLES_PRODUCTION: parsed_command_results.get(
                    "import_cycle_production_proof"
                ),
                quality_gate_shared.ENTRY_IMPORT_CYCLES_WITH_TESTS: parsed_command_results.get(
                    "import_cycle_with_tests_proof"
                ),
            }
        )
    missing_check = next((check_id for check_id, value in required_proofs.items() if not value), "")
    if missing_check:
        raise QualityGateError(f"shared command plan 缺少必需证明命令或解析结果：{missing_check}")


def _load_runtime_state(ctx: GateContext) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, str]]:
    paths = resolve_runtime_state_paths(ctx.repo_root)
    contract_exists = os.path.exists(paths["contract_path"])
    lock_exists = os.path.exists(paths["lock_path"])
    contract_result = read_runtime_contract_result(ctx.repo_root)
    contract = contract_result.payload if contract_result.ok else None
    lock_result = read_runtime_lock_result(ctx.repo_root)
    lock = lock_result.payload if lock_result.ok else None
    if contract_exists and contract is None:
        raise QualityGateError("仓库根运行时契约存在但无法解析：{}".format(paths["contract_path"]))
    if lock_exists and lock is None:
        raise QualityGateError("仓库根运行时锁存在但无法解析：{}".format(paths["lock_path"]))
    return contract, lock, paths


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
    pid_state: RuntimeProbeState, health_state: RuntimeProbeState, exe_path: str
) -> str:
    reasons = []
    if pid_state == RuntimeProbeState.UNKNOWN:
        reasons.append("缺少 exe_path 或无法确认 PID 对应可执行文件路径" if not exe_path else "无法确认 PID 对应可执行文件路径")
    if health_state == RuntimeProbeState.ABSENT:
        reasons.append("缺少运行时契约，无法做健康探测")
    return "；".join(reasons)


def _pid_signal(payload: Optional[Dict[str, Any]]) -> Tuple[RuntimeProbeState, Optional[int], Optional[bool], str]:
    if not payload:
        return RuntimeProbeState.ABSENT, None, None, ""
    pid = payload["pid"]
    exe_path = str(payload.get("exe_path") or "").strip()
    pid_state = query_pid_state(pid, state_dir=None)
    if pid_state is False:
        return RuntimeProbeState.STALE, pid, False, exe_path
    if pid_state is None:
        return RuntimeProbeState.UNKNOWN, pid, None, exe_path
    if not exe_path:
        return RuntimeProbeState.UNKNOWN, pid, None, exe_path
    pid_match = pid_matches_contract(pid, exe_path, state_dir=None)
    if pid_match is False:
        return RuntimeProbeState.STALE, pid, False, exe_path
    if pid_match is True:
        return RuntimeProbeState.ACTIVE, pid, True, exe_path
    return RuntimeProbeState.UNKNOWN, pid, None, exe_path


_PROBE_PRIORITY = {
    RuntimeProbeState.ABSENT: 0,
    RuntimeProbeState.STALE: 1,
    RuntimeProbeState.UNKNOWN: 2,
    RuntimeProbeState.ACTIVE: 3,
}


def _effective_pid_signal(
    contract: Optional[Dict[str, Any]],
    lock: Optional[Dict[str, Any]],
) -> Tuple[RuntimeProbeState, Optional[int], Optional[bool], str]:
    contract_sig = _pid_signal(contract)
    if lock is None:
        return contract_sig
    if contract is None:
        return _pid_signal(lock)
    if (lock["pid"], str(lock.get("exe_path") or "").strip()) == (contract_sig[1], contract_sig[3]):
        return contract_sig
    lock_sig = _pid_signal(lock)
    return lock_sig if _PROBE_PRIORITY[lock_sig[0]] > _PROBE_PRIORITY[contract_sig[0]] else contract_sig


def _health_signal(contract: Optional[Dict[str, Any]]) -> Tuple[RuntimeProbeState, Optional[str], Optional[int]]:
    if not contract:
        return RuntimeProbeState.ABSENT, None, None
    host = contract["host"]
    port = contract["port"]
    healthy = probe_runtime_health_result(f"http://{host}:{port}", timeout_s=1.0, log_failures=True).ok
    return (RuntimeProbeState.ACTIVE if healthy else RuntimeProbeState.STALE), host, port


def _runtime_state_snapshot(ctx: GateContext) -> Dict[str, Any]:
    contract, lock, paths = _load_runtime_state(ctx)
    pid_state, pid, pid_match, exe_path = _effective_pid_signal(contract, lock)
    health_state, host, port = _health_signal(contract)
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


def _assert_no_active_runtime(ctx: GateContext) -> None:
    contract, lock, paths = _load_runtime_state(ctx)
    if contract is None and lock is None:
        return

    contract_pid_state, contract_pid, _contract_match, contract_exe = _pid_signal(contract)
    health_state, host, port = _health_signal(contract)
    endpoint_text = _describe_runtime_endpoint(host, port)
    cleanup_hint = _describe_cleanup_hint(paths)

    if (
        contract_pid_state == RuntimeProbeState.ACTIVE and health_state == RuntimeProbeState.STALE
    ) or (
        contract_pid_state == RuntimeProbeState.STALE and health_state == RuntimeProbeState.ACTIVE
    ):
        raise QualityGateError(
            "活动实例判定出现矛盾："
            f"pid_state={contract_pid_state.value} health_state={health_state.value} pid={contract_pid} {endpoint_text} exe_path={contract_exe}。{cleanup_hint}"
        )
    if contract_pid_state == RuntimeProbeState.UNKNOWN and health_state != RuntimeProbeState.ACTIVE:
        reason_text = _describe_uncertain_reason(contract_pid_state, health_state, contract_exe)
        raise QualityGateError(
            "活动实例判定不确定："
            f"pid_state={contract_pid_state.value} health_state={health_state.value} pid={contract_pid} {endpoint_text} exe_path={contract_exe}"
            + (f"；原因：{reason_text}" if reason_text else "")
            + f"。{cleanup_hint}"
        )
    if contract_pid_state == RuntimeProbeState.ACTIVE or health_state == RuntimeProbeState.ACTIVE:
        raise QualityGateError(
            f"检测到仓库根存在活动 APS 实例，请先退出后再执行门禁：pid={contract_pid} {endpoint_text} exe_path={contract_exe}"
        )

    if lock is not None and (
        contract is None or (lock["pid"], str(lock.get("exe_path") or "").strip()) != (contract_pid, contract_exe)
    ):
        lock_pid_state, lock_pid, _lock_match, lock_exe = _pid_signal(lock)
        if lock_pid_state == RuntimeProbeState.UNKNOWN:
            reason_text = _describe_uncertain_reason(lock_pid_state, RuntimeProbeState.ABSENT, lock_exe)
            raise QualityGateError(
                "活动实例判定不确定："
                f"pid_state={lock_pid_state.value} health_state={health_state.value} pid={lock_pid} {endpoint_text} exe_path={lock_exe}"
                + (f"；原因：{reason_text}" if reason_text else "")
                + f"。{cleanup_hint}"
            )
        if lock_pid_state == RuntimeProbeState.ACTIVE:
            raise QualityGateError(
                f"检测到仓库根存在活动 APS 实例，请先退出后再执行门禁：pid={lock_pid} {endpoint_text} exe_path={lock_exe}"
            )

    print(
        "提示：检测到仓库根存在陈旧运行时痕迹，将继续执行；未自动删除：contract={} lock={}".format(
            paths["contract_path"], paths["lock_path"]
        ),
        flush=True,
    )


def _git_head_sha(ctx: GateContext) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise QualityGateError("无法读取当前 HEAD SHA")
    return str(completed.stdout or "").strip()


def _git_status_lines(ctx: GateContext) -> List[str]:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--short", "--untracked-files=all"],
        cwd=ctx.repo_root,
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


def _long_gate_execution_proof(
    entry: GateEntry,
    result: CommandResult,
    *,
    schema_version: int,
    run_id: str,
    fingerprint: Mapping[str, Any],
    cache_dir: str,
) -> Dict[str, Any]:
    """long-gate 专题证明共有的执行事实；日志指向本条目的成功缓存日志，run_id 绑定本次 manifest。"""
    stdout_log_path, stderr_log_path = cache_log_rel_paths(entry.spec.check_id, cache_dir=cache_dir)
    return {
        "schema_version": schema_version,
        "status": "passed",
        "entry_id": entry.spec.check_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
        "command_index": entry.index,
        "command": entry.command,
        "fingerprint": fingerprint,
        "returncode": result.returncode,
        "execution_mode": result.execution_mode,
        "duration_s": result.duration_s,
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_content": quality_gate_shared.sanitize_quality_gate_output(result.stdout),
        "stderr_content": quality_gate_shared.sanitize_quality_gate_output(result.stderr),
        "does_not_claim": "clean_worktree_proof",
    }


def _write_long_gate_topic_proof(ctx: GateContext, rel_path: str, payload: Dict[str, Any]) -> str:
    abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return rel_path


def _write_required_regressions_proof(
    ctx: GateContext,
    entry: GateEntry,
    result: CommandResult,
    *,
    run_id: str,
    fingerprint: Mapping[str, Any],
    cache_dir: str,
) -> str:
    payload = _long_gate_execution_proof(
        entry,
        result,
        schema_version=REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION,
        run_id=run_id,
        fingerprint=fingerprint,
        cache_dir=cache_dir,
    )
    payload.update(
        required_target_count=len(REQUIRED_TEST_ARGS),
        required_target_paths=REQUIRED_TEST_ARGS,
        verification_method="full_test_debt_payload_required_coverage",
    )
    return _write_long_gate_topic_proof(ctx, entry.spec.output_result_files[0], payload)


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
    ctx: GateContext,
    entry: GateEntry,
    result: CommandResult,
    *,
    run_id: str,
    fingerprint: Mapping[str, Any],
    cache_dir: str,
) -> str:
    summary = _parse_debt_ledger_check_stdout(result.stdout)
    payload = _long_gate_execution_proof(
        entry,
        result,
        schema_version=DEBT_LEDGER_SYNC_PROOF_SCHEMA_VERSION,
        run_id=run_id,
        fingerprint=fingerprint,
        cache_dir=cache_dir,
    )
    payload.update(
        ledger_path=LEDGER_REL,
        ledger_schema_version=int(summary.get("schema_version") or 0),
        ledger_checked_at=str(summary.get("checked_at") or ""),
        ledger_counts={key: int(summary.get(key) or 0) for key in (
            "oversize_count", "complexity_count", "silent_fallback_count", "test_debt_count", "accepted_risk_count")},
        samples=dict(summary.get("samples") or {}),
    )
    return _write_long_gate_topic_proof(ctx, entry.spec.output_result_files[0], payload)


def _option_value(args: Sequence[str], option: str) -> str:
    try:
        index = list(args).index(option)
    except ValueError:
        return ""
    if index + 1 >= len(args):
        return ""
    return str(args[index + 1])


def _write_static_check_proof(
    ctx: GateContext,
    entry: GateEntry,
    result: CommandResult,
    *,
    run_id: str,
    fingerprint: Mapping[str, Any],
    cache_dir: str,
) -> str:
    payload = _long_gate_execution_proof(
        entry,
        result,
        schema_version=STATIC_CHECK_PROOF_SCHEMA_VERSION,
        run_id=run_id,
        fingerprint=fingerprint,
        cache_dir=cache_dir,
    )
    args = entry.command["args"]
    config_path = _option_value(args, "-p")
    paths = list(QUALITY_GATE_TOOL_PATHS) if config_path == PYRIGHT_TOOLS_CONFIG else [
        path for path in QUALITY_GATE_TOOL_PATHS if path in args]
    payload.update(config_path=config_path, tool_path_count=len(paths), tool_paths=paths)
    return _write_long_gate_topic_proof(ctx, entry.spec.output_result_files[0], payload)


def _write_long_gate_output_files(
    ctx: GateContext,
    entry: GateEntry,
    result: CommandResult,
    *,
    run_id: str,
    fingerprint: Mapping[str, Any],
    cache_dir: str,
) -> Tuple[str, ...]:
    """写本条目随成功缓存保存的输出文件，返回它们的仓库相对路径。"""
    proof_kind = entry.spec.proof_kind
    if proof_kind == "collect_nodeids":
        collect_payload = build_collect_nodeids_payload(
            result.stdout,
            pytest_version=pytest_distribution_version(strict=True),
            collect_stdout_log_path=result.stdout_log_path,
        )
        return (write_collect_nodeids(collect_payload, repo_root=ctx.repo_root),)
    writers = {
        "required_regressions": _write_required_regressions_proof,
        "debt_ledger_sync": _write_debt_ledger_sync_proof,
        "static_check": _write_static_check_proof,
    }
    if proof_kind in writers:
        writer = writers[proof_kind]
        return (writer(ctx, entry, result, run_id=run_id, fingerprint=fingerprint, cache_dir=cache_dir),)
    return entry.spec.output_result_files


def _cache_unavailable_runtime_entry(rt: RuntimeEntry, *, failure_kind: str, message: str) -> RuntimeEntry:
    decision = cache_unavailable_decision(failure_kind=failure_kind, message=message)
    return replace(rt, decision=decision, record=None)


def _usable_cache_metadata(rt: RuntimeEntry, context: LongGateCacheContext) -> Optional[Mapping[str, Any]]:
    """该条目本次能读写缓存时返回缓存元数据；决策为 cache unavailable（含元数据不可用）时返回 None。"""
    if rt.decision.cache_unavailable:
        return None
    return context.metadata


def _cache_fingerprint(rt: RuntimeEntry) -> Mapping[str, Any]:
    """决策不是 cache unavailable 的条目必有本次完整指纹。"""
    return cast(Mapping[str, Any], rt.fingerprint)


def _refresh_long_gate_decision(ctx: GateContext, rt: RuntimeEntry, context: LongGateCacheContext) -> RuntimeEntry:
    """输入含本次前序步骤产物的条目，执行前按当前输入重新判定；full_test_debt 不复用时删掉旧输出。"""
    entry = rt.entry
    metadata = _usable_cache_metadata(rt, context)
    if (
        entry.spec.proof_kind not in _INPUTS_FROM_EARLIER_STEPS
        or metadata is None
        or rt.decision.cause is DecisionCause.FORCED
    ):
        return rt
    try:
        fingerprint = _strict_long_gate_fingerprint(ctx, entry)
    except QualityGateError as exc:
        refreshed = _cache_unavailable_runtime_entry(
            replace(rt, fingerprint=None), failure_kind=_fingerprint_failure_kind(exc), message=str(exc)
        )
    else:
        evaluation = evaluate_cache(
            entry, fingerprint, kind="success", metadata=metadata, repo_root=ctx.repo_root, cache_dir=context.cache_dir
        )
        refreshed = replace(rt, decision=evaluation.decision, fingerprint=fingerprint, record=evaluation.record)
    if entry.spec.proof_kind == "full_test_debt" and refreshed.record is None:
        for rel_path in entry.spec.output_result_files:
            abs_path = os.path.join(ctx.repo_root, rel_path.replace("/", os.sep))
            if os.path.isfile(abs_path):
                os.remove(abs_path)
    return refreshed


def _failure_cache_metadata(rt: RuntimeEntry, context: LongGateCacheContext) -> Optional[Mapping[str, Any]]:
    """reuse_policy=success_or_failure 的条目在写缓存、未强制重跑时读写失败缓存；返回可用的缓存元数据。"""
    if (
        not context.write_success
        or rt.entry.spec.reuse_policy != "success_or_failure"
        or rt.decision.cause is DecisionCause.FORCED
    ):
        return None
    return _usable_cache_metadata(rt, context)


def _cached_failure_record(ctx: GateContext, rt: RuntimeEntry, context: LongGateCacheContext) -> Optional[CacheRecord]:
    metadata = _failure_cache_metadata(rt, context)
    if metadata is None:
        return None
    return evaluate_cache(
        rt.entry,
        _cache_fingerprint(rt),
        kind="failure",
        metadata=metadata,
        repo_root=ctx.repo_root,
        cache_dir=context.cache_dir,
    ).record


def _write_failure_cache(
    ctx: GateContext,
    rt: RuntimeEntry,
    result: CommandResult,
    *,
    receipt_path: str,
    context: LongGateCacheContext,
    run_id: str,
) -> None:
    metadata = _failure_cache_metadata(rt, context)
    if metadata is None:
        return
    write_failure(
        rt.entry,
        _cache_fingerprint(rt),
        result,
        receipt_path=receipt_path,
        run_id=run_id,
        metadata=metadata,
        repo_root=ctx.repo_root,
        cache_dir=context.cache_dir,
    )


def _stage_long_gate_success(
    ctx: GateContext,
    rt: RuntimeEntry,
    context: LongGateCacheContext,
    result: CommandResult,
    *,
    receipt_path: str,
    progress: PlanProgress,
) -> Tuple[RuntimeEntry, Tuple[str, ...]]:
    """命令通过后写输出文件并登记待落盘的成功缓存；返回更新后的条目与输出文件路径。"""
    entry = rt.entry
    skip_prefix = f"==> 第 {entry.index}/{progress.total} 步：跳过 long-gate success cache 写入，"
    metadata = _usable_cache_metadata(rt, context)
    if metadata is None:
        print(skip_prefix + f"该 entry 当前 cache unavailable：{rt.decision.reason}", flush=True)
        return rt, ()
    if not context.write_success:
        print(skip_prefix + "因为本次不是干净工作区的完整成功证明", flush=True)
        return rt, ()
    try:
        fingerprint = (
            _strict_long_gate_fingerprint(ctx, entry)
            if entry.spec.proof_kind in _INPUTS_FROM_EARLIER_STEPS
            else _cache_fingerprint(rt)
        )
    except QualityGateError as exc:
        print(skip_prefix + "因为 strict fingerprint 失败，该 entry 当前 cache unavailable", flush=True)
        return _cache_unavailable_runtime_entry(rt, failure_kind=_fingerprint_failure_kind(exc), message=str(exc)), ()
    output_files = _write_long_gate_output_files(
        ctx, entry, result, run_id=progress.run_id, fingerprint=fingerprint, cache_dir=context.cache_dir
    )
    progress.pending_successes.append(PendingSuccess(entry, fingerprint, result, receipt_path, output_files, metadata))
    return replace(rt, fingerprint=fingerprint), output_files


def _should_preserve_full_test_debt_outputs(
    ctx: GateContext, runtime_entries: Mapping[str, RuntimeEntry], *, cache_dir: str
) -> bool:
    """full_test_debt 本次复用，或只因 collect 证明待本次重新生成而暂判重跑且已有成功缓存时，执行前保留它的输出。"""
    for rt in runtime_entries.values():
        if rt.entry.spec.proof_kind != "full_test_debt":
            continue
        if rt.record is not None:
            return True
        if rt.decision.cause is not DecisionCause.COLLECT_NODEIDS_INVALID:
            return False
        result_rel = cache_result_rel_path(rt.entry.spec.check_id, kind="success", cache_dir=cache_dir)
        return os.path.isfile(os.path.join(ctx.repo_root, result_rel.replace("/", os.sep)))
    return False


def _resolve_command_args(raw_args: Sequence[str]) -> List[str]:
    return [sys.executable if idx == 0 and arg == "python" else arg for idx, arg in enumerate(raw_args)]


def _write_quality_gate_manifest(ctx: GateContext, manifest: Dict[str, Any]) -> None:
    manifest_path = _quality_gate_manifest_abs_path(ctx)
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _apply_worktree_proof(
    ctx: GateContext,
    manifest: Dict[str, Any],
    *,
    git_status_short_before: Sequence[str],
    git_status_short_after: Optional[Sequence[str]],
) -> None:
    before = _worktree_status_lines(git_status_short_before)
    after = None
    if git_status_short_after is not None:
        after = _worktree_status_lines(git_status_short_after)
    previous_before_fingerprint = manifest.get("dirty_worktree_content_before")
    if isinstance(previous_before_fingerprint, dict) and previous_before_fingerprint.get("status_lines") == before:
        before_fingerprint = previous_before_fingerprint
    else:
        before_fingerprint = _dirty_worktree_content(ctx, before)
    after_fingerprint = _dirty_worktree_content(ctx, after) if after is not None else None
    manifest.update(
        {
            "git_status_short_before": before,
            "dirty_worktree_content_before": before_fingerprint,
            "is_dirty_before": bool(before),
            "git_status_short_after": after,
            "dirty_worktree_content_after": after_fingerprint,
            "is_dirty_after": None if after is None else bool(after),
            "tracked_drift_detected": None if after is None else not content_equal(before_fingerprint, after_fingerprint),
        }
    )


def _assert_resume_dirty_content_still_current(
    ctx: GateContext,
    resume_decision: ResumeDecision,
    *,
    git_status_short_before: Sequence[str],
) -> None:
    if not resume_decision.enabled:
        return
    current = _dirty_worktree_content(ctx, git_status_short_before)
    if not content_equal(current, resume_decision.validated_dirty_content):
        raise QualityGateError("脏工作区内容在续跑判定后又发生变化，本次不能复用上次的步骤")


def _base_quality_gate_manifest(
    ctx: GateContext,
    *,
    run_id: str,
    started_at: str,
    head_sha: str,
    git_status_short_before: Sequence[str],
    runtime_snapshot: Dict[str, Any],
    plan: Sequence[GateEntry],
) -> Dict[str, Any]:
    manifest = {
        "schema_version": QUALITY_GATE_PROOF_SCHEMA_VERSION,
        "proof_scope": dict(QUALITY_GATE_PROOF_SCOPE),
        "status": "running",
        "head_sha": head_sha,
        "run_id": run_id,
        **_repo_identity(ctx),
        "runtime_snapshot": runtime_snapshot,
        "python_version": sys.version.splitlines()[0].strip(),
        "python_executable": sys.executable,
        "ruff_version": None,
        "pyright_version": None,
        "started_at": started_at,
        "finished_at": None,
        # collect 步骤通过前记 None；之后写出时换成该步骤构造的那一份。
        "collection_proof": None,
        "required_tests": list(REQUIRED_TEST_ARGS),
        "planned_commands": [entry.command for entry in plan],
        "commands": [],
        "command_receipts": [],
        "gate_sources": build_quality_gate_source_proof(ctx.repo_root),
        "clean_worktree_excluded_paths": list(GENERATED_CLEAN_WORKTREE_EXCLUDED_PATHS),
        "failure_kind": None,
        "failure_message": None,
        "failure_command_index": None,
    }
    _apply_worktree_proof(ctx, manifest, git_status_short_before=git_status_short_before, git_status_short_after=None)
    return manifest


def _mark_manifest_unbound(manifest: Dict[str, Any]) -> None:
    manifest["proof_scope"] = {
        "claim": "diagnostic_run_completed_in_dirty_worktree",
        "does_not_claim": "required_registry_bound_to_clean_worktree",
    }


def _cli_impact_path(raw_path: str) -> str:
    path = normalize_repo_path(raw_path)
    if not path:
        raise argparse.ArgumentTypeError(f"not a repository-relative path: {raw_path!r}")
    return path


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
        type=_cli_impact_path,
        metavar="PATH",
        help="changed path to explain; may be repeated; defaults to current git changed paths",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="do not reuse successful steps from the previous failed dirty-worktree run",
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


_DISABLED_LONG_GATE_DECISION = CacheDecision(
    "disabled", DecisionCause.DISABLED, "long gate cache is disabled for this run"
)


def _forced_long_gate_decision(fingerprint: Mapping[str, Any], reason: str) -> CacheDecision:
    return CacheDecision(
        "run",
        DecisionCause.FORCED,
        reason,
        invalidated_by=(reason,),
        non_reusable_env_keys=tuple(fingerprint["components"]["environment"]["non_reusable_env_keys"]),
    )


def _prepare_long_gate_cache_decisions(
    ctx: GateContext,
    plan: Sequence[GateEntry],
    *,
    cache_enabled: bool,
    cache_dir: str,
    write_success: bool,
    force_rerun_entry_ids: Sequence[str],
    force_rerun_all: bool,
) -> Tuple[Dict[str, RuntimeEntry], Optional[LongGateCacheContext]]:
    """给每个可复用条目本次的缓存决策；缓存生效时同时返回本次的缓存上下文。"""
    cache_entries = [entry for entry in plan if entry.spec.reuse_allowed]
    forced_entry_ids: Set[str] = {entry_id.strip() for entry_id in force_rerun_entry_ids if entry_id.strip()}
    unknown_forced = sorted(forced_entry_ids - {entry.spec.check_id for entry in cache_entries})
    if unknown_forced:
        raise QualityGateError(
            "--long-gate-force-rerun 指定了未知的 long gate check_id: " + ", ".join(unknown_forced)
        )
    if not cache_enabled:
        disabled = {
            entry.spec.check_id: RuntimeEntry(entry, _DISABLED_LONG_GATE_DECISION, None, None)
            for entry in cache_entries
        }
        return disabled, None
    try:
        metadata = long_gate_cache_metadata(ctx.repo_root, cache_dir=cache_dir)
    except SensitiveSourceError as exc:
        unavailable = {
            entry.spec.check_id: RuntimeEntry(
                entry,
                cache_unavailable_decision(failure_kind="cache_metadata_unavailable", message=str(exc)),
                None,
                None,
            )
            for entry in cache_entries
        }
        return unavailable, LongGateCacheContext(cache_dir, None, write_success)
    file_snapshot = FingerprintFileSnapshot(ctx.repo_root, strict=True)
    runtime_entries: Dict[str, RuntimeEntry] = {}
    for entry in cache_entries:
        entry_id = entry.spec.check_id
        try:
            fingerprint = _strict_long_gate_fingerprint(ctx, entry, file_snapshot=file_snapshot)
        except QualityGateError as exc:
            decision = cache_unavailable_decision(failure_kind=_fingerprint_failure_kind(exc), message=str(exc))
            runtime_entries[entry_id] = RuntimeEntry(entry, decision, None, None)
            continue
        if force_rerun_all or entry_id in forced_entry_ids:
            reason = (
                "forced by --long-gate-force-rerun-all" if force_rerun_all else f"forced by --long-gate-force-rerun {entry_id}"
            )
            runtime_entries[entry_id] = RuntimeEntry(
                entry, _forced_long_gate_decision(fingerprint, reason), fingerprint, None
            )
            continue
        evaluation = evaluate_cache(
            entry, fingerprint, kind="success", metadata=metadata, repo_root=ctx.repo_root, cache_dir=cache_dir
        )
        runtime_entries[entry_id] = RuntimeEntry(entry, evaluation.decision, fingerprint, evaluation.record)
    return runtime_entries, LongGateCacheContext(cache_dir, metadata, write_success)


def _print_long_gate_cache_decisions(
    ctx: GateContext, runtime_entries: Sequence[RuntimeEntry], *, cache_dir: str
) -> None:
    print("Long gate cache decisions", flush=True)
    print("note: explain mode prints decisions only; it is not a quality gate proof", flush=True)
    print(f"cache_dir: {cache_dir}", flush=True)
    if not runtime_entries:
        print("- no eligible long-gate entries", flush=True)
        return
    for rt in runtime_entries:
        row = summary_entry(rt)
        fingerprint_error = rt.decision.fingerprint_error
        print(f"- {row['entry_id']}: {row['decision'].upper()}", flush=True)
        print(f"  cache: {row['cache_status']}", flush=True)
        print(f"  reason: {row['reason']}", flush=True)
        if fingerprint_error is not None:
            if fingerprint_error.failure_kind:
                print(f"  failure_kind: {fingerprint_error.failure_kind}", flush=True)
            print("  note: cache unavailable for this entry; old success cache will not be reused", flush=True)
        if row["previous_result_path"]:
            print(f"  previous_result: {row['previous_result_path']}", flush=True)
        if rt.fingerprint is not None:
            print("  fingerprint: complete input content compared", flush=True)
        _print_long_gate_cache_decision_hint(ctx, rt)
        invalidated_by = row["invalidated_by"]
        if invalidated_by:
            print("  invalidated_by:", flush=True)
            for item in invalidated_by[:10]:
                print(f"    - {item}", flush=True)
            if len(invalidated_by) > 10:
                print(f"    - ... {len(invalidated_by) - 10} more", flush=True)
        _print_fingerprint_diff(row["fingerprint_diff"])


def _format_fingerprint_component(change: Mapping[str, Any]) -> str:
    details = " ".join(f"{key}={change[key]}" for key in ("path", "key", "field") if key in change)
    suffix = " " + details if details else ""
    return f"{change['component']}: {change['reason']}{suffix}"


def _print_fingerprint_diff(changes: Sequence[Mapping[str, Any]]) -> None:
    if not changes:
        return
    print("  fingerprint_changed_components:", flush=True)
    for change in changes[:20]:
        print(f"    - {_format_fingerprint_component(change)}", flush=True)
    if len(changes) > 20:
        print(f"    - ... {len(changes) - 20} more", flush=True)


def _dedupe_impact_paths(paths: Sequence[str]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for raw_path in list(paths or []):
        path = str(raw_path or "")
        if not path or path in seen:
            continue
        seen.add(path)
        rows.append(path)
    return rows


def _git_impact_paths(ctx: GateContext, args: Sequence[str]) -> List[str]:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=ctx.repo_root,
        capture_output=True,
        check=False,
    )
    if int(completed.returncode) != 0:
        stderr = bytes(completed.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = bytes(completed.stdout or b"").decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or "git command failed"
        raise QualityGateError("long-gate impact explain 无法读取 git 变更路径：git " + " ".join(args) + "：" + detail)
    return _dedupe_impact_paths(decode_nul_paths(bytes(completed.stdout or b"")))


def _current_impact_paths(ctx: GateContext) -> List[str]:
    paths: List[str] = []
    for args in (
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ):
        paths.extend(_git_impact_paths(ctx, args))
    return _dedupe_impact_paths(paths)


def _print_long_gate_impact_explain(ctx: GateContext, command_specs: Sequence[GateCheckSpec], paths: Sequence[str]) -> None:
    impact = explain_long_gate_impact(command_specs, paths, repo_root=ctx.repo_root)
    print(json.dumps(impact, ensure_ascii=False, sort_keys=True, indent=2), flush=True)


def _quality_gate_rel_exists(ctx: GateContext, rel_path: str) -> bool:
    return os.path.isfile(os.path.join(ctx.repo_root, rel_path))


def _print_long_gate_cache_decision_hint(ctx: GateContext, rt: RuntimeEntry) -> None:
    if rt.decision.kind != "run":
        return
    if rt.decision.cause is DecisionCause.MISSING:
        print("  cache_state: missing", flush=True)
    if rt.entry.spec.proof_kind != "full_test_debt":
        return
    direct_outputs = [
        rel_path
        for rel_path in [
            QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
            QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
        ]
        if _quality_gate_rel_exists(ctx, rel_path)
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


def _write_and_print_long_gate_summary(
    ctx: GateContext,
    *,
    run_id: str,
    head_sha: str,
    worktree_clean: bool,
    cache_enabled: bool,
    runtime_entries: Mapping[str, RuntimeEntry],
    cache_dir: str,
) -> None:
    entries = list(runtime_entries.values())
    failure = next(
        (copyable_failure(rt.entry, rt.outcome) for rt in entries if rt.outcome is not None and rt.outcome.failed),
        None,
    )
    summary = build_long_gate_summary(
        run_id=run_id,
        repo_root=ctx.repo_root,
        head_sha=head_sha,
        worktree_clean=worktree_clean,
        cache_enabled=cache_enabled,
        entries=[summary_entry(rt) for rt in entries],
        failure=failure,
        cache_dir=cache_dir,
    )
    summary_paths = write_long_gate_summary(summary, ctx.repo_root)
    print("Long gate summary", flush=True)
    for key in SUMMARY_COUNT_KEYS:
        print(f"- {key}: {summary['counts'][key]}", flush=True)
    print(f"- summary_json: {summary_paths['summary_json']}", flush=True)
    print(f"- summary_md: {summary_paths['summary_md']}", flush=True)


def _prepare_pending_long_gate_successes(
    ctx: GateContext,
    pending_successes: Sequence[PendingSuccess],
    *,
    runtime_entries: Dict[str, RuntimeEntry],
    run_id: str,
    cache_dir: str,
) -> List[PreparedSuccessWrite]:
    prepared_writes: List[PreparedSuccessWrite] = []
    for pending in pending_successes:
        entry_id = pending.entry.spec.check_id
        try:
            prepared_writes.append(
                prepare_success_write(
                    pending.entry,
                    pending.fingerprint,
                    pending.result,
                    pending.output_files,
                    receipt_path=pending.receipt_path,
                    run_id=run_id,
                    metadata=pending.metadata,
                    repo_root=ctx.repo_root,
                    cache_dir=cache_dir,
                )
            )
        except SensitiveSourceError as exc:
            runtime_entries[entry_id] = _cache_unavailable_runtime_entry(
                runtime_entries[entry_id], failure_kind="cache_write_unavailable", message=str(exc)
            )
    return prepared_writes


def _print_long_gate_failure(failure: Mapping[str, Any]) -> None:
    print(f"FAILED: {failure['entry_id']}", flush=True)
    print("command:", flush=True)
    print(f"  {failure['display']}", flush=True)
    print("copyable rerun:", flush=True)
    print(f"  {failure['copyable_command']}", flush=True)
    print("receipt:", flush=True)
    print(f"  {failure['receipt_path']}", flush=True)
    print("stdout log:", flush=True)
    print(f"  {failure['stdout_log_path']}", flush=True)
    print("stderr log:", flush=True)
    print(f"  {failure['stderr_log_path']}", flush=True)
    print("stdout tail:", flush=True)
    print(failure["stdout_tail"], flush=True)
    print("stderr tail:", file=sys.stderr, flush=True)
    print(failure["stderr_tail"], file=sys.stderr, flush=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.fast_precheck:
        from tools import fast_static_precheck

        return int(fast_static_precheck.main([]))
    ctx = GateContext(resolve_repo_root())
    command_specs = quality_gate_shared.build_quality_gate_check_specs(
        ctx.repo_root, allow_dirty_worktree=args.allow_dirty_worktree
    )
    if args.long_gate_impact_explain:
        impact_paths = (
            _dedupe_impact_paths(args.long_gate_impact_path)
            if args.long_gate_impact_path
            else _current_impact_paths(ctx)
        )
        _print_long_gate_impact_explain(ctx, command_specs, impact_paths)
        return 0
    plan = gate_entries(command_specs)
    long_gate_cache_enabled = (args.long_gate_cache or args.long_gate_cache_explain) and not args.no_long_gate_cache
    long_gate_cache_dir = LONG_GATE_CACHE_DIR_REL
    if long_gate_cache_enabled:
        try:
            long_gate_cache_dir = resolve_cache_dir(ctx.repo_root, args.long_gate_cache_dir)
        except ValueError as exc:
            raise QualityGateError(str(exc)) from exc
    if args.long_gate_cache_explain:
        explain_entries, _explain_context = _prepare_long_gate_cache_decisions(
            ctx,
            plan,
            cache_enabled=True,
            cache_dir=long_gate_cache_dir,
            write_success=False,
            force_rerun_entry_ids=args.long_gate_force_rerun,
            force_rerun_all=args.long_gate_force_rerun_all,
        )
        _print_long_gate_cache_decisions(ctx, list(explain_entries.values()), cache_dir=long_gate_cache_dir)
        return 0
    started_at = datetime.now().isoformat(timespec="seconds")
    head_sha = _git_head_sha(ctx)
    git_status_short_before = _git_status_lines(ctx)
    if not args.allow_dirty_worktree:
        resume_decision = ResumeDecision(False, "当前不是 allow-dirty-worktree 模式")
    elif args.no_resume:
        resume_decision = ResumeDecision(False, "--no-resume 已指定")
    else:
        resume_decision = _decide_resume_from_previous_failure(
            ctx, plan, current_head_sha=head_sha, current_git_status_short=git_status_short_before
        )
    if resume_decision.enabled:
        print(
            f"提示：检测到上次质量门禁在第 {resume_decision.failed_command_index}/{len(plan)} 步失败"
            f"（{resume_decision.failed_command_display}），本次复用其前 {len(resume_decision.resumed_steps)} 个"
            "已通过的步骤，其余步骤照常执行。",
            flush=True,
        )
    else:
        print(f"提示：未使用续跑：{resume_decision.reason}。本次完整重跑。", flush=True)
    require_clean_worktree = args.require_clean_worktree or not args.allow_dirty_worktree
    effective_long_gate_cache_enabled = long_gate_cache_enabled and not resume_decision.enabled
    runtime_entries, long_gate_context = _prepare_long_gate_cache_decisions(
        ctx,
        plan,
        cache_enabled=effective_long_gate_cache_enabled,
        cache_dir=long_gate_cache_dir,
        write_success=require_clean_worktree,
        force_rerun_entry_ids=args.long_gate_force_rerun if effective_long_gate_cache_enabled else (),
        force_rerun_all=args.long_gate_force_rerun_all and effective_long_gate_cache_enabled,
    )
    if long_gate_cache_enabled:
        _print_long_gate_cache_decisions(ctx, list(runtime_entries.values()), cache_dir=long_gate_cache_dir)
    run_id = f"{head_sha}:{started_at}"
    runtime_snapshot = _runtime_state_snapshot(ctx)
    progress = PlanProgress(
        run_id=run_id,
        total=len(plan),
        commands=[],
        command_receipts=[],
        parsed_command_results={},
        pending_successes=[],
    )
    parsed_command_results = progress.parsed_command_results
    failure_kind: Optional[str] = None
    git_status_short_after: Optional[List[str]] = None
    preserve_full_test_debt_outputs = _should_preserve_full_test_debt_outputs(
        ctx, runtime_entries, cache_dir=long_gate_cache_dir
    )
    manifest = _base_quality_gate_manifest(
        ctx,
        run_id=run_id,
        started_at=started_at,
        head_sha=head_sha,
        git_status_short_before=git_status_short_before,
        runtime_snapshot=runtime_snapshot,
        plan=plan,
    )
    if long_gate_context is not None:
        manifest["long_gate_cache_dir"] = long_gate_cache_dir
    manifest["resume"] = {
        "enabled": resume_decision.enabled,
        "reason": resume_decision.reason,
        "previous_run_id": resume_decision.previous_run_id,
        "resumed_command_indexes": [step.receipt.command_index for step in resume_decision.resumed_steps],
        "failed_command_index": resume_decision.failed_command_index,
        "failed_command_display": resume_decision.failed_command_display,
        "previous_failure_message": resume_decision.previous_failure_message,
        "proof_status": "pending",
    }
    if not require_clean_worktree:
        _mark_manifest_unbound(manifest)
    _write_quality_gate_manifest(ctx, manifest)

    try:
        try:
            _clear_quality_gate_run_outputs(
                ctx,
                keep_receipts_and_logs=resume_decision.enabled,
                keep_full_test_debt_outputs=preserve_full_test_debt_outputs,
            )
            if long_gate_context is not None:
                _clear_stale_long_gate_output_files(
                    ctx,
                    runtime_entries,
                    preserve_full_test_debt_outputs=preserve_full_test_debt_outputs,
                )
        except Exception:
            failure_kind = "quality_gate_cleanup_failed"
            raise

        if require_clean_worktree and git_status_short_before:
            failure_kind = "dirty_before_gate"
            raise QualityGateError(_dirty_worktree_message(git_status_short_before))

        try:
            _assert_no_active_runtime(ctx)
        except QualityGateError:
            failure_kind = "environment_blocked"
            raise
        _assert_guard_tests_ready(ctx, require_tracked=require_clean_worktree)
        try:
            _assert_resume_dirty_content_still_current(
                ctx,
                resume_decision,
                git_status_short_before=git_status_short_before,
            )
        except QualityGateError:
            failure_kind = "resume_dirty_fingerprint_changed"
            raise

        _run_quality_gate_command_plan(
            ctx,
            plan,
            progress,
            resume_decision=resume_decision,
            long_gate_runtime_entries=runtime_entries,
            long_gate_context=long_gate_context,
        )
        _require_quality_gate_command_proofs(command_specs, parsed_command_results)

        git_status_short_after = _git_status_lines(ctx)
        _apply_worktree_proof(
            ctx,
            manifest,
            git_status_short_before=git_status_short_before,
            git_status_short_after=git_status_short_after,
        )
        if manifest["tracked_drift_detected"]:
            failure_kind = "tracked_drift_detected"
            raise QualityGateError("tracked drift detected during quality gate execution")
        if require_clean_worktree and git_status_short_after:
            failure_kind = "dirty_after_gate"
            raise QualityGateError("dirty worktree: clean proof requires an empty worktree after the gate runs")

        if long_gate_cache_enabled:
            prepared_long_gate_successes = _prepare_pending_long_gate_successes(
                ctx,
                progress.pending_successes,
                runtime_entries=runtime_entries,
                run_id=run_id,
                cache_dir=long_gate_cache_dir,
            )
            _write_and_print_long_gate_summary(
                ctx,
                run_id=run_id,
                head_sha=head_sha,
                worktree_clean=not (git_status_short_before or git_status_short_after),
                cache_enabled=effective_long_gate_cache_enabled,
                runtime_entries=runtime_entries,
                cache_dir=long_gate_cache_dir,
            )
            for prepared in prepared_long_gate_successes:
                commit_prepared_success_write(ctx.repo_root, prepared)

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
                "质量门禁续跑完成；本次复用了上次已通过的步骤，只能当作本地快速反馈，不能当作完整通过证明。"
            )
        manifest["resume"]["proof_status"] = (
            "fast_feedback_only"
            if resume_decision.enabled
            else ("full_command_plan_bound" if require_clean_worktree else "full_command_plan_unbound")
        )
        manifest.update(
            {
                "status": success_status,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "collection_proof": parsed_command_results["collection_proof"],
                "commands": progress.commands,
                "command_receipts": progress.command_receipts,
                "ruff_version": parsed_command_results["ruff_version_output"],
                "pyright_version": parsed_command_results["pyright_version_output"],
                "failure_kind": None,
                "failure_message": None,
                "failure_command_index": None,
            }
        )
        _write_quality_gate_manifest(ctx, manifest)
        print(success_message, flush=True)
        return success_return_code
    except (Exception, KeyboardInterrupt) as exc:
        # 中断也先写完失败总账与 summary（已完成与被中断的步骤都在其中），再原样向外传播。
        if isinstance(exc, KeyboardInterrupt):
            failure_kind = "interrupted"
        worktree_proof_errors: List[str] = []
        if git_status_short_after is None:
            try:
                git_status_short_after = _git_status_lines(ctx)
            except (QualityGateError, OSError) as status_exc:
                git_status_short_after = None
                worktree_proof_errors.append(f"git_status_after: {status_exc}")
        try:
            _apply_worktree_proof(
                ctx,
                manifest,
                git_status_short_before=git_status_short_before,
                git_status_short_after=git_status_short_after,
            )
        except (QualityGateError, OSError) as proof_exc:
            worktree_proof_errors.append(f"worktree_fingerprint: {proof_exc}")
        manifest["resume"]["proof_status"] = "failed"
        manifest.update(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "collection_proof": parsed_command_results.get("collection_proof"),
                "commands": progress.commands,
                "command_receipts": progress.command_receipts,
                "ruff_version": parsed_command_results.get("ruff_version_output"),
                "pyright_version": parsed_command_results.get("pyright_version_output"),
                "failure_kind": failure_kind or "quality_gate_failed",
                "failure_message": str(exc),
                "failure_command_index": progress.running_command_index,
            }
        )
        if worktree_proof_errors:
            manifest["worktree_proof_error"] = "；".join(worktree_proof_errors)
        try:
            _write_quality_gate_manifest(ctx, manifest)
            print(
                f"==> 失败总账已写入：{QUALITY_GATE_MANIFEST_REL.replace(os.sep, '/')}"
                "（含每步 receipt 与 failure_message，是事后排错的总入口）",
                file=sys.stderr,
                flush=True,
            )
        except Exception as manifest_write_exc:
            print(f"ERROR: 无法写入失败质量门禁 manifest：{manifest_write_exc}", file=sys.stderr, flush=True)
        if long_gate_cache_enabled:
            try:
                _write_and_print_long_gate_summary(
                    ctx,
                    run_id=run_id,
                    head_sha=head_sha,
                    worktree_clean=not (git_status_short_before or git_status_short_after),
                    cache_enabled=effective_long_gate_cache_enabled,
                    runtime_entries=runtime_entries,
                    cache_dir=long_gate_cache_dir,
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
