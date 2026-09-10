"""Validate frozen work witnesses; never infer points from a bare equal interval."""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence

from .zero_duration import PointEventError, internal_duration_hours, point_event_dto, point_work_quantity


def work_point_evidence(operation, batch, execution, payload, *, operation_ref):
    if (operation.get("source") != "internal" or payload.get("source") != "internal"
            or operation.get("id") != payload.get("op_id")
            or operation.get("batch_id") != batch.get("batch_id")):
        raise PointEventError("point_identity_unproven", "Point work must retain its original common or piece operation.")
    quantity = point_work_quantity(operation, batch, execution, operation_ref)
    setup, unit = operation.get("setup_hours"), operation.get("unit_hours")
    if internal_duration_hours(setup, unit, quantity) != 0:
        raise PointEventError("point_duration_nonzero", "Positive work is not a point event.")
    start, end = (datetime.fromisoformat(payload[key]) for key in ("start_time", "end_time"))
    point_event_dto(start, end)
    witness = SchedulePointEvidence(operation["id"], payload.get("machine_id"), payload.get("operator_id"),
                                    start, setup, unit, quantity)
    if not witness.matches(SimpleNamespace(**dict(payload, start_time=start, end_time=end))):
        raise PointEventError("point_evidence_invalid", "Point arrangement does not match its exact-work witness.")
    return witness


class CandidatePointReader:
    def __init__(self, candidate, facts):
        self.facts = facts
        artifact = candidate["artifact"]
        fields = ("op_id", "machine_id", "operator_id", "start_time", "end_time", "source")
        validated = artifact.get("validated_payload", {}).get("schedule_rows", [])
        engine = [{key: row.get(key) for key in fields} for row in artifact.get("results", [])]
        self.validated = {row["op_id"]: row for row in validated}
        self.engine = {row["op_id"]: row for row in engine}
        if len(self.validated) != len(validated) or len(self.engine) != len(engine):
            raise PointEventError("point_evidence_invalid", "Duplicate operation in point source evidence.")

    def work(self, operation_ref, payload):
        expected = {key: value for key, value in payload.items() if key != "locked"}
        op_id = payload.get("op_id")
        if self.validated.get(op_id) != expected or self.engine.get(op_id) != expected:
            raise PointEventError("point_evidence_missing", "The point lacks matching validated and original engine rows.")
        gaps = []
        operation = self.facts.operation(operation_ref, payload, gaps)
        batch = self.facts.tables["Batches"].get(operation.get("batch_id"), {})
        execution = self.facts.execution.get(operation_ref)
        if gaps:
            raise PointEventError("point_identity_unproven", "Original point identity is missing.")
        witness = work_point_evidence(operation, batch, execution, payload, operation_ref=operation_ref)
        return {"witness": witness, "operation": operation, "batch": batch, "execution": execution}


def overlaps(start, end, low, high):
    return low <= start < high if start == end else start < high and end > low


def trial_point_evidence(original, current=None):
    basis = original.get("point_basis")
    if type(basis) is not dict:
        raise PointEventError("point_evidence_missing", "A historical equal interval has no frozen point witness.")
    arrangement = current if current is not None else original["arrangement"]
    op, batch, execution = (original[key] for key in ("operation", "batch", "execution"))
    if type(execution) is not dict:
        raise PointEventError("point_identity_unproven", "Frozen point work lacks its original execution projection.")
    payload = {"op_id": op["id"], "source": op["source"], "machine_id": arrangement["machine_id"],
               "operator_id": arrangement["operator_id"], "start_time": arrangement["start"],
               "end_time": arrangement.get("end", arrangement["start"])}
    operation_ref = basis.get("operation_ref") if op.get("piece_id") is not None else execution.get("operation_ref")
    witness = work_point_evidence(op, batch, execution, payload, operation_ref=operation_ref)
    expected = point_basis({"witness": witness, "operation": op, "execution": execution})
    if basis != expected or any(type(basis[key]) is not type(value) for key, value in expected.items()):
        raise PointEventError("point_evidence_invalid", "Frozen point work was changed.")
    return witness


def point_basis(work):
    value = work["witness"]
    basis = {"op_id": value.op_id, "setup_hours": value.setup_hours,
             "unit_hours": value.unit_hours, "quantity": value.quantity}
    op = work["operation"]
    if op.get("piece_id") is not None:
        basis.update(piece_id=op["piece_id"], batch_id=op["batch_id"], operation_ref=work["execution"]["operation_ref"])
    return basis
