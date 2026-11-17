"""The saved standard requirement, its actual allocation and coverage summaries."""

from typing import Any, Dict

from core.models.enums import OperationRequirementRole, SourceType
from core.models.hours import public_hours, sum_hours

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
_RUNTIME_ALLOCATIONS = (OperationRequirementRole.NEW_SCHEDULE.value,) + _ROLES


def operation_allocation(runtime, *, arranged, source, deferred, available):
    """Where one operation's work went on one side: the side's saved runtime requirement ``runtime`` (None when its
    ledger records none), whether the side ``arranged`` the operation, and the operation's ``source`` there (the
    runtime's, else its arrangement's).

    The one allocation rule of the decision, candidate and trial views. Without a side to read (``available`` False)
    the allocation is unknown. An unarranged operation is deferred when it waits for material (``deferred``) and
    unplanned otherwise; an arranged one is external when its source is, otherwise the runtime's requirement role,
    unknown without one.
    """
    if not available:
        return "unknown"
    if not arranged:
        return "deferred" if deferred else "unplanned"
    if source == SourceType.EXTERNAL.value:
        return "external"
    role = runtime["requirement_role"] if runtime is not None else None
    return role if role in _RUNTIME_ALLOCATIONS else "unknown"


def project_operation_effort(runtime, standard, *, allocation_state, source_available=True, source=None,
                             execution, evidence_source=None) -> Dict[str, Any]:
    """The old standard remains visible without inventing a runtime split.

    execution is the operation's captured execution projection; every caller's execution
    snapshot covers its whole operation scope, so a missing projection is a broken contract.
    """
    standard = standard or {"basis": "archived_operation_standard", "setup_standard_hours": None, "unit_standard_hours": None,
                            "target_quantity": None, "remaining_quantity": None, "standard_total_hours": None, "state": "unavailable",
                            "reason": {"code": "standard_effort_missing", "message": "此来源未保存可核对的工序标准。"}}
    result: Dict[str, Any]
    if runtime is None:
        result = {field: None for field in _FIELDS}
        completed = source_available and execution["execution_state"] == "complete"
        result.update(source=source, quantity_basis="unknown", execution_quantity_basis=execution["target_basis"],
                      execution_target_quantity=execution["target_quantity"], remaining_quantity=execution["remaining_quantity"],
                      setup_state="already_completed" if completed else "unknown", requirement_role="completed" if completed else "unknown", state="unavailable",
                      data_gaps=[{"field": "runtime_requirement", "code": "runtime_requirement_missing" if source_available else "reference_required",
                                  "message": "这条记录未分别保存准备和加工所需的标准工时。" if source_available else "此比较没有可用的基准安排。"}])
    else:
        result = {field: runtime.get(field) for field in _FIELDS}
        result.update(execution_quantity_basis=execution["target_basis"],
                      execution_target_quantity=execution["target_quantity"], remaining_quantity=execution["remaining_quantity"])
        result["data_gaps"] = runtime["data_gaps"]
        unknown = sum(result[field] is None for field in ("setup_standard_hours", "processing_standard_hours", "required_standard_hours"))
        result["state"] = ("not_applicable" if result["source"] == SourceType.EXTERNAL.value else
                           "unavailable" if unknown == 3 else "partial" if unknown else "complete")
    if runtime is None and result["requirement_role"] == OperationRequirementRole.COMPLETED.value and allocation_state == "unknown":
        allocation_state = OperationRequirementRole.COMPLETED.value
    result.update(
        allocation_state=allocation_state,
        evidence_source=evidence_source,
        standard=standard,
    )
    return result


def metric_summary(rows, field, *, available=True):
    """Exact standard hours of ``field`` over ``rows``; a row whose hours are None counts as unknown."""
    hours = sum_hours(row[field] for row in rows)
    total, unknown = len(rows), hours.unknown
    subtotal = 0 if hours.known is None else public_hours(hours.known)
    state = ("unavailable" if not available or unknown == total and unknown else
             "partial" if unknown else "not_applicable" if not rows else "complete")
    reason = ({"code": "reference_required", "message": "此比较没有可用的基准需求。"} if not available else
              {"code": "runtime_requirement_missing", "message": "部分工序未分别保存准备和加工所需的标准工时；已保存的工时与原工时定额分别列出。"} if unknown else None)
    return {"value": None if unknown or not available else subtotal,
            "known_subtotal": subtotal if available else None, "state": state,
            "known_count": total - unknown if available else 0, "unknown_count": unknown if available else total, "total_count": total,
            "scope": "full_admission", "metric_version": PREPARATION_METRIC_VERSION, "member_unit": "operation", "reason": reason,
            "covered_operation_refs": sorted(row["operation_ref"] for row in rows if row[field] is not None) if available else []}


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
    pending_in_order = [row for row in internal if row["allocation_state"] in _GROUPS["pending"]]
    demand = metric_summary(pending_in_order, "required_standard_hours", available=requirements_available)
    return {"metrics": values, "role_totals": roles, "coverage": coverage, "demand": demand}


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


_COVERAGE_FIELDS = ("covered_batch_refs", "covered_operation_refs", "covered_resource_refs")


def public_preparation_metrics(values):
    """Strip member reference lists at the public outlet; keep scalar member_unit."""
    return {key: {name: value for name, value in item.items() if name not in _COVERAGE_FIELDS} for key, item in values.items()}


def public_preparation_roles(roles):
    return {role: {key: value if key == "count" else {field: number for field, number in value.items() if field not in _COVERAGE_FIELDS}
                   for key, value in items.items()} for role, items in roles.items()}
