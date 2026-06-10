from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, MutableMapping

from core.models.resource_dispatch_public_labels import lock_status_public_label, source_public_label
from core.models.resource_identity import ResourceIdentity, build_resource_identity

from .scheduler_plan_guardrail_messages import result_status_label, summary_unavailable_guardrail_text

_PERIOD_PRESET_LABELS = {
    "week": "按周",
    "month": "按月",
    "custom": "自定义",
}

_SCOPE_TYPE_LABELS = {
    "operator": "人员",
    "machine": "设备",
    "team": "班组",
}

_TEAM_AXIS_LABELS = {
    "operator": "人员轴",
    "machine": "设备轴",
}

_FILENAME_REPLACEMENTS = (
    ("/", "-"),
    ("\\", "-"),
    (":", "-"),
    ("*", ""),
    ("?", ""),
    ('"', ""),
    ("<", ""),
    (">", ""),
    ("|", "-"),
)

_PUBLIC_FILTER_DROP_KEYS = {
    "source_table",
    "candidate_id",
    "selection_candidate_id",
    "resolved_candidate_id",
    "scenario_id",
    "candidate_key",
    "candidate_kind",
    "candidate_status",
    "detail_saved",
    "plan_role",
    "requested_plan_role",
    "effective_plan_role",
    "plan_role_label",
    "requested_plan_role_label",
    "effective_plan_role_label",
    "plan_role_status",
    "plan_role_message",
    "plan_identity_label",
    "plan_identity_error",
    "plan_identity_blocking_error", "plan_identity_blocking_scope",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
    "schedule_result_status",
    "can_dispatch",
    "can_write_feedback",
    "is_official_plan",
    "is_preview_plan",
    "is_comparison",
    "is_current_executable_version",
    "is_current_executable_official_version",
    "is_superseded_by_newer_version",
    "scenario_name",
}

_PUBLIC_PLAN_ROLE_OPTION_KEYS = {
    "role",
    "label",
    "display_label",
    "display_candidate_label",
    "display_text",
    "is_comparison",
}
_PUBLIC_ROW_DROP_KEYS = {"schedule_id", "op_id", "_row_identity"}

def _text(value: Any) -> str:
    return str(value or "").strip()

def _operation_title(row: MutableMapping[str, Any]) -> str:
    op_code = _text(row.get("op_code"))
    if op_code:
        return op_code
    batch_id = _text(row.get("batch_id"))
    seq = _text(row.get("seq"))
    return " ".join(part for part in (batch_id, f"工序{seq}" if seq else "工序") if part)

def _drop_internal_row_keys(row: MutableMapping[str, Any]) -> None:
    for key in _PUBLIC_ROW_DROP_KEYS:
        row.pop(key, None)

def _safe_filename_part(value: Any) -> str:
    text = _text(value)
    for old, new in _FILENAME_REPLACEMENTS:
        text = text.replace(old, new)
    return "".join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127).strip()

def _scenario_public_label(filters: Dict[str, Any]) -> str:
    return _text(filters.get("scenario_display_name") or filters.get("scenario_name")) or "模拟预览（未命名）"

def _scenario_filename_label(filters: Dict[str, Any]) -> str:
    return _safe_filename_part(_scenario_public_label(filters)) or "模拟预览（未命名）"

def _public_plan_view_label(filters: Dict[str, Any], plan_identity: Dict[str, Any]) -> str:
    if filters.get("is_scenario_preview"):
        return _scenario_public_label(filters)
    has_identity_context = any(
        bool(filters.get(key))
        for key in (
            "plan_identity_label",
            "requested_plan_role_label",
            "effective_plan_role_label",
            "plan_role_label",
            "is_official_plan",
            "is_preview_plan",
            "is_comparison",
        )
    )
    kind_label = _text(plan_identity.get("kind_label"))
    if not has_identity_context and kind_label == "只能查看的方案":
        return ""
    if kind_label == "对比参考方案":
        role_label = _text(filters.get("requested_plan_role_label") or filters.get("effective_plan_role_label"))
        if role_label and role_label not in ("正式采用方案", kind_label):
            return f"{kind_label}-{role_label}"
    if kind_label:
        return kind_label
    return _public_plan_identity_label(filters) or _text(filters.get("effective_plan_role_label") or filters.get("plan_role_label"))

def _plan_view_filename_label(filters: Dict[str, Any]) -> str:
    return _safe_filename_part(filters.get("plan_view_label"))

def _public_plan_identity_label(filters: Dict[str, Any]) -> str:
    if filters.get("is_scenario_preview"):
        return _scenario_public_label(filters)
    if _has_unexecutable_result(filters):
        return "不可执行正式方案"
    return _text(filters.get("plan_identity_label") or filters.get("effective_plan_role_label") or filters.get("plan_role_label"))

def _has_unexecutable_result(filters: Dict[str, Any]) -> bool:
    status = _text(filters.get("schedule_result_status")).lower()
    return bool(filters.get("is_official_plan") and status and status not in ("success", "partial"))

def _official_kind_label(filters: Dict[str, Any]) -> str:
    if filters.get("is_superseded_by_newer_version"):
        return "历史正式方案"
    if _has_unexecutable_result(filters):
        return "只能查看的方案"
    if not (filters.get("plan_identity_blocking_error") or filters.get("result_summary_parse_failed")):
        return "正式采用方案"
    return "只能查看的方案"

def _public_plan_kind_label(filters: Dict[str, Any], *, can_dispatch: bool, can_write_feedback: bool) -> str:
    if filters.get("is_scenario_preview"):
        return "模拟预览"
    if can_dispatch and can_write_feedback:
        return "正式采用方案"
    if filters.get("is_comparison"):
        return "对比参考方案"
    if filters.get("is_official_plan"):
        return _official_kind_label(filters)
    return "只能查看的方案"

def _official_guardrail_text(filters: Dict[str, Any]) -> str:
    if filters.get("is_superseded_by_newer_version"):
        return "这是历史正式方案，只能查看，不能写现场记录。"
    if _has_unexecutable_result(filters):
        status = result_status_label(filters.get("schedule_result_status"))
        return f"这套正式方案的排产结果状态是“{status}”，不能当作当前可执行正式方案写现场记录。"
    return "这套正式方案暂时只能查看，不能写现场记录。"

def _public_plan_guardrail_text(filters: Dict[str, Any], *, can_dispatch: bool, can_write_feedback: bool) -> str:
    if filters.get("is_scenario_preview"):
        return "这是模拟预览，正式计划还没有改变，只能查看，不能写现场记录。"
    if filters.get("plan_identity_blocking_error"):
        return _text(filters.get("plan_identity_error")) or "请求里的方案身份不可用，不能写现场记录。"
    if filters.get("result_summary_parse_failed"):
        return summary_unavailable_guardrail_text(filters.get("result_summary_parse_reason"), blocked_action="不能写现场记录")
    if can_dispatch and can_write_feedback:
        return "这套是当前可执行的正式采用方案，可以查看资源排班，并按规则填写现场实际。"
    if filters.get("is_comparison"):
        return "这是对比参考方案，只用来和正式采用方案比一比，只能查看，不能写现场记录。"
    if filters.get("is_official_plan"):
        return _official_guardrail_text(filters)
    return "当前方案只能查看，不能写现场记录。"

def _public_plan_identity(filters: MutableMapping[str, Any]) -> Dict[str, Any]:
    filters_dict = dict(filters)
    write_blocked = bool(filters_dict.get("plan_identity_blocking_error") or filters_dict.get("result_summary_parse_failed"))
    can_dispatch = bool(filters_dict.get("can_dispatch")) and not write_blocked
    can_write_feedback = bool(filters_dict.get("can_write_feedback")) and not write_blocked
    can_write = can_dispatch and can_write_feedback
    return {
        "label": _public_plan_identity_label(filters_dict) or "正式采用方案",
        "kind_label": _public_plan_kind_label(
            filters_dict,
            can_dispatch=can_dispatch,
            can_write_feedback=can_write_feedback,
        ),
        "dispatch_feedback_label": "可以填写现场实际" if can_write else "只能查看计划和实际",
        "guardrail_text": _public_plan_guardrail_text(
            filters_dict,
            can_dispatch=can_dispatch,
            can_write_feedback=can_write_feedback,
        ),
        "can_dispatch": can_dispatch,
        "can_write_feedback": can_write,
    }

def period_preset_label(value: Any) -> str:
    text = _text(value).lower()
    return _PERIOD_PRESET_LABELS.get(text, _text(value))

def scope_type_label(value: Any) -> str:
    text = _text(value).lower()
    return _SCOPE_TYPE_LABELS.get(text, _text(value))

def team_axis_label(value: Any) -> str:
    text = _text(value).lower()
    return _TEAM_AXIS_LABELS.get(text, _text(value))

def _id_name_label(item: MutableMapping[str, Any]) -> None:
    item_id = _text(item.get("id"))
    name = _text(item.get("name"))
    identity = build_resource_identity(resource_id=item_id, resource_name=name)
    item["display_label"] = identity.display_label
    item["identity_label"] = identity.identity_label
    item["label"] = identity.label

def _decorate_options(context: MutableMapping[str, Any]) -> None:
    for key in ("operator_options", "machine_options", "team_options"):
        items = context.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, MutableMapping):
                _id_name_label(item)

def _decorate_filters(filters: MutableMapping[str, Any]) -> None:
    scope_type = _text(filters.get("scope_type")).lower()
    team_axis = _text(filters.get("team_axis")).lower()
    period_preset = _text(filters.get("period_preset")).lower()
    scope_id = _text(filters.get("scope_id"))
    scope_name = _text(filters.get("scope_name"))

    if scope_type:
        filters["scope_type_label"] = scope_type_label(scope_type)
    if team_axis:
        filters["team_axis_label"] = team_axis_label(team_axis)
    if period_preset:
        filters["period_preset_label"] = period_preset_label(period_preset)
    if scope_id or scope_name:
        identity = build_resource_identity(resource_id=scope_id, resource_name=scope_name)
        filters["scope_display_label"] = identity.display_label
        filters["scope_identity_label"] = identity.identity_label
        filters["scope_label"] = identity.label
    if filters.get("is_scenario_preview"):
        filters["scenario_display_name"] = _scenario_public_label(dict(filters))

def _public_filters(filters: MutableMapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in filters.items() if key not in _PUBLIC_FILTER_DROP_KEYS}

def _public_plan_role_option(option: MutableMapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in option.items() if key in _PUBLIC_PLAN_ROLE_OPTION_KEYS}

def _public_plan_role_options(options: Any) -> List[Dict[str, Any]]:
    if not isinstance(options, list):
        return []
    out: List[Dict[str, Any]] = []
    for option in options:
        if isinstance(option, MutableMapping):
            public_option = _public_plan_role_option(option)
            if public_option.get("role"):
                out.append(public_option)
    return out

def _machine_identity(machine_id: Any, machine_name: Any, supplier_name: Any = None) -> ResourceIdentity:
    machine_id_text = _text(machine_id)
    if machine_id_text:
        return build_resource_identity(resource_id=machine_id_text, resource_name=machine_name)
    supplier_text = _text(supplier_name)
    display = f"外协供应商：{supplier_text}".strip() if supplier_text else "外协未分配"
    return build_resource_identity(display_label=display, identity_label=display)

def _operator_identity(operator_id: Any, operator_name: Any) -> ResourceIdentity:
    operator_id_text = _text(operator_id)
    if not operator_id_text:
        return build_resource_identity(display_label="外协未分配", identity_label="外协未分配")
    return build_resource_identity(resource_id=operator_id_text, resource_name=operator_name)

def _resource_export_fields(row: MutableMapping[str, Any], prefix: str, identity: ResourceIdentity) -> None:
    row[f"{prefix}_display_label"] = identity.display_label
    row[f"{prefix}_identity_label"] = identity.identity_label
    row[f"{prefix}_label"] = identity.label

def _team_relation_label(current_team_id: Any, counterpart_team_id: Any) -> str:
    current = _text(current_team_id)
    counterpart = _text(counterpart_team_id)
    if current and counterpart:
        if current == counterpart:
            return "同班组"
        return "跨班组"
    return "班组归属未维护"

def _current_resource_identity(row: MutableMapping[str, Any]) -> ResourceIdentity:
    scope_type = _text(row.get("scope_type")).lower()
    if scope_type == "operator":
        return _operator_identity(
            row.get("current_resource_id") or row.get("operator_id"),
            row.get("current_resource_name") or row.get("operator_name"),
        )
    return _machine_identity(
        row.get("current_resource_id") or row.get("machine_id"),
        row.get("current_resource_name") or row.get("machine_name"),
        row.get("supplier_name"),
    )

def _counterpart_resource_identity(row: MutableMapping[str, Any]) -> ResourceIdentity:
    scope_type = _text(row.get("scope_type")).lower()
    if scope_type == "operator":
        return _machine_identity(
            row.get("machine_id") or row.get("counterpart_resource_id"),
            row.get("machine_name") or row.get("counterpart_resource_name"),
            row.get("supplier_name"),
        )
    return _operator_identity(
        row.get("operator_id") or row.get("counterpart_resource_id"),
        row.get("operator_name") or row.get("counterpart_resource_name"),
    )

def _decorate_detail_row(row: MutableMapping[str, Any]) -> None:
    scope_type = _text(row.get("scope_type")).lower()
    current_identity = _current_resource_identity(row)
    counterpart_identity = _counterpart_resource_identity(row)
    row["scope_type_label"] = scope_type_label(scope_type)
    row["counterpart_type_label"] = "设备" if scope_type == "operator" else "人员"
    row["scope_label"] = f"{_text(row.get('scope_id'))} {_text(row.get('scope_name'))}".strip()
    row["source_label"] = source_public_label(row.get("source"))
    row["lock_status_label"] = lock_status_public_label(row.get("lock_status"))
    _resource_export_fields(row, "current_resource", current_identity)
    _resource_export_fields(row, "counterpart_resource", counterpart_identity)
    row["team_relation_label"] = _team_relation_label(row.get("current_team_id"), row.get("counterpart_team_id"))
    _drop_internal_row_keys(row)

def _decorate_detail_rows(rows: Any) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if isinstance(row, MutableMapping):
            _decorate_detail_row(row)

def _calendar_item_text(item: MutableMapping[str, Any]) -> str:
    time_label = _text(item.get("time_label"))
    if not time_label:
        legacy_text = _text(item.get("text"))
        if legacy_text:
            return legacy_text
    parts: List[str] = [time_label]
    title = _operation_title(item)
    if title:
        parts.append(title)
    counterpart = _text(item.get("counterpart_resource_display_label") or item.get("counterpart_resource_label"))
    if counterpart:
        parts.append(counterpart)
    part_no = _text(item.get("part_no"))
    if part_no:
        parts.append(part_no)
    return " ".join(part for part in parts if part)

def _decorate_calendar_item(item: MutableMapping[str, Any]) -> None:
    counterpart_identity = _counterpart_resource_identity(item)
    _resource_export_fields(item, "counterpart_resource", counterpart_identity)
    item["text"] = _calendar_item_text(item)
    _drop_internal_row_keys(item)

def _decorate_calendar_row(row: MutableMapping[str, Any]) -> None:
    scope_type = _text(row.get("scope_type")).lower()
    current_identity = _current_resource_identity(row)
    row["scope_type_label"] = scope_type_label(scope_type)
    _resource_export_fields(row, "current_resource", current_identity)
    row["scope_label"] = _text(row.get("current_resource_label")) or f"{_text(row.get('scope_id'))} {_text(row.get('scope_name'))}".strip()
    row["scope_display_label"] = _text(row.get("current_resource_display_label")) or row["scope_label"]
    row["scope_identity_label"] = _text(row.get("current_resource_identity_label")) or row["scope_label"]
    cells = row.get("cells")
    if not isinstance(cells, list):
        return
    for cell in cells:
        if not isinstance(cell, MutableMapping):
            continue
        items = cell.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, MutableMapping):
                    _decorate_calendar_item(item)
            cell["text"] = "\n".join(_text(item.get("text")) for item in items if isinstance(item, MutableMapping))

def _decorate_calendar_rows(rows: Any) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if isinstance(row, MutableMapping):
            _decorate_calendar_row(row)

def _decorate_task(task: MutableMapping[str, Any]) -> None:
    meta = task.get("meta")
    if isinstance(meta, MutableMapping):
        _decorate_detail_row(meta)
        task_id = _text(task.get("id"))
        title = _operation_title(meta) or _text(task.get("name")) or task_id
        counterpart = _text(meta.get("counterpart_resource_display_label") or meta.get("counterpart_resource_label"))
    else:
        title = _text(task.get("name")) or _text(task.get("id"))
        counterpart = ""
    task["name"] = f"{title} {counterpart}".strip()
    _drop_internal_row_keys(task)

def _decorate_tasks(tasks: Any) -> None:
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if isinstance(task, MutableMapping):
            _decorate_task(task)

def _row_collection_names() -> Iterable[str]:
    return ("detail_rows", "operator_rows", "machine_rows", "cross_team_rows")

def _calendar_collection_names() -> Iterable[str]:
    return ("calendar_rows", "operator_calendar_rows", "machine_calendar_rows")

def decorate_resource_dispatch_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(payload)
    filters = out.get("filters")
    if isinstance(filters, MutableMapping):
        _decorate_filters(filters)
        plan_identity = _public_plan_identity(filters)
        filters["plan_view_label"] = _public_plan_view_label(dict(filters), plan_identity)
        out["plan_identity"] = plan_identity
        out["filters"] = _public_filters(filters)
    out["plan_role_options"] = _public_plan_role_options(out.get("plan_role_options"))
    for key in _row_collection_names():
        _decorate_detail_rows(out.get(key))
    _decorate_tasks(out.get("tasks"))
    for key in _calendar_collection_names():
        _decorate_calendar_rows(out.get(key))
    return out

def decorate_resource_dispatch_context(context: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(context)
    filters = out.get("filters")
    if isinstance(filters, MutableMapping):
        _decorate_filters(filters)
        plan_identity = _public_plan_identity(filters)
        filters["plan_view_label"] = _public_plan_view_label(dict(filters), plan_identity)
        out["plan_identity"] = plan_identity
        out["client_filters"] = _public_filters(filters)
    out["plan_role_options"] = _public_plan_role_options(out.get("plan_role_options"))
    _decorate_options(out)
    return out

def build_resource_dispatch_filename(payload: Dict[str, Any]) -> str:
    filters = payload.get("filters") or {}
    filename = "资源排班"
    scope_type_text = _safe_filename_part(filters.get("scope_type_label"))
    if scope_type_text:
        filename += f"_{scope_type_text}"
    scope_id = _safe_filename_part(filters.get("scope_id"))
    if scope_id:
        filename += f"_{scope_id}"
    if _text(filters.get("scope_type")) == "team" and _text(filters.get("team_axis")):
        team_axis_text = _safe_filename_part(filters.get("team_axis_label")) or _safe_filename_part(
            team_axis_label(filters.get("team_axis"))
        )
        filename += f"_{team_axis_text}"
    if _text(filters.get("start_date")) and _text(filters.get("end_date")):
        filename += f"_{_safe_filename_part(filters.get('start_date'))}_{_safe_filename_part(filters.get('end_date'))}"
    if _text(filters.get("version")):
        filename += f"_v{_safe_filename_part(filters.get('version'))}"
    plan_view_label = _plan_view_filename_label(filters)
    if plan_view_label:
        filename += f"_{plan_view_label}"
    return f"{filename}.xlsx"
