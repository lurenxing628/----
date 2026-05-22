from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import url_for


def _plan_role_links(version: int, role: str) -> List[Dict[str, str]]:
    return [
        {
            "label": "设备甘特图",
            "url": url_for("scheduler.gantt_page", view="machine", version=version, plan_role=role),
        },
        {
            "label": "人员甘特图",
            "url": url_for("scheduler.gantt_page", view="operator", version=version, plan_role=role),
        },
        {
            "label": "周计划",
            "url": url_for("scheduler.week_plan_page", version=version, plan_role=role),
        },
        {
            "label": "资源排班",
            "url": url_for("scheduler.resource_dispatch_page", version=version, plan_role=role),
        },
    ]


def attach_candidate_plan_links(ctx: Dict[str, Any], selected_ver: Optional[int]) -> None:
    display = ctx.get("candidate_comparison_display")
    if selected_ver is None or not isinstance(display, dict):
        return
    for row in list(display.get("rows") or []):
        if not isinstance(row, dict) or not row.get("plan_role_available"):
            continue
        role = str(row.get("role") or "").strip()
        if not role:
            continue
        row["links"] = _plan_role_links(int(selected_ver), role)


__all__ = ["attach_candidate_plan_links"]
