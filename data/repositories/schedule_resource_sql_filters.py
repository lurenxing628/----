from __future__ import annotations

from typing import Any, List, Optional

from core.models.schedule_resource_filter import normalize_overdue_resource_filter, normalize_schedule_resource_filter


def detail_resource_filter(resource_type: Optional[str], resource_id: Optional[str]):
    return normalize_schedule_resource_filter(
        resource_type,
        resource_id,
        missing_type_message="计划明细查询缺少资源类型，不能只带资源编号。",
        unsupported_message="计划明细查询只支持设备或人员维度。",
        missing_id_message="计划明细查询缺少资源编号，不能只带资源类型。",
    )


def overdue_resource_filter(resource_type: Optional[str], resource_id: Optional[str]):
    return normalize_overdue_resource_filter(resource_type, resource_id)


def append_detail_filters(
    where_clauses: List[str],
    params: List[Any],
    *,
    batch_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> None:
    batch_id_text = str(batch_id or "").strip()
    if batch_id_text:
        where_clauses.append("TRIM(CAST(bo.batch_id AS TEXT)) = ?")
        params.append(batch_id_text)
    resource_filter = detail_resource_filter(resource_type, resource_id)
    if resource_filter.has_filter:
        where_clauses.append(f"TRIM(COALESCE(s.{resource_filter.column_name}, '')) = ?")
        params.append(resource_filter.resource_id)


__all__ = ["append_detail_filters", "detail_resource_filter", "overdue_resource_filter"]
