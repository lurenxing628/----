"""Malformed, partial and uncertifiable results never issue an adopt WriteContext."""

from datetime import datetime, timedelta

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.run_candidate_adoption_support import (
    INTENT,
    KEY,
    candidate,
    preview,
    rewrite_candidate,
    service,
    snapshot,
)
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import corrupt_update, edit_artifact


@pytest.mark.parametrize("sql", [
    "UPDATE Machines SET name='changed' WHERE machine_id='M1'",
    "UPDATE Operators SET status='inactive' WHERE operator_id='O1'",
    "DELETE FROM OperatorMachine",
    "INSERT INTO WorkCalendar(date,shift_hours) VALUES ('2026-09-09',4)",
    "UPDATE BatchOperations SET unit_hours=unit_hours+1",
    "UPDATE Batches SET ready_date='2026-09-20'",
    "UPDATE ScheduleConfig SET config_value='yes' WHERE config_key='freeze_window_enabled'",
])
def test_admission_facts_drift_rejected_even_with_unexpired_token(candidate_case, sql):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    case.conn.execute(sql)
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert error.value.code == "snapshot_stale" and error.value.status == 409
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("change", ["baseline", "execution", "lock"])
def test_official_execution_and_lock_drift_are_409(candidate_case, change):
    case = candidate_case
    case.plan(1, [case.op_id])
    ref = candidate(case)
    token = preview(case, ref)
    if change == "baseline":
        case.plan(2, [case.op_id])
    elif change == "execution":
        case.event(case.op_id, "start")
    else:
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
        case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert error.value.code == "snapshot_stale" and error.value.status == 409
    assert snapshot(case.conn) == before


def _time_change(row, mode):
    start = datetime.fromisoformat(row["start_time"])
    end = datetime.fromisoformat(row["end_time"])
    if mode == "calendar":
        offset = timedelta(hours=15)
        row.update(start_time=(start + offset).isoformat(), end_time=(end + offset).isoformat())
    elif mode == "duration":
        row["end_time"] = (end - timedelta(minutes=1)).isoformat()
    elif mode == "resource":
        row["machine_id"] = "not-a-machine"
    elif mode == "overlap":
        row.update(start_time="2026-09-09T08:00:00", end_time="2026-09-09T08:45:00")
    elif mode == "locked":
        row["locked"] = not row["locked"]


@pytest.mark.parametrize("mode", ["calendar", "duration", "resource", "overlap", "locked"])
def test_completed_and_consistent_artifacts_are_not_legality_proof(candidate_case, mode):
    case = candidate_case
    if mode == "overlap":
        case.batch("B2")
        case.operation("B2")
        case.conn.commit()
    ref = candidate(case, case.settings("B1", "B2") if mode == "overlap" else None)
    rewrite_candidate(case, ref, lambda row: _time_change(row, mode))
    before = snapshot(case.conn)
    result = service(case.conn).preview(ref)
    assert result["validation"]["status"] == "blocked"
    assert result["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before


def test_precedence_violation_blocked(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    case.conn.commit()
    ref = candidate(case)

    def violate(row):
        if row["op_id"] == second:
            row.update(start_time="2026-09-09T08:00:00", end_time="2026-09-09T08:45:00")

    rewrite_candidate(case, ref, violate)
    assert service(case.conn).preview(ref)["validation"]["can_adopt"] is False


def test_scope_cannot_drop_unselected_official_arrangements(candidate_case):
    case = candidate_case
    case.plan(1, [case.op_id])
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    ref = candidate(case, case.settings("B2"))
    result = service(case.conn).preview(ref)
    assert result["validation"]["issues"][0]["code"] == "official_scope_not_covered"


def test_complete_single_piece_candidate_has_read_only_adoption_evidence(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET piece_id='single-piece'")
    case.conn.execute("UPDATE Batches SET quantity=1")
    case.conn.commit()
    ref = candidate(case)
    before = snapshot(case.conn)
    result = service(case.conn).preview(ref)
    assert result["validation"]["can_adopt"] is True, result
    assert result["validation"]["issues"] == []
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("kind", ["partial", "corrupt", "missing_row", "missing_payload"])
def test_partial_and_broken_candidates_stay_blocked(candidate_case, kind):
    case = candidate_case
    if kind == "partial":
        case.operation(seq=2, unit_hours=100)
        case.conn.commit()
    ref = candidate(case, case.settings(end_date="2026-09-09") if kind == "partial" else None)
    if kind == "corrupt":
        corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET artifact_json='{' WHERE candidate_ref=?", (ref,))
    elif kind == "missing_row":
        corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))
    elif kind == "missing_payload":
        edit_artifact(case, ref, lambda data: data.pop("validated_payload"))
    before = snapshot(case.conn)
    data = service(case.conn).preview(ref)
    assert data["validation"]["can_adopt"] is False and data["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before


def test_no_token_wrong_candidate_and_no_schema_never_write(candidate_case):
    case = candidate_case
    ref = candidate(case)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).adopt(ref, None, KEY, INTENT)
    assert snapshot(case.conn) == before
    case.conn.execute("DROP TABLE ScheduleVersionSeq")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).preview(ref)
    assert error.value.code == "adoption_schema_unavailable"
    assert case.conn.execute("SELECT 1 FROM sqlite_master WHERE name='ScheduleVersionSeq'").fetchone() is None


def test_missing_admission_receipt_cannot_authorize_a_candidate(candidate_case):
    case = candidate_case
    ref = candidate(case)
    case.conn.execute("PRAGMA foreign_keys=OFF")
    try:
        corrupt_update(case.conn, "WorkbenchCommandReceipts", "DELETE FROM WorkbenchCommandReceipts WHERE action='scheduling.run'")
    finally:
        case.conn.execute("PRAGMA foreign_keys=ON")
    data = service(case.conn).preview(ref)
    assert data["validation"]["can_adopt"] is False
    assert data["validation"]["issues"][0]["code"] == "run_result_inconsistent"


def test_explicit_empty_baseline_does_not_hide_orphan_official_rows(candidate_case):
    case = candidate_case
    case.conn.execute("INSERT INTO Schedule(op_id,machine_id,operator_id,start_time,end_time,version) "
                      "VALUES (?,'M1','O1','2026-09-09 08:00:00','2026-09-09 08:45:00',1)", (case.op_id,))
    case.conn.commit()
    ref = candidate(case)
    data = service(case.conn).preview(ref)
    assert data["validation"]["issues"][0]["code"] == "empty_baseline_inconsistent"


def test_another_adoption_key_cannot_reapply_the_same_candidate(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    service(case.conn).adopt(ref, token, KEY, INTENT)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(ref, token, KEY + "different", INTENT)
    assert error.value.code == "snapshot_stale" and snapshot(case.conn) == before


def test_preview_context_cannot_authorize_another_candidate(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    other = case.conn.execute("SELECT candidate_ref FROM WorkbenchRunCandidates WHERE candidate_ref<>? LIMIT 1", (ref,)).fetchone()[0]
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(other, token, KEY, INTENT)
    assert error.value.code == "stale_write" and snapshot(case.conn) == before


def test_microsecond_candidate_never_gets_rounded_into_official_rows(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    case.conn.commit()
    ref = candidate(case)
    data = service(case.conn).preview(ref)
    assert data["validation"]["issues"][0]["code"] == "candidate_time_precision_unsupported"


@pytest.mark.parametrize("summary", [b"\x00\xffbroken-current", '{"is_simulation":true}'])
def test_largest_history_version_is_not_assumed_to_be_executable_official(candidate_case, summary):
    case = candidate_case
    case.plan(1, [case.op_id])
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=?", (summary,))
    case.conn.commit()
    ref = candidate(case)
    before = snapshot(case.conn)
    data = service(case.conn).preview(ref)
    assert data["validation"]["can_adopt"] is False
    assert data["validation"]["issues"][0]["code"] == "baseline_not_current_official"
    assert snapshot(case.conn) == before
