"""Real persisted artifacts, full read scope, references and generation-time labels."""

import json

import pytest

from core.models.workbench_run_candidate import RunCandidateCatalogScope, RunCandidateReadScope
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from tests.workbench.test_run_candidate_support import (
    api,
    compute,
    connect,
    edit_artifact,
    public,
    read,
    retained,
)
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case


def test_real_four_candidates_workspace_and_all_tables_readonly(candidate_case):
    case = candidate_case
    run_ref, refs = compute(case)
    reader = WorkbenchRunCandidateQueryService(case.conn)
    with retained(case.conn):
        catalog, _ = reader.catalog(RunCandidateCatalogScope(run_ref))
        assert len(catalog["candidates"]) == 4 and catalog["catalog_complete"]
        for item in catalog["candidates"]:
            assert item["status"] == "completed" and item["completeness"] == "complete"
            assert item["task_count"] == 1 and not item["capabilities"]["adopt"]
            data, fingerprint = reader.workspace(RunCandidateReadScope(item["candidate_ref"]))
            public(data)
            assert data["task_count"] == 1 and data["tasks_complete"]
            task = data["tasks"][0]
            assert len(task["row_ref"]) == len(task["operation_ref"]) == 48
            assert task["quantity"] == 3 and task["due_date"] == "2026-09-25"
            assert task["machine"]["label"] == "Original lathe"
            assert task["operator"]["label"] == "Original operator"
            assert task["execution_at_generation"]["execution_state"] == "unreported"
            assert data["generation"]["current_entities_consulted"] is False
            assert data["generation"]["formal_version_allocated"] is False
            raw = json.loads(case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (item["candidate_ref"],)).fetchone()[0])
            assert data["candidate"]["metrics"]["makespan_hours"]["value"] == raw["metrics"]["makespan_hours"]
    with connect(case.path) as reopened:
        second, value = WorkbenchRunCandidateQueryService(reopened).workspace(RunCandidateReadScope(refs[-1]))
        assert data == second and value == fingerprint


def test_metadata_rename_and_same_key_replacement_never_rebind_history(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    reader = WorkbenchRunCandidateQueryService(case.conn)
    before, fingerprint = reader.workspace(RunCandidateReadScope(refs[0]))
    case.conn.execute("UPDATE Machines SET name='Renamed current machine'")
    case.conn.execute("UPDATE Parts SET part_name='Current part'")
    case.conn.execute("UPDATE BatchOperations SET op_type_name='New process'")
    case.conn.commit()
    assert reader.workspace(RunCandidateReadScope(refs[0])) == (before, fingerprint)
    case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (case.op_id,))
    case.conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,'Replacement','B1',1,'Replacement process')", (case.op_id,))
    case.conn.execute("DELETE FROM OperatorMachine")
    case.conn.execute("DELETE FROM Machines WHERE machine_id='M1'")
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Replacement machine','T1')")
    case.conn.commit()
    with retained(case.conn):
        assert reader.workspace(RunCandidateReadScope(refs[0])) == (before, fingerprint)
    assert before["tasks"][0]["machine"]["ref"] != case.ref("machine", "M1")


def test_partial_preserves_skipped_operations_and_does_not_claim_full_plan(candidate_case):
    case = candidate_case
    case.batch("B2", ready_status="no")
    case.operation("B2")
    case.conn.commit()
    run_ref, refs = compute(case, case.settings("B1", "B2"))
    reader = WorkbenchRunCandidateQueryService(case.conn)
    catalog, _ = reader.catalog(RunCandidateCatalogScope(run_ref, status="partial"))
    assert len(catalog["candidates"]) == 4
    data, _ = reader.workspace(RunCandidateReadScope(refs[0]))
    assert data["candidate"]["status"] == "partial" and data["candidate"]["persisted_status"] == "completed"
    assert data["task_count"] == 1 and data["tasks_complete"]
    assert len(data["unplanned_operations"]) == 1
    assert data["unplanned_operations"][0]["status"] == "skipped"
    assert data["unplanned_operations"][0]["row_ref"] is None


def test_actual_catalog_pagination_filters_and_snapshot_binding(candidate_case):
    case = candidate_case
    run_ref, refs = compute(case)
    client, _ = api(case)
    path = "/runs/" + run_ref + "/candidates"
    first = read(client, path, size=1, sort="label", order="desc")
    token = first["meta"]["snapshot_ref"]
    items = [first["data"]["candidates"][0]]
    for page in (2, 3, 4):
        result = read(client, path, size=1, page=page, sort="label", order="desc", snapshot_ref=token)
        items.extend(result["data"]["candidates"])
    assert len({row["candidate_ref"] for row in items}) == len(refs)
    assert [row["label"] for row in items] == sorted((row["label"] for row in items), reverse=True)
    response = client.get("/api/workbench/v1/scheduling" + path, query_string={"size": 1, "status": "failed", "snapshot_ref": token})
    assert response.status_code == 409
    assert read(client, path, status="failed")["data"]["candidates"] == []


def test_metrics_missing_are_null_with_reason_not_static_numbers(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    edit_artifact(case, refs[0], lambda artifact: artifact.pop("metrics"))
    data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    for key, measure in data["candidate"]["metrics"].items():
        if key != "elapsed_seconds":
            assert measure["value"] is None and measure["reason"]
    assert "cost" not in str(data["candidate"]["metrics"])


@pytest.mark.parametrize("scope", [dict(sort="start"), dict(sort="end", order="desc"), dict(sort="sequence")])
def test_detail_alias_and_half_open_overlap_keep_original_intervals(candidate_case, scope):
    case = candidate_case
    _, refs = compute(case)
    client, _ = api(case)
    path = "/candidates/" + refs[0]
    first = read(client, path, **scope)
    detail = read(client, path + "/workspace", snapshot_ref=first["meta"]["snapshot_ref"], **scope)
    assert detail["data"] == first["data"]
    task = first["data"]["tasks"][0]
    empty = read(client, path, range_start=task["end"], range_end="2026-10-01T00:00:00", **scope)
    assert empty["data"]["tasks"] == []
    assert empty["data"]["candidate_span"] == first["data"]["candidate_span"]
