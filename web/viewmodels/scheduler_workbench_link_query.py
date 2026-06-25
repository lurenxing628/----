from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.models.schedule_plan_role import project_plan_guard_fields

from .scheduler_workbench_link_specs import (
    _CONTEXT_FREE_TARGET_FORBIDDEN_EXTRA_PARAMS,
    _CONTEXT_FREE_TARGETS,
    _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS,
    _TARGET_QUERY_SPECS,
)

TARGET_PAGE_PATHS = {
    "dashboard": "/",
    # 执行排产页（context-free）：首页「待排批次」体检格点跳回排产入口，
    # 不带版本/方案身份/日期等工作台上下文（待排是「还没进排产结果」的全量列表）
    "batches": "/scheduler/",
    "analysis": "/scheduler/analysis",
    "gantt": "/scheduler/gantt",
    "week_plan": "/scheduler/week-plan",
    "resource_dispatch": "/scheduler/resource-dispatch",
    "overdue_report": "/reports/overdue",
    "delay_diagnosis": "/reports/overdue",
    "utilization_report": "/reports/utilization",
    "execution_review": "/reports/execution-review",
    "downtime_report": "/reports/downtime",
    "reports_index": "/reports/",
    "history": "/system/history",
    # 路径参数型目标：{batch_id} 占位在 build_workbench_link 拼 URL 时替换，
    # 缺 batch_id 直接 raise（fail-loud，不出半截 URL）
    "batch_detail": "/scheduler/batches/{batch_id}",
}

TARGET_DEFAULT_LABELS = {
    "dashboard": "回到计划工作台",
    "batches": "去执行排产",
    "analysis": "查看排产分析",
    "gantt": "查看甘特图",
    "week_plan": "查看周计划",
    "resource_dispatch": "查看资源排班",
    "overdue_report": "查看超期清单",
    "delay_diagnosis": "查看延期说明",
    "utilization_report": "查看资源负荷",
    "execution_review": "查看计划和现场实际",
    "downtime_report": "查看停机影响",
    "reports_index": "查看报表中心",
    "history": "查看排产历史",
    "batch_detail": "查看批次详情",
}

VERSION_REQUIRED_TARGETS = {
    "analysis",
    "gantt",
    "week_plan",
    "resource_dispatch",
    "overdue_report",
    "delay_diagnosis",
    "utilization_report",
    "execution_review",
    "downtime_report",
    "reports_index",
}

WORKBENCH_CONTINUATION_TARGETS = VERSION_REQUIRED_TARGETS - {"analysis"}
PLAN_CONTEXT_TOKEN_TARGETS = {
    "dashboard",
    "analysis",
    "gantt",
    "week_plan",
    "resource_dispatch",
    "overdue_report",
    "delay_diagnosis",
    "utilization_report",
    "downtime_report",
    "reports_index",
}

DATE_RANGE_REQUIRED_TARGETS = {
    "gantt",
    "week_plan",
    "resource_dispatch",
    "utilization_report",
    "execution_review",
    "downtime_report",
    "reports_index",
}

_PLAN_GUARD_COMMON_FIELDS = (
    "requested_plan_role",
    "effective_plan_role",
    "is_scenario_preview",
    "is_comparison",
    "is_superseded_by_newer_version",
    "is_official_plan",
    "is_preview_plan",
    "is_current_executable_official_version",
    "can_dispatch",
    "can_write_feedback",
    "source_table",
    "schedule_result_status",
    "detail_saved",
    "is_simulation_plan",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
)

_PLAN_IDENTITY_BLOCKING_FIELDS = (
    "plan_identity_error",
    "plan_identity_blocking_error",
    "plan_identity_blocking_scope",
)

REPORT_PLAN_GUARD_FIELDS = _PLAN_GUARD_COMMON_FIELDS
RESOURCE_PLAN_GUARD_FIELDS = (
    _PLAN_GUARD_COMMON_FIELDS[:10] + _PLAN_IDENTITY_BLOCKING_FIELDS + _PLAN_GUARD_COMMON_FIELDS[10:]
)
FULL_PLAN_GUARD_FIELDS = (
    _PLAN_GUARD_COMMON_FIELDS[:2]
    + ("plan_role_status",)
    + _PLAN_GUARD_COMMON_FIELDS[2:10]
    + _PLAN_IDENTITY_BLOCKING_FIELDS
    + _PLAN_GUARD_COMMON_FIELDS[10:]
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    return value is not None and _text(value) != ""


def plan_guard_fields_for_resolution(plan_resolution: Any, field_names: Iterable[str]) -> Dict[str, Any]:
    source = dict(plan_resolution) if isinstance(plan_resolution, dict) else {}
    fields = project_plan_guard_fields(source)
    out: Dict[str, Any] = {}
    for key in field_names:
        value = fields.get(key)
        if value is None and key in source:
            value = source.get(key)
        if value is not None:
            out[key] = value
    return out


def _append_param(query: List[Tuple[str, str]], key: str, value: Any) -> None:
    if _has_value(value):
        query.append((key, _text(value)))


def _append_date_range_as_start_end(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "start_date", context.get("date_from"))
    _append_param(query, "end_date", context.get("date_to"))


def _append_date_range_as_date_from_to(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "date_from", context.get("date_from"))
    _append_param(query, "date_to", context.get("date_to"))


def _derived_plan_context_token(context: Dict[str, Any]) -> str:
    existing_token = context.get("plan_context_token")
    if _has_value(existing_token):
        return _text(existing_token)
    return ""


def has_public_plan_context_token_source(context: Dict[str, Any]) -> bool:
    return _has_value(context.get("plan_context_token"))


def _append_plan_query(query: List[Tuple[str, str]], context: Dict[str, Any], target_page: str) -> None:
    _append_param(query, "version", context.get("version"))
    _append_param(query, "plan_role", context.get("plan_role"))
    if target_page in PLAN_CONTEXT_TOKEN_TARGETS:
        _append_param(query, "plan_context_token", _derived_plan_context_token(context))
        return
    _append_param(query, "scenario_id", context.get("scenario_id"))


def _append_period_query(query: List[Tuple[str, str]], context: Dict[str, Any], *, period_preset: Optional[str] = None) -> None:
    _append_param(query, "query_date", context.get("query_date"))
    _append_param(query, "period_preset", period_preset or context.get("period_preset"))


def _append_batch_query(query: List[Tuple[str, str]], batch_value: Any, *, key: str = "batch_id") -> None:
    _append_param(query, key, batch_value)


def ordered_required_params(query: Iterable[Tuple[str, str]]) -> List[str]:
    out: List[str] = []
    for key, _value in query:
        if key not in out:
            out.append(key)
    return out


def _target_spec(target_page: str) -> Dict[str, Any]:
    spec = _TARGET_QUERY_SPECS.get(target_page)
    if spec is None:
        raise ValueError(f"未知工作台目标页：{target_page}")
    return spec


def target_uses_primary_resource_filter(target_page: str) -> bool:
    return str(_target_spec(target_page)["resource_style"]) == "resource"


def _append_target_plan_query(query: List[Tuple[str, str]], context: Dict[str, Any], target_page: str, plan_style: str) -> None:
    if plan_style == "none":
        return
    if plan_style == "version_only":
        _append_param(query, "version", context.get("version"))
        return
    if plan_style == "execution_review":
        _append_param(query, "version", context.get("version"))
        _append_param(query, "plan_role", context.get("plan_role"))
        return
    if plan_style == "standard":
        _append_plan_query(query, context, target_page)
        return
    raise ValueError(f"未知方案参数格式：{plan_style}")


def _append_target_date_query(query: List[Tuple[str, str]], context: Dict[str, Any], date_style: str) -> None:
    if date_style == "none":
        return
    if date_style == "start_end":
        _append_date_range_as_start_end(query, context)
        return
    if date_style == "date_from_to":
        _append_date_range_as_date_from_to(query, context)
        return
    raise ValueError(f"未知日期参数格式：{date_style}")


def _resource_query_value(
    context: Dict[str, Any],
    resource_type: Optional[str],
    resource_id: Any,
    *,
    default_type: Optional[str] = None,
) -> List[Tuple[str, str]]:
    type_text = _text(resource_type or context.get("resource_type") or default_type)
    if not type_text:
        return []
    id_text = _text(resource_id or context.get("resource_id"))
    query: List[Tuple[str, str]] = [("scope_type", type_text)]
    if id_text:
        query.append(("scope_id", id_text))
        if type_text == "operator":
            query.append(("operator_id", id_text))
        elif type_text == "machine":
            query.append(("machine_id", id_text))
        elif type_text == "team":
            query.append(("team_id", id_text))
    return query


def _append_resource_query(
    query: List[Tuple[str, str]],
    context: Dict[str, Any],
    resource_type: Optional[str],
    resource_id: Any,
    *,
    style: str,
    default_type: Optional[str] = None,
    view: Optional[str] = None,
) -> None:
    if style == "none":
        return
    effective_type = _text(resource_type or context.get("resource_type") or default_type)
    for key, value in _resource_query_value(context, resource_type, resource_id, default_type=default_type):
        if style == "resource":
            if key == "scope_type":
                _append_param(query, "resource_type", value)
            elif key == "scope_id":
                _append_param(query, "resource_id", value)
        elif style == "scope":
            _append_param(query, key, value)
        elif style == "gantt_filter":
            if key == "scope_id" and (not view or effective_type == _text(view)):
                _append_param(query, "gantt_resource", value)
        else:
            raise ValueError(f"未知资源上下文格式：{style}")


def _append_target_resource_query(
    query: List[Tuple[str, str]],
    context: Dict[str, Any],
    spec: Dict[str, Any],
    resource_type: Optional[str],
    resource_id: Any,
    view: Optional[str],
) -> None:
    _append_resource_query(
        query,
        context,
        resource_type,
        resource_id,
        style=str(spec["resource_style"]),
        default_type=spec.get("default_resource_type"),
        view=view,
    )


def _append_query_from_spec(
    query: List[Tuple[str, str]],
    context: Dict[str, Any],
    spec: Dict[str, Any],
    *,
    target_page: str,
    view: Optional[str],
    resource_type: Optional[str],
    resource_id: Any,
    batch_value: Any,
) -> None:
    if spec.get("include_gantt_view"):
        _append_param(query, "view", view or "machine")
    _append_target_plan_query(query, context, target_page, str(spec["plan_style"]))
    if spec.get("include_week_start"):
        _append_param(query, "week_start", context.get("date_from"))
    _append_target_date_query(query, context, str(spec["date_style"]))
    if str(spec["date_style"]) != "none":
        _append_period_query(query, context, period_preset=spec.get("period_preset"))
    batch_position = str(spec["batch_position"])
    if batch_position not in ("none", "before_resource", "after_resource"):
        raise ValueError(f"未知批次参数位置：{batch_position}")
    batch_param = str(spec.get("batch_param") or "batch_id")
    if batch_position == "before_resource":
        _append_batch_query(query, batch_value, key=batch_param)
    _append_target_resource_query(query, context, spec, resource_type, resource_id, view)
    if batch_position == "after_resource":
        _append_batch_query(query, batch_value, key=batch_param)


def _append_extra_params(
    query: List[Tuple[str, str]],
    target_page: str,
    extra_params: Optional[Dict[str, Any]],
) -> None:
    for key, value in (extra_params or {}).items():
        if target_page == "execution_review" and _text(key) in _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:
            raise ValueError("计划和现场实际入口不能通过 extra_params 追加方案身份或模拟预览参数。")
        if target_page in _CONTEXT_FREE_TARGETS and _text(key) in _CONTEXT_FREE_TARGET_FORBIDDEN_EXTRA_PARAMS:
            raise ValueError(f"{target_page} 入口不能通过 extra_params 追加工作台上下文参数 {_text(key)}。")
        _append_param(query, key, value)


def _append_return_query(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "back_to", context.get("back_to"))


def query_for_target(
    context: Dict[str, Any],
    target_page: str,
    *,
    view: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Any = None,
    batch_id: Any = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, str]]:
    spec = _target_spec(target_page)
    query: List[Tuple[str, str]] = []
    batch_value = batch_id if _has_value(batch_id) else context.get("batch_id")
    _append_query_from_spec(
        query,
        context,
        spec,
        target_page=target_page,
        view=view,
        resource_type=resource_type,
        resource_id=resource_id,
        batch_value=batch_value,
    )
    _append_extra_params(query, target_page, extra_params)
    _append_return_query(query, context)
    return query


__all__ = [
    "DATE_RANGE_REQUIRED_TARGETS",
    "FULL_PLAN_GUARD_FIELDS",
    "REPORT_PLAN_GUARD_FIELDS",
    "RESOURCE_PLAN_GUARD_FIELDS",
    "TARGET_DEFAULT_LABELS",
    "TARGET_PAGE_PATHS",
    "VERSION_REQUIRED_TARGETS",
    "WORKBENCH_CONTINUATION_TARGETS",
    "ordered_required_params",
    "PLAN_CONTEXT_TOKEN_TARGETS",
    "plan_guard_fields_for_resolution",
    "query_for_target",
    "target_uses_primary_resource_filter",
]
