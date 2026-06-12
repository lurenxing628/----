"""甘特负荷条带的 Web 展示装饰（fusion-gantt-load-strip）。

core 的 resource_load 行只有六个事实字段（date/resource_id/resource_label/
hours/capacity_hours/ratio）；severity 档位与跳转 links 属展示语义，在这里
追加——core 不 import web 阈值常量（分层），阈值取
dashboard_workbench_cards 的 LOAD_WARNING_RATIO/LOAD_DANGER_RATIO 唯一字源。

severity 映射（4.6 显式裁决）：ratio None→unknown；低于 LOAD_WARNING_RATIO
→normal；[LOAD_WARNING_RATIO, LOAD_DANGER_RATIO)→warning；达到
LOAD_DANGER_RATIO→danger。首页 'notice' 档是待办提醒语义，负荷四档与其
并存不混用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .dashboard_workbench_cards import LOAD_DANGER_RATIO, LOAD_WARNING_RATIO
from .scheduler_workbench_links import build_workbench_link, build_workbench_plan_context

_PREVIEW_REASON = "模拟预览不能直接跳转到正式工作台，请回到排产分析查看。"


def _text(value: Any) -> str:
    return str(value or "").strip()


def load_severity(ratio: Optional[float]) -> str:
    if ratio is None:
        return "unknown"
    if ratio >= LOAD_DANGER_RATIO:
        return "danger"
    if ratio >= LOAD_WARNING_RATIO:
        return "warning"
    return "normal"


def _strip_context(data: Dict[str, Any], row: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
    is_preview = bool(data.get("is_scenario_preview") or _text(data.get("scenario_id")))
    return build_workbench_plan_context(
        version=data.get("version"),
        plan_role=_text(data.get("requested_plan_role")) or _text(data.get("effective_plan_role")) or "adopted",
        scenario_id=_text(data.get("scenario_id")),
        date_from=row.get("date"),
        date_to=row.get("date"),
        query_date=row.get("date"),
        period_preset="custom",
        resource_type=resource_type,
        resource_id=row.get("resource_id"),
        resource_label=row.get("resource_label"),
        is_preview=is_preview,
    )


def _row_links(data: Dict[str, Any], row: Dict[str, Any]) -> List[Dict[str, Any]]:
    resource_type = "operator" if _text(data.get("view")) == "operator" else "machine"
    context = _strip_context(data, row, resource_type)
    preview_disabled = bool(context.get("is_preview") or _text(context.get("scenario_id")))
    public_context = dict(context)
    if preview_disabled:
        public_context["scenario_id"] = None
    return [
        build_workbench_link(
            public_context,
            "resource_dispatch",
            label="查看资源排班",
            resource_type=resource_type,
            resource_id=row.get("resource_id"),
            disabled=preview_disabled,
            disabled_reason=_PREVIEW_REASON if preview_disabled else "",
        ),
        build_workbench_link(
            public_context,
            "utilization_report",
            label="查看资源负荷报表",
            resource_type=resource_type,
            resource_id=row.get("resource_id"),
        ),
    ]


def decorate_gantt_resource_load_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """给负荷行追加 severity/links（幂等：已装饰的行原样跳过）。"""
    if not isinstance(data, dict):
        return data
    rows = data.get("resource_load")
    if not isinstance(rows, list):
        return data
    for row in rows:
        if not isinstance(row, dict) or "severity" in row:
            continue
        row["severity"] = load_severity(row.get("ratio"))
        row["links"] = _row_links(data, row)
    return data


__all__ = ["decorate_gantt_resource_load_payload", "load_severity"]
