"""Fresh real ledger facts, independent pieces, explicit locks and occupied resources."""

from dataclasses import replace
from datetime import timedelta

import pytest

from core.errors import AppError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.run.schedule_execution_persistence_guard import validate_execution_guard_before_persist
from core.services.scheduler.schedule_service import ScheduleService
from tests.workbench.piece_adoption_support import START, lower_input, payload, slot_payload, split
from tests.workbench.piece_adoption_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.test_piece_adoption import check


def _second_resource(case, ids, piece="item-B"):
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Other lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Other operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    for seq in (20, 30):
        case.conn.execute("UPDATE BatchOperations SET machine_id='M2',operator_id='O2' WHERE id=?", (ids[piece, seq],))
    case.conn.commit()


def test_completed_piece_preserves_actual_hours_but_does_not_order_other_piece(candidate_case):
    case = candidate_case
    ids = split(case, common=False, quantity=2)
    _second_resource(case, ids)
    first = ids["item-A", 20]
    case.plan(1, [first])
    receipt = case.command("create", case.task(1, first), case.values(1))
    assert receipt["ok"]
    prepared = lower_input(case)
    value = slot_payload(prepared)
    evidence = check(case, prepared, value)
    rows = {row.op_id: row for row in value.schedule_rows}
    assert rows[first].end_time == START + timedelta(hours=2)
    assert rows[ids["item-B", 30]].start_time < rows[first].end_time
    assert rows[ids["item-A", 30]].start_time >= rows[first].end_time
    assert first in evidence.protected_op_ids
    projection = next(row["execution"] for row in prepared.dispositions if row["op_id"] == first)
    assert projection["reports"][0]["effective_processing_hours"] == 1.5
    assert projection["known_completed_quantity"] == projection["target_quantity"] == 1
    # This is an explicit integration gap in the still-unmodified shared guard.
    with pytest.raises(AppError) as caught:
        validate_execution_guard_before_persist(ScheduleService(case.conn), validated_schedule_payload=value,
            execution_guard_state_revisions=prepared.execution_guard_state_revisions,
            execution_facts=prepared.execution_facts, execution_fixed_op_ids=prepared.execution_fixed_op_ids,
            execution_completed_op_ids=prepared.execution_completed_op_ids,
            execution_snapshot_revision=prepared.execution_snapshot_revision,
            execution_snapshot_op_ids=prepared.execution_snapshot_op_ids, payload_validation_operations=prepared.operations)
    assert caught.value.details["reason"] == "execution_completed_downstream_before_actual_finish"


@pytest.mark.parametrize("quantity", [None, 0])
def test_unknown_or_partial_piece_execution_never_becomes_guessed_remaining_work(candidate_case, quantity):
    case = candidate_case
    ids = split(case, common=False)
    first = ids["item-A", 20]
    case.plan(1, [first])
    prepared = lower_input(case)
    value = slot_payload(prepared)
    case.command("create", case.task(1, first), case.values(quantity))
    current = {item.operation_ref: item.to_dict() for item in case.projections()}
    for row in prepared.dispositions:
        row["execution"] = current[row["operation_ref"]]
    with pytest.raises((PieceAdoptionBlocked, AppError)) as caught:
        check(case, prepared, value)
    if quantity is None:
        assert caught.value.code == "piece_execution_quantity_unproven"
    else:
        assert caught.value.code == "execution_ledger_requires_reconciliation"


def test_legacy_completed_quantity_is_not_guessed_or_multiplied(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    first = ids["item-A", 20]
    case.plan(1, [first])
    case.event(first, "start")
    case.event(first, "finish", quantity=None)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_execution_quantity_unproven"


@pytest.mark.parametrize("change", ["completion_flag", "revisions", "snapshot_scope", "actual_interval", "actual_resource"])
def test_no_execution_protection_component_can_be_dropped(candidate_case, change):
    case = candidate_case
    ids = split(case, common=False)
    first = ids["item-A", 20]
    case.plan(1, [first])
    case.command("create", case.task(1, first), case.values(1))
    prepared = lower_input(case)
    value = slot_payload(prepared)
    if change == "completion_flag":
        prepared.execution_completed_op_ids.clear()
    elif change == "revisions":
        prepared.execution_guard_state_revisions.clear()
    elif change == "snapshot_scope":
        prepared.execution_snapshot_op_ids.clear()
    else:
        patch = {"end_time": START + timedelta(hours=1)} if change == "actual_interval" else {"machine_id": "M2"}
        value = payload(prepared, [replace(row, **patch) if row.op_id == first else row for row in value.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code in ("piece_execution_protection_changed", "piece_protected_seed_changed")


def test_explicit_lock_survives_and_cannot_be_forgotten_or_rewritten(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    first = ids["item-A", 20]
    case.plan(1, [first], end="2026-09-09T08:15:00")
    case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    prepared = lower_input(case)
    value = slot_payload(prepared)
    assert first in check(case, prepared, value).protected_op_ids
    prepared.frozen_op_ids.clear()
    prepared.seed_results.clear()
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_inherited_lock_missing"
    prepared = lower_input(case)
    prepared.seed_results[0]["start_time"] += timedelta(minutes=1)
    changed = payload(prepared, [replace(row, start_time=row.start_time + timedelta(minutes=1))
                                 if row.op_id == first else row for row in value.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, changed)
    assert caught.value.code == "piece_inherited_lock_changed"


@pytest.mark.parametrize("kind", ["machine", "operator"])
def test_independent_pieces_still_compete_for_shared_resources(candidate_case, kind):
    case = candidate_case
    ids = split(case, common=False, quantity=2)
    _second_resource(case, ids)
    prepared = lower_input(case)
    valid = slot_payload(prepared)
    check(case, prepared, valid)
    row_id = ids["item-B", 20]
    patch = {"machine_id": "M1"} if kind == "machine" else {"operator_id": "O1"}
    value = payload(prepared, [replace(row, **patch) if row.op_id == row_id else row for row in valid.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "candidate_resource_overlap"


def test_old_unselected_official_work_cannot_disappear(candidate_case):
    case = candidate_case
    split(case)
    case.batch("B2")
    omitted = case.operation("B2")
    case.plan(1, [omitted])
    prepared = lower_input(case, "B1")
    value = slot_payload(prepared)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "official_scope_not_covered"
