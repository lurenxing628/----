"""Explicit invalid/absent/oversized sources, without writes or fallback."""

import json
import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateCatalogScope, RunCandidateReadScope
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from tests.workbench.test_run_candidate_support import (
    BASE,
    api,
    compute,
    corrupt_update,
    edit_artifact,
    edit_capture,
    read,
    retained,
)
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case


@pytest.mark.parametrize("query", ["size=0", "size=51", "page=0", "page=1.0", "size=1&size=2",
                                  "status=ready", "sort=cost", "version=1", "plan_ref=anything"])
def test_bad_catalog_scope_never_reaches_database(candidate_case, query):
    client, statements = api(candidate_case)
    response = client.get(BASE + "/runs/" + "a" * 48 + "/candidates?" + query)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"
    assert statements == []


@pytest.mark.parametrize("query", ["range_start=2026-09-09T01:00:00", "range_start=bad&range_end=bad",
                                  "range_start=2026-09-09T01:00:00Z&range_end=2026-09-10T01:00:00Z",
                                  "batch_ref=123", "op_id=1", "page=1", "sort=cost", "sort=start&sort=end"])
def test_bad_workspace_scope_never_reaches_database(candidate_case, query):
    client, statements = api(candidate_case)
    response = client.get(BASE + "/candidates/" + "a" * 48 + "?" + query)
    assert response.status_code == 400 and statements == []


def test_unknown_refs_and_absent_schema_never_install(candidate_case):
    case = candidate_case
    client, _ = api(case)
    with retained(case.conn):
        for ref, status in (("123", 400), ("a" * 48, 404)):
            response = client.get(BASE + "/candidates/" + ref)
            assert response.status_code == status
    case.conn.execute("DROP TABLE WorkbenchRunCandidateTasks")
    case.conn.commit()
    with retained(case.conn):
        response = client.get(BASE + "/candidates/" + "a" * 48)
        assert response.status_code == 503 and response.get_json()["error"]["code"] == "candidate_schema_unavailable"


def test_missing_task_rows_and_wrong_operation_binding_fail_explicitly(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (refs[0],))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert error.value.code == "candidate_artifact_invalid"


@pytest.mark.parametrize("value", [b"{}", "{broken", '{"status":"completed","status":"failed"}', '{"metrics":NaN}', "[]"])
def test_bad_or_byte_artifact_never_becomes_empty_success(candidate_case, value):
    case = candidate_case
    run_ref, refs = compute(case)
    corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?", (value, refs[0]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).catalog(RunCandidateCatalogScope(run_ref))
    assert error.value.code == "candidate_artifact_invalid"


def test_missing_snapshot_source_and_blob_name_are_data_gaps(candidate_case):
    case = candidate_case
    _, refs = compute(case)

    def change(facts):
        facts["tables"]["Parts"] = []
        sql = next(row[3] for row in facts["schema"] if row[0] == "table" and row[1] == "Machines")
        from core.services.workbench.run_candidate_facts import _columns
        index = _columns(sql, "Machines").index("name")
        facts["tables"]["Machines"][0][index] = {"sqlite_blob_base64": "c2VjcmV0"}

    edit_capture(case, "facts_json", change)
    with retained(case.conn):
        data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    row = data["tasks"][0]
    assert row["part_label"] is None and row["machine"]["label"] is None
    assert any(item["code"] == "blob_metadata" for item in row["data_gaps"])
    assert any(item["code"] == "source_missing" for item in row["data_gaps"])
    assert "c2VjcmV0" not in json.dumps(data)


@pytest.mark.parametrize("sql", ["CREATE TABLE BatchOperations AS SELECT 42", "ATTACH DATABASE ':memory:' AS other",
                                "CREATE TABLE BatchOperations (id INTEGER); DELETE FROM Batches"])
def test_captured_schema_is_not_an_executable_data_program(candidate_case, sql):
    case = candidate_case
    _, refs = compute(case)

    def change(facts):
        next(row for row in facts["schema"] if row[0] == "table" and row[1] == "BatchOperations")[3] = sql

    edit_capture(case, "facts_json", change)
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected):
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))


@pytest.mark.parametrize("field", ["facts_json", "execution_json", "baseline_json", "normalized_input_json"])
def test_oversized_history_checked_before_materialization(candidate_case, monkeypatch, field):
    import core.services.workbench.run_candidate_storage as storage
    case = candidate_case
    _, refs = compute(case)
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET " + field + "=?", ('{"history":"' + "x" * 300000 + '"}',))
    monkeypatch.setattr(storage, "MAX_FACT_BYTES", 250000)
    statements = []
    case.conn.set_trace_callback(statements.append)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert error.value.code == "candidate_capacity_exceeded"
    assert not any("SELECT normalized_input_json,execution_json" in sql for sql in statements)


def test_existing_transaction_and_authorizer_are_preserved(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    case.conn.execute("BEGIN")
    case.conn.execute("UPDATE Machines SET name='Outer transaction only'")

    def authorizer(action, *args):
        return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) else sqlite3.SQLITE_OK

    case.conn.set_authorizer(authorizer)
    data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert case.conn.in_transaction and data["tasks"][0]["machine"]["label"] == "Original lathe"
    with pytest.raises(sqlite3.DatabaseError):
        case.conn.execute("UPDATE Machines SET name='Must still be rejected'")
    case.conn.rollback()


def test_public_field_whitelist_omits_private_engine_history(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    edit_artifact(case, refs[0], lambda artifact: artifact.update(version=999, op_id=98765,
                  history={"facts_json": "PRIVATE-CAPTURE-SECRET"}, failure_reason="private op_id=98765"))
    client, _ = api(case)
    result = read(client, "/candidates/" + refs[0])
    assert "PRIVATE-CAPTURE-SECRET" not in json.dumps(result) and "98765" not in json.dumps(result)


def test_missing_captured_operation_keeps_durable_row_with_null_labels(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    reader = WorkbenchRunCandidateQueryService(case.conn)
    original, _ = reader.workspace(RunCandidateReadScope(refs[0]))
    edit_capture(case, "facts_json", lambda facts: facts["tables"].update(BatchOperations=[]))
    with retained(case.conn):
        data, _ = reader.workspace(RunCandidateReadScope(refs[0]))
    task = data["tasks"][0]
    assert task["row_ref"] == original["tasks"][0]["row_ref"]
    assert task["start"] == original["tasks"][0]["start"]
    assert task["process_label"] is None and task["quantity"] is None
    assert any(item["code"] == "source_missing" for item in task["data_gaps"])


def test_task_payload_disagrees_with_validated_artifact_is_rejected(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    raw = json.loads(case.conn.execute("SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (refs[0],)).fetchone()[0])
    raw["op_id"] += 1
    corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "UPDATE WorkbenchRunCandidateTasks SET payload_json=? WHERE candidate_ref=?",
                   (json.dumps(raw), refs[0]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert error.value.code == "candidate_artifact_invalid"


def test_declared_scope_disagrees_with_validated_rows_is_rejected_in_catalog(candidate_case):
    case = candidate_case
    run_ref, refs = compute(case)
    edit_artifact(case, refs[0], lambda artifact: artifact["validated_payload"].update(scheduled_op_ids=[999999]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).catalog(RunCandidateCatalogScope(run_ref))
    assert error.value.code == "candidate_artifact_invalid"


def test_fresh_v26_has_exact_run_contract_and_reads_do_not_install(candidate_case, monkeypatch):
    from core.infrastructure import workbench_run_schema
    case = candidate_case
    run_ref, refs = compute(case)
    assert len(workbench_run_schema.workbench_run_objects()) == 14
    assert workbench_run_schema.workbench_run_contract_issues(case.conn) == []

    def forbidden(*args, **kwargs):
        pytest.fail("Query must never install or repair schema")

    monkeypatch.setattr(workbench_run_schema, "install_workbench_run_schema", forbidden)
    with retained(case.conn):
        reader = WorkbenchRunCandidateQueryService(case.conn)
        reader.catalog(RunCandidateCatalogScope(run_ref))
        reader.workspace(RunCandidateReadScope(refs[0]))
