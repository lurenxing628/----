from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tools.long_gate_fingerprint import diff_fingerprints
from tools.long_gate_paths import (
    LONG_GATE_CACHE_DIR_REL,
    LONG_GATE_LOGS_DIR_NAME,
    LONG_GATE_RESULTS_DIR_NAME,
    real_repo_root,
    resolve_repo_path,
)
from tools.long_gate_records import (
    CacheDecision,
    CacheRecord,
    CommandResult,
    DecisionCause,
    FingerprintError,
    GateEntry,
    Rejection,
    admit_cache_record,
)
from tools.long_gate_schema import LONG_GATE_CACHE_SCHEMA_VERSION, content_equal, read_file_content
from tools.quality_gate_shared import sanitize_quality_gate_output


def resolve_cache_dir(repo_root: str, cache_dir: Optional[str]) -> str:
    """把 CLI 给的缓存目录（未给时取默认目录）解析成仓库相对 posix 路径；必须位于默认目录之下。"""
    root = real_repo_root(repo_root)
    raw_path = LONG_GATE_CACHE_DIR_REL if cache_dir is None else cache_dir.replace("\\", "/").strip()
    if not raw_path:
        raise ValueError("long gate cache dir is empty")
    try:
        abs_path = resolve_repo_path(root, raw_path, description="cache path")
    except ValueError as exc:
        raise ValueError(f"long gate cache dir is invalid: {exc}") from exc
    default_abs = resolve_repo_path(root, LONG_GATE_CACHE_DIR_REL, description="cache path")
    if abs_path != default_abs and not abs_path.startswith(default_abs + os.sep):
        raise ValueError(f"long gate cache dir must be under {LONG_GATE_CACHE_DIR_REL}: {raw_path}")
    return os.path.relpath(abs_path, root).replace("\\", "/")


def cache_result_rel_path(entry_id: str, *, kind: str, cache_dir: str) -> str:
    """成功/失败缓存记录的唯一路径规则；kind 为 success 或 failure。"""
    return f"{cache_dir}/{LONG_GATE_RESULTS_DIR_NAME}/{entry_id}.v2.{kind}.json"


def cache_log_rel_paths(entry_id: str, *, cache_dir: str) -> Tuple[str, str]:
    """缓存日志的唯一路径规则：(stdout, stderr)。"""
    logs_dir = f"{cache_dir}/{LONG_GATE_LOGS_DIR_NAME}"
    return f"{logs_dir}/{entry_id}.v2.stdout.log", f"{logs_dir}/{entry_id}.v2.stderr.log"


# --------------------------------------------------------------------------- 决策


@dataclass(frozen=True)
class CacheEvaluation:
    """一次缓存判定：决策，以及命中（复用成功或缓存失败）时已准入的记录。"""

    decision: CacheDecision
    record: Optional[CacheRecord]


CACHE_UNAVAILABLE_CAUSES: Dict[str, str] = {
    "": "strict fingerprint failed",
    "source_content_unavailable": "strict fingerprint failed",
    "cache_metadata_unavailable": "cache metadata unavailable",
    "cache_write_unavailable": "cache write failed",
}


def cache_unavailable_decision(*, failure_kind: str, message: str) -> CacheDecision:
    """唯一的“缓存不可用”决策；理由由 failure_kind 派生。"""
    cause = CACHE_UNAVAILABLE_CAUSES[failure_kind]
    invalidated_by: Tuple[str, ...] = (cause, "failure_kind=" + failure_kind) if failure_kind else (cause,)
    return CacheDecision(
        "run",
        DecisionCause.CACHE_UNAVAILABLE,
        cause + "; cache unavailable; executing command without read/write cache",
        invalidated_by=invalidated_by,
        fingerprint_error=FingerprintError(message, failure_kind),
    )


def _run(
    reason: str,
    *,
    cause: DecisionCause = DecisionCause.REJECTED,
    invalidated_by: Sequence[str] = (),
    fingerprint_diff: Sequence[Mapping[str, Any]] = (),
    previous_result_path: str = "",
) -> CacheEvaluation:
    decision = CacheDecision(
        "run",
        cause,
        reason,
        invalidated_by=tuple(invalidated_by),
        fingerprint_diff=tuple(fingerprint_diff),
        previous_result_path=previous_result_path,
    )
    return CacheEvaluation(decision, None)


def _metadata_mismatch(record: CacheRecord, metadata: Mapping[str, Any]) -> Optional[Tuple[str, Tuple[str, ...]]]:
    for current_untrusted, previous_untrusted, reason in (
        (
            metadata["runner_version_untrusted_paths"],
            record.runner_version_untrusted_paths,
            "runner version contains untrusted path",
        ),
        (
            metadata["tooling_version_untrusted_paths"],
            record.tooling_version_untrusted_paths,
            "tooling version contains untrusted path",
        ),
    ):
        if current_untrusted:
            return reason, tuple(current_untrusted)
        if previous_untrusted:
            return reason, tuple(previous_untrusted)
    if not content_equal(record.runner_version_content, metadata["runner_version_content"]):
        return "runner version changed", ()
    if not content_equal(record.tooling_version_content, metadata["tooling_version_content"]):
        return "tooling version changed", ()
    if record.cache_dir != metadata["cache_dir"]:
        return "cache dir changed", ()
    if os.path.realpath(record.repo_root_realpath) != metadata["repo_root_realpath"] or os.path.realpath(
        record.git_common_dir_realpath
    ) != metadata["git_common_dir_realpath"]:
        return "repo identity changed", ()
    return None


def _untrusted_input_path(fingerprint: Mapping[str, Any]) -> str:
    for row in fingerprint["components"]["files"]["files"]:
        if row["kind"] == "outside_repo":
            return f"input path is outside repo: {row['path']}"
        if row["kind"] == "symlink_outside_repo":
            return f"input symlink points outside repo: {row['path']}"
    return ""


def _log_mismatch(repo_root: str, record: CacheRecord, *, entry_id: str, cache_dir: str) -> str:
    expected_stdout, expected_stderr = cache_log_rel_paths(entry_id, cache_dir=cache_dir)
    for rel_path, expected_rel_path, content in (
        (record.stdout_log_path, expected_stdout, record.stdout_content),
        (record.stderr_log_path, expected_stderr, record.stderr_content),
    ):
        if rel_path != expected_rel_path:
            return f"previous logs path changed: {rel_path}"
        try:
            with open(resolve_repo_path(repo_root, rel_path, description="cache path"), "rb") as handle:
                data = handle.read()
        except OSError as exc:
            return f"previous logs unreadable: {rel_path}: {exc}"
        if data != content.encode("utf-8"):
            return "previous logs missing or content mismatch"
    return ""


def _output_file_mismatch(repo_root: str, row: Mapping[str, Any]) -> str:
    try:
        abs_path = resolve_repo_path(repo_root, row["path"], description="cache path")
        if not os.path.isfile(abs_path) or not content_equal(read_file_content(abs_path), row["content_base64"]):
            return "previous output files missing or content mismatch"
    except (OSError, ValueError) as exc:
        return str(exc)
    return ""


def missing_declared_output(entry: GateEntry, output_files: Sequence[Mapping[str, Any]]) -> str:
    """复用前确认缓存记录覆盖了规格声明的全部输出文件。"""
    cached_paths = {row["path"] for row in output_files}
    for rel_path in entry.spec.output_result_files:
        if rel_path not in cached_paths:
            return f"previous output files missing required path: {rel_path}"
    return ""


def evaluate_cache(
    entry: GateEntry,
    current_fingerprint: Mapping[str, Any],
    *,
    kind: str,
    metadata: Mapping[str, Any],
    repo_root: str,
    cache_dir: str,
) -> CacheEvaluation:
    """成功缓存（kind=success）与失败缓存（kind=failure）的同一条判定链；真实差异由准入规则表按 kind 表达。"""
    root = real_repo_root(repo_root)
    entry_id = entry.spec.check_id
    private_keys = tuple(current_fingerprint["components"]["environment"]["non_reusable_env_keys"])
    if private_keys:
        decision = CacheDecision(
            "run",
            DecisionCause.CACHE_UNAVAILABLE,
            "environment values remain in memory; cache unavailable",
            invalidated_by=private_keys,
            non_reusable_env_keys=private_keys,
        )
        return CacheEvaluation(decision, None)
    result_rel = cache_result_rel_path(entry_id, kind=kind, cache_dir=cache_dir)
    admitted = admit_cache_record(root, result_rel, kind=kind)
    if isinstance(admitted, Rejection):
        return _run(admitted.reason, cause=admitted.cause, invalidated_by=admitted.invalidated_by)
    record = admitted
    metadata_mismatch = _metadata_mismatch(record, metadata)
    if metadata_mismatch is not None:
        return _run(metadata_mismatch[0], invalidated_by=metadata_mismatch[1])
    if record.entry_id != entry_id:
        return _run("cache entry_id changed")
    untrusted = _untrusted_input_path(current_fingerprint)
    if untrusted:
        return _run("input fingerprint contains untrusted path", invalidated_by=(untrusted,))
    components = current_fingerprint["components"]
    if entry.spec.proof_kind == "full_test_debt" and components["collect_nodeids"]["error"]:
        return _run(
            "collect nodeids proof is invalid",
            cause=DecisionCause.COLLECT_NODEIDS_INVALID,
            invalidated_by=(components["collect_nodeids"]["error"],),
        )
    if entry.spec.proof_kind == "required_regressions" and components["required_full_test_debt"]["error"]:
        return _run(
            "required full-test-debt evidence is invalid",
            invalidated_by=(components["required_full_test_debt"]["error"],),
        )
    diff = diff_fingerprints(record.fingerprint, current_fingerprint)
    if diff["changed"]:
        return _run(
            "input fingerprint changed",
            invalidated_by=diff["reasons"],
            fingerprint_diff=diff["components"],
            previous_result_path=result_rel,
        )
    log_error = _log_mismatch(root, record, entry_id=entry_id, cache_dir=cache_dir)
    if log_error:
        return _run(log_error)
    if kind == "success":
        for row in record.output_files:
            output_error = _output_file_mismatch(root, row)
            if output_error:
                return _run(output_error)
        coverage_error = missing_declared_output(entry, record.output_files)
        if coverage_error:
            return _run(coverage_error)
        decision = CacheDecision(
            "reuse",
            DecisionCause.MATCHED,
            "fingerprint matched previous successful result",
            previous_result_path=result_rel,
        )
    else:
        decision = CacheDecision(
            "cached_failure",
            DecisionCause.MATCHED,
            "fingerprint matched previous failed result",
            previous_result_path=result_rel,
        )
    return CacheEvaluation(decision, record)


# --------------------------------------------------------------------------- 写入


def _write_text(repo_root: str, rel_path: str, text: str) -> None:
    abs_path = resolve_repo_path(repo_root, rel_path, description="cache path")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _write_json(repo_root: str, rel_path: str, payload: Mapping[str, Any]) -> None:
    abs_path = resolve_repo_path(repo_root, rel_path, description="cache path")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)


def _read_output_files(repo_root: str, output_files: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rel_path in output_files:
        abs_path = resolve_repo_path(repo_root, rel_path, description="cache path")
        if not os.path.isfile(abs_path):
            raise ValueError(f"long gate output file does not exist: {rel_path}")
        rows.append({"path": rel_path, "content_base64": read_file_content(abs_path)})
    return rows


def _cache_payload(
    entry: GateEntry,
    fingerprint: Mapping[str, Any],
    result: CommandResult,
    *,
    status: str,
    output_files: List[Dict[str, Any]],
    log_paths: Tuple[str, str],
    receipt_path: str,
    run_id: str,
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    """成功/失败缓存记录的唯一写出形状；`admit_cache_record` 按同一形状读回。"""
    return {
        "schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        **metadata,
        "entry_id": entry.spec.check_id,
        "status": status,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "duration_s": result.duration_s,
        "fingerprint": fingerprint,
        "returncode": result.returncode,
        "stdout_content": sanitize_quality_gate_output(result.stdout),
        "stderr_content": sanitize_quality_gate_output(result.stderr),
        "stdout_log_path": log_paths[0],
        "stderr_log_path": log_paths[1],
        "output_files": output_files,
        "receipt_path": receipt_path,
        "run_id": run_id,
        "command_index": entry.index,
    }


@dataclass(frozen=True)
class PreparedSuccessWrite:
    """成功缓存的两段写：summary 写成功后才 commit。"""

    result_path: str
    payload: Mapping[str, Any]


def prepare_success_write(
    entry: GateEntry,
    fingerprint: Mapping[str, Any],
    result: CommandResult,
    output_files: Sequence[str],
    *,
    receipt_path: str,
    run_id: str,
    metadata: Mapping[str, Any],
    repo_root: str,
    cache_dir: str,
) -> PreparedSuccessWrite:
    root = real_repo_root(repo_root)
    payload = _cache_payload(
        entry,
        fingerprint,
        result,
        status="passed",
        output_files=_read_output_files(root, output_files),
        log_paths=cache_log_rel_paths(entry.spec.check_id, cache_dir=cache_dir),
        receipt_path=receipt_path,
        run_id=run_id,
        metadata=metadata,
    )
    return PreparedSuccessWrite(cache_result_rel_path(entry.spec.check_id, kind="success", cache_dir=cache_dir), payload)


def commit_prepared_success_write(repo_root: str, prepared: PreparedSuccessWrite) -> None:
    root = real_repo_root(repo_root)
    payload = prepared.payload
    _write_text(root, payload["stdout_log_path"], payload["stdout_content"])
    _write_text(root, payload["stderr_log_path"], payload["stderr_content"])
    _write_json(root, prepared.result_path, payload)


def write_failure(
    entry: GateEntry,
    fingerprint: Mapping[str, Any],
    result: CommandResult,
    *,
    receipt_path: str,
    run_id: str,
    metadata: Mapping[str, Any],
    repo_root: str,
    cache_dir: str,
) -> None:
    root = real_repo_root(repo_root)
    payload = _cache_payload(
        entry,
        fingerprint,
        result,
        status="failed",
        output_files=[],
        log_paths=cache_log_rel_paths(entry.spec.check_id, cache_dir=cache_dir),
        receipt_path=receipt_path,
        run_id=run_id,
        metadata=metadata,
    )
    _write_text(root, payload["stdout_log_path"], payload["stdout_content"])
    _write_text(root, payload["stderr_log_path"], payload["stderr_content"])
    _write_json(root, cache_result_rel_path(entry.spec.check_id, kind="failure", cache_dir=cache_dir), payload)
