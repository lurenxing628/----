from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)
from core.services.common.overdue_calculations import compute_overdue_bucket_groups

_MAX_LISTED_INVALID_BATCHES = 10


def build_overdue_batch_ids_from_plan_rows(rows: List[Dict[str, Any]]) -> Tuple[Set[str], List[str]]:
    """返回 (逾期标红批次号集合, 排程时间异常批次号列表)。

    “排程时间异常”批次（有排程记录、但计划完成时间写法坏、读不出有效时间）【不】纳入逾期标红：
    无法判定是否真逾期，标红会冤枉它们（finding-09：不再把时间坏的批次误报成逾期）。但它们的
    批次号单独返回，供上层在甘特/派工视图给出“数据异常、请核对”的诚实提示，而不是闷不吭声。
    """
    scheduled, unscheduled, invalid_time, _as_of = compute_overdue_bucket_groups(rows or [])
    overdue: Set[str] = set()
    for item in list(scheduled) + list(unscheduled):
        batch_id = str((item or {}).get("batch_id") or "").strip()
        if batch_id:
            overdue.add(batch_id)
    invalid_batch_ids: List[str] = []
    seen: Set[str] = set()
    for item in invalid_time:
        batch_id = str((item or {}).get("batch_id") or "").strip()
        if batch_id and batch_id not in seen:
            seen.add(batch_id)
            invalid_batch_ids.append(batch_id)
    return overdue, invalid_batch_ids


def _invalid_time_overdue_message(invalid_batch_ids: List[str]) -> str:
    count = len(invalid_batch_ids)
    listed = "、".join(invalid_batch_ids[:_MAX_LISTED_INVALID_BATCHES])
    if count > _MAX_LISTED_INVALID_BATCHES:
        listed += f" 等 {count} 个"
    return (
        f"另有 {count} 个批次的计划完成时间写法不对，没法判断是否逾期，已暂不标记逾期，"
        f"请核对这些批次的时间（批次号：{listed}）。"
    )


def build_overdue_meta_for_plan(
    *,
    version: int,
    role: str,
    source_table: str,
    list_plan_overdue_base_rows: Callable[..., List[Dict[str, Any]]],
    load_adopted_meta: Callable[[int], Dict[str, Any]],
    log_degraded: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    normalized_source = str(source_table or "").strip()
    if normalized_source == SOURCE_SCHEDULE:
        return load_adopted_meta(int(version))
    if normalized_source not in (SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS):
        raise ValueError(f"未知的排产方案数据来源：{normalized_source or '-'}")
    rows = list_plan_overdue_base_rows(version=int(version), role=role)
    ids, invalid_batch_ids = build_overdue_batch_ids_from_plan_rows([dict(row) for row in rows])
    has_invalid = bool(invalid_batch_ids)
    message = _invalid_time_overdue_message(invalid_batch_ids) if has_invalid else ""
    if has_invalid and log_degraded is not None:
        log_degraded(version=int(version), reason="schedule_time_invalid", message=message)
    return {
        "ids": sorted(ids),
        "degraded": False,
        "partial": has_invalid,
        "message": message,
        "reason": "schedule_time_invalid" if has_invalid else "",
    }
