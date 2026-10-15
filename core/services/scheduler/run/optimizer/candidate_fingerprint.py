from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.objective_specs import objective_metric_keys
from core.errors import ValidationError

CANDIDATE_FINGERPRINT_SCHEMA_VERSION = 2
OUTPUT_FINGERPRINT_SCOPE = "decoded_output"
DISTINCT_FINGERPRINT_SCOPE = OUTPUT_FINGERPRINT_SCOPE
DISTINCT_FINGERPRINT_DESCRIPTION = "distinct_candidates 按正式解码结果去重"


@dataclass(frozen=True)
class CandidateFingerprint:
    schema_version: int
    fingerprint_scope: str
    objective_name: str
    candidate_id: int
    output_key: Tuple[Any, ...] = field(repr=False)
    parent_candidate_id: Optional[int]
    same_as_parent: bool
    same_as_seen: bool
    fingerprint_changed: bool

    def with_context(self, *, parent_fingerprint: Optional[CandidateFingerprint],
                     seen_output_fingerprints: Iterable[Tuple[Any, ...]]) -> CandidateFingerprint:
        same_as_parent = bool(parent_fingerprint is not None and self.output_key == parent_fingerprint.output_key)
        return replace(self, parent_candidate_id=parent_fingerprint.candidate_id if parent_fingerprint is not None else None,
                       same_as_parent=same_as_parent,
                       same_as_seen=self.output_key in (seen_output_fingerprints or ()),
                       fingerprint_changed=not same_as_parent)

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "output_scope": str(self.fingerprint_scope),
            "objective_name": str(self.objective_name),
            "candidate_id": int(self.candidate_id),
            "parent_candidate_id": self.parent_candidate_id,
            "same_as_parent": bool(self.same_as_parent),
            "same_as_seen": bool(self.same_as_seen),
            "output_changed": bool(self.fingerprint_changed),
        }


def jsonable_fingerprint_payload(value: Any) -> Any:
    return _jsonable(value)


def schedule_content_key(results: Iterable[ScheduleResult]) -> Tuple[Tuple[Any, ...], ...]:
    """Identify the actual arrangement independently of its evaluation."""
    return tuple(
        (
            result.op_id,
            result.batch_id,
            result.seq,
            result.machine_id,
            result.operator_id,
            result.start_time,
            result.end_time,
            result.source,
            result.seed_source,
            result.state_revision,
            result.op_type_id,
        )
        for result in sorted(results, key=lambda row: row.op_id)
    )


def build_candidate_fingerprint(
    candidate: Dict[str, Any],
    *,
    objective_name: str,
    parent_fingerprint: Optional[CandidateFingerprint],
    seen_output_fingerprints: Iterable[Tuple[Any, ...]],
    identity: Optional[CandidateFingerprint] = None,
    candidate_id: int = 0,
) -> CandidateFingerprint:
    _validate_candidate(candidate)
    if identity is not None:
        return identity.with_context(parent_fingerprint=parent_fingerprint,
                                     seen_output_fingerprints=seen_output_fingerprints)
    return CandidateFingerprint(
        schema_version=CANDIDATE_FINGERPRINT_SCHEMA_VERSION,
        fingerprint_scope=DISTINCT_FINGERPRINT_SCOPE,
        objective_name=str(objective_name),
        candidate_id=int(candidate_id),
        output_key=_output_payload(candidate, objective_name=objective_name),
        parent_candidate_id=None,
        same_as_parent=False,
        same_as_seen=False,
        fingerprint_changed=True,
    ).with_context(parent_fingerprint=parent_fingerprint, seen_output_fingerprints=seen_output_fingerprints)


def score_strictly_better(candidate_score: Any, parent_score: Any) -> bool:
    candidate = _score_tuple(candidate_score)
    parent = _score_tuple(parent_score)
    if not candidate or not parent:
        return False
    return candidate < parent


def _validate_candidate(candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise ValidationError("候选内容只能从候选 dict 生成。", field="candidate_fingerprint")
    if not isinstance(candidate.get("results"), list):
        raise ValidationError("候选内容缺少正式解码结果。", field="candidate_fingerprint")


def _output_payload(candidate: Dict[str, Any], *, objective_name: str) -> Tuple[Any, ...]:
    results = list(candidate.get("results") or [])
    metrics = _objective_metric_signature(candidate.get("metrics"), objective_name=objective_name)
    summary = candidate.get("summary")
    return (str(objective_name), len(results),
            (bool(getattr(summary, "success", False)),
             _non_negative_int(getattr(summary, "total_ops", 0)),
             _non_negative_int(getattr(summary, "scheduled_ops", 0)),
             _non_negative_int(getattr(summary, "failed_ops", 0))),
            tuple(tuple(row.values()) for row in _result_signature(results)),
            tuple(metrics.items()), _score_tuple(candidate.get("score")))


def _objective_metric_signature(metrics: Any, *, objective_name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in objective_metric_keys(objective_name):
        if hasattr(metrics, key):
            out[str(key)] = _finite_float(getattr(metrics, key), field_name=str(key))
    return out


def _result_signature(results: List[Any]) -> List[Dict[str, Any]]:
    rows = [_result_row(result) for result in results]
    return sorted(
        rows,
        key=lambda row: (
            row.get("op_id"),
            row.get("batch_id"),
            row.get("seq"),
            row.get("start_time"),
            row.get("end_time"),
            row.get("machine_id"),
            row.get("operator_id"),
        ),
    )


def _result_row(result: Any) -> Dict[str, Any]:
    return {
        "op_id": str(getattr(result, "op_id", "") or ""),
        "op_code": str(getattr(result, "op_code", "") or ""),
        "batch_id": str(getattr(result, "batch_id", "") or ""),
        "seq": _non_negative_int(getattr(result, "seq", 0)),
        "machine_id": str(getattr(result, "machine_id", "") or ""),
        "operator_id": str(getattr(result, "operator_id", "") or ""),
        "start_time": _time_text(getattr(result, "start_time", None)),
        "end_time": _time_text(getattr(result, "end_time", None)),
        "source": str(getattr(result, "source", "") or ""),
        "op_type_name": str(getattr(result, "op_type_name", "") or ""),
    }


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValidationError("候选结果整数值须使用数字。", field="candidate_fingerprint")
    try:
        number = int(value or 0)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"候选内容字段必须是非负整数：{value!r}", field="candidate_fingerprint") from exc
    if number < 0:
        raise ValidationError(f"候选内容字段必须是非负整数：{value!r}", field="candidate_fingerprint")
    return number


def _finite_float(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"候选结果指标 {field_name} 须使用数字。", field="candidate_fingerprint")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"候选内容指标 {field_name} 必须是数字：{value!r}", field="candidate_fingerprint") from exc
    if not math.isfinite(number):
        raise ValidationError(f"候选内容指标 {field_name} 必须是有限数字：{value!r}", field="candidate_fingerprint")
    return float(round(number, 6))


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return ()
    return tuple(_finite_float(item, field_name="score") for item in score)


def _time_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")


def _jsonable(value: Any) -> Any:
    # 只负责 skipped-phase 等诊断的 JSON 表示；候选判等使用明确字段的不可变 output_key。
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return _time_text(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=lambda item: str(item))]
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _jsonable(enum_value)
    return {"type": value.__class__.__name__}


__all__ = [
    "CANDIDATE_FINGERPRINT_SCHEMA_VERSION",
    "DISTINCT_FINGERPRINT_DESCRIPTION",
    "DISTINCT_FINGERPRINT_SCOPE",
    "OUTPUT_FINGERPRINT_SCOPE",
    "CandidateFingerprint",
    "build_candidate_fingerprint",
    "jsonable_fingerprint_payload",
    "schedule_content_key",
    "score_strictly_better",
]
