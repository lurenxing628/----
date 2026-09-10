"""Exact scope/quantity/precedence proof and the connected input contract."""

from dataclasses import replace
from datetime import timedelta

import pytest

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.workbench.piece_adoption import validate_piece_adoption
from core.services.workbench.piece_adoption_scope import build_piece_adoption_scope
from core.services.workbench.run_input import prepare_candidate_run_input
from tests.workbench.piece_adoption_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.piece_adoption_support import (
    checked_read_only,
    greedy_payload,
    lower_input,
    payload,
    slot_payload,
    split,
)


def check(case, prepared, value):
    return checked_read_only(case, lambda: validate_piece_adoption(case.conn, prepared=prepared, payload=value))


def test_common_fan_out_and_join_exact_quantities_with_real_slot_engine(candidate_case):
    case = candidate_case
    ids = split(case)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    evidence = check(case, prepared, value)
    by_id = {row.op_id: row for row in evidence.scope.operations}
    for piece in ("item-A", "item-B", "item-C"):
        assert by_id[ids[piece, 20]].predecessor_op_ids == (ids[None, 10],)
        assert by_id[ids[piece, 30]].predecessor_op_ids == (ids[piece, 20],)
        assert by_id[ids[piece, 30]].target_quantity == 1
    assert set(by_id[ids[None, 40]].predecessor_op_ids) == {ids[piece, 30] for piece in ("item-A", "item-B", "item-C")}
    durations = {row.op_id: (row.end_time - row.start_time).total_seconds() for row in value.schedule_rows}
    assert durations[ids[None, 10]] == 2700
    assert durations[ids["item-A", 20]] == 900
    assert by_id[ids[None, 40]].target_quantity == 3


def test_real_greedy_preserves_setup_and_uses_single_piece_multiplier(candidate_case):
    case = candidate_case
    split(case, unit=0)
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0.5")
    case.conn.commit()
    prepared = lower_input(case)
    results, value = greedy_payload(prepared)
    assert len(results) == 8
    check(case, prepared, value)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.25")
    case.conn.commit()
    prepared = lower_input(case)
    _, correct = greedy_payload(prepared)
    check(case, prepared, correct)
    piece_ids = {op.id for op in prepared.operations if op.piece_id is not None}
    assert all((row.end_time - row.start_time).total_seconds() == 2700
               for row in correct.schedule_rows if row.op_id in piece_ids)


@pytest.mark.parametrize("quantity", [0, 2, 4, -1, 1.5, (1 << 53)])
def test_piece_count_and_invalid_batch_quantity_fail_closed(candidate_case, quantity):
    case = candidate_case
    split(case)
    prepared = lower_input(case)
    prepared.batches["B1"].quantity = quantity
    with pytest.raises(PieceAdoptionBlocked):
        build_piece_adoption_scope(prepared.operations, prepared.batches)


@pytest.mark.parametrize("change,code", [
    ("missing_stage_member", "piece_stage_incomplete"),
    ("duplicate_stage_member", "piece_stage_incomplete"),
    ("common_same_sequence", "piece_dependency_ambiguous"),
    ("blank_piece", "piece_identity_invalid"),
    ("duplicate_op_id", "piece_identity_invalid"),
])
def test_ambiguous_or_incomplete_piece_facts(candidate_case, change, code):
    case = candidate_case
    ids = split(case)
    prepared = lower_input(case)
    ops = prepared.operations
    index = next(i for i, op in enumerate(ops) if op.id == ids["item-A", 20])
    if change == "missing_stage_member":
        ops.pop(index)
    elif change == "duplicate_stage_member":
        ops[index] = replace(ops[index], piece_id="item-B")
    elif change == "common_same_sequence":
        ops[index] = replace(ops[index], piece_id=None)
    elif change == "blank_piece":
        ops[index] = replace(ops[index], piece_id="")
    else:
        ops.append(ops[index])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        build_piece_adoption_scope(ops, prepared.batches)
    assert caught.value.code == code


@pytest.mark.parametrize("change,code", [
    ("wrong_piece_ref", "piece_identity_changed"),
    ("cross_piece_chain", "piece_dependency_mismatch"),
    ("missing_common", "piece_dependency_mismatch"),
    ("missing_row", "piece_scope_incomplete"),
    ("wrong_source", "invalid_schedule_rows"),
    ("fractional_second", "piece_time_unrepresentable"),
])
def test_malformed_prepared_or_payload_is_not_adoption_evidence(candidate_case, change, code):
    case = candidate_case
    ids = split(case)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    rows = {row["op_id"]: row for row in prepared.dispositions}
    a = rows[ids["item-A", 30]]
    if change == "wrong_piece_ref":
        a["operation_ref"] = rows[ids["item-B", 30]]["operation_ref"]
    elif change == "cross_piece_chain":
        a["predecessor_refs"] = [rows[ids["item-B", 20]]["operation_ref"]]
    elif change == "missing_common":
        rows[ids["item-A", 20]]["predecessor_refs"] = []
    elif change == "missing_row":
        value = replace(value, schedule_rows=value.schedule_rows[:-1])
    else:
        row = value.schedule_rows[0]
        patch = {"source": "external"} if change == "wrong_source" else {"end_time": row.end_time + timedelta(microseconds=1)}
        value = replace(value, schedule_rows=[replace(row, **patch)] + value.schedule_rows[1:])
    with pytest.raises(Exception) as caught:
        check(case, prepared, value)
    error = caught.value
    assert getattr(error, "code", None) == code or getattr(error, "details", {}).get("reason") == code


def test_actual_calendar_conflict_and_common_join_cannot_be_skipped(candidate_case):
    case = candidate_case
    ids = split(case)
    prepared = lower_input(case)
    original = slot_payload(prepared)
    join = next(row for row in original.schedule_rows if row.op_id == ids[None, 40])
    moved = replace(join, start_time=join.start_time - timedelta(minutes=15), end_time=join.end_time - timedelta(minutes=15))
    value = payload(prepared, [moved if row.op_id == join.op_id else row for row in original.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_precedence_violation"
    first = original.schedule_rows[0]
    value = payload(prepared, [replace(row, end_time=row.end_time - timedelta(minutes=1)) if row == first else row
                               for row in original.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_calendar_duration_conflict"


def test_connected_input_retains_full_piece_scope_and_stale_raw_is_rejected(candidate_case):
    case = candidate_case
    ids = split(case)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    connected = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    assert connected.schedule_output_allowed_op_ids == set(ids.values())
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.5 WHERE id=?", (ids["item-A", 20],))
    case.conn.commit()
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_raw_changed"
