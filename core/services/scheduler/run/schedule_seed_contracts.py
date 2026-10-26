from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult, SchedulePointEvidence
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithms.greedy.seed import (
    identity_int,
    with_seed_external_group_metadata,
    with_seed_resource_segments,
)
from core.errors import ValidationError

from .schedule_payload_contract import arrangement_row


def _raise_invalid_seed_results_error(*, invalid_seed_count: int, invalid_seed_samples: List[Dict[str, Any]]) -> None:
    raise ValidationError(
        "本次排产引用的已有排产记录无效，系统已停止排产，没有写入新结果。请刷新排产数据后重试。",
        field="seed_results",
        details={
            "reason": "invalid_seed_results",
            "invalid_seed_count": int(invalid_seed_count),
            "invalid_seed_samples": invalid_seed_samples,
        },
    )


def _seed_result_sample(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__, "repr": repr(item)[:200]}
    return {
        "op_id": item.get("op_id"),
        "op_code": item.get("op_code"),
        "batch_id": item.get("batch_id"),
        "seq": item.get("seq"),
        "machine_id": item.get("machine_id"),
        "operator_id": item.get("operator_id"),
    }


def _coerce_seed_time_range(item: Dict[str, Any], *, idx: int) -> Tuple[Any, Any]:
    start_time = item.get("start_time")
    end_time = item.get("end_time")
    if start_time is None or end_time is None:
        raise TypeError(f"第 {idx + 1} 条已有排产记录缺少开始时间或结束时间。")
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise TypeError(f"第 {idx + 1} 条已有排产记录的开始时间和结束时间必须是有效时间。")
    valid_time_range = start_time < end_time
    evidence = item.get("_point_evidence")
    if start_time == end_time and type(evidence) is SchedulePointEvidence:
        valid_time_range = evidence.matches(arrangement_row(item))
    if not valid_time_range:
        raise TypeError(f"第 {idx + 1} 条已有排产记录的开始时间必须早于结束时间。")
    return start_time, end_time


def _required_seed_identity(value: Any, *, idx: int, field: str) -> int:
    # 三处种子生产者都写本次输入工序的正整数编号和工序号；缺失、非正或不是整数都按无效种子停止排产。
    identity = identity_int(value)
    if identity <= 0:
        raise TypeError(f"第 {idx + 1} 条已有排产记录的{field}必须是正整数。")
    return identity


def _optional_seed_text(item: Dict[str, Any], field: str) -> Optional[str]:
    return str(item.get(field) or "") or None


def _seed_source(item: Dict[str, Any], *, idx: int) -> str:
    # 种子来源与工序来源同一值域：缺失或不规范都按无效种子停止排产，不再静默当作自制。
    source = item.get("source")
    if type(source) is not str or source not in OPERATION_SOURCES:
        raise TypeError(f"第 {idx + 1} 条已有排产记录的工序来源不正确。")
    return source


def coerce_seed_result_item(item: Any, *, idx: int) -> ScheduleResult:
    if not isinstance(item, dict):
        raise TypeError(f"第 {idx + 1} 条已有排产记录格式不正确。")
    start_time, end_time = _coerce_seed_time_range(item, idx=idx)
    op_id = _required_seed_identity(item.get("op_id"), idx=idx, field="工序编号")
    seq = _required_seed_identity(item.get("seq"), idx=idx, field="工序号")
    result = ScheduleResult(
        op_id=op_id,
        # All three seed producers write non-empty op_code/batch_id (freeze_window_seed_rows,
        # schedule_execution_guardrails, schedule_input_seed_metadata).
        op_code=item["op_code"],
        batch_id=item["batch_id"],
        seq=seq,
        machine_id=_optional_seed_text(item, "machine_id"),
        operator_id=_optional_seed_text(item, "operator_id"),
        start_time=start_time,
        end_time=end_time,
        source=_seed_source(item, idx=idx),
        op_type_name=_optional_seed_text(item, "op_type_name"),
        seed_source=_optional_seed_text(item, "seed_source"),
        state_revision=_optional_seed_text(item, "state_revision"),
        op_type_id=_optional_seed_text(item, "op_type_id"),
    )
    if "_external_group_metadata" in item:
        result = with_seed_external_group_metadata(result, item["_external_group_metadata"])
    if "_resource_segments" in item:
        result = with_seed_resource_segments(result, item["_resource_segments"])
    if start_time == end_time:
        return PointSeedResult(result, item["_point_evidence"])
    return result


def coerce_seed_results(
    seed_results: List[Dict[str, Any]],
    *,
    optimizer_algo_stats: Dict[str, Any],
) -> List[ScheduleResult]:
    seed_sr_list: List[ScheduleResult] = []
    invalid_seed_samples: List[Dict[str, Any]] = []
    invalid_seed_count = 0
    for idx, item in enumerate(seed_results):
        try:
            seed_sr_list.append(coerce_seed_result_item(item, idx=idx))
        except Exception as exc:
            invalid_seed_count += 1
            if len(invalid_seed_samples) < 5:
                invalid_seed_samples.append({"index": int(idx), "error": str(exc), "sample": _seed_result_sample(item)})

    increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", invalid_seed_count)
    if invalid_seed_count > 0:
        optimizer_algo_stats.setdefault("fallback_samples", {})
        optimizer_algo_stats["fallback_samples"]["optimizer_seed_result_invalid_samples"] = invalid_seed_samples
        _raise_invalid_seed_results_error(
            invalid_seed_count=invalid_seed_count,
            invalid_seed_samples=invalid_seed_samples,
        )
    return seed_sr_list
