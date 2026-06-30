from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core.algorithms.objective_specs import objective_metric_keys
from core.infrastructure.errors import ValidationError

CANDIDATE_FINGERPRINT_SCHEMA_VERSION = 1
DECISION_FINGERPRINT_SCOPE = "decision"
OUTPUT_FINGERPRINT_SCOPE = "decoded_output"
DISTINCT_FINGERPRINT_SCOPE = OUTPUT_FINGERPRINT_SCOPE
DISTINCT_FINGERPRINT_DESCRIPTION = "distinct_candidates 按正式解码结果去重"


@dataclass(frozen=True)
class CandidateFingerprint:
    schema_version: int
    fingerprint_scope: str
    objective_name: str
    decision_fingerprint: str
    output_fingerprint: str
    parent_fingerprint: Optional[str]
    same_as_parent: bool
    same_as_seen: bool
    fingerprint_changed: bool

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "fingerprint_scope": str(self.fingerprint_scope),
            "objective_name": str(self.objective_name),
            "decision_fingerprint": str(self.decision_fingerprint),
            "output_fingerprint": str(self.output_fingerprint),
            "parent_fingerprint": self.parent_fingerprint,
            "same_as_parent": bool(self.same_as_parent),
            "same_as_seen": bool(self.same_as_seen),
            "fingerprint_changed": bool(self.fingerprint_changed),
        }


def stable_fingerprint(payload: Dict[str, Any]) -> str:
    text = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def jsonable_fingerprint_payload(value: Any) -> Any:
    return _jsonable(value)


def build_candidate_fingerprint(
    candidate: Dict[str, Any],
    *,
    objective_name: str,
    parent_fingerprint: Optional[str],
    seen_output_fingerprints: Iterable[str],
) -> CandidateFingerprint:
    _validate_candidate(candidate)
    decision_fingerprint = stable_fingerprint(_decision_payload(candidate, objective_name=objective_name))
    output_fingerprint = stable_fingerprint(_output_payload(candidate, objective_name=objective_name))
    seen = {str(item) for item in seen_output_fingerprints or [] if str(item)}
    same_as_parent = bool(parent_fingerprint and output_fingerprint == parent_fingerprint)
    same_as_seen = output_fingerprint in seen
    return CandidateFingerprint(
        schema_version=CANDIDATE_FINGERPRINT_SCHEMA_VERSION,
        fingerprint_scope=DISTINCT_FINGERPRINT_SCOPE,
        objective_name=str(objective_name),
        decision_fingerprint=decision_fingerprint,
        output_fingerprint=output_fingerprint,
        parent_fingerprint=parent_fingerprint,
        same_as_parent=same_as_parent,
        same_as_seen=same_as_seen,
        fingerprint_changed=not same_as_parent,
    )


def score_strictly_better(candidate_score: Any, parent_score: Any) -> bool:
    candidate = _score_tuple(candidate_score)
    parent = _score_tuple(parent_score)
    if not candidate or not parent:
        return False
    return candidate < parent


def _validate_candidate(candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise ValidationError("候选指纹只能从候选 dict 生成。", field="candidate_fingerprint")
    if not isinstance(candidate.get("results"), list):
        raise ValidationError("候选指纹缺少正式解码结果。", field="candidate_fingerprint")


def _decision_payload(candidate: Dict[str, Any], *, objective_name: str) -> Dict[str, Any]:
    strategy = candidate.get("strategy")
    order = list(candidate.get("decision_batch_order") or candidate.get("order") or [])
    return {
        "schema_version": CANDIDATE_FINGERPRINT_SCHEMA_VERSION,
        "fingerprint_scope": DECISION_FINGERPRINT_SCOPE,
        "objective_name": str(objective_name),
        "strategy": getattr(strategy, "value", strategy),
        "params": candidate.get("params") or {},
        "dispatch_mode": candidate.get("dispatch_mode"),
        "dispatch_rule": candidate.get("dispatch_rule"),
        "batch_order": order,
        "resource_override": _resource_override_payload(candidate),
        "locked_seed_scope": _locked_seed_scope_payload(candidate),
        "mutable_scope": _mutable_scope_payload(candidate, order),
    }


def _resource_override_payload(candidate: Dict[str, Any]) -> Any:
    # 候选只会写入 resource_pool（baseline/ortools/multi_start/local_search 四条路径统一），
    # 不臆造其它别名兜底；该值进的是 decision_fingerprint（仅 diagnostics）。
    return candidate.get("resource_pool") or {}


def _locked_seed_scope_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "seed_result_count": _non_negative_int(candidate.get("seed_result_count")),
        "locked_seed_range": candidate.get("locked_seed_range") or [],
    }


def _mutable_scope_payload(candidate: Dict[str, Any], order: List[Any]) -> Dict[str, Any]:
    mutable_scope = candidate.get("mutable_scope")
    if isinstance(mutable_scope, dict):
        return dict(mutable_scope)
    return {
        "scope": "batch_order",
        "batch_count": len(order),
    }


def _output_payload(candidate: Dict[str, Any], *, objective_name: str) -> Dict[str, Any]:
    results = list(candidate.get("results") or [])
    metrics = _objective_metric_signature(candidate.get("metrics"), objective_name=objective_name)
    summary = candidate.get("summary")
    return {
        "schema_version": CANDIDATE_FINGERPRINT_SCHEMA_VERSION,
        "fingerprint_scope": OUTPUT_FINGERPRINT_SCOPE,
        "objective_name": str(objective_name),
        "scheduled_result_count": len(results),
        "summary": {
            "success": bool(getattr(summary, "success", False)),
            "total_ops": _non_negative_int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": _non_negative_int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": _non_negative_int(getattr(summary, "failed_ops", 0)),
        },
        "schedule_signature": _result_signature(results),
        "objective_metrics": metrics,
        "score": _score_tuple(candidate.get("score")),
    }


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
    try:
        number = int(value or 0)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"候选指纹字段必须是非负整数：{value!r}", field="candidate_fingerprint") from exc
    if number < 0:
        raise ValidationError(f"候选指纹字段必须是非负整数：{value!r}", field="candidate_fingerprint")
    return number


def _finite_float(value: Any, *, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"候选指纹指标 {field_name} 必须是数字：{value!r}", field="candidate_fingerprint") from exc
    if not math.isfinite(number):
        raise ValidationError(f"候选指纹指标 {field_name} 必须是有限数字：{value!r}", field="candidate_fingerprint")
    return float(round(number, 6))


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return ()
    return tuple(_finite_float(item, field_name="score") for item in score)


def _time_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")


def _jsonable(value: Any) -> Any:
    # 仅服务 decision_fingerprint 与 skipped-phase 诊断 extra 的确定性序列化；output_fingerprint
    # 的输入已是显式纯量（见 _output_payload），不经过下面的对象分支。未知对象按类名做「有损但
    # 确定」降级：resource_pool 等业务输入可能含对象,此处不 fail-loud 以免误伤 diagnostics;由此
    # 带来的同类不同实例 hash 碰撞只降低诊断区分度,不影响按 output_fingerprint 的去重/improved 判定。
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
    "DECISION_FINGERPRINT_SCOPE",
    "DISTINCT_FINGERPRINT_DESCRIPTION",
    "DISTINCT_FINGERPRINT_SCOPE",
    "OUTPUT_FINGERPRINT_SCOPE",
    "CandidateFingerprint",
    "build_candidate_fingerprint",
    "jsonable_fingerprint_payload",
    "score_strictly_better",
    "stable_fingerprint",
]
