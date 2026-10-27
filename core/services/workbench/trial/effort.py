"""Saved trial requirement lineage; geometry never manufactures runtime work."""

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts

from .arrangements import same_arrangement


def retained_role(row, execution):
    anchor = (row["original"].get("execution_anchor") or {}).get("basis")
    if anchor == "completed_actuals" or execution["execution_state"] == "complete":
        return "completed"
    if anchor is not None or execution["first_actual_start"] or execution["reports"] or execution["legacy_facts"]:
        return "execution"
    return "retained"


def _retained(value, row, admission):
    execution = admission["execution"][row["operation_ref"]]
    role = retained_role(row, execution)
    state = ("external" if value["source"] == "external" else "already_completed" if role == "completed"
             else "retained_in_execution" if role == "execution" and value["setup_standard_hours"] is not None
             else value["setup_state"])
    return dict(value, execution_target_quantity=execution["target_quantity"],
                execution_quantity_basis=execution["target_basis"],
                remaining_quantity=execution["remaining_quantity"], requirement_role=role, setup_state=state)


def operation_effort_ledger(rows, admission, *, before_efforts):
    """Collect source records or actual committed slot records, once per operation."""
    source = admission["source"].get("operation_effort")
    current_items = [row["current"]["operation_effort"] for row in rows if "operation_effort" in row["current"]]
    current = saved_operation_efforts({"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": current_items},
                                      identities={row["operation_ref"]: row["original"]["operation"]["id"] for row in rows})
    arranged = {row["operation_ref"] for row in rows}
    items = [item for ref, item in before_efforts.items() if ref not in arranged]
    for row in rows:
        value = current.get(row["operation_ref"])
        if value is None and (row["original"].get("execution_anchor") is not None
                              or same_arrangement(row["current"], row["original"]["arrangement"])):
            original_value = before_efforts.get(row["operation_ref"])
            value = _retained(original_value, row, admission) if original_value is not None else None
        if value is not None:
            if value["op_id"] != row["original"]["operation"]["id"]:
                corrupt()
            items.append(value)
    if source is None and not items:
        return None
    return {"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": items}


def operation_types(rows, refs, work_types, traces=()):
    trace_types = {row["op_id"]: row["op_type_id"] for row in traces if "op_type_id" in row}
    result = {}
    for row in rows:
        op = row["original"]["operation"]
        key = trace_types.get(op["id"], op["op_type_id"])
        result[row["operation_ref"]] = {"ref": refs.get(("op_type", key)),
                                         "label": work_types.get(key, {}).get("name")}
    return result
