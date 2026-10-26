"""Planned labels of one report row (``WorkbenchReportFactsRepository.plan_rows``) for screen and exports.

Rows come from ``Schedule s LEFT JOIN BatchOperations bo``: ``Schedule.op_id`` is a NOT NULL foreign key
(enforced on every connection), so ``bo.op_code`` / ``bo.op_type_name`` / ``bo.batch_id`` are present
NOT NULL text; legacy rows may still hold blank text. Planned machine and operator are nullable.
"""

from typing import Any, Dict

from core.models.resource_identity import resource_display_label


def _operation_label(row: Dict[str, Any]) -> str:
    op_name = row["op_type_name"].strip()
    op_code = row["op_code"].strip()
    if op_name and op_code:
        return f"{op_code} / {op_name}"
    return op_name or op_code or "未命名工序"


def resource_pair_label(machine_display: str, operator_display: str, *, empty_label: str) -> str:
    if machine_display and operator_display:
        return f"{machine_display} / {operator_display}"
    if machine_display:
        return f"{machine_display} / 未安排人员"
    if operator_display:
        return f"未安排设备 / {operator_display}"
    return empty_label


def planned_review_labels(row: Dict[str, Any]) -> Dict[str, Any]:
    """Render only planned facts; actual labels come from the relevant ledger."""
    machine = resource_display_label(row["machine_id"], row["machine_name"])
    operator = resource_display_label(row["operator_id"], row["operator_name"])
    return {
        "batch_id_label": row["batch_id"],
        "operation_label": _operation_label(row),
        # Schedule.start_time/end_time 是 NOT NULL 的 ISO 文本，屏幕与导出用同一原文。
        "planned_start_time_label": row["start_time"],
        "planned_end_time_label": row["end_time"],
        "planned_resource_label": resource_pair_label(machine, operator, empty_label="未安排计划资源"),
    }
