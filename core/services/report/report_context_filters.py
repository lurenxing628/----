from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.models.schedule_resource_filter import (
    SUPPORTED_SCHEDULE_RESOURCE_TYPES,
    normalize_schedule_resource_filter,
)

from .calculation_helpers import overlap_seconds, parse_dt

SUPPORTED_REPORT_RESOURCE_TYPES = SUPPORTED_SCHEDULE_RESOURCE_TYPES


def _report_resource_validation_messages() -> Dict[str, Any]:
    return {
        "missing_type_message": "资源筛选缺少资源类型，请重新从设备或人员入口进入报表。",
        "unsupported_message": lambda kind: f"当前报表暂不支持{'班组' if kind == 'team' else kind}维度筛选，请切换到设备或人员后再查看。",
        "missing_id_message": lambda kind: (
            "资源筛选类型是设备，但缺少设备编号，请重新从设备入口进入报表。"
            if kind == "machine"
            else "资源筛选类型是人员，但缺少人员编号，请重新从人员入口进入报表。"
        ),
    }


def _raise_resource_conflict(message: str, *, field: str, details: Dict[str, str]) -> None:
    raise ValidationError(message, field=field, details=details)


def _merge_primary_and_scope_aliases(
    resource_type_text: str,
    resource_id_text: str,
    scope_type_text: str,
    scope_id_text: str,
) -> Tuple[str, str]:
    if resource_type_text and scope_type_text and resource_type_text != scope_type_text:
        _raise_resource_conflict(
            "资源筛选类型冲突，请只保留一个资源维度后再查看报表。",
            field="resource_type",
            details={"resource_type": resource_type_text, "scope_type": scope_type_text},
        )
    if resource_id_text and scope_id_text and resource_id_text != scope_id_text:
        _raise_resource_conflict(
            "资源筛选编号冲突，请只保留一个资源编号后再查看报表。",
            field="resource_id",
            details={"resource_id": resource_id_text, "scope_id": scope_id_text},
        )
    return resource_type_text or scope_type_text, resource_id_text or scope_id_text


def _infer_single_resource_alias(
    resource_type_text: str,
    resource_id_text: str,
    machine_id_text: str,
    operator_id_text: str,
) -> Tuple[str, str]:
    if resource_type_text or resource_id_text:
        return resource_type_text, resource_id_text
    if machine_id_text and operator_id_text:
        _raise_resource_conflict(
            "资源筛选同时包含设备和人员，请只保留一个资源维度后再查看报表。",
            field="resource_type",
            details={"machine_id": machine_id_text, "operator_id": operator_id_text},
        )
    if machine_id_text:
        return "machine", machine_id_text
    if operator_id_text:
        return "operator", operator_id_text
    return "", ""


def _merge_machine_alias(resource_id_text: str, machine_id_text: str, operator_id_text: str) -> str:
    if operator_id_text:
        _raise_resource_conflict(
            "资源筛选类型是设备，但同时收到了人员编号，请重新从设备入口进入报表。",
            field="resource_id",
            details={"resource_type": "machine", "operator_id": operator_id_text},
        )
    if resource_id_text and machine_id_text and resource_id_text != machine_id_text:
        _raise_resource_conflict(
            "资源筛选设备编号冲突，请只保留一个设备编号后再查看报表。",
            field="resource_id",
            details={"resource_type": "machine", "resource_id": resource_id_text, "machine_id": machine_id_text},
        )
    return resource_id_text or machine_id_text


def _merge_operator_alias(resource_id_text: str, machine_id_text: str, operator_id_text: str) -> str:
    if machine_id_text:
        _raise_resource_conflict(
            "资源筛选类型是人员，但同时收到了设备编号，请重新从人员入口进入报表。",
            field="resource_id",
            details={"resource_type": "operator", "machine_id": machine_id_text},
        )
    if resource_id_text and operator_id_text and resource_id_text != operator_id_text:
        _raise_resource_conflict(
            "资源筛选人员编号冲突，请只保留一个人员编号后再查看报表。",
            field="resource_id",
            details={"resource_type": "operator", "resource_id": resource_id_text, "operator_id": operator_id_text},
        )
    return resource_id_text or operator_id_text


def _merge_resource_specific_aliases(
    resource_type_text: str,
    resource_id_text: str,
    machine_id_text: str,
    operator_id_text: str,
) -> str:
    if resource_type_text == "machine":
        return _merge_machine_alias(resource_id_text, machine_id_text, operator_id_text)
    if resource_type_text == "operator":
        return _merge_operator_alias(resource_id_text, machine_id_text, operator_id_text)
    return resource_id_text


def normalize_report_resource_filter(
    resource_type: Any = None,
    resource_id: Any = None,
    *,
    scope_type: Any = None,
    scope_id: Any = None,
    machine_id: Any = None,
    operator_id: Any = None,
) -> Tuple[str, str]:
    resource_type_text, resource_id_text = _merge_primary_and_scope_aliases(
        str(resource_type or "").strip().lower(),
        str(resource_id or "").strip(),
        str(scope_type or "").strip().lower(),
        str(scope_id or "").strip(),
    )
    machine_id_text = str(machine_id or "").strip()
    operator_id_text = str(operator_id or "").strip()
    resource_type_text, resource_id_text = _infer_single_resource_alias(
        resource_type_text,
        resource_id_text,
        machine_id_text,
        operator_id_text,
    )
    resource_id_text = _merge_resource_specific_aliases(
        resource_type_text,
        resource_id_text,
        machine_id_text,
        operator_id_text,
    )
    resource_filter = normalize_schedule_resource_filter(
        resource_type_text,
        resource_id_text,
        **_report_resource_validation_messages(),
    )
    return resource_filter.resource_type, resource_filter.resource_id


def _row_text(row: Dict[str, Any], key: str) -> str:
    return str((row or {}).get(key) or "").strip()


def _plan_row_matches_batch(row: Dict[str, Any], batch_filter: str) -> bool:
    return not batch_filter or _row_text(row, "batch_id") == batch_filter


def _plan_row_matches_resource(row: Dict[str, Any], resource_type: str, resource_id: str) -> bool:
    if not resource_type or not resource_id:
        return True
    key_by_type = {"machine": "machine_id", "operator": "operator_id"}
    row_key = key_by_type.get(resource_type)
    return bool(row_key) and _row_text(row, row_key) == resource_id


def filter_plan_rows_for_report_context(
    rows: Iterable[Dict[str, Any]],
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    batch_filter = str(batch_id or "").strip()
    resource_type_text, resource_id_text = normalize_report_resource_filter(resource_type, resource_id)
    out = []
    for row in rows or []:
        item = dict(row or {})
        if _plan_row_matches_batch(item, batch_filter):
            if _plan_row_matches_resource(item, resource_type_text, resource_id_text):
                out.append(item)
    return out


def _schedule_machine_ids(schedule_rows: Iterable[Dict[str, Any]]) -> set:
    return {_row_text(row, "machine_id") for row in schedule_rows or [] if _row_text(row, "machine_id")}


def _downtime_machine_filter(
    schedule_rows: Iterable[Dict[str, Any]],
    *,
    resource_type: str,
    resource_id: str,
    batch_filter: str,
) -> Optional[set]:
    if resource_type == "machine" and resource_id and not batch_filter:
        return {resource_id}
    if batch_filter:
        return _schedule_machine_ids(schedule_rows)
    if resource_type == "operator" and resource_id:
        return _schedule_machine_ids(schedule_rows)
    return None


def _filter_downtime_rows_by_machine(
    downtime_rows: Iterable[Dict[str, Any]],
    allowed_machine_ids: Optional[set],
) -> List[Dict[str, Any]]:
    if allowed_machine_ids is None:
        return [dict(row or {}) for row in downtime_rows or []]
    if not allowed_machine_ids:
        return []
    return [
        dict(row or {})
        for row in downtime_rows or []
        if _row_text(row, "machine_id") in allowed_machine_ids
    ]


def _parsed_interval(row: Dict[str, Any]) -> Optional[Tuple[Any, Any]]:
    start = parse_dt((row or {}).get("start_time"))
    end = parse_dt((row or {}).get("end_time"))
    if not start or not end:
        return None
    return start, end


def _schedule_overlaps_downtime(
    schedule_row: Dict[str, Any],
    *,
    machine_id: str,
    downtime_interval: Tuple[Any, Any],
) -> bool:
    if _row_text(schedule_row, "machine_id") != machine_id:
        return False
    schedule_interval = _parsed_interval(schedule_row)
    if schedule_interval is None:
        return False
    downtime_start, downtime_end = downtime_interval
    schedule_start, schedule_end = schedule_interval
    return overlap_seconds(downtime_start, downtime_end, schedule_start, schedule_end) > 0


def _downtime_row_overlaps_schedule(
    downtime_row: Dict[str, Any],
    schedule_rows: Iterable[Dict[str, Any]],
) -> bool:
    machine_id = _row_text(downtime_row, "machine_id")
    downtime_interval = _parsed_interval(downtime_row)
    if not machine_id or downtime_interval is None:
        return False
    return any(
        _schedule_overlaps_downtime(row, machine_id=machine_id, downtime_interval=downtime_interval)
        for row in schedule_rows or []
    )


def _filter_downtime_rows_by_batch_overlap(
    downtime_rows: Iterable[Dict[str, Any]],
    schedule_rows: Iterable[Dict[str, Any]],
    *,
    batch_filter: str,
) -> List[Dict[str, Any]]:
    if not batch_filter:
        return list(downtime_rows or [])
    return [row for row in downtime_rows or [] if _downtime_row_overlaps_schedule(row, schedule_rows)]


def filter_downtime_rows_for_report_context(
    downtime_rows: Iterable[Dict[str, Any]],
    schedule_rows: Iterable[Dict[str, Any]],
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    resource_type_text, resource_id_text = normalize_report_resource_filter(resource_type, resource_id)
    batch_filter = str(batch_id or "").strip()
    filtered_rows = _filter_downtime_rows_by_machine(
        downtime_rows,
        _downtime_machine_filter(
            schedule_rows,
            resource_type=resource_type_text,
            resource_id=resource_id_text,
            batch_filter=batch_filter,
        ),
    )
    return _filter_downtime_rows_by_batch_overlap(filtered_rows, schedule_rows, batch_filter=batch_filter)
