from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_workbench_links import build_workbench_link, build_workbench_plan_context

_MISSING = object()
_PLAN_GUARD_FIELD_ALIASES = (
    ("requested_plan_role", ("requested_plan_role", "requested_role")),
    ("effective_plan_role", ("effective_plan_role", "selected_role")),
    ("plan_role_status", ("plan_role_status", "status")),
    ("is_scenario_preview", ("is_scenario_preview",)),
    ("is_comparison", ("is_comparison", "is_comparison_plan")),
    ("is_superseded_by_newer_version", ("is_superseded_by_newer_version",)),
    ("is_official_plan", ("is_official_plan", "is_official")),
    ("is_preview_plan", ("is_preview_plan", "is_preview")),
    ("is_current_executable_official_version", ("is_current_executable_official_version",)),
    ("can_dispatch", ("can_dispatch",)),
    ("can_write_feedback", ("can_write_feedback",)),
    ("plan_identity_error", ("plan_identity_error",)),
    ("plan_identity_blocking_error", ("plan_identity_blocking_error",)),
    ("plan_identity_blocking_scope", ("plan_identity_blocking_scope",)),
    ("result_summary_parse_failed", ("result_summary_parse_failed",)),
    ("result_summary_parse_reason", ("result_summary_parse_reason",)),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _date_from(data: Dict[str, Any]) -> Optional[str]:
    return _text(data.get("week_start")) or None


def _date_to(data: Dict[str, Any]) -> Optional[str]:
    return _text(data.get("week_end")) or None


def _resource_for_task(view: Any, meta: Dict[str, Any]) -> Dict[str, str]:
    view_text = _text(view) or "machine"
    if view_text == "operator":
        return {
            "resource_type": "operator",
            "resource_id": _text(meta.get("operator_id")),
            "resource_label": _text(meta.get("operator")),
        }
    return {
        "resource_type": "machine",
        "resource_id": _text(meta.get("machine_id")),
        "resource_label": _text(meta.get("machine")),
    }


def _plan_resolution(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = data.get("plan_role_resolution")
    return resolution if isinstance(resolution, dict) else {}


def _lookup_identity_field(data: Dict[str, Any], resolution: Dict[str, Any], names: Any) -> Any:
    for name in names:
        if name in data:
            return data[name]
        if name in resolution:
            return resolution[name]
    return _MISSING


def _plan_role_for_context(data: Dict[str, Any]) -> str:
    return _text(data.get("requested_plan_role")) or _text(data.get("effective_plan_role")) or "adopted"


def _base_context(data: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    resource = _resource_for_task(data.get("view"), meta)
    resolution = _plan_resolution(data)
    can_write = _lookup_identity_field(data, resolution, ("can_write_feedback",))
    is_preview = bool(data.get("is_scenario_preview") or _text(data.get("scenario_id")))
    context = build_workbench_plan_context(
        version=data.get("version"),
        plan_role=_plan_role_for_context(data),
        scenario_id=_text(data.get("scenario_id")),
        scenario_display_label=_text(data.get("scenario_display_name")),
        date_from=_date_from(data),
        date_to=_date_to(data),
        query_date=_date_from(data),
        period_preset="custom",
        batch_id=meta.get("batch_id"),
        resource_type=resource["resource_type"],
        resource_id=resource["resource_id"],
        resource_label=resource["resource_label"],
        is_preview=is_preview,
        can_write_feedback=can_write if can_write is not _MISSING else None,
    )
    for key, names in _PLAN_GUARD_FIELD_ALIASES:
        value = _lookup_identity_field(data, resolution, names)
        if value is not _MISSING:
            context[key] = value
    context["is_comparison"] = bool(context.get("is_comparison") or data.get("is_comparison_plan"))
    context["is_scenario_preview"] = is_preview
    return context


def _detail_links(data: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    context = _base_context(data, meta)
    resource = _resource_for_task(data.get("view"), meta)
    batch_id = meta.get("batch_id")
    preview_reason = "模拟预览不能直接跳转到正式工作台，请回到排产分析查看。"
    preview_disabled = bool(context.get("is_preview") or context.get("is_scenario_preview") or _text(context.get("scenario_id")))
    public_context = dict(context)
    if preview_disabled:
        public_context["scenario_id"] = None
    return [
        build_workbench_link(
            public_context,
            "resource_dispatch",
            label="查看资源排班",
            resource_type=resource["resource_type"],
            resource_id=resource["resource_id"],
            batch_id=batch_id,
            disabled=preview_disabled,
            disabled_reason=preview_reason if preview_disabled else "",
        ),
        build_workbench_link(
            public_context,
            "execution_review",
            label="查看计划和现场实际",
            resource_type=resource["resource_type"],
            resource_id=resource["resource_id"],
            batch_id=batch_id,
        ),
        build_workbench_link(
            public_context,
            "overdue_report",
            label="查看超期清单",
            batch_id=batch_id,
            disabled=preview_disabled,
            disabled_reason=preview_reason if preview_disabled else "",
        ),
    ]


def decorate_gantt_task_detail_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """给甘特任务追加详情区可用的工作台链接。

    core 层只负责排程和执行事实；这里属于 Web 展示装饰，不反向污染 core service。
    """
    if not isinstance(data, dict):
        return data
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return data
    for task in tasks:
        if not isinstance(task, dict):
            continue
        meta = task.get("meta")
        if not isinstance(meta, dict):
            continue
        meta["detail_links"] = _detail_links(data, meta)
    return data


__all__ = ["decorate_gantt_task_detail_payload"]
