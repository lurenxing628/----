from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.algorithms import ScheduleResult
from core.algorithms.greedy.algo_stats import increment_counter
from core.algorithms.value_domains import INTERNAL
from core.infrastructure.errors import ValidationError


def _raise_invalid_seed_results_error(*, invalid_seed_count: int, invalid_seed_samples: List[Dict[str, Any]]) -> None:
    exc = ValidationError("本次排产引用的已有排产记录无效，系统已停止排产，没有写入新结果。请刷新排产数据后重试。", field="seed_results")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "invalid_seed_results"
    exc.details["invalid_seed_count"] = int(invalid_seed_count)
    exc.details["invalid_seed_samples"] = list(invalid_seed_samples)
    raise exc


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
    try:
        valid_time_range = start_time < end_time
    except Exception as exc:
        raise TypeError(f"第 {idx + 1} 条已有排产记录的时间区间不正确。") from exc
    if not valid_time_range:
        raise TypeError(f"第 {idx + 1} 条已有排产记录的开始时间必须早于结束时间。")
    return start_time, end_time


def coerce_seed_result_item(item: Any, *, idx: int) -> ScheduleResult:
    if not isinstance(item, dict):
        raise TypeError(f"第 {idx + 1} 条已有排产记录格式不正确。")
    start_time, end_time = _coerce_seed_time_range(item, idx=idx)
    return ScheduleResult(
        op_id=int(item.get("op_id") or 0),
        op_code=str(item.get("op_code") or ""),
        batch_id=str(item.get("batch_id") or ""),
        seq=int(item.get("seq") or 0),
        machine_id=(str(item.get("machine_id") or "") or None),
        operator_id=(str(item.get("operator_id") or "") or None),
        start_time=start_time,
        end_time=end_time,
        source=str(item.get("source") or INTERNAL),
        op_type_name=(str(item.get("op_type_name") or "") or None),
    )


def coerce_seed_results(
    seed_results: List[Dict[str, Any]],
    *,
    optimizer_algo_stats: Dict[str, Any],
) -> List[ScheduleResult]:
    seed_sr_list: List[ScheduleResult] = []
    invalid_seed_samples: List[Dict[str, Any]] = []
    invalid_seed_count = 0
    for idx, item in enumerate(seed_results or []):
        try:
            seed_sr_list.append(coerce_seed_result_item(item, idx=idx))
        except Exception as exc:
            invalid_seed_count += 1
            if len(invalid_seed_samples) < 5:
                invalid_seed_samples.append({"index": int(idx), "error": str(exc), "sample": _seed_result_sample(item)})

    increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", invalid_seed_count)
    if invalid_seed_count > 0:
        optimizer_algo_stats.setdefault("fallback_samples", {})
        optimizer_algo_stats["fallback_samples"]["optimizer_seed_result_invalid_samples"] = list(invalid_seed_samples)
        _raise_invalid_seed_results_error(
            invalid_seed_count=invalid_seed_count,
            invalid_seed_samples=invalid_seed_samples,
        )
    return seed_sr_list
