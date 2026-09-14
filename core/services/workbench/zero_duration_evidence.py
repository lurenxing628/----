"""Validate frozen work witnesses; never infer points from a bare equal interval."""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence

from .zero_duration import PointEventError, internal_duration_hours, point_event_dto, point_work_quantity


def work_point_evidence(operation, batch, execution, payload, *, operation_ref):
    if (operation.get("source") != "internal" or payload.get("source") != "internal"
            or operation.get("id") != payload.get("op_id")
            or operation.get("batch_id") != batch.get("batch_id")):
        raise PointEventError("point_identity_unproven", "零工时工序必须对应原来的整批或分件工序。")
    quantity = point_work_quantity(operation, batch, execution, operation_ref)
    setup, unit = operation.get("setup_hours"), operation.get("unit_hours")
    if internal_duration_hours(setup, unit, quantity) != 0:
        raise PointEventError("point_duration_nonzero", "这道工序有实际工时，不是零工时工序。")
    start, end = (datetime.fromisoformat(payload[key]) for key in ("start_time", "end_time"))
    point_event_dto(start, end)
    witness = SchedulePointEvidence(operation["id"], payload.get("machine_id"), payload.get("operator_id"),
                                    start, setup, unit, quantity)
    if not witness.matches(SimpleNamespace(**dict(payload, start_time=start, end_time=end))):
        raise PointEventError("point_evidence_invalid", "零工时工序的安排与核对依据不一致。")
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
            raise PointEventError("point_evidence_invalid", "零工时工序的来源记录里有重复工序。")

    def work(self, operation_ref, payload):
        expected = {key: value for key, value in payload.items() if key != "locked"}
        op_id = payload.get("op_id")
        if self.validated.get(op_id) != expected or self.engine.get(op_id) != expected:
            raise PointEventError("point_evidence_missing", "零工时工序在本次排产结果里没有完全一致的记录。")
        gaps = []
        operation = self.facts.operation(operation_ref, payload, gaps)
        batch = self.facts.tables["Batches"].get(operation.get("batch_id"), {})
        execution = self.facts.execution.get(operation_ref)
        if gaps:
            raise PointEventError("point_identity_unproven", "零工时工序缺少原工序信息。")
        witness = work_point_evidence(operation, batch, execution, payload, operation_ref=operation_ref)
        return {"witness": witness, "operation": operation, "batch": batch, "execution": execution}


def overlaps(start, end, low, high):
    return low <= start < high if start == end else start < high and end > low


def trial_point_evidence(original, current=None):
    basis = original.get("point_basis")
    if type(basis) is not dict:
        raise PointEventError("point_evidence_missing", "这条起止时间相同的历史安排没有留下零工时工序的核对依据。")
    arrangement = current if current is not None else original["arrangement"]
    op, batch, execution = (original[key] for key in ("operation", "batch", "execution"))
    if type(execution) is not dict:
        raise PointEventError("point_identity_unproven", "这道零工时工序缺少当时的报工记录。")
    payload = {"op_id": op["id"], "source": op["source"], "machine_id": arrangement["machine_id"],
               "operator_id": arrangement["operator_id"], "start_time": arrangement["start"],
               "end_time": arrangement.get("end", arrangement["start"])}
    operation_ref = basis.get("operation_ref") if op.get("piece_id") is not None else execution.get("operation_ref")
    witness = work_point_evidence(op, batch, execution, payload, operation_ref=operation_ref)
    expected = point_basis({"witness": witness, "operation": op, "execution": execution})
    if basis != expected or any(type(basis[key]) is not type(value) for key, value in expected.items()):
        raise PointEventError("point_evidence_invalid", "这道零工时工序的存档内容已被改动，不能作为依据。")
    return witness


def point_basis(work):
    value = work["witness"]
    basis = {"op_id": value.op_id, "setup_hours": value.setup_hours,
             "unit_hours": value.unit_hours, "quantity": value.quantity}
    op = work["operation"]
    if op.get("piece_id") is not None:
        basis.update(piece_id=op["piece_id"], batch_id=op["batch_id"], operation_ref=work["execution"]["operation_ref"])
    return basis
