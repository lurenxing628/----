from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models.operation_execution_labels import suggest_reschedule_label


def positive_row_op_ids(rows: List[Dict[str, Any]]) -> List[int]:
    op_ids = []
    seen = set()
    for row in rows:
        try:
            op_id = int(row.get("op_id") or 0)
        except (TypeError, ValueError):
            op_id = 0
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        op_ids.append(op_id)
    return op_ids


def row_op_id(row: Dict[str, Any]) -> Optional[int]:
    try:
        op_id = int(row.get("op_id") or 0)
    except (TypeError, ValueError):
        return None
    return op_id if op_id > 0 else None


def execution_exception_labels(state: Any, *, has_exception: bool) -> Dict[str, Any]:
    if not has_exception:
        return {
            "latest_exception_reason_label": "暂无异常",
            "latest_exception_severity_label": "",
            "latest_exception_impact_minutes_label": "",
            "latest_exception_affected_machine_id": "",
            "latest_exception_affected_machine_name": "",
            "latest_exception_affected_machine_display_label": "",
            "latest_exception_affected_machine_identity_label": "",
            "latest_exception_affected_machine_label": "",
            "latest_exception_affected_operator_id": "",
            "latest_exception_affected_operator_name": "",
            "latest_exception_affected_operator_display_label": "",
            "latest_exception_affected_operator_identity_label": "",
            "latest_exception_affected_operator_label": "",
            "latest_exception_handling_status_label": "",
            "latest_exception_suggest_reschedule_label": "",
            "latest_exception_remark": "",
        }
    return {
        "latest_exception_reason_label": state.latest_exception_reason_label,
        "latest_exception_severity_label": state.latest_exception_severity_label,
        "latest_exception_impact_minutes_label": state.latest_exception_impact_minutes_label
        or "暂时不知道影响多久",
        "latest_exception_affected_machine_id": state.latest_exception_affected_machine_id or "",
        "latest_exception_affected_machine_name": state.latest_exception_affected_machine_name or "",
        "latest_exception_affected_machine_display_label": state.latest_exception_affected_machine_display_label
        or "未填写影响设备",
        "latest_exception_affected_machine_identity_label": state.latest_exception_affected_machine_identity_label
        or state.latest_exception_affected_machine_label
        or "未填写影响设备",
        "latest_exception_affected_machine_label": state.latest_exception_affected_machine_label or "未填写影响设备",
        "latest_exception_affected_operator_id": state.latest_exception_affected_operator_id or "",
        "latest_exception_affected_operator_name": state.latest_exception_affected_operator_name or "",
        "latest_exception_affected_operator_display_label": state.latest_exception_affected_operator_display_label
        or "未填写影响人员",
        "latest_exception_affected_operator_identity_label": state.latest_exception_affected_operator_identity_label
        or state.latest_exception_affected_operator_label
        or "未填写影响人员",
        "latest_exception_affected_operator_label": state.latest_exception_affected_operator_label or "未填写影响人员",
        "latest_exception_handling_status_label": state.latest_exception_handling_status_label,
        "latest_exception_suggest_reschedule_label": suggest_reschedule_label(state.latest_exception_suggest_reschedule),
        "latest_exception_remark": state.latest_exception_remark,
    }


def apply_execution_state_to_row(row: Dict[str, Any], state: Any) -> None:
    has_exception = bool(state.latest_exception_event_id)
    row["execution_status_label"] = state.current_status_label or "待开工"
    row["actual_machine_id"] = state.actual_machine_id or ""
    row["actual_machine_name"] = state.actual_machine_name or ""
    row["actual_machine_display_label"] = state.actual_machine_display_label or ""
    row["actual_machine_identity_label"] = state.actual_machine_identity_label or state.actual_machine_label or ""
    row["actual_machine_label"] = state.actual_machine_label or ""
    row["actual_operator_id"] = state.actual_operator_id or ""
    row["actual_operator_name"] = state.actual_operator_name or ""
    row["actual_operator_display_label"] = state.actual_operator_display_label or ""
    row["actual_operator_identity_label"] = state.actual_operator_identity_label or state.actual_operator_label or ""
    row["actual_operator_label"] = state.actual_operator_label or ""
    row.update(execution_exception_labels(state, has_exception=has_exception))
