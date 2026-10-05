"""Plan labels shared by execution feedback, ledger review and XLSX exports."""

from typing import Any, Dict

from core.models.resource_identity import ResourceIdentity, build_resource_identity


def _display_time(value: Any) -> str:
    # Keep the same ISO text on screen and in exports.
    text = str(value or "").strip()
    return text or "未填写计划时间"


def _operation_label(row: Dict[str, Any]) -> str:
    op_name = str(row.get("op_type_name") or "").strip()
    op_code = str(row.get("op_code") or "").strip()
    if op_name and op_code:
        return f"{op_code} / {op_name}"
    return op_name or op_code or "未命名工序"


def resource_pair_label(machine: ResourceIdentity, operator: ResourceIdentity, *, empty_label: str) -> str:
    machine_display = machine.display_label
    operator_display = operator.display_label
    if machine_display and operator_display:
        return f"{machine_display} / {operator_display}"
    if machine_display:
        return f"{machine_display} / 未安排人员"
    if operator_display:
        return f"未安排设备 / {operator_display}"
    return empty_label


def planned_review_labels(row: Dict[str, Any]) -> Dict[str, Any]:
    """Render only planned facts; actual labels come from the relevant ledger."""
    machine = build_resource_identity(row.get("machine_id"), row.get("machine_name"))
    operator = build_resource_identity(row.get("operator_id"), row.get("operator_name"))
    return {
        "batch_id_label": str(row.get("batch_id") or ""),
        "operation_label": _operation_label(row),
        "planned_start_time_label": _display_time(row.get("start_time")),
        "planned_end_time_label": _display_time(row.get("end_time")),
        "planned_resource_label": resource_pair_label(machine, operator, empty_label="未安排计划资源"),
        "planned_machine_id": str(row.get("machine_id") or ""),
        "planned_machine_name": str(row.get("machine_name") or ""),
        "planned_operator_id": str(row.get("operator_id") or ""),
        "planned_operator_name": str(row.get("operator_name") or ""),
    }
