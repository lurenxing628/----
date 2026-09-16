"""Real scheduler calendar and duration math over exact snapshot-local inputs."""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.models.workbench_trial import reject
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.workbench.preflight_checks import number

from .zero_duration import PointEventError, estimate_point_event, internal_duration_hours
from .zero_duration_evidence import trial_point_evidence


def calendar_engine(tables):
    profiles = {row["profile_id"]: row for row in tables["WorkbenchShiftProfiles"]}
    selected = []
    for row in tables["WorkbenchOperatorProfiles"]:
        if row["shift_profile_id"] is not None:
            profile = profiles.get(row["shift_profile_id"])
            selected.append({"operator_id": row["operator_id"], "shift_profile_id": row["shift_profile_id"],
                             **(profile or {"profile_id": None, "status": None, "anchor_date": None, "cycle_days": None})})
    return SnapshotCalendarEngine({"global": tables["WorkCalendar"], "personal": tables["OperatorCalendar"],
                                   "profiles": selected, "patterns": tables["WorkbenchShiftPatternDays"]})


def original_duration(original, *, allow_point=False):
    """Saved points require a frozen witness; opt-in allows calendar math only."""
    op, batch, execution = original["operation"], original["batch"], original["execution"]
    if op["source"] == "external":
        group = original.get("external_group")
        days = group["total_days"] if group and group["merge_mode"] == "merged" else op["ext_days"]
        if not number(days, positive=True):
            reject("external_duration_unknown", "原外协周期缺失或无效，不能推测完工时间。", 422)
        return {"basis": "calendar_days", "days": days, "total_hours": None, "quantity": None}
    if op["source"] != "internal":
        reject("duration_source_unknown", "这道工序是自制还是外协读不到，算不出时长。", 422)
    if not number(op["setup_hours"]) or not number(op["unit_hours"]):
        reject("hours_missing", "原换型工时或单件工时缺失。", 422)
    quantity = _original_target(op, batch, execution)
    try:
        total = internal_duration_hours(op["setup_hours"], op["unit_hours"], quantity)
    except PointEventError as exc:
        reject(exc.code, str(exc), 422)
    if total == 0 and allow_point is not True:
        try:
            trial_point_evidence(original)
        except PointEventError:
            reject("zero_or_invalid_duration", "零工时工序的归档依据缺失。", 422)
    return {"basis": "effective_processing_hours", "setup_hours": op["setup_hours"],
            "unit_hours": op["unit_hours"], "quantity": quantity, "total_hours": total}


def _original_target(op, batch, execution):
    quantity = execution.get("target_quantity") if execution else None
    basis = "piece" if op["piece_id"] is not None else "batch"
    target = 1 if op["piece_id"] is not None else batch["quantity"]
    if not number(quantity, integer=True) or quantity != target or execution.get("target_basis") != basis:
        reject("piece_quantity_unknown" if op["piece_id"] is not None else "quantity_unknown",
               "原分件或批次目标量缺失。", 422)
    return quantity


def estimate(engine, original, arrangement, *, allow_point=False):
    """allow_point enables calendar math only, not production save or adoption."""
    duration = original_duration(original, allow_point=allow_point)
    start = datetime.fromisoformat(arrangement["start"])
    if duration["basis"] == "calendar_days":
        return start, _second_precision(engine.add_calendar_days(start, duration["days"]))
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
    batch = SimpleNamespace(**original["batch"])
    slot = estimate_internal_slot(calendar=engine, op=SimpleNamespace(**original["operation"]), batch=batch,
        machine_id=arrangement["machine_id"], operator_id=arrangement["operator_id"], base_time=start,
        prev_end=start, machine_timeline=(), operator_timeline=(), machine_downtimes=(),
        end_dt_exclusive=None, last_op_type_by_machine=None, abort_after=None,
        total_hours_base=duration["total_hours"])
    if slot.efficiency_fallback_used:
        reject("calendar_efficiency_unknown", "班表效率缺失，请核对工作日历。", 422)
    if slot.end_time <= slot.start_time:
        reject("duration_precision_unsupported", "这道工序有实际工时，但算出来不足 1 秒，不能按零工时工序保存。", 422)
    return slot.start_time, _second_precision(slot.end_time)


def _second_precision(value):
    if value.microsecond:
        reject("duration_precision_unsupported", "计算结果包含不足一秒的部分，无法按整秒精度保存。", 422)
    return value
