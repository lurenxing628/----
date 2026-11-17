"""门禁磁盘 JSON 的唯一准入边界，以及门禁运行期间的不可变记录类型。

分工：`quality_gate_shared` 管检查规格与命令构造；本模块管磁盘 JSON 的结构准入
（缓存记录、collect 收集结果、命令 receipt、QualityGate manifest）和内存记录形状；
记录与“本次运行”的关系（指纹比对、run_id、计划序号）由缓存模块与 runner 绑定。
`quality_gate_shared` 不得反向导入本模块。
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple, Union

from tools.long_gate_paths import is_within_repo, resolve_repo_path
from tools.long_gate_schema import (
    COLLECT_NODEIDS_SCHEMA_VERSION,
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
)
from tools.quality_gate_shared import (
    QUALITY_GATE_COLLECT_NODEIDS_REL,
    QUALITY_GATE_COMMAND_KEYS,
    QUALITY_GATE_PROOF_SCHEMA_VERSION,
    QUALITY_GATE_RECEIPTS_DIR_REL,
    GateCheckSpec,
    normalize_command_output_for_policy,
    normalize_quality_gate_command,
    parse_pytest_collect_nodeids,
)

# --------------------------------------------------------------------------- 读入边界


class GateJsonError(Exception):
    """门禁证据 JSON 读不出来；`missing` 区分“文件不存在”与“文件坏了”。"""

    def __init__(self, detail: str, *, missing: bool) -> None:
        super().__init__(detail)
        self.missing = missing


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite number is not allowed: {text}")
    return value


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number is not allowed: {name}")


def load_gate_json(abs_path: str) -> Dict[str, Any]:
    """唯一读入：缺失、不可读、非对象、NaN/Infinity 字面量和指数溢出（如 1e999）一律拒绝。"""
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle, parse_float=_finite_float, parse_constant=_reject_constant)
    except FileNotFoundError as exc:
        raise GateJsonError(str(exc), missing=True) from exc
    except (OSError, ValueError) as exc:
        raise GateJsonError(str(exc), missing=False) from exc
    if not isinstance(payload, dict):
        raise GateJsonError("top-level value is not an object", missing=False)
    return payload


def gate_schema_matches(payload: Mapping[str, Any], expected: int) -> bool:
    """schema_version 必须是普通整数且等于当前版本；每种准入第一步都比它。"""
    value = payload.get("schema_version")
    return type(value) is int and value == expected


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_number(value: Any) -> bool:
    return type(value) in (int, float)


def _is_optional_int(value: Any) -> bool:
    return value is None or type(value) is int


def _is_optional_number(value: Any) -> bool:
    return value is None or type(value) in (int, float)


def _is_text(value: Any) -> bool:
    return type(value) is str


def _is_optional_text(value: Any) -> bool:
    return value is None or type(value) is str


def _is_bool(value: Any) -> bool:
    return type(value) is bool


def _is_object(value: Any) -> bool:
    return type(value) is dict


def _is_list(value: Any) -> bool:
    return type(value) is list


def _is_text_list(value: Any) -> bool:
    return type(value) is list and all(type(item) is str for item in value)


def _is_object_list(value: Any) -> bool:
    return type(value) is list and all(type(item) is dict for item in value)


_FieldRules = Sequence[Tuple[str, Callable[[Any], bool]]]


def _first_bad_field(payload: Mapping[str, Any], rules: _FieldRules) -> Optional[Tuple[str, bool]]:
    """返回第一个不合规字段及它是否缺失；全部合规返回 None。"""
    for field, predicate in rules:
        if field not in payload:
            return field, True
        if not predicate(payload[field]):
            return field, False
    return None


# --------------------------------------------------------------------------- 计划条目


@dataclass(frozen=True)
class GateEntry:
    """完整计划里的一步：检查规格、整份计划里的 1 基序号、在源头规范化一次的命令身份。"""

    spec: GateCheckSpec
    index: int
    command: Mapping[str, Any]


def gate_entries(command_specs: Sequence[GateCheckSpec]) -> Tuple[GateEntry, ...]:
    return tuple(
        GateEntry(spec, index, normalize_quality_gate_command(spec.to_command_dict()))
        for index, spec in enumerate(command_specs, start=1)
    )


# --------------------------------------------------------------------------- 缓存决策


class DecisionCause(str, Enum):
    """缓存决策的原因分类；runner 只读它判状态，`reason` 文字只给人看。"""

    MATCHED = "matched"
    MISSING = "missing"
    REJECTED = "rejected"
    COLLECT_NODEIDS_INVALID = "collect_nodeids_invalid"
    FORCED = "forced"
    CACHE_UNAVAILABLE = "cache_unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class FingerprintError:
    message: str
    failure_kind: str


@dataclass(frozen=True)
class CacheDecision:
    kind: str
    cause: DecisionCause
    reason: str
    invalidated_by: Tuple[str, ...] = ()
    fingerprint_diff: Tuple[Mapping[str, Any], ...] = ()
    previous_result_path: str = ""
    fingerprint_error: Optional[FingerprintError] = None
    non_reusable_env_keys: Tuple[str, ...] = ()

    @property
    def cache_unavailable(self) -> bool:
        return self.fingerprint_error is not None or bool(self.non_reusable_env_keys)


@dataclass(frozen=True)
class Rejection:
    """任一准入的拒绝结果：原因分类（缺失或被拒）与给人看的理由。"""

    cause: DecisionCause
    reason: str
    invalidated_by: Tuple[str, ...] = ()


# --------------------------------------------------------------------------- 缓存记录


_INVALID_NUMERIC_FIELD_REASON = "cache unreadable/corrupt: numeric field has invalid type"
_CACHE_NUMERIC_FIELDS = frozenset({"returncode", "duration_s"})


def _is_output_file_rows(value: Any) -> bool:
    return _is_object_list(value) and all(
        _is_text(row.get("path")) and _is_text(row.get("content_base64")) for row in value
    )


_CACHE_RECORD_FIELDS: _FieldRules = (
    ("entry_id", _is_text),
    ("status", _is_text),
    ("completed_at", _is_text),
    ("duration_s", _is_number),
    ("returncode", _is_int),
    ("fingerprint", _is_object),
    ("stdout_content", _is_text),
    ("stderr_content", _is_text),
    ("stdout_log_path", _is_text),
    ("stderr_log_path", _is_text),
    ("output_files", _is_output_file_rows),
    ("runner_version_content", _is_list),
    ("tooling_version_content", _is_list),
    ("runner_version_untrusted_paths", _is_text_list),
    ("tooling_version_untrusted_paths", _is_text_list),
    ("cache_dir", _is_text),
    ("repo_root_realpath", _is_text),
    ("git_common_dir_realpath", _is_text),
)


@dataclass(frozen=True)
class _CacheKindRule:
    status: str
    status_reason: str
    returncode_ok: Callable[[int], bool]
    returncode_reason: str


_CACHE_KIND_RULES: Dict[str, _CacheKindRule] = {
    "success": _CacheKindRule(
        "passed", "previous result was not successful", lambda code: code == 0, "previous returncode was non-zero"
    ),
    "failure": _CacheKindRule(
        "failed",
        "previous failure cache status changed",
        lambda code: code != 0,
        "previous failure returncode was zero",
    ),
}


@dataclass(frozen=True)
class CacheRecord:
    """已通过结构准入的成功或失败缓存；日志正文与日志文件的一致性由缓存模块在复用前核对。"""

    result_path: str
    entry_id: str
    completed_at: str
    duration_s: float
    returncode: int
    fingerprint: Mapping[str, Any]
    stdout_content: str
    stderr_content: str
    stdout_log_path: str
    stderr_log_path: str
    output_files: Tuple[Mapping[str, Any], ...]
    runner_version_content: Sequence[Any]
    tooling_version_content: Sequence[Any]
    runner_version_untrusted_paths: Tuple[str, ...]
    tooling_version_untrusted_paths: Tuple[str, ...]
    cache_dir: str
    repo_root_realpath: str
    git_common_dir_realpath: str


def admit_cache_record(repo_root: str, rel_path: str, *, kind: str) -> Union[CacheRecord, Rejection]:
    rule = _CACHE_KIND_RULES[kind]
    try:
        payload = load_gate_json(resolve_repo_path(repo_root, rel_path, description="cache path"))
    except GateJsonError as exc:
        if exc.missing:
            return Rejection(DecisionCause.MISSING, f"no previous {kind} cache")
        return Rejection(DecisionCause.REJECTED, f"cache unreadable/corrupt: {exc}")
    if "schema_version" not in payload:
        return Rejection(DecisionCause.REJECTED, "cache unreadable/corrupt/missing required field: schema_version")
    if not _is_int(payload["schema_version"]):
        return Rejection(DecisionCause.REJECTED, _INVALID_NUMERIC_FIELD_REASON)
    if payload["schema_version"] != LONG_GATE_CACHE_SCHEMA_VERSION:
        return Rejection(DecisionCause.REJECTED, "cache schema changed")
    bad = _first_bad_field(payload, _CACHE_RECORD_FIELDS)
    if bad is not None:
        field, missing = bad
        if missing:
            return Rejection(DecisionCause.REJECTED, f"cache unreadable/corrupt/missing required field: {field}")
        if field in _CACHE_NUMERIC_FIELDS:
            return Rejection(DecisionCause.REJECTED, _INVALID_NUMERIC_FIELD_REASON)
        return Rejection(DecisionCause.REJECTED, f"cache unreadable/corrupt: {field} has invalid type")
    fingerprint = payload["fingerprint"]
    if not _is_int(fingerprint.get("schema_version")):
        return Rejection(DecisionCause.REJECTED, "cache unreadable/corrupt: fingerprint schema_version has invalid type")
    if fingerprint["schema_version"] != LONG_GATE_FINGERPRINT_SCHEMA_VERSION:
        return Rejection(DecisionCause.REJECTED, "input fingerprint changed", ("fingerprint schema changed",))
    if not _is_object(fingerprint.get("components")):
        return Rejection(DecisionCause.REJECTED, "cache unreadable/corrupt: fingerprint components is not an object")
    if payload["status"] != rule.status:
        return Rejection(DecisionCause.REJECTED, rule.status_reason)
    if not rule.returncode_ok(payload["returncode"]):
        return Rejection(DecisionCause.REJECTED, rule.returncode_reason)
    if kind == "failure" and payload["output_files"]:
        return Rejection(DecisionCause.REJECTED, "previous failure cache declares output files")
    return CacheRecord(
        result_path=rel_path,
        entry_id=payload["entry_id"],
        completed_at=payload["completed_at"],
        duration_s=float(payload["duration_s"]),
        returncode=payload["returncode"],
        fingerprint=fingerprint,
        stdout_content=payload["stdout_content"],
        stderr_content=payload["stderr_content"],
        stdout_log_path=payload["stdout_log_path"],
        stderr_log_path=payload["stderr_log_path"],
        output_files=tuple(payload["output_files"]),
        runner_version_content=payload["runner_version_content"],
        tooling_version_content=payload["tooling_version_content"],
        runner_version_untrusted_paths=tuple(payload["runner_version_untrusted_paths"]),
        tooling_version_untrusted_paths=tuple(payload["tooling_version_untrusted_paths"]),
        cache_dir=payload["cache_dir"],
        repo_root_realpath=payload["repo_root_realpath"],
        git_common_dir_realpath=payload["git_common_dir_realpath"],
    )


# --------------------------------------------------------------------------- collect 收集结果


@dataclass(frozen=True)
class CollectNodeids:
    nodeids: Tuple[str, ...]
    collect_stdout_content: str
    collect_stdout_log_path: str
    pytest_version: str


_COLLECT_FIELDS: _FieldRules = (
    ("nodeids", _is_text_list),
    ("collect_stdout_content", _is_text),
    ("collect_stdout_log_path", _is_text),
    ("pytest_version", _is_text),
)


def admit_collect_nodeids(repo_root: str) -> Union[CollectNodeids, Rejection]:
    """collect 收集结果的唯一准入：返回完整产物，下游不再复核其字段。"""
    rel_path = QUALITY_GATE_COLLECT_NODEIDS_REL
    try:
        payload = load_gate_json(resolve_repo_path(repo_root, rel_path, description="collect nodeids path"))
    except GateJsonError as exc:
        if exc.missing:
            return Rejection(DecisionCause.MISSING, f"collect_nodeids payload is missing: {rel_path}")
        return Rejection(DecisionCause.REJECTED, f"collect_nodeids payload is invalid: {exc}")
    if not gate_schema_matches(payload, COLLECT_NODEIDS_SCHEMA_VERSION):
        return Rejection(DecisionCause.REJECTED, "collect_nodeids payload is invalid: schema_version is invalid")
    bad = _first_bad_field(payload, _COLLECT_FIELDS)
    if bad is not None:
        return Rejection(DecisionCause.REJECTED, f"collect_nodeids payload is invalid: {bad[0]} has invalid type")
    nodeids = payload["nodeids"]
    stdout = payload["collect_stdout_content"]
    if parse_pytest_collect_nodeids(stdout) != nodeids:
        return Rejection(DecisionCause.REJECTED, "collect_nodeids payload is invalid: stdout does not match nodeids")
    log_path = payload["collect_stdout_log_path"]
    try:
        with open(resolve_repo_path(repo_root, log_path, description="collect stdout log path"), "rb") as handle:
            log_bytes = handle.read()
    except (OSError, ValueError) as exc:
        return Rejection(DecisionCause.REJECTED, f"collect_nodeids payload is invalid: {exc}")
    if log_bytes != stdout.encode("utf-8"):
        return Rejection(DecisionCause.REJECTED, "collect_nodeids payload is invalid: stdout log content changed")
    return CollectNodeids(
        nodeids=tuple(nodeids),
        collect_stdout_content=stdout,
        collect_stdout_log_path=log_path,
        pytest_version=payload["pytest_version"],
    )


# --------------------------------------------------------------------------- 命令执行结果与 receipt


@dataclass(frozen=True)
class CommandResult:
    """一步命令的结果；执行、long-gate 复用、缓存失败复用与续跑复用共用这一个形状。"""

    stdout: str
    stderr: str
    returncode: int
    stdout_log_path: str
    stderr_log_path: str
    execution_mode: str
    reused_from: Mapping[str, Any]
    started_at: str
    ended_at: str
    duration_s: float
    duration_kind: str
    original_duration_s: Optional[float]


#: execution_mode → reused_from 必有的非空键；executed 不复用任何旧结果。
_REUSED_FROM_REQUIRED_KEYS: Dict[str, Tuple[Tuple[str, Callable[[Any], bool]], ...]] = {
    "executed": (),
    "reused_success_cache": (("result_path", _is_text), ("completed_at", _is_text), ("fingerprint", _is_object)),
    "cached_failure": (("result_path", _is_text), ("completed_at", _is_text), ("fingerprint", _is_object)),
    "resumed_success": (
        ("receipt_path", _is_text),
        ("receipt_content", _is_object),
        ("run_id", _is_text),
        ("completed_at", _is_text),
    ),
}


def build_receipt(
    command: Mapping[str, Any],
    *,
    run_id: str,
    command_index: int,
    result: CommandResult,
    environment: Mapping[str, Any],
) -> Dict[str, Any]:
    """receipt 的唯一写出形状；`admit_receipt` 按同一形状读回。"""
    policy = command["output_policy"]
    return {
        "schema_version": QUALITY_GATE_PROOF_SCHEMA_VERSION,
        "run_id": run_id,
        "command_index": command_index,
        **command,
        "environment": environment,
        "returncode": result.returncode,
        "stdout_content": normalize_command_output_for_policy(result.stdout, policy=policy),
        "stderr_content": normalize_command_output_for_policy(result.stderr, policy=policy),
        "stdout_log_path": result.stdout_log_path,
        "stderr_log_path": result.stderr_log_path,
        "execution_mode": result.execution_mode,
        "reused_from": result.reused_from,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "duration_s": result.duration_s,
        "duration_kind": result.duration_kind,
        "original_duration_s": result.original_duration_s,
    }


def _is_environment(value: Any) -> bool:
    """环境声明的 `keys` 是文本列表，`values` 恰好以这些键为键；下游按 `keys` 直接索引 `values`。"""
    return (
        _is_object(value)
        and _is_text_list(value.get("keys"))
        and _is_object(value.get("values"))
        and set(value["values"]) == set(value["keys"])
    )


_COMMAND_FIELD_RULES: Dict[str, Callable[[Any], bool]] = {
    "display": _is_text,
    "args": _is_text_list,
    "capture_output": _is_bool,
    "output_policy": _is_text,
    "env_overlay": _is_object,
    "check_id": _is_text,
    "entry_type": _is_text,
    "proof_kind": _is_optional_text,
    "reuse_policy": _is_text,
    "runner_handler": _is_text,
}
_RECEIPT_COMMAND_FIELDS: _FieldRules = tuple((key, _COMMAND_FIELD_RULES[key]) for key in QUALITY_GATE_COMMAND_KEYS)
_RECEIPT_FIELDS: _FieldRules = (
    ("run_id", _is_text),
    ("command_index", _is_int),
    *_RECEIPT_COMMAND_FIELDS,
    ("environment", _is_environment),
    ("returncode", _is_int),
    ("stdout_content", _is_text),
    ("stderr_content", _is_text),
    ("stdout_log_path", _is_text),
    ("stderr_log_path", _is_text),
    ("execution_mode", _is_text),
    ("reused_from", _is_object),
    ("started_at", _is_text),
    ("ended_at", _is_text),
    ("duration_s", _is_number),
    ("duration_kind", _is_text),
    ("original_duration_s", _is_optional_number),
)


@dataclass(frozen=True)
class Receipt:
    """已通过结构准入的命令 receipt；`payload` 是读到的完整内容，供与 manifest 内嵌副本逐字绑定。"""

    path: str
    payload: Mapping[str, Any]
    run_id: str
    command_index: int
    command: Mapping[str, Any]
    environment: Mapping[str, Any]
    returncode: int
    stdout_content: str
    stderr_content: str
    stdout_log_path: str
    stderr_log_path: str
    ended_at: str
    duration_s: float
    duration_kind: str
    original_duration_s: Optional[float]


def _receipt_reason(detail: str) -> Rejection:
    return Rejection(DecisionCause.REJECTED, f"UNBOUND: quality gate command receipt {detail}")


def admit_receipt(repo_root: str, rel_path: str) -> Union[Receipt, Rejection]:
    """receipt 的唯一结构准入；与本次计划、run_id、manifest 的关系由调用方绑定。

    路径先按解析符号链接与 Windows 目录联接后的真实位置限定在仓库内，再限定在 receipts 目录下；
    receipts 目录整体链到仓库外时，第一步就拒绝。
    """
    try:
        abs_path = resolve_repo_path(repo_root, rel_path, description="receipt path")
    except ValueError:
        return _receipt_reason("path mismatch")
    if not is_within_repo(abs_path, os.path.join(repo_root, QUALITY_GATE_RECEIPTS_DIR_REL)):
        return _receipt_reason("path mismatch")
    try:
        payload = load_gate_json(abs_path)
    except GateJsonError as exc:
        if exc.missing:
            return Rejection(DecisionCause.MISSING, "UNBOUND: quality gate command receipt missing")
        return _receipt_reason("unreadable")
    if not gate_schema_matches(payload, QUALITY_GATE_PROOF_SCHEMA_VERSION):
        return _receipt_reason("schema_version mismatch")
    bad = _first_bad_field(payload, _RECEIPT_FIELDS)
    if bad is not None:
        return _receipt_reason(f"{bad[0]} invalid")
    execution_mode = payload["execution_mode"]
    if execution_mode not in _REUSED_FROM_REQUIRED_KEYS or (
        execution_mode == "cached_failure" and payload["returncode"] == 0
    ):
        return _receipt_reason("execution_mode mismatch")
    reused_from = payload["reused_from"]
    for key, predicate in _REUSED_FROM_REQUIRED_KEYS[execution_mode]:
        if not predicate(reused_from.get(key)) or not reused_from[key]:
            return _receipt_reason(f"reused_from {key} missing")
    original_duration_s = payload["original_duration_s"]
    return Receipt(
        path=rel_path,
        payload=payload,
        run_id=payload["run_id"],
        command_index=payload["command_index"],
        command={key: payload[key] for key in QUALITY_GATE_COMMAND_KEYS},
        environment=payload["environment"],
        returncode=payload["returncode"],
        stdout_content=payload["stdout_content"],
        stderr_content=payload["stderr_content"],
        stdout_log_path=payload["stdout_log_path"],
        stderr_log_path=payload["stderr_log_path"],
        ended_at=payload["ended_at"],
        duration_s=float(payload["duration_s"]),
        duration_kind=payload["duration_kind"],
        original_duration_s=None if original_duration_s is None else float(original_duration_s),
    )


# --------------------------------------------------------------------------- QualityGate manifest


@dataclass(frozen=True)
class ReceiptRow:
    """manifest 里一步的 receipt 索引：路径与内嵌的完整 receipt 内容。"""

    path: str
    content: Mapping[str, Any]


@dataclass(frozen=True)
class GateManifest:
    """续跑读取的上次 manifest 中经过结构准入的字段。"""

    status: str
    head_sha: str
    run_id: str
    checkout_root_realpath: str
    git_common_dir_realpath: str
    dirty_worktree_content_before: Mapping[str, Any]
    planned_commands: Tuple[Mapping[str, Any], ...]
    command_receipts: Tuple[ReceiptRow, ...]
    failure_message: Optional[str]
    #: 失败时正在执行的步骤序号；失败不在某一步上（步骤开始前或全部步骤结束后）时为 None。
    failure_command_index: Optional[int]


def _is_receipt_rows(value: Any) -> bool:
    return _is_object_list(value) and all(
        _is_text(row.get("path")) and _is_object(row.get("content")) for row in value
    )


_MANIFEST_FIELDS: _FieldRules = (
    ("status", _is_text),
    ("head_sha", _is_text),
    ("run_id", _is_text),
    ("checkout_root_realpath", _is_text),
    ("git_common_dir_realpath", _is_text),
    ("dirty_worktree_content_before", _is_object),
    ("planned_commands", _is_object_list),
    ("command_receipts", _is_receipt_rows),
    ("failure_message", _is_optional_text),
    ("failure_command_index", _is_optional_int),
)


def admit_manifest(abs_path: str) -> Union[GateManifest, Rejection]:
    try:
        payload = load_gate_json(abs_path)
    except GateJsonError as exc:
        if exc.missing:
            return Rejection(DecisionCause.MISSING, "旧 manifest 不存在")
        return Rejection(DecisionCause.REJECTED, f"旧 manifest 不是合法 JSON：{exc}")
    if not gate_schema_matches(payload, QUALITY_GATE_PROOF_SCHEMA_VERSION):
        return Rejection(DecisionCause.REJECTED, "旧 manifest schema_version 不一致，不能续跑")
    bad = _first_bad_field(payload, _MANIFEST_FIELDS)
    if bad is not None:
        return Rejection(DecisionCause.REJECTED, f"旧 manifest 字段缺失或类型不对，不能续跑：{bad[0]}")
    return GateManifest(
        status=payload["status"],
        head_sha=payload["head_sha"],
        run_id=payload["run_id"],
        checkout_root_realpath=payload["checkout_root_realpath"],
        git_common_dir_realpath=payload["git_common_dir_realpath"],
        dirty_worktree_content_before=payload["dirty_worktree_content_before"],
        planned_commands=tuple(payload["planned_commands"]),
        command_receipts=tuple(ReceiptRow(row["path"], row["content"]) for row in payload["command_receipts"]),
        failure_message=payload["failure_message"],
        failure_command_index=payload["failure_command_index"],
    )


# --------------------------------------------------------------------------- 运行期条目


@dataclass(frozen=True)
class StepOutcome:
    """一步执行完成后取得的结果：命令结果、receipt 路径、实际存在的输出文件、是否失败。"""

    result: CommandResult
    receipt_path: str
    output_files: Tuple[str, ...]
    failed: bool


@dataclass(frozen=True)
class RuntimeEntry:
    """long-gate 可复用条目在本次运行中的状态；summary 与 explain 都由它显式生成。

    `fingerprint` 只在本次取得完整指纹后存在；`record` 只在决策为复用成功缓存时存在。
    """

    entry: GateEntry
    decision: CacheDecision
    fingerprint: Optional[Mapping[str, Any]]
    record: Optional[CacheRecord]
    outcome: Optional[StepOutcome] = None
