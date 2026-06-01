from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_workbench_links import build_workbench_link, build_workbench_plan_context


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


def _plan_role_for_context(data: Dict[str, Any]) -> str:
    return _text(data.get("requested_plan_role")) or _text(data.get("effective_plan_role")) or "adopted"


def _base_context(data: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    resource = _resource_for_task(data.get("view"), meta)
    context = build_workbench_plan_context(
        version=data.get("version"),
        plan_role=_plan_role_for_context(data),
        scenario_id=data.get("scenario_id"),
        scenario_display_label=_text(data.get("scenario_display_name")),
        date_from=_date_from(data),
        date_to=_date_to(data),
        query_date=_date_from(data),
        period_preset="custom",
        batch_id=meta.get("batch_id"),
        resource_type=resource["resource_type"],
        resource_id=resource["resource_id"],
        resource_label=resource["resource_label"],
        is_preview=bool(data.get("is_scenario_preview")),
        can_write_feedback=data.get("can_write_feedback") if "can_write_feedback" in data else None,
    )
    context["is_comparison"] = bool(data.get("is_comparison_plan"))
    context["is_scenario_preview"] = bool(data.get("is_scenario_preview"))
    return context


def _detail_links(data: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    context = _base_context(data, meta)
    resource = _resource_for_task(data.get("view"), meta)
    batch_id = meta.get("batch_id")
    return [
        build_workbench_link(
            context,
            "resource_dispatch",
            label="查看资源排班",
            resource_type=resource["resource_type"],
            resource_id=resource["resource_id"],
            batch_id=batch_id,
        ),
        build_workbench_link(
            context,
            "execution_review",
            label="查看计划和现场实际",
            resource_type=resource["resource_type"],
            resource_id=resource["resource_id"],
            batch_id=batch_id,
        ),
        build_workbench_link(
            context,
            "overdue_report",
            label="查看超期清单",
            batch_id=batch_id,
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
