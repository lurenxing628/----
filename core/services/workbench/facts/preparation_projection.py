"""The saved standard requirement, its actual allocation and coverage summaries."""

from typing import Any, Dict

from core.models.enums import OperationRequirementRole, SourceType

PREPARATION_METRIC_VERSION = "decision-preparation-v4"
PREPARATION_METRICS = (
    ("pending_setup_hours", "本次准备标准工时需求", "setup_standard_hours", "pending", False),
    ("scheduled_setup_hours", "新安排准备标准工时", "setup_standard_hours", "scheduled", True),
    ("unplanned_setup_hours", "其他未安排准备标准工时", "setup_standard_hours", "unplanned", False),
    ("deferred_setup_hours", "缺料未安排准备标准工时", "setup_standard_hours", "deferred", False),
    ("pending_processing_hours", "本次加工标准工时需求", "processing_standard_hours", "pending", False),
    ("scheduled_processing_hours", "新安排加工标准工时", "processing_standard_hours", "scheduled", False),
    ("unplanned_processing_hours", "其他未安排加工标准工时", "processing_standard_hours", "unplanned", False),
    ("deferred_processing_hours", "缺料未安排加工标准工时", "processing_standard_hours", "deferred", False),
)
_FIELDS = ("source", "quantity_basis", "target_quantity", "execution_quantity_basis", "execution_target_quantity", "remaining_quantity",
           "setup_standard_hours", "processing_standard_hours", "required_standard_hours", "setup_state", "requirement_role",
           "external_cycle_days", "external_group_id", "external_merge_mode", "effort_basis")
ALLOCATIONS = ("new_schedule", "unplanned", "deferred", "retained", "execution", "completed", "external", "unknown")
_GROUPS = {"pending": ("new_schedule", "unplanned", "deferred", "unknown"), "scheduled": ("new_schedule", "unknown"),
           "unplanned": ("unplanned",), "deferred": ("deferred",)}
_ROLES = (OperationRequirementRole.RETAINED.value, OperationRequirementRole.EXECUTION.value, OperationRequirementRole.COMPLETED.value)


def project_operation_effort(runtime, standard, *, allocation_state, source_available=True, source=None,
                             execution, evidence_source=None) -> Dict[str, Any]:
    """The old standard remains visible without inventing a runtime split.

    execution is the operation's captured execution row, or {} when none was captured.
    """
    standard = standard or {"basis": "archived_operation_standard", "setup_standard_hours": None, "unit_standard_hours": None,
                            "target_quantity": None, "remaining_quantity": None, "standard_total_hours": None, "state": "unavailable",
                            "reason": {"code": "standard_effort_missing", "message": "此来源未保存可核对的工序标准。"}}
    result: Dict[str, Any]
    if runtime is None:
        result = {field: None for field in _FIELDS}
        completed = source_available and execution.get("execution_state") == "complete"
        result.update(source=source, quantity_basis="unknown", execution_quantity_basis=execution.get("target_basis", "unknown"),
                      execution_target_quantity=execution.get("target_quantity"), remaining_quantity=execution.get("remaining_quantity"),
                      setup_state="already_completed" if completed else "unknown", requirement_role="completed" if completed else "unknown", state="unavailable",
                      data_gaps=[{"field": "runtime_requirement", "code": "runtime_requirement_missing" if source_available else "reference_required",
                                  "message": "这条记录未分别保存准备和加工所需的标准工时。" if source_available else "此比较没有可用的基准安排。"}])
    else:
        result = {field: runtime.get(field) for field in _FIELDS}
        result.update(execution_quantity_basis=execution.get("target_basis", "unknown"),
                      execution_target_quantity=execution.get("target_quantity"), remaining_quantity=execution.get("remaining_quantity"))
        result["data_gaps"] = list(runtime.get("data_gaps", []))
        unknown = sum(result[field] is None for field in ("setup_standard_hours", "processing_standard_hours", "required_standard_hours"))
        result["state"] = ("not_applicable" if result["source"] == SourceType.EXTERNAL.value else
                           "unavailable" if unknown == 3 else "partial" if unknown else "complete")
    if runtime is None and result["requirement_role"] == OperationRequirementRole.COMPLETED.value and allocation_state == "unknown":
        allocation_state = OperationRequirementRole.COMPLETED.value
    result.update(allocation_state=allocation_state, evidence_source=evidence_source, standard=standard)
    return result


def metric_summary(rows, field, *, available=True):
    known = [row for row in rows if row.get(field) is not None]
    subtotal = sum(row[field] for row in known)
    total, unknown = len(rows), len(rows) - len(known)
    state = ("unavailable" if not available or unknown == total and unknown else
             "partial" if unknown else "not_applicable" if not rows else "complete")
    reason = ({"code": "reference_required", "message": "此比较没有可用的基准需求。"} if not available else
              {"code": "runtime_requirement_missing", "message": "部分工序未分别保存准备和加工所需的标准工时；已保存的工时与原工时定额分别列出。"} if unknown else None)
    return {"value": None if unknown or not available else subtotal,
            "known_subtotal": subtotal if available else None, "state": state,
            "known_count": len(known) if available else 0, "unknown_count": unknown if available else total, "total_count": total,
            "scope": "full_admission", "metric_version": PREPARATION_METRIC_VERSION, "reason": reason,
            "covered_operation_refs": sorted(row["operation_ref"] for row in known) if available else []}


def preparation_summary(rows, *, available=True, requirements_available=None):
    """Each internal permanent operation belongs to one actual allocation group."""
    internal = [row for row in rows if row.get("source") != SourceType.EXTERNAL.value]
    requirements_available = available if requirements_available is None else requirements_available
    by_allocation = {name: [row for row in internal if row["allocation_state"] == name] for name in ALLOCATIONS}
    selected_by_group = {}
    for group, allocations in _GROUPS.items():
        if not available and group in ("scheduled", "unplanned"):
            selected_by_group[group] = [row for row in internal if row.get("requirement_role") in ("new_schedule", "unknown")]
        else:
            selected = [row for name in allocations for row in by_allocation[name]]
            # A missing old runtime role cannot prove that an arranged operation was
            # newly scheduled; its unknown contribution remains in the scheduled view.
            if group == "scheduled":
                selected = [row for row in selected if row["allocation_state"] != "unknown" or row.get("arranged")]
            selected_by_group[group] = selected
    values = {}
    for key, _label, field, group, _common in PREPARATION_METRICS:
        values[key] = metric_summary(selected_by_group[group], field, available=requirements_available if group == "pending" else available)
        values[key]["coverage_groups"] = list(_GROUPS[group])
    roles = {}
    for role in _ROLES:
        selected = [row for row in rows if row.get("requirement_role") == role]
        standard_rows = [row for row in selected if row.get("source") != SourceType.EXTERNAL.value]
        roles[role] = {"count": len(selected), **{field: metric_summary(standard_rows, field, available=requirements_available)
                      for field in ("setup_standard_hours", "processing_standard_hours", "required_standard_hours")}}
    coverage = {name: [row["operation_ref"] for row in by_allocation[name]] for name in ALLOCATIONS}
    return {"metrics": values, "role_totals": roles, "coverage": coverage}


def preparation_delta(selected, previous):
    """A reduction in scheduled work is a neutral change in demand coverage."""
    value, reference = selected.get("value"), previous.get("value")
    same = (selected.get("total_count") == previous.get("total_count")
            and selected.get("covered_operation_refs") == previous.get("covered_operation_refs"))
    state = "unavailable" if value is None or reference is None else "comparable" if same else "different_coverage"
    difference = value - reference if value is not None and reference is not None else None
    result = {"value": difference, "state": state, "direction": "equal" if difference == 0 and same else "neutral",
              "reference_value": reference, "selected_value": value}
    if state == "different_coverage":
        result["reason"] = {"code": "preparation_allocation_changed", "message": "实际安排的需求范围不同；少安排或暂缓的需求单列为中性变化。"}
    return result


def public_preparation_metrics(values):
    """Large operation coverage is represented once by the source's role groups."""
    return {key: {name: value for name, value in item.items() if name != "covered_operation_refs"} for key, item in values.items()}


def public_preparation_roles(roles):
    return {role: {key: value if key == "count" else {field: number for field, number in value.items() if field != "covered_operation_refs"}
                   for key, value in items.items()} for role, items in roles.items()}
