"""Real scheduler calendar and duration math over exact snapshot-local inputs."""

from dataclasses import replace
from datetime import datetime

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.models.workbench_trial import reject
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.preflight_checks import number
from core.services.workbench.facts.stored_algo_inputs import stored_batch, stored_operation
from core.services.workbench.facts.zero_duration import PointEventError, estimate_point_event
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence


def calendar_engine(tables):
    """Reuse the same snapshot policy rules for live edit estimation and capacity.

    ``None`` means the captured calendar tables are structurally damaged; damaged
    calendar content stays inside the engine until a policy reads that day.
    """
    return ArchivedCalendar({"tables": tables}, metadata_basis="current_transaction_snapshot").engine


def original_duration(original, *, effort=None):
    """Saved zero-hour work requires a frozen point witness."""
    op = original["operation"]
    if effort is None:
        effort = new_slot_effort(original)
    if op["source"] == "external":
        return {"basis": "calendar_days", "days": effort.external_cycle_days, "total_hours": None, "quantity": None}
    quantity = effort.target_quantity
    total = effort.required_standard_hours
    if total == 0:
        try:
            trial_point_evidence(original)
        except PointEventError:
            reject("zero_or_invalid_duration", "零工时工序的归档依据缺失。", 422)
    return {"basis": "effective_processing_hours", "setup_hours": op["setup_hours"],
            "unit_hours": op["unit_hours"], "quantity": quantity, "total_hours": total}


def new_slot_effort(original):
    """The same operation-local standard requirement the real trial slot consumes."""
    op, batch, execution = original["operation"], original["batch"], original["execution"]
    remaining = execution.get("remaining_quantity") if execution else None
    if op["source"] == "external":
        result = external_operation_effort(stored_operation(op, original.get("external_group")), stored_batch(batch),
                                           remaining_quantity=remaining)
        if not number(result.external_cycle_days, positive=True):
            reject("external_duration_unknown", "原外协周期缺失或无效，不能推测完工时间。", 422)
        return replace(result, execution_target_quantity=execution.get("target_quantity") if execution else None,
                       execution_quantity_basis=execution.get("target_basis", "unknown") if execution else "unknown")
    if op["source"] != "internal":
        reject("duration_source_unknown", "这道工序的来源缺项，标准需求未知。", 422)
    if not number(op["setup_hours"]) or not number(op["unit_hours"]):
        reject("hours_missing", "原准备工时或单件工时缺失。", 422)
    _original_target(op, batch, execution)
    result = internal_operation_effort(stored_operation(op), stored_batch(batch), remaining_quantity=remaining)
    return replace(result, execution_target_quantity=execution.get("target_quantity") if execution else None,
                   execution_quantity_basis=execution.get("target_basis", "unknown") if execution else "unknown")

def _original_target(op, batch, execution):
    quantity = execution.get("target_quantity") if execution else None
    basis = "piece" if op["piece_id"] is not None else "batch"
    target = 1 if op["piece_id"] is not None else batch["quantity"]
    if not number(quantity, integer=True) or quantity != target or execution.get("target_basis") != basis:
        reject("piece_quantity_unknown" if op["piece_id"] is not None else "quantity_unknown",
               "原分件或批次目标量缺失。", 422)
    return quantity


def estimate(engine, original, arrangement, *, effort=None):
    """Estimate a slot with saved work and the snapshot-local calendar."""
    duration = original_duration(original, effort=effort)
    start = datetime.fromisoformat(arrangement["start"])
    if duration["basis"] == "calendar_days":
        return start, engine.add_calendar_days(start, duration["days"])
    if arrangement["machine_ref"] is None or arrangement["operator_ref"] is None:
        reject("resource_required", "请选择设备和人员。", 422)
    if duration["total_hours"] == 0:
        try:
            return estimate_point_event(engine, setup_hours=duration["setup_hours"],
                unit_hours=duration["unit_hours"], quantity=duration["quantity"],
                machine_id=arrangement["machine_id"], operator_id=arrangement["operator_id"],
                priority=original["batch"]["priority"], start=start)
        except PointEventError as exc:
            reject(exc.code, str(exc), 422)
    slot = estimate_internal_slot(calendar=engine, op=stored_operation(original["operation"]),
        batch=stored_batch(original["batch"]),
        machine_id=arrangement["machine_id"], operator_id=arrangement["operator_id"], base_time=start,
        prev_end=start, machine_timeline=(), operator_timeline=(), machine_downtimes=(),
        end_dt_exclusive=None, last_op_type_by_machine=None, abort_after=None,
        total_hours_base=duration["total_hours"])
    if slot.end_time <= slot.start_time:
        reject("duration_precision_unsupported", "这道工序有实际工时，但计算结果没有形成正时长，不能按零工时工序保存。", 422)
    return slot.start_time, slot.end_time
