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
        raise PointEventError("quantity_unknown", "Point work requires an explicit original batch quantity.")
    if piece is not None:
        if not _canonical_identity(piece) or quantity == 0:
            raise PointEventError("point_identity_unproven", "Single-piece work requires a canonical piece in a positive batch.")
        quantity = 1
    if (type(execution.get("target_quantity")) is not int or execution["target_quantity"] != quantity
            or execution.get("target_basis") != ("piece" if piece is not None else "batch")):
        raise PointEventError("quantity_unknown", "Point quantity and basis must match the original execution target.")
    return quantity


def _point_work_identity(operation, batch, execution, operation_ref):
    if (not number(operation.get("id"), integer=True, positive=True)
            or operation.get("source") != "internal"
            or not _canonical_identity(operation.get("batch_id"))
            or operation["batch_id"] != batch.get("batch_id")
            or not public_ref(operation_ref)
            or not execution or execution.get("operation_ref") != operation_ref):
        raise PointEventError("point_identity_unproven", "Point work lacks its original operation and ledger identity.")


def _canonical_identity(value):
    return type(value) is str and bool(value) and value.strip() == value


def internal_duration_hours(setup_hours, unit_hours, quantity):
    """Validate operands before multiplication: missing/negative times are not zero."""
    if not number(setup_hours) or not number(unit_hours):
        raise PointEventError("hours_missing", "Explicit finite non-negative setup and unit hours are required.")
    if not number(quantity, integer=True):
        raise PointEventError("quantity_unknown", "An explicit non-negative integer target quantity is required.")
    total = setup_hours + unit_hours * quantity
    if not number(total):
        raise PointEventError("invalid_duration", "Total processing hours are outside the supported finite range.")
    return total


def point_event_dto(start, end):
    """Temporal DTO only; callers retain their original operation/task/plan refs."""
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise PointEventError("point_time_invalid", "Point event times must be explicit datetimes.")
    if start.tzinfo is not None or end.tzinfo is not None or start != end:
        raise PointEventError("point_time_invalid", "Point events require equal factory-local start and end times.")
    if start.microsecond or end.microsecond:
        raise PointEventError("duration_precision_unsupported", "Point event time cannot be rounded to seconds.")
    return {"event_kind": "point", "start": start.isoformat(), "end": end.isoformat(),
            "duration_seconds": 0, "occupies_resources": False}


def estimate_point_event(calendar, *, setup_hours, unit_hours, quantity, machine_id, operator_id, priority, start):
    """Use real shift/priority/efficiency rules, with no occupied resource interval.

    This is not an adoption proof: identity, precedence, readiness, locks and
    execution remain mandatory at the caller's complete-plan boundary.
    """
    if internal_duration_hours(setup_hours, unit_hours, quantity) != 0:
        raise PointEventError("point_duration_nonzero", "Positive work cannot be represented by a point event.")
    point_event_dto(start, start)
    if any(type(value) is not str or not value or value.strip() != value for value in (machine_id, operator_id)):
        raise PointEventError("resource_required", "Point events still require explicit machine and operator identities.")
    if priority not in ("normal", "urgent", "critical"):
        raise PointEventError("priority_unknown", "Point events require a known batch priority.")
    slot = estimate_internal_slot(calendar=calendar,
        op=SimpleNamespace(setup_hours=setup_hours, unit_hours=unit_hours),
        batch=SimpleNamespace(quantity=quantity, priority=priority), machine_id=machine_id,
        operator_id=operator_id, base_time=start, prev_end=start, machine_timeline=(),
        operator_timeline=(), machine_downtimes=(), end_dt_exclusive=None,
        last_op_type_by_machine=None, abort_after=None, total_hours_base=0)
    if slot.efficiency_fallback_used:
        raise PointEventError("calendar_efficiency_unknown", "Point events cannot use an unknown calendar efficiency.")
    point_event_dto(slot.start_time, slot.end_time)
    return slot.start_time, slot.end_time


def candidate_point_validator(schedule_input):
    """Build one index for all rows in this exact prepared input."""
    operations = {op.id: op for op in schedule_input.operations}
    dispositions = {item["op_id"]: item for item in schedule_input.dispositions}
    if len(operations) != len(schedule_input.operations) or len(dispositions) != len(schedule_input.dispositions):
        raise PointEventError("point_identity_unproven", "Point input cannot contain duplicate original operations.")

    def validate(row):
        return _candidate_point_evidence(schedule_input, row, operations, dispositions)

    return validate


def _candidate_point_evidence(schedule_input, row, operations, dispositions):
    op = operations.get(row.op_id)
    disposition = dispositions.get(row.op_id)
    if op is None or disposition is None:
        raise PointEventError("point_identity_unproven", "The point has no original operation identity.")
    batch = schedule_input.batches[op.batch_id]
    if op.source != "internal" or row.source != "internal":
        raise PointEventError("point_source_unproven", "Only exact internal work has a point contract.")
    if any(disposition[key] != value for key, value in (
            ("piece_id", op.piece_id), ("batch_id", op.batch_id), ("sequence", op.seq))):
        raise PointEventError("point_identity_unproven", "Point disposition differs from its original piece operation.")
    work = {key: getattr(op, key) for key in ("id", "batch_id", "piece_id", "source")}
    quantity = point_work_quantity(work, {"batch_id": batch.batch_id, "quantity": batch.quantity},
                                   disposition["execution"], disposition["operation_ref"])
    start, end = estimate_point_event(schedule_input.cal_svc, setup_hours=op.setup_hours,
        unit_hours=op.unit_hours, quantity=quantity, machine_id=row.machine_id,
        operator_id=row.operator_id, priority=batch.priority, start=row.start_time)
    if (start, end) != (row.start_time, row.end_time):
        raise PointEventError("point_calendar_conflict", "Point time does not satisfy its actual work calendar.")
    return SchedulePointEvidence(row.op_id, row.machine_id, row.operator_id, start,
                                 op.setup_hours, op.unit_hours, quantity)
