from __future__ import annotations

from typing import Any, Dict, List, Optional

from web.viewmodels.scheduler_workbench_links import build_workbench_link, build_workbench_plan_context


def _text(value: Any) -> str:
    return str(value or "").strip()


def _plan_role_links(
    version: int,
    role: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    query_date: Optional[str] = None,
    period_preset: Optional[str] = None,
    batch_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    context = build_workbench_plan_context(
        version=version,
        plan_role=role,
        date_from=date_from,
        date_to=date_to,
        query_date=query_date,
        period_preset=period_preset,
        batch_id=batch_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return [
        build_workbench_link(context, "gantt", label="设备甘特图", view="machine"),
        build_workbench_link(context, "gantt", label="人员甘特图", view="operator"),
        build_workbench_link(context, "week_plan", label="周计划"),
        build_workbench_link(context, "resource_dispatch", label="资源排班"),
        build_workbench_link(context, "overdue_report", label="超期清单"),
    ]


def attach_candidate_plan_links(
    ctx: Dict[str, Any],
    selected_ver: Optional[int],
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    query_date: Optional[str] = None,
    period_preset: Optional[str] = None,
    batch_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> None:
    display = ctx.get("candidate_comparison_display")
    if selected_ver is None or not isinstance(display, dict):
        return
    for row in list(display.get("rows") or []):
        if not isinstance(row, dict) or not row.get("plan_role_available") or not row.get("can_open_detail"):
            continue
        role = str(row.get("role") or "").strip()
        if not role:
            continue
        row["links"] = _plan_role_links(
            int(selected_ver),
            role,
            date_from=date_from,
            date_to=date_to,
            query_date=query_date,
            period_preset=period_preset,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )


__all__ = ["attach_candidate_plan_links"]
