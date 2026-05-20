from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.services.common.overdue_calculations import compute_overdue_buckets
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

_CANDIDATE_OVERDUE_MESSAGE = "候选方案超期标记计算失败，当前不显示候选方案超期标记。"


def build_overdue_batch_ids_from_plan_rows(rows: List[Dict[str, Any]]) -> Set[str]:
    scheduled, unscheduled, _as_of = compute_overdue_buckets(rows or [])
    overdue: Set[str] = set()
    for item in list(scheduled) + list(unscheduled):
        batch_id = str((item or {}).get("batch_id") or "").strip()
        if batch_id:
            overdue.add(batch_id)
    return overdue


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
    if normalized_source != SOURCE_CANDIDATE_ROWS:
        raise ValueError(f"未知的排产方案数据来源：{normalized_source or '-'}")
    try:
        rows = list_plan_overdue_base_rows(version=int(version), role=role)
        ids = build_overdue_batch_ids_from_plan_rows([dict(row) for row in rows])
        return {
            "ids": sorted(ids),
            "degraded": False,
            "partial": False,
            "message": "",
            "reason": "",
        }
    except ValidationError:
        raise
    except ValueError:
        raise
    except Exception as exc:
        meta = {
            "ids": [],
            "degraded": True,
            "partial": True,
            "message": _CANDIDATE_OVERDUE_MESSAGE,
            "reason": f"candidate_overdue_calculation_failed:{exc.__class__.__name__}",
        }
        if log_degraded is not None:
            log_degraded(version=int(version), reason=str(meta["reason"]), message=str(meta["message"]))
        return meta
