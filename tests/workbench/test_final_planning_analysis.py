"""ANA001/003 use the real worker and immutable source, not visible task totals."""

import sqlite3
from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_analysis import operation_metrics
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.dashboard_candidate_comparison import read_candidate_comparison
from core.services.workbench.run_candidate_analysis import read_candidate_analysis
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from tests.workbench.test_run_candidate_baseline_support import baseline, original_plan
from tests.workbench.test_run_candidate_support import api, compute, connect, retained
from tests.workbench.test_run_candidate_support import candidate_case as _case  # noqa: F401


def test_full_admission_metrics_reuse_delivery_comparison_and_ignore_visible_scope(candidate_case):
    case = candidate_case
    case.batch("B2", due_date="2026-09-08")
    second = case.operation("B2")
    case.batch("OUTSIDE")
    outside = case.operation("OUTSIDE")
    original_plan(case, [case.op_id, second, outside], start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    run_ref, refs = compute(case, case.settings("B1", "B2"))
    with retained(case.conn):
        for ref in refs:
            data, state = read_candidate_analysis(case.conn, ref)
            comparison, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(ref,
                range_start="2026-09-09T00:00:00", range_end="2026-09-26T00:00:00"))
            assert data["candidate_ref"] == ref and data["run_ref"] == run_ref
            assert data["batches"] == comparison["batches"]
            assert data["metrics"]["overdue_count"]["value"] == comparison["summary"]["after"]["overdue_count"] == 1
            assert data["metrics"]["total_tardiness_hours"]["value"] == comparison["summary"]["after"]["total_tardiness_hours"]
            assert data["metrics"]["changed_operation_count"]["value"] == 2
            assert data["metrics"]["machine_change_count"]["value"] == 0
            assert len(data["operations"]["operation_refs"]) == 2
            assert set(data["batch_refs"]) == {case.ref("batch", "B1"), case.ref("batch", "B2")}
            assert data["basis"]["recommendation"] is None and not data["basis"]["current_entities_consulted"]
            empty, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref,
                range_start="2027-01-01T00:00:00", range_end="2027-01-02T00:00:00", batch_ref=case.ref("batch", "B1")))
            assert empty["task_count"] == 0
            assert read_candidate_analysis(case.conn, ref) == (data, state)


def test_missing_baseline_and_due_date_keep_unknown_totals_and_known_subtotals(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET due_date='2026-09-08' WHERE batch_id='B1'")
    case.batch("NO-DUE", due_date=None)
    case.operation("NO-DUE")
    case.conn.commit()
    run_ref, refs = compute(case, case.settings("B1", "NO-DUE"))
    with retained(case.conn):
        data, _ = read_candidate_analysis(case.conn, refs[0])
    assert data["run_ref"] == run_ref and data["baseline"]["baseline_ref"] is None
    for key in ("changed_operation_count", "machine_change_count"):
        assert data["metrics"][key]["value"] is None
        assert data["metrics"][key]["known_subtotal"] == 0
        assert data["metrics"][key]["unknown_count"] == data["metrics"][key]["total_count"] == 2
        assert data["metrics"][key]["reason"]
    assert data["metrics"]["overdue_count"]["value"] is None
    assert data["metrics"]["overdue_count"]["known_subtotal"] == 1
    assert data["metrics"]["overdue_count"]["unknown_count"] == 1
    assert data["metrics"]["total_tardiness_hours"]["value"] is None
    assert data["metrics"]["total_tardiness_hours"]["known_subtotal"] > 0
    assert all(value is None for value in data["delivery_deltas"].values())
    assert all(row["before"]["planned_finish"] is None for row in data["batches"])


@pytest.mark.parametrize("unknown", [False, True])
def test_machine_changes_are_permanent_id_comparisons_not_changeovers(candidate_case, unknown):
    case = candidate_case
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Original lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Original operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    original_plan(case)
    case.conn.execute("UPDATE Schedule SET machine_id=?,operator_id=?", (None, None) if unknown else ("M2", "O2"))
    case.conn.commit()
    _, refs = compute(case)
    with retained(case.conn):
        data, _ = read_candidate_analysis(case.conn, refs[0])
    m = data["metrics"]["machine_change_count"]
    assert m["value"] is None if unknown else m["value"] == 1
    assert m["known_subtotal"] == (0 if unknown else 1)
    assert m["unknown_count"] == int(unknown)
    assert m["total_count"] == 1
    assert len(data["operations"]["machine_changed_operation_refs"]) == (0 if unknown else 1)


def test_model_rejects_partial_or_duplicate_identity_and_keeps_multiple_segments_unknown(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    full, _ = baseline(case, refs[0])
    batch_refs = full["generation"]["input"]["batch_refs"]
    for change in (lambda dto: dto.update(full_operation_count=2), lambda dto: dto["comparisons"].append(deepcopy(dto["comparisons"][0]))):
        altered = deepcopy(full)
        change(altered)
        with pytest.raises(WorkbenchCommandRejected) as error:
            operation_metrics(altered, batch_refs)
        assert error.value.code == "candidate_analysis_incomplete"
    altered = deepcopy(full)
    row = altered["comparisons"][0]
    row.update(comparison_available=False, status="not_comparable", reasons=[{"code": "baseline_multiple_segments", "message": "Multiple original segments"}])
    row["baseline_segments"].append(deepcopy(row["baseline_segments"][0]))
    metrics, operations = operation_metrics(altered, batch_refs)
    assert metrics["changed_operation_count"]["value"] is None
    assert metrics["machine_change_count"]["value"] is None
    assert operations["issues"][0]["reasons"][0]["code"] == "baseline_multiple_segments"


def test_frozen_analysis_survives_current_edits_reopen_and_denied_live_reads(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    expected = read_candidate_analysis(case.conn, refs[0])
    case.conn.execute("UPDATE Batches SET due_date='2027-01-01'")
    case.conn.execute("UPDATE Machines SET name='Later name'")
    case.conn.commit()
    case.plan(8, [case.op_id])
    denied = {"Batches", "Machines", "Operators", "Schedule", "ScheduleHistory", "BatchOperations", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs"}
    conn = connect(case.path)
    try:
        before = case.path.read_bytes()
        conn.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and name in denied else sqlite3.SQLITE_OK)
        assert read_candidate_analysis(conn, refs[0]) == expected
        assert conn.total_changes == 0 and case.path.read_bytes() == before
    finally:
        conn.close()


@pytest.mark.parametrize("query", [{"batch_ref": "a" * 48}, {"range_start": "2026-09-09T00:00:00"}, {"run_ref": "a" * 48}])
def test_analysis_endpoint_never_accepts_a_subset_as_whole(candidate_case, query):
    case = candidate_case
    _, refs = compute(case)
    client, _ = api(case)
    before = case.path.read_bytes()
    response = client.get("/api/workbench/v1/scheduling/candidates/" + refs[0] + "/analysis", query_string=query)
    assert response.status_code == 400 and response.get_json()["committed"] is False
    assert case.path.read_bytes() == before
