"""Trial interval parsing and archived occupancy spans."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
from core.models.workbench_trial import reject
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from core.services.workbench.facts.zero_duration import PointEventError, point_work_quantity
from core.shared.stored_dates import stored_local_iso_datetime

from .arrangements import same_arrangement
from .occupancy import ReportedExecution, arranged_occupancy, reported_archive

_ARRANGEMENT_INVALID = "试调保存的安排时间已损坏，不能继续核对或采用，正式计划没有改变。请从当前正式计划重新发起试调。"


def trial_point_witness(original, arrangement, *, at):
    """The point witness of a zero-length ``arrangement`` of ``original`` at its admitted instant ``at``.

    ``witness.matches`` makes the point-work judgement (``is_point_work``: internal, zero setup and unit hours).
    """
    basis = original.get("point_basis")
    if type(basis) is not dict:
        raise PointEventError("point_evidence_missing", "这条起止时间相同的历史安排没有留下零工时工序的核对依据。")
    op, batch, execution = original["operation"], original["batch"], original["execution"]
    if type(execution) is not dict or op.get("source") != "internal":
        raise PointEventError("point_identity_unproven", "这道零工时工序缺少当时的报工记录。")
    operation_ref = basis.get("operation_ref") if op.get("piece_id") is not None else execution.get("operation_ref")
    quantity = point_work_quantity(op, batch, execution, operation_ref)
    setup, unit = op.get("setup_hours"), op.get("unit_hours")
    machine_id, operator_id = arrangement["machine_id"], arrangement["operator_id"]
    witness = SchedulePointEvidence(op["id"], machine_id, operator_id, at, setup, unit, quantity)
    row = ValidatedScheduleRow(
        op_id=op["id"],
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=at,
        end_time=at,
        source=op["source"],
    )
    if not witness.matches(row):
        raise PointEventError("point_evidence_invalid", "零工时工序的安排与核对依据不一致。")
    expected = {
        "op_id": witness.op_id,
        "setup_hours": witness.setup_hours,
        "unit_hours": witness.unit_hours,
        "quantity": witness.quantity,
    }
    if op.get("piece_id") is not None:
        expected.update(piece_id=op["piece_id"], batch_id=op["batch_id"], operation_ref=operation_ref)
    if basis != expected or any(type(basis[key]) is not type(val) for key, val in expected.items()):
        raise PointEventError("point_evidence_invalid", "这道零工时工序的存档内容已被改动，不能作为依据。")
    return witness


def _admitted_interval(value, *, original):
    """One arrangement's stored interval and, for a zero-length one its point basis proves, its witness.

    Draft rows (``original_json``/``current_json``) and a saved scenario's ``payload_json`` times are JSON copies
    without a table CHECK; this is their only read boundary, and rows computed in this process for a create or an
    edit pass here too. It admits only the storage invariants, strict instants and ``start <= end``, and rejects a
    breach as damaged storage. Whether a zero-length row is a proven point event is a domain judgment, not a storage
    invariant: an unproven one keeps its ``(start, start)`` interval without a witness, so it is in no points map and
    validation, adoption and freezing block it by their own rules.
    """
    start, end = stored_local_iso_datetime(value["start"]), stored_local_iso_datetime(value["end"])
    if start is None or end is None or end < start:
        reject("trial_snapshot_invalid", _ARRANGEMENT_INVALID)
    if start < end:
        return (start, end), None
    try:
        return (start, end), trial_point_witness(original, value, at=start)
    except PointEventError:
        return (start, end), None


def build_current_trial_spans(rows):
    """Each row's admitted current interval and point witness, without execution occupancy."""
    current_by_op = {}
    current_by_row = {}
    current_points_by_op = {}
    current_points_by_row = {}
    for row in rows:
        span, witness = _admitted_interval(row["current"], original=row["original"])
        current_by_op[row["operation_ref"]] = current_by_row[row["row_ref"]] = span
        if witness is not None:
            current_points_by_op[witness.op_id] = witness
            current_points_by_row[row["row_ref"]] = witness
    return {
        "current_by_op": current_by_op,
        "current_by_row": current_by_row,
        "current_points_by_op": current_points_by_op,
        "current_points_by_row": current_points_by_row,
    }


def build_trial_intervals(rows, *, reported: Mapping[str, ReportedExecution]):
    """Each row's admitted current and original interval and the resources they occupy."""
    spans = build_current_trial_spans(rows)
    current_by_row = spans["current_by_row"]
    current_points_by_row = spans["current_points_by_row"]
    original_by_row = {}
    original_by_source_row = {}
    original_points_by_row = {}
    current_occupancy, original_occupancy = {}, {}
    for row in rows:
        original = row["original"]
        current = row["current"]
        orig_arr = original["arrangement"]
        op_ref = row["operation_ref"]
        row_ref = row["row_ref"]
        curr_span = current_by_row[row_ref]
        curr_reported = reported[op_ref]
        current_occupancy[row_ref] = arranged_occupancy(curr_span, current, curr_reported)
        if (
            current["start"] == orig_arr["start"]
            and current["end"] == orig_arr["end"]
            and (current["start"] != current["end"] or same_arrangement(current, orig_arr))
        ):
            orig_span = curr_span
            if row_ref in current_points_by_row:
                original_points_by_row[row_ref] = current_points_by_row[row_ref]
        else:
            orig_span, orig_witness = _admitted_interval(orig_arr, original=original)
            if orig_witness is not None:
                original_points_by_row[row_ref] = orig_witness
        shared = original["execution"] is curr_reported.execution
        orig_reported = curr_reported if shared else reported_archive(original["execution"])
        original_occupancy[row_ref] = arranged_occupancy(orig_span, orig_arr, orig_reported)
        original_by_row[row_ref] = orig_span
        original_by_source_row[row["source_row_ref"]] = orig_span
    return {
        **spans,
        "original_by_row": original_by_row,
        "original_by_source_row": original_by_source_row,
        "original_points_by_row": original_points_by_row,
        "current_occupancy_by_row": current_occupancy,
        "original_occupancy_by_row": original_occupancy,
    }


def build_archived_trial_intervals(rows, *, execution: Mapping[str, Dict[str, Any]]):
    """Each row's current and original interval and occupancy from archived execution snapshots."""
    return build_trial_intervals(
        rows,
        reported={row["operation_ref"]: reported_archive(execution[row["operation_ref"]]) for row in rows},
    )
