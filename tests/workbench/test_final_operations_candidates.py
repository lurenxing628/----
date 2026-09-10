"""Real persisted engine candidates; immutable scope and full-batch delivery."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.dashboard_candidate_comparison import read_candidate_comparison
from tests.workbench.run_candidate_baseline_support import original_plan
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.run_candidate_support import compute, retained

RANGE = {"range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00"}


def test_final_operations_four_real_candidates_allow_identical_zero_differences(candidate_case):
    case = candidate_case
    expected_baseline = original_plan(case, start="2026-09-09T08:00:00", end="2026-09-09T08:45:00")
    run_ref, refs = compute(case)
    assert len(set(refs)) == 4
    with retained(case.conn):
        values = [read_candidate_comparison(case.conn, RunCandidateReadScope(ref, **RANGE))[0] for ref in refs]
        for value, ref in zip(values, refs):
            assert value["candidate"]["candidate_ref"] == ref and value["candidate"]["run_ref"] == run_ref
            assert value["baseline"]["baseline_ref"] == expected_baseline
            assert value["batch_refs"] == case.settings()["batch_refs"]
            assert value["summary"]["changeover_delta"] == 0
            assert value["summary"]["before"]["total_tardiness_hours"] == 0
            assert value["summary"]["after"]["total_tardiness_hours"] == 0
            assert value["batches"][0]["delay_delta_hours"] == 0
            assert value["resources"][0]["delta"] == 0
            assert value["machine_changes"]["count"] == 0
            assert value["capabilities"] == {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}
        assert all(value["summary"] == values[0]["summary"] for value in values)


def test_final_operations_comparison_ignores_changed_live_labels_calendar_and_plan(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    scope = RunCandidateReadScope(refs[0], **RANGE)
    before = read_candidate_comparison(case.conn, scope)
    case.conn.execute("UPDATE Machines SET name='Later machine',status='inactive'")
    case.conn.execute("UPDATE Batches SET due_date='2027-01-01'")
    case.conn.execute("UPDATE Schedule SET start_time='2027-01-01T08:00:00',end_time='2027-01-01T16:00:00'")
    case.conn.execute("DELETE FROM WorkCalendar")
    case.conn.commit()
    denied = {"Batches", "BatchOperations", "Machines", "Schedule", "ScheduleHistory", "WorkCalendar", "MachineDowntimes"}
    case.conn.set_authorizer(lambda action, first, *rest: sqlite3.SQLITE_DENY
                            if action == sqlite3.SQLITE_READ and first in denied else sqlite3.SQLITE_OK)
    try:
        assert read_candidate_comparison(case.conn, scope) == before
    finally:
        case.conn.set_authorizer(None)


def test_final_operations_comparison_missing_baseline_is_not_zero_improvement(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    data, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(refs[0], **RANGE))
    assert data["baseline"]["available"] is False
    assert data["summary"]["before"]["overdue_count"] is None
    assert data["summary"]["before"]["changeovers"]["value"] is None
    assert data["summary"]["changeover_delta"] is None
    assert all(row["delay_delta_hours"] is None for row in data["batches"])
    assert all(row["delta"] is None for row in data["resources"])


def test_final_operations_unproven_legacy_zero_interval_is_not_zero_pressure(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    original_plan(case, start="2026-09-12T08:00:00", end="2026-09-12T08:00:00")
    _, refs = compute(case)
    with retained(case.conn):
        data, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(refs[0], **RANGE))
        resource, = data["resources"]
        assert resource["before"]["peak_utilization"] is None
        assert resource["after"]["peak_utilization"] == 0
        assert resource["delta"] is None
        assert data["summary"]["before"]["changeovers"]["value"] is None
        assert data["summary"]["after"]["changeovers"]["value"] == 0
        assert data["summary"]["changeover_delta"] is None


def test_final_operations_local_range_does_not_drop_unscheduled_operations(candidate_case):
    case = candidate_case
    case.operation(seq=2, unit_hours=100)
    original_plan(case)
    _, refs = compute(case)
    data, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(refs[0],
        range_start="2026-09-09T08:00:00", range_end="2026-09-09T09:00:00"))
    assert len(data["batches"]) == 1
    assert data["batches"][0]["after"]["operation_count"] == 2
    assert data["batches"][0]["after"]["schedule_complete"] is False
    assert data["summary"]["after"]["overdue_count"] is None
    assert data["summary"]["after"]["total_tardiness_hours"] is None


def test_final_operations_comparison_rejects_unbound_range_and_foreign_batch(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    with pytest.raises(WorkbenchCommandRejected) as error:
        read_candidate_comparison(case.conn, RunCandidateReadScope(refs[0]))
    assert error.value.code == "invalid_input"
    with pytest.raises(WorkbenchCommandRejected):
        read_candidate_comparison(case.conn, RunCandidateReadScope(refs[0], batch_ref="f" * 48, **RANGE))
