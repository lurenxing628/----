"""Exact internal point events; no payload, persistence or adoption bypass."""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.models.workbench_preflight import public_ref

from .preflight_checks import number


class PointEventError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def point_work_quantity(operation, batch, execution, operation_ref):
    """Use the original single-piece target, never the enclosing batch quantity."""
    _point_work_identity(operation, batch, execution, operation_ref)
    piece, quantity = operation.get("piece_id"), batch.get("quantity")
    if type(quantity) is not int or not number(quantity, integer=True):
        raise PointEventError("quantity_unknown", "零工时工序没有读到原批次数量，不能核对。请先补好批次数量。")
    if piece is not None:
        if not _canonical_identity(piece) or quantity == 0:
            raise PointEventError("point_identity_unproven", "分件的零工时工序必须有明确的分件号，而且批次数量要大于 0。")
        quantity = 1
    if (type(execution.get("target_quantity")) is not int or execution["target_quantity"] != quantity
            or execution.get("target_basis") != ("piece" if piece is not None else "batch")):
        raise PointEventError("quantity_unknown", "零工时工序的数量或计数方式与原报工记录不一致，不能核对。")
    return quantity


def _point_work_identity(operation, batch, execution, operation_ref):
    if (not number(operation.get("id"), integer=True, positive=True)
            or operation.get("source") != "internal"
            or not _canonical_identity(operation.get("batch_id"))
            or operation["batch_id"] != batch.get("batch_id")
            or not public_ref(operation_ref)
            or not execution or execution.get("operation_ref") != operation_ref):
        raise PointEventError("point_identity_unproven", "零工时工序缺少原工序或报工记录的对应关系，不能核对。")


def _canonical_identity(value):
    return type(value) is str and bool(value) and value.strip() == value


def internal_duration_hours(setup_hours, unit_hours, quantity):
    """Validate operands before multiplication: missing/negative times are not zero."""
    if not number(setup_hours) or not number(unit_hours):
        raise PointEventError("hours_missing", "换型工时和单件工时必须填好，而且不能是负数。")
    if not number(quantity, integer=True):
        raise PointEventError("quantity_unknown", "目标数量必须填 0 或正整数。")
    total = setup_hours + unit_hours * quantity
    if not number(total):
        raise PointEventError("invalid_duration", "算出来的总工时超出可支持的范围，不能继续。")
    return total


def point_event_dto(start, end):
    """Temporal DTO only; callers retain their original operation/task/plan refs."""
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise PointEventError("point_time_invalid", "零工时工序的开始和结束时间必须是完整时刻。")
    if start.tzinfo is not None or end.tzinfo is not None or start != end:
        raise PointEventError("point_time_invalid", "零工时工序的开始和结束时间必须相同。")
    if start.microsecond or end.microsecond:
        raise PointEventError("duration_precision_unsupported", "零工时工序的时间带了秒以下的零头，不能保存，请改成整秒。")
    return {"event_kind": "point", "start": start.isoformat(), "end": end.isoformat(),
            "duration_seconds": 0, "occupies_resources": False}


def estimate_point_event(calendar, *, setup_hours, unit_hours, quantity, machine_id, operator_id, priority, start):
    """Use real shift/priority/efficiency rules, with no occupied resource interval.

    This is not an adoption proof: identity, precedence, readiness, locks and
    execution remain mandatory at the caller's complete-plan boundary.
    """
    if internal_duration_hours(setup_hours, unit_hours, quantity) != 0:
        raise PointEventError("point_duration_nonzero", "这道工序有实际工时，不是零工时工序。")
    point_event_dto(start, start)
    if any(type(value) is not str or not value or value.strip() != value for value in (machine_id, operator_id)):
        raise PointEventError("resource_required", "零工时工序也要选好设备和人员，虽然它不占设备人员时间。")
    if priority not in ("normal", "urgent", "critical"):
        raise PointEventError("priority_unknown", "零工时工序所在批次的优先级读不到，不能核对。")
    slot = estimate_internal_slot(calendar=calendar,
        op=SimpleNamespace(setup_hours=setup_hours, unit_hours=unit_hours),
        batch=SimpleNamespace(quantity=quantity, priority=priority), machine_id=machine_id,
        operator_id=operator_id, base_time=start, prev_end=start, machine_timeline=(),
        operator_timeline=(), machine_downtimes=(), end_dt_exclusive=None,
        last_op_type_by_machine=None, abort_after=None, total_hours_base=0)
    if slot.efficiency_fallback_used:
        raise PointEventError("calendar_efficiency_unknown", "零工时工序对应的班表效率读不到，这里不会改用默认效率。")
    point_event_dto(slot.start_time, slot.end_time)
    return slot.start_time, slot.end_time


def candidate_point_validator(schedule_input):
    """Build one index for all rows in this exact prepared input."""
    operations = {op.id: op for op in schedule_input.operations}
    dispositions = {item["op_id"]: item for item in schedule_input.dispositions}
    if len(operations) != len(schedule_input.operations) or len(dispositions) != len(schedule_input.dispositions):
        raise PointEventError("point_identity_unproven", "零工时工序的输入里有重复工序，不能核对。")

    def validate(row):
        return _candidate_point_evidence(schedule_input, row, operations, dispositions)

    return validate


def _candidate_point_evidence(schedule_input, row, operations, dispositions):
    op = operations.get(row.op_id)
    disposition = dispositions.get(row.op_id)
    if op is None or disposition is None:
        raise PointEventError("point_identity_unproven", "这道零工时工序找不到对应的原工序。")
    batch = schedule_input.batches[op.batch_id]
    if op.source != "internal" or row.source != "internal":
        raise PointEventError("point_source_unproven", "只有自制工序才能是零工时工序。")
    if any(disposition[key] != value for key, value in (
            ("piece_id", op.piece_id), ("batch_id", op.batch_id), ("sequence", op.seq))):
        raise PointEventError("point_identity_unproven", "零工时工序的归属与原分件工序不一致。")
    work = {key: getattr(op, key) for key in ("id", "batch_id", "piece_id", "source")}
    quantity = point_work_quantity(work, {"batch_id": batch.batch_id, "quantity": batch.quantity},
                                   disposition["execution"], disposition["operation_ref"])
    start, end = estimate_point_event(schedule_input.cal_svc, setup_hours=op.setup_hours,
        unit_hours=op.unit_hours, quantity=quantity, machine_id=row.machine_id,
        operator_id=row.operator_id, priority=batch.priority, start=row.start_time)
    if (start, end) != (row.start_time, row.end_time):
        raise PointEventError("point_calendar_conflict", "零工时工序的时间不符合实际班表，不能采用。")
    return SchedulePointEvidence(row.op_id, row.machine_id, row.operator_id, start,
                                 op.setup_hours, op.unit_hours, quantity)
