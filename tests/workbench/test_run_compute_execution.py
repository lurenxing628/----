"""Shared AQ execution protection with real AJ reports and legacy events."""

from datetime import datetime

import pytest

from core.infrastructure.errors import AppError
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.run_compute import compute_candidate_run
from core.services.workbench.run_input_projection_codec import restore_execution_projections
from tests.workbench.test_run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.test_run_compute_support import unchanged


def test_complete_actual_interval_is_preserved_and_successor_waits(run_case, monkeypatch):
    case = run_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.command("create", case.task(1, case.op_id), case.values(3))
    projections = restore_execution_projections([row.to_dict() for row in case.projections()])

    def no_reaggregation(*args, **kwargs):
        raise AssertionError("Supplied AJ projections must not be aggregated again")

    for reader in (ExecutionLedgerReader, ExecutionLedgerService):
        for method in ("load", "project_loaded", "project_operations"):
            monkeypatch.setattr(reader, method, no_reaggregation)
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
    assert result.schedule_input.execution_completed_op_ids == {case.op_id}
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert rows[case.op_id].start_time == datetime(2026, 9, 9, 8)
        assert rows[case.op_id].end_time == datetime(2026, 9, 9, 10)
        assert (rows[case.op_id].machine_id, rows[case.op_id].operator_id) == ("M1", "O1")
        assert rows[successor].start_time >= rows[case.op_id].end_time


@pytest.mark.parametrize("quantity", [None, 0, 1])
def test_unknown_zero_and_partial_reports_never_create_guessed_remaining_work(run_case, quantity):
    case = run_case
    case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.command("create", case.task(1, case.op_id), case.values(quantity))
    with pytest.raises(AppError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.details["reason"] == "execution_ledger_requires_reconciliation"
    assert error.value.details["op_id"] == case.op_id
    assert error.value.details["remaining_quantity"] == (None if quantity is None else 3 - quantity)


def test_legacy_finish_is_preserved_without_inventing_quantity(run_case):
    case = run_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    projections = case.projections()
    old = next(row for row in projections if row.execution_state == "complete")
    assert old.completion_basis == "legacy_finish_event"
    assert old.known_completed_quantity == 0
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
    assert result.schedule_input.execution_completed_op_ids == {case.op_id}
    assert all(payload.scheduled_op_ids == {case.op_id, successor} for payload in result.candidate_payloads.values())


def test_unselected_legacy_execution_still_reserves_actual_resources(run_case):
    case = run_case
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    case.batch("B2")
    selected = case.operation("B2")
    case.conn.commit()
    projections = case.projections("B2")
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B2"), projections))
    assert result.schedule_input.normalized_batch_ids == ["B2"]
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == {selected}
        assert payload.schedule_rows[0].start_time >= datetime(2026, 9, 9, 10)


def test_completed_marker_without_event_does_not_unlock_original_operation(run_case):
    case = run_case
    case.operation(seq=2)
    case.conn.execute("UPDATE BatchOperations SET status='completed' WHERE id=?", (case.op_id,))
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "input_blocked"
    assert any(row["op_id"] == case.op_id for row in error.value.issues)


def test_explicit_original_lock_is_preserved_even_when_freeze_window_disabled(run_case):
    case = run_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert result.schedule_input.frozen_op_ids == {case.op_id}
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert (rows[case.op_id].start_time, rows[case.op_id].end_time) == (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 10))
        assert rows[successor].start_time >= rows[case.op_id].end_time
