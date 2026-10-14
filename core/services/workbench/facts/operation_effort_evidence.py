"""Read saved runtime decomposition separately from archived work standards."""

import math

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.models.enums import OperationQuantityBasis, OperationRequirementRole, OperationSetupState, SourceType
from core.models.workbench_run_candidate import MAX_TASKS, reference

from .candidate_values import bounded_size, corrupt, number

_HOURS = ("setup_standard_hours", "processing_standard_hours", "required_standard_hours", "external_cycle_days")
_QUANTITIES = ("target_quantity", "remaining_quantity", "execution_target_quantity")


def saved_operation_efforts(record, *, identities=None):
    """A missing historical ledger stays missing; malformed identities reject it."""
    if record is None:
        return {}
    if type(record) is not dict or record.get("effort_basis") != RUNTIME_REQUIREMENT_BASIS or type(record.get("items")) is not list:
        corrupt()
    bounded_size(len(record["items"]), MAX_TASKS)
    result = {}
    roles = {item.value for item in OperationRequirementRole}
    states = {item.value for item in OperationSetupState}
    bases = {item.value for item in OperationQuantityBasis}
    for item in record["items"]:
        if type(item) is not dict:
            corrupt()
        ref = reference(item.get("operation_ref"), stored=True)
        op_id = item.get("op_id")
        if (ref in result or type(op_id) is not int or op_id < 1 or item.get("source") not in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value)
                or item.get("effort_basis") != RUNTIME_REQUIREMENT_BASIS or item.get("requirement_role") not in roles
                or item.get("setup_state") not in states or item.get("quantity_basis") not in bases
                or item.get("execution_quantity_basis", OperationQuantityBasis.UNKNOWN.value) not in bases
                or identities is not None and identities.get(ref) != op_id):
            corrupt()
        for field in _HOURS + _QUANTITIES:
            value = item.get(field)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                corrupt()
        gaps = item.get("data_gaps")
        if type(gaps) is not list or any(type(gap) is not dict for gap in gaps):
            corrupt()
        result[ref] = item
    return result


def archived_standard_effort(operation, execution):
    """Keep the existing standard/AJ-target projection distinct from runtime work."""
    gaps = []
    setup = number(operation.get("setup_hours"), "setup_hours", gaps)
    unit = number(operation.get("unit_hours"), "unit_hours", gaps)
    setup_number = int(setup) if isinstance(setup, str) else setup
    unit_number = int(unit) if isinstance(unit, str) else unit
    target = execution.get("target_quantity")
    internal = operation.get("source") == SourceType.INTERNAL.value
    total = (setup_number + unit_number * target
             if internal and setup_number is not None and unit_number is not None and type(target) is int else None)
    return {"basis": "archived_operation_standard", "setup_standard_hours": setup if internal else None,
            "unit_standard_hours": unit if internal else None, "target_quantity": target, "remaining_quantity": execution.get("remaining_quantity"),
            "standard_total_hours": total, "state": "complete" if total is not None else "not_applicable" if not internal else "unavailable",
            "reason": None if total is not None else {"code": "external_cycle" if not internal else "standard_effort_missing",
                "message": "外协按周期安排。" if not internal else "归档工序标准工时或执行目标量缺失。"}}
