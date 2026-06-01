from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS = {
    "plan_role",
    "requested_plan_role",
    "effective_plan_role",
    "scenario_id",
    "is_preview",
    "is_scenario_preview",
    "is_comparison",
    "is_superseded_by_newer_version",
    "can_dispatch",
    "can_write_feedback",
}

_TARGET_QUERY_SPECS: Dict[str, Dict[str, Any]] = {
    "dashboard": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "analysis": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "gantt": {
        "plan_style": "standard",
        "date_style": "start_end",
        "batch_position": "before_resource",
        "resource_style": "resource",
        "include_gantt_view": True,
    },
    "week_plan": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
        "include_week_start": True,
    },
    "resource_dispatch": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "after_resource",
        "resource_style": "scope",
        "default_resource_type": "operator",
    },
    "overdue_report": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "delay_diagnosis": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "utilization_report": {
        "plan_style": "standard",
        "date_style": "start_end",
        "batch_position": "before_resource",
        "resource_style": "scope",
    },
    "execution_review": {
        "plan_style": "execution_review",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "scope",
    },
    "reports_index": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "scope",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    return value is not None and _text(value) != ""


def _append_param(query: List[Tuple[str, str]], key: str, value: Any) -> None:
    if _has_value(value):
        query.append((key, _text(value)))


def _append_date_range_as_start_end(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "start_date", context.get("date_from"))
    _append_param(query, "end_date", context.get("date_to"))


def _append_date_range_as_date_from_to(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "date_from", context.get("date_from"))
    _append_param(query, "date_to", context.get("date_to"))


def _append_plan_query(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "version", context.get("version"))
    _append_param(query, "plan_role", context.get("plan_role"))
    _append_param(query, "scenario_id", context.get("scenario_id"))


def _append_period_query(query: List[Tuple[str, str]], context: Dict[str, Any]) -> None:
    _append_param(query, "query_date", context.get("query_date"))
    _append_param(query, "period_preset", context.get("period_preset"))


def _append_batch_query(query: List[Tuple[str, str]], batch_value: Any) -> None:
    _append_param(query, "batch_id", batch_value)


def ordered_required_params(query: Iterable[Tuple[str, str]]) -> List[str]:
    out: List[str] = []
    for key, _value in query:
        if key not in out:
            out.append(key)
    return out


def _append_target_plan_query(query: List[Tuple[str, str]], context: Dict[str, Any], plan_style: str) -> None:
    if plan_style == "execution_review":
        _append_param(query, "version", context.get("version"))
        _append_param(query, "plan_role", context.get("plan_role"))
        return
    _append_plan_query(query, context)


def _append_target_date_query(query: List[Tuple[str, str]], context: Dict[str, Any], date_style: str) -> None:
    if date_style == "start_end":
        _append_date_range_as_start_end(query, context)
        return
    _append_date_range_as_date_from_to(query, context)


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
) -> None:
    for key, value in _resource_query_value(context, resource_type, resource_id, default_type=default_type):
        if style == "resource":
            if key == "scope_type":
                _append_param(query, "resource_type", value)
            elif key == "scope_id":
                _append_param(query, "resource_id", value)
        elif style == "scope":
            _append_param(query, key, value)
        else:
            raise ValueError(f"未知资源上下文格式：{style}")


def _append_target_resource_query(
    query: List[Tuple[str, str]],
    context: Dict[str, Any],
    spec: Dict[str, Any],
    resource_type: Optional[str],
    resource_id: Any,
) -> None:
    _append_resource_query(
        query,
        context,
        resource_type,
        resource_id,
        style=str(spec["resource_style"]),
        default_type=spec.get("default_resource_type"),
    )


def _append_query_from_spec(
    query: List[Tuple[str, str]],
    context: Dict[str, Any],
    spec: Dict[str, Any],
    *,
    view: Optional[str],
    resource_type: Optional[str],
    resource_id: Any,
    batch_value: Any,
) -> None:
    if spec.get("include_gantt_view"):
        _append_param(query, "view", view or "machine")
    _append_target_plan_query(query, context, str(spec["plan_style"]))
    if spec.get("include_week_start"):
        _append_param(query, "week_start", context.get("date_from"))
    _append_target_date_query(query, context, str(spec["date_style"]))
    _append_period_query(query, context)
    if spec["batch_position"] == "before_resource":
        _append_batch_query(query, batch_value)
    _append_target_resource_query(query, context, spec, resource_type, resource_id)
    if spec["batch_position"] == "after_resource":
        _append_batch_query(query, batch_value)


def _append_extra_params(
    query: List[Tuple[str, str]],
    target_page: str,
    extra_params: Optional[Dict[str, Any]],
) -> None:
    for key, value in (extra_params or {}).items():
        if target_page == "execution_review" and _text(key) in _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:
            raise ValueError("计划和现场实际入口不能通过 extra_params 追加方案身份或模拟预览参数。")
        _append_param(query, key, value)


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
    spec = _TARGET_QUERY_SPECS.get(target_page)
    if spec is None:
        raise ValueError(f"未知工作台目标页：{target_page}")
    query: List[Tuple[str, str]] = []
    batch_value = batch_id if _has_value(batch_id) else context.get("batch_id")
    _append_query_from_spec(
        query,
        context,
        spec,
        view=view,
        resource_type=resource_type,
        resource_id=resource_id,
        batch_value=batch_value,
    )
    _append_extra_params(query, target_page, extra_params)
    return query


__all__ = ["ordered_required_params", "query_for_target"]
