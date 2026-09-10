"""Read-source corruption must not produce an apparently successful comparison."""

import json
import sqlite3
from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_candidate_facts import _columns
from tests.workbench.run_candidate_baseline_support import baseline, legacy_blob_events, original_plan
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.run_candidate_support import compute, corrupt_update, edit_capture, retained


@pytest.mark.parametrize("field,value", [("baseline_json", "{}"), ("baseline_json", b"{}"), ("execution_json", "[]"),
                                        ("normalized_input_json", "{}"), ("facts_json", "{}")])
def test_missing_or_unhashed_read_sources_fail_closed(candidate_case, field, value):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET " + field + "=?", (value,))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code in ("candidate_baseline_invalid", "candidate_artifact_invalid")


@pytest.mark.parametrize("edit", [lambda value: value.update(version=8), lambda value: value.update(plan_ref="a" * 48),
                                  lambda value: value["rows"][0].update(start_time="2020-01-01T00:00:00"),
                                  lambda value: value.update(rows=[])])
def test_baseline_copy_must_match_hashed_archived_schedule(candidate_case, edit):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    edit_capture(case, "baseline_json", edit)
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_baseline_invalid"


@pytest.mark.parametrize("table", ["Schedule", "ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
                                  "WorkbenchProductionReports", "WorkbenchExecutionLegacyFacts"])
def test_absent_hashed_source_table_is_not_an_empty_baseline(candidate_case, table):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    edit_capture(case, "facts_json", lambda facts: facts["tables"].pop(table))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected):
        baseline(case, refs[0])


def test_candidate_operation_ref_cannot_be_rebound_to_another_run_operation(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    case.batch("LATER")
    other = case.operation("LATER")
    other_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1", (str(other),)).fetchone()[0]
    case.conn.commit()
    corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "UPDATE WorkbenchRunCandidateTasks SET operation_ref=? WHERE candidate_ref=?", (other_ref, refs[0]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_baseline_invalid"


def test_tampered_execution_and_receipt_cannot_override_archived_evidence(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    edit_capture(case, "execution_json", lambda rows: rows[0].update(known_completed_quantity=1))
    receipt = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts").fetchone()[0])
    receipt["dispositions"][0]["execution"]["known_completed_quantity"] = 1
    corrupt_update(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET result_json=?", (json.dumps(receipt),))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_baseline_invalid"


@pytest.mark.parametrize("field", ["facts_json", "execution_json", "baseline_json", "normalized_input_json"])
def test_oversized_capture_rejected_before_loading(candidate_case, monkeypatch, field):
    import core.services.workbench.run_candidate_storage as storage
    case = candidate_case
    _, refs = compute(case)
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET " + field + "=?", ('{"payload":"' + "x" * 300000 + '"}',))
    monkeypatch.setattr(storage, "MAX_FACT_BYTES", 250000)
    statements = []
    case.conn.set_trace_callback(statements.append)
    with pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_capacity_exceeded"
    assert not any("SELECT normalized_input_json,execution_json" in sql for sql in statements)


@pytest.mark.parametrize("end_value,expected", [("2026-09-09T08:00:00", 0),
                                                ({"sqlite_blob_base64": "cmF3LXRpbWU="}, None),
                                                ("2026-09-08T08:00:00", None)])
def test_zero_blob_and_negative_historical_intervals_are_explicitly_incomparable(candidate_case, end_value, expected):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)

    def change(facts):
        sql = next(row[3] for row in facts["schema"] if row[0:2] == ["table", "Schedule"])
        columns = _columns(sql, "Schedule")
        facts["tables"]["Schedule"][0][columns.index("end_time")] = end_value

    edit_capture(case, "facts_json", change)
    edit_capture(case, "baseline_json", lambda value: value["rows"][0].update(end_time=end_value))
    data, _ = baseline(case, refs[0])
    row = data["comparisons"][0]
    assert row["status"] == "not_comparable" and row["baseline_segments"][0]["elapsed_hours"] == expected
    assert row["delta"]["elapsed_hours"] is None
    assert "cmF3LXRpbWU=" not in json.dumps(data)


def test_outer_transaction_and_caller_authorizer_survive(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    case.conn.execute("BEGIN")
    case.conn.execute("UPDATE Machines SET name='Uncommitted caller value'")

    def authorize(action, *args):
        return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) else sqlite3.SQLITE_OK

    case.conn.set_authorizer(authorize)
    data, _ = baseline(case, refs[0])
    assert case.conn.in_transaction and data["comparisons"][0]["baseline_segments"][0]["machine"]["label"] == "Original lathe"
    with pytest.raises(sqlite3.DatabaseError):
        case.conn.execute("UPDATE Machines SET name='Denied'")
    case.conn.rollback()


def test_real_legacy_blob_facts_survive_admission_compute_and_baseline_read(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    original_plan(case)
    legacy_blob_events(case)
    original = [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    archived = [tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    _, refs = compute(case)
    with retained(case.conn):
        data, _ = baseline(case, refs[0])
    row = next(item for item in data["comparisons"] if item["baseline_segments"])
    assert row["execution_affected"] and row["execution_at_generation"]["execution_state"] == "complete"
    assert row["execution_at_generation"]["known_completed_quantity"] == 0
    assert row["execution_at_generation"]["remaining_quantity"] is None
    assert row["execution_at_generation"]["legacy_unavailable_field_count"] == 4
    assert "old-note" not in json.dumps(data) and "old-time" not in json.dumps(data)
    assert original == [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    assert archived == [tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    assert [tuple(row) for row in case.conn.execute("SELECT typeof(remark),typeof(created_at) FROM WorkbenchExecutionLegacyFacts")] == [("blob", "blob")] * 2


def test_archived_multisegment_envelope_keeps_all_segments_without_picking_one(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    # Historical-shape fixture only: current admission itself rejects duplicate official tasks.
    def change(facts):
        def columns(table):
            sql = next(row[3] for row in facts["schema"] if row[0:2] == ["table", table])
            return _columns(sql, table)

        schedule = facts["tables"]["Schedule"]
        schedule.append(deepcopy(schedule[0]))
        schedule[-1][columns("Schedule").index("id")] = 2
        names = columns("WorkbenchPlanSourceRefs")
        sources = facts["tables"]["WorkbenchPlanSourceRefs"]
        row = deepcopy(next(row for row in sources if row[names.index("kind")] == "schedule_row"))
        row[names.index("ref")] = "a" * 48
        row[names.index("source_key")] = "2"
        sources.append(row)
        names = columns("WorkbenchTaskRefs")
        row = deepcopy(facts["tables"]["WorkbenchTaskRefs"][0])
        row[names.index("ref")] = "b" * 48
        row[names.index("row_ref")] = "a" * 48
        facts["tables"]["WorkbenchTaskRefs"].append(row)

    edit_capture(case, "facts_json", change)
    edit_capture(case, "baseline_json", lambda value: value["rows"].append({**value["rows"][0], "id": 2}))
    with retained(case.conn):
        data, _ = baseline(case, refs[0])
    row = data["comparisons"][0]
    assert row["status"] == "not_comparable" and len(row["baseline_segments"]) == 2
    assert {segment["row_ref"] for segment in row["baseline_segments"]} == {"a" * 48, row["baseline_segments"][0]["row_ref"]}
    assert row["delta"]["elapsed_hours"] is None
    assert any(reason["code"] == "baseline_multiple_segments" for reason in row["reasons"])


def test_output_capacity_returns_error_instead_of_truncating(candidate_case, monkeypatch):
    import core.services.workbench.run_candidate_baseline as module
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 50)
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_capacity_exceeded"


def test_valid_but_contradictory_input_window_does_not_relabel_candidate(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    edit_capture(case, "normalized_input_json", lambda value: value.update(start_date="2026-09-20"))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        baseline(case, refs[0])
    assert error.value.code == "candidate_baseline_invalid"
