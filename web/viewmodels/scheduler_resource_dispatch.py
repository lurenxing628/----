from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, MutableMapping

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


def _text(value: Any) -> str:
    return str(value or "").strip()


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
    item["label"] = f"{item_id} {name}".strip()


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
        filters["scope_label"] = f"{scope_id} {scope_name}".strip()


def _display_machine(machine_id: Any, machine_name: Any, supplier_name: Any = None) -> str:
    machine_id_text = _text(machine_id)
    if machine_id_text:
        return f"{machine_id_text} {_text(machine_name)}".strip()
    supplier_text = _text(supplier_name)
    return f"外协供应商：{supplier_text}".strip() if supplier_text else "外协未分配"


def _display_operator(operator_id: Any, operator_name: Any) -> str:
    operator_id_text = _text(operator_id)
    if not operator_id_text:
        return "外协未分配"
    return f"{operator_id_text} {_text(operator_name)}".strip()


def _team_relation_label(current_team_id: Any, counterpart_team_id: Any) -> str:
    current = _text(current_team_id)
    counterpart = _text(counterpart_team_id)
    if current and counterpart:
        if current == counterpart:
            return "同班组"
        return "跨班组"
    return "班组归属未维护"


def _current_resource_label(row: MutableMapping[str, Any]) -> str:
    scope_type = _text(row.get("scope_type")).lower()
    if scope_type == "operator":
        return _display_operator(row.get("current_resource_id") or row.get("operator_id"), row.get("current_resource_name") or row.get("operator_name"))
    return _display_machine(
        row.get("current_resource_id") or row.get("machine_id"),
        row.get("current_resource_name") or row.get("machine_name"),
        row.get("supplier_name"),
    )


def _counterpart_resource_label(row: MutableMapping[str, Any]) -> str:
    scope_type = _text(row.get("scope_type")).lower()
    if scope_type == "operator":
        return _display_machine(
            row.get("machine_id") or row.get("counterpart_resource_id"),
            row.get("machine_name") or row.get("counterpart_resource_name"),
            row.get("supplier_name"),
        )
    return _display_operator(
        row.get("operator_id") or row.get("counterpart_resource_id"),
        row.get("operator_name") or row.get("counterpart_resource_name"),
    )


def _decorate_detail_row(row: MutableMapping[str, Any]) -> None:
    scope_type = _text(row.get("scope_type")).lower()
    row["scope_type_label"] = scope_type_label(scope_type)
    row["counterpart_type_label"] = "设备" if scope_type == "operator" else "人员"
    row["scope_label"] = f"{_text(row.get('scope_id'))} {_text(row.get('scope_name'))}".strip()
    row["current_resource_label"] = _current_resource_label(row)
    row["counterpart_resource_label"] = _counterpart_resource_label(row)
    row["team_relation_label"] = _team_relation_label(row.get("current_team_id"), row.get("counterpart_team_id"))


def _decorate_detail_rows(rows: Any) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if isinstance(row, MutableMapping):
            _decorate_detail_row(row)


def _hhmm(value: Any) -> str:
    text = _text(value)
    if len(text) >= 16 and text[10] in (" ", "T"):
        return text[11:16]
    return text


def _calendar_item_text(item: MutableMapping[str, Any]) -> str:
    parts: List[str] = []
    start = _hhmm(item.get("start"))
    end = _hhmm(item.get("end"))
    if start or end:
        parts.append(f"{start}-{end}".strip("-"))
    title = _text(item.get("op_code")) or _text(item.get("batch_id"))
    if title:
        parts.append(title)
    counterpart = _text(item.get("counterpart_resource_label"))
    if counterpart:
        parts.append(counterpart)
    part_no = _text(item.get("part_no"))
    if part_no:
        parts.append(part_no)
    return " ".join(part for part in parts if part)


def _decorate_calendar_item(item: MutableMapping[str, Any]) -> None:
    item["counterpart_resource_label"] = _counterpart_resource_label(item)
    item["text"] = _calendar_item_text(item)


def _decorate_calendar_row(row: MutableMapping[str, Any]) -> None:
    scope_type = _text(row.get("scope_type")).lower()
    row["scope_type_label"] = scope_type_label(scope_type)
    row["current_resource_label"] = _current_resource_label(row)
    row["scope_label"] = _text(row.get("current_resource_label")) or f"{_text(row.get('scope_id'))} {_text(row.get('scope_name'))}".strip()
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
        title = _text(meta.get("op_code")) or _text(task.get("name")) or task_id
        counterpart = _text(meta.get("counterpart_resource_label"))
    else:
        title = _text(task.get("name")) or _text(task.get("id"))
        counterpart = ""
    task["name"] = f"{title} {counterpart}".strip()


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
    _decorate_options(out)
    return out


def build_resource_dispatch_filename(payload: Dict[str, Any]) -> str:
    filters = payload.get("filters") or {}
    filename = "资源排班"
    scope_type_text = _text(filters.get("scope_type_label"))
    if scope_type_text:
        filename += f"_{scope_type_text}"
    scope_id = _text(filters.get("scope_id"))
    if scope_id:
        filename += f"_{scope_id}"
    if _text(filters.get("scope_type")) == "team" and _text(filters.get("team_axis")):
        team_axis_text = _text(filters.get("team_axis_label")) or team_axis_label(filters.get("team_axis"))
        filename += f"_{team_axis_text}"
    if _text(filters.get("start_date")) and _text(filters.get("end_date")):
        filename += f"_{_text(filters.get('start_date'))}_{_text(filters.get('end_date'))}"
    if _text(filters.get("version")):
        filename += f"_v{_text(filters.get('version'))}"
    return f"{filename}.xlsx"
