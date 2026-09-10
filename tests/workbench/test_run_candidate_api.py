"""Real full Flask app integration plus terminal catalog and snapshot boundaries."""

import json
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from flask import Blueprint

from tests._support.excel_templates import point_env_at_shared
from tests.workbench.test_run_candidate_support import BASE, api, compute, corrupt_update, read, retained, state
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case
from web.routes.workbench.run_candidates import register_run_candidate_routes


def test_full_app_explicit_registration_only_temporary_connections(candidate_case, tmp_path, monkeypatch):
    case = candidate_case
    run_ref, refs = compute(case)
    for key, path in (("APS_DB_PATH", case.path), ("APS_LOG_DIR", tmp_path / "logs"), ("APS_BACKUP_DIR", tmp_path / "backups")):
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("APS_ENV", "development")
    point_env_at_shared(monkeypatch)
    original = sqlite3.connect
    connections = []

    def guarded(path, *args, **kwargs):
        value = unquote(urlsplit(str(path)).path) if str(path).startswith("file:") else str(path)
        assert value == ":memory:" or Path(value).resolve() == case.path.resolve(), "Unexpected nonfixture SQLite path"
        connections.append(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    from web.bootstrap.entrypoint import create_app_with_mode
    app = create_app_with_mode("default")
    bp = Blueprint("bl_full_app_candidates", __name__)
    register_run_candidate_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    before = state(case.conn)
    catalog = read(client, "/runs/" + run_ref + "/candidates")
    assert catalog["data"]["candidate_count"] == 4
    result = read(client, "/candidates/" + refs[0])
    token = result["meta"]["snapshot_ref"]
    for fmt in ("csv", "xlsx"):
        response = client.get(BASE + "/candidates/" + refs[0] + "/export", query_string={"format": fmt, "snapshot_ref": token})
        assert response.status_code == 200 and response.headers["X-Workbench-Task-Count"] == "1"
    assert state(case.conn) == before
    assert connections and str(case.path) in connections
    assert client.post(BASE + "/candidates/" + refs[0]).status_code == 405


def test_failed_skipped_candidates_stay_in_catalog_and_have_explicit_empty_results(candidate_case):
    case = candidate_case
    run_ref, refs = compute(case)
    receipt = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts").fetchone()[0])
    for ref, status in zip(refs[:2], ("failed", "skipped")):
        corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))
        row = case.conn.execute("SELECT sequence FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()
        artifact = {"status": status, "sequence": row[0], "label": "Recorded " + status, "failure_reason": "private internal explanation"}
        corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET status=?,task_count=0,artifact_json=? WHERE candidate_ref=?",
                       (status, json.dumps(artifact), ref))
        next(item for item in receipt["candidates"] if item["candidate_ref"] == ref).update(status=status, task_count=0)
    receipt["state"] = "partial"
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET state='partial'")
    corrupt_update(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET state='partial',result_json=?", (json.dumps(receipt),))
    client, _ = api(case)
    with retained(case.conn):
        assert read(client, "/runs/" + run_ref + "/candidates")["data"]["candidate_count"] == 4
        for ref, status in zip(refs[:2], ("failed", "skipped")):
            catalog = read(client, "/runs/" + run_ref + "/candidates", status=status)
            assert [item["candidate_ref"] for item in catalog["data"]["candidates"]] == [ref]
            result = read(client, "/candidates/" + ref)
            assert result["data"]["candidate"]["completeness"] == "no_result"
            assert result["data"]["task_count"] == 0 and len(result["data"]["unplanned_operations"]) == 1
            assert any(item["code"] == "candidate_" + status for item in result["data"]["candidate"]["blocked_reasons"])
            assert "private internal explanation" not in json.dumps(result)


def test_queued_catalog_and_failed_empty_run_are_not_mislabeled_complete(candidate_case):
    case = candidate_case
    accepted = case.accept()
    client, _ = api(case)
    path = "/runs/" + accepted["run_ref"] + "/candidates"
    queued = read(client, path)
    assert queued["data"]["candidates"] == [] and not queued["data"]["catalog_complete"]
    case.conn.execute("UPDATE Machines SET name='Changed after admission'")
    case.conn.commit()
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.run_worker import WorkbenchRunWorker
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    failed = read(client, path)
    assert failed["data"]["run_state"] == "failed" and failed["data"]["candidates"] == []
    response = client.get(BASE + path, query_string={"snapshot_ref": queued["meta"]["snapshot_ref"]})
    assert response.status_code == 409


def test_snapshot_expiry_does_not_refresh_implicitly(candidate_case, monkeypatch):
    from web import public_token_registry
    case = candidate_case
    _, refs = compute(case)
    client, _ = api(case)
    path = "/candidates/" + refs[0]
    first = read(client, path)
    now = public_token_registry.time.time()
    monkeypatch.setattr(public_token_registry.time, "time", lambda: now + 1000)
    response = client.get(BASE + path, query_string={"snapshot_ref": first["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
