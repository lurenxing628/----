"""Actual four candidates, admission history and exact permanent-ref alignment."""

import sqlite3
from datetime import timedelta

import pytest

from core.models.workbench_run_candidate import local_time
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_candidate_baseline_support import baseline, original_plan
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case
from tests.workbench.test_run_candidate_support import compute, retained


def test_real_four_candidates_compare_only_captured_official_rows(candidate_case):
    case = candidate_case
    plan_ref = original_plan(case, start="2026-09-12 08:00:00", end="2026-09-12 10:00:00")
    run_ref, refs = compute(case)
    assert len(refs) == 4
    with retained(case.conn):
        for ref in refs:
            data, _ = baseline(case, ref)
            assert data["candidate"]["run_ref"] == run_ref
            assert data["baseline"]["baseline_ref"] == plan_ref
            assert data["baseline"]["comparison_available"]
            assert data["operation_count"] == data["full_operation_count"] == 1
            item = data["comparisons"][0]
            old, new = item["baseline_segments"][0], item["candidate"]
            assert len(item["operation_ref"]) == len(item["row_ref"]) == len(old["row_ref"]) == 48
            assert old["row_ref"] != item["row_ref"]
            assert item["status"] == "matched" and not item["execution_affected"]
            assert old["start"] == "2026-09-12T08:00:00" and old["elapsed_hours"] == 2
            assert item["delta"]["end_hours"] == (local_time(new["end"]) - local_time(old["end"])).total_seconds() / 3600
            assert item["delta"]["machine_changed"] is False
            assert item["delta"]["operator_changed"] is False
            assert item["delta"]["supplier_changed"] is None
            assert item["improvement_assessment"] is None


def test_no_original_plan_is_explicit_and_not_a_zero_baseline(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    data, _ = baseline(case, refs[0])
    assert data["baseline"] == {"baseline_ref": None, "kind": "admission_official", "available": False,
                                "captured_task_count": 0, "comparison_available": False,
                                "reason": {"code": "no_admission_baseline", "message": "受理时没有正式初始计划，不能计算相对改善。"}}
    item = data["comparisons"][0]
    assert item["status"] == "newly_scheduled" and item["baseline_segments"] == []
    assert all(value is None for value in item["delta"].values())


def test_current_rename_replacement_and_later_plan_changes_leave_read_unchanged(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    original = baseline(case, refs[0])
    case.conn.execute("UPDATE Machines SET name='Later name'")
    case.conn.execute("UPDATE Operators SET name='Later person'")
    case.conn.execute("UPDATE Schedule SET start_time='2026-10-01T00:00:00',end_time='2026-10-02T00:00:00'")
    case.conn.commit()
    case.plan(8, [case.op_id])
    case.conn.execute("DELETE FROM Schedule WHERE version=7")
    case.conn.commit()
    with retained(case.conn):
        assert baseline(case, refs[0]) == original
    denied = {"Schedule", "ScheduleHistory", "Machines", "Operators", "BatchOperations", "WorkbenchPlanSourceRefs"}

    def authorize(action, first, *rest):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and first in denied else sqlite3.SQLITE_OK

    case.conn.set_authorizer(authorize)
    assert baseline(case, refs[0]) == original


def test_skipped_zero_quantity_and_unselected_baseline_are_not_improvements(candidate_case):
    case = candidate_case
    # Zero quantity alone is eligible; actual unreadiness must still exclude work.
    case.batch("ZERO", quantity=0, ready_status="no")
    zero = case.operation("ZERO")
    case.batch("UNSELECTED")
    outside = case.operation("UNSELECTED")
    original_plan(case, [case.op_id, zero, outside])
    _, refs = compute(case, case.settings("B1", "ZERO"))
    data, _ = baseline(case, refs[0], range_start="2027-01-01T00:00:00", range_end="2027-01-02T00:00:00")
    rows = {row["batch_label"]: row for row in data["comparisons"]}
    assert set(rows) == {"ZERO", "UNSELECTED"}
    assert rows["ZERO"]["quantity"] == 0
    assert rows["ZERO"]["execution_at_generation"]["remaining_quantity"] == 0
    assert rows["ZERO"]["status"] == "unscheduled"
    assert rows["ZERO"]["candidate_operation_status"] == "skipped"
    assert rows["UNSELECTED"]["status"] == "baseline_only"
    for row in rows.values():
        assert row["row_ref"] is None and row["candidate"] is None
        assert all(value is None for value in row["delta"].values())
        assert row["improvement_assessment"] is None
    assert data["improvement_assessment"] is None


@pytest.mark.parametrize("setup", [0, 2])
def test_zero_quantity_scheduled_work_and_old_baseline_are_not_optimization_scores(candidate_case, setup):
    case = candidate_case
    case.batch("ZERO", quantity=0)
    zero = case.operation("ZERO", setup_hours=setup, unit_hours=7)
    case.batch("UNSELECTED")
    outside = case.operation("UNSELECTED")
    plan_ref = original_plan(case, [case.op_id, zero, outside],
        start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    zero_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs "
        "WHERE kind='operation' AND source_key=? AND active=1", (str(zero),)).fetchone()[0]
    _, refs = compute(case, case.settings("B1", "ZERO"))
    assert len(refs) == 4
    with retained(case.conn):
        for ref in refs:
            data, _ = baseline(case, ref)
            rows = {row["batch_label"]: row for row in data["comparisons"]}
            assert set(rows) == {"B1", "ZERO", "UNSELECTED"}
            assert data["baseline"]["baseline_ref"] == plan_ref and data["improvement_assessment"] is None
            row = rows["ZERO"]
            old, = row["baseline_segments"]
            new = row["candidate"]
            assert row["operation_ref"] == zero_ref and row["quantity"] == 0
            assert row["execution_at_generation"]["remaining_quantity"] == 0
            assert row["status"] == "matched" and row["candidate_operation_status"] == "scheduled"
            assert row["row_ref"] == new["row_ref"] and row["row_ref"] != old["row_ref"]
            assert old["start"] == "2026-09-12T08:00:00" and old["end"] == "2026-09-12T10:00:00"
            assert old["elapsed_hours"] == 2 and old["interval_comparable"] is True
            assert old.get("event_kind") != "point" and old["effective_processing_hours"] is None
            assert new["elapsed_hours"] == setup and row["delta"]["elapsed_hours"] == setup - 2
            assert row["delta"]["effective_processing_hours"] is None and row["improvement_assessment"] is None
            if setup == 0:
                assert new["start"] == new["end"] and new["duration_seconds"] == 0
                assert new["event_kind"] == "point" and new["occupies_resources"] is False
            else:
                assert new["start"] < new["end"] and new.get("event_kind") != "point"
            outside_row = rows["UNSELECTED"]
            assert outside_row["status"] == "baseline_only" and outside_row["selected_at_admission"] is False
            assert outside_row["candidate"] is None and outside_row["row_ref"] is None
            assert all(value is None for value in outside_row["delta"].values())
            assert outside_row["improvement_assessment"] is None
            future, _ = baseline(case, ref, range_start="2027-01-01T00:00:00", range_end="2027-01-02T00:00:00")
            assert future["comparisons"] == [outside_row] and future["full_operation_count"] == 3
            at = local_time(new["start"])
            included, _ = baseline(case, ref, range_start=at.isoformat(), range_end=(at + timedelta(seconds=1)).isoformat())
            assert row in included["comparisons"]
            excluded, _ = baseline(case, ref, range_start=(at - timedelta(seconds=1)).isoformat(), range_end=at.isoformat())
            assert zero_ref not in {item["operation_ref"] for item in excluded["comparisons"]}


def test_legacy_equal_interval_is_not_point_evidence_or_a_zero_improvement_baseline(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    original_plan(case, start="2026-09-12T08:00:00", end="2026-09-12T08:00:00")
    _, refs = compute(case)
    with retained(case.conn):
        for ref in refs:
            data, _ = baseline(case, ref)
            row, = data["comparisons"]
            old, = row["baseline_segments"]
            assert old["start"] == old["end"] == "2026-09-12T08:00:00"
            assert old["elapsed_hours"] == 0 and old["interval_comparable"] is False
            assert old.get("event_kind") != "point" and "occupies_resources" not in old
            assert row["candidate"]["event_kind"] == "point"
            assert row["status"] == "not_comparable" and row["comparison_available"] is False
            assert "baseline_interval_unavailable" in {reason["code"] for reason in row["reasons"]}
            assert all(value is None for value in row["delta"].values())
            assert row["improvement_assessment"] is data["improvement_assessment"] is None
            assert data["baseline"]["comparison_available"] is False


def test_range_is_half_open_union_and_keeps_full_opposite_interval(candidate_case):
    case = candidate_case
    original_plan(case, start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    _, refs = compute(case)
    data, _ = baseline(case, refs[0])
    item = data["comparisons"][0]
    for interval in (item["candidate"], item["baseline_segments"][0]):
        start = local_time(interval["start"]) + timedelta(minutes=1)
        end = start + timedelta(minutes=1)
        filtered, _ = baseline(case, refs[0], range_start=start.isoformat(), range_end=end.isoformat())
        assert filtered["comparisons"] == [item]
    empty, _ = baseline(case, refs[0], range_start="2026-09-12T10:00:00", range_end="2026-09-13T00:00:00")
    assert empty["comparisons"] == [] and empty["full_operation_count"] == 1
    between, _ = baseline(case, refs[0], range_start=item["candidate"]["end"], range_end="2026-09-12T08:00:00")
    assert between["comparisons"] == []


def test_zero_deltas_are_real_numbers_not_missing(candidate_case):
    case = candidate_case
    original_plan(case, start="2026-09-09T08:00:00", end="2026-09-09T10:00:00")
    case.operation(seq=2)
    case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    _, refs = compute(case)
    data, _ = baseline(case, refs[0])
    row = next(item for item in data["comparisons"] if item["baseline_segments"])
    assert [row["delta"][key] for key in ("start_hours", "end_hours", "elapsed_hours")] == [0, 0, 0]
    assert row["candidate"]["locked"] is True


def test_completed_execution_is_visible_without_optimization_attribution(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    original_plan(case)
    case.command("create", case.task(7, case.op_id), case.values(3, effective_processing_hours=0))
    _, refs = compute(case)
    data, _ = baseline(case, refs[0])
    row = next(item for item in data["comparisons"] if item["baseline_segments"])
    assert row["execution_at_generation"]["execution_state"] == "complete"
    assert row["execution_at_generation"]["remaining_quantity"] == 0
    assert row["execution_affected"] and row["improvement_assessment"] is None
    assert row["candidate"]["effective_processing_hours"] is None
    assert row["candidate"]["elapsed_hours"] == 2


def test_second_run_keeps_its_own_admission_baseline(candidate_case):
    case = candidate_case
    original_plan(case)
    _, first = compute(case)
    expected = baseline(case, first[0])
    case.plan(8, [case.op_id], start="2026-09-15T08:00:00", end="2026-09-15T10:00:00")
    admitted = case.accept(key="baseline-second-run")
    result = WorkbenchRunWorker(case.conn).execute(admitted["run_ref"])
    second, _ = baseline(case, result["candidates"][0]["candidate_ref"])
    assert baseline(case, first[0]) == expected
    assert second["baseline"]["baseline_ref"] != expected[0]["baseline"]["baseline_ref"]
    assert second["comparisons"][0]["baseline_segments"][0]["start"] == "2026-09-15T08:00:00"


def test_resource_changes_use_captured_permanent_refs_not_labels(candidate_case):
    case = candidate_case
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Old resource','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Old person')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    original_plan(case)
    case.conn.execute("UPDATE Schedule SET machine_id='M2',operator_id='O2'")
    case.conn.commit()
    _, refs = compute(case)
    data, _ = baseline(case, refs[0])
    item = data["comparisons"][0]
    assert item["delta"]["machine_changed"] and item["delta"]["operator_changed"]
    assert item["baseline_segments"][0]["machine"]["label"] == "Old resource"
    assert item["candidate"]["machine"]["label"] == "Original lathe"


def test_unknown_and_zero_report_quantities_are_not_guessed_as_remaining_time(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    original_plan(case)
    case.event(case.op_id, "start", version=7)
    case.event(case.op_id, "finish", version=7)
    _, refs = compute(case)
    row = next(item for item in baseline(case, refs[0])[0]["comparisons"] if item["baseline_segments"])
    assert row["execution_at_generation"]["legacy_fact_count"] == 2
    assert row["execution_at_generation"]["known_completed_quantity"] == 0
    assert row["execution_at_generation"]["unknown_record_count"] == 1
    assert row["execution_at_generation"]["remaining_quantity"] is None
    assert row["execution_affected"] and row["improvement_assessment"] is None
