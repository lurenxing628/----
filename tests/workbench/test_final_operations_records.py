"""Projection-only event contracts on a real private SQLite and journal fixture."""

import json
from contextlib import closing
from pathlib import Path

import pytest

from core.services.workbench.system_maintenance_records import maintenance_records
from tests.workbench.system_maintenance_support import SystemTestAPI


def _audit(conn, action, level="INFO", detail=None):
    conn.execute("INSERT INTO OperationLogs(log_time,log_level,module,action,detail) VALUES (?,?,?,?,?)",
                 ("2026-09-10 12:00:00", level, "system", action, json.dumps(detail or {"removed_count": 0})))


def test_final_operations_records_are_disjoint_readonly_sources(tmp_path):
    api = SystemTestAPI(tmp_path)
    filename = api.backup()
    journal = api.journal()
    record, _ = journal.begin("final-operations-record-fixture-0001", "restore", {})
    journal.record(record, "succeeded", code="verified", target={"filename": Path(filename).name, "sha256": "a" * 64})
    with closing(api.connect()) as conn:
        _audit(conn, "cleanup")
        _audit(conn, "logs_cleanup", "ERROR", {"error": "fixture audit error"})
        conn.commit()
        before = {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table)]
                  for table in ("OperationLogs", "SystemConfig", "SystemJobState")}
        raw_journal = next(api.journal_dir.glob("*.json")).read_bytes()
        rows, sources = maintenance_records(conn, str(api.backups), journal)
        assert {row["record_kind"] for row in rows} == {"backup_file", "restore_event", "cleanup_event"}
        assert len(rows) == 4
        for row in rows:
            assert "backup_ref" not in row and "write_context" not in row
            if row["record_kind"] != "backup_file":
                assert row["file_capabilities"] == {"download": False, "restore": False, "delete": False}
                assert "_signature" not in row and "filename" not in row
        assert {row["status"] for row in rows if row["type"] == "cleanup"} == {"succeeded", "failed"}
        assert any(item["code"] == "maintenance_sources" for item in sources)
        for table, value in before.items():
            assert [tuple(row) for row in conn.execute("SELECT * FROM " + table)] == value
        assert next(api.journal_dir.glob("*.json")).read_bytes() == raw_journal


@pytest.mark.parametrize("detail,state", [({"removed_count": 0}, "succeeded"), ({"error": "failed"}, "failed"), ({}, "unknown")])
def test_final_operations_latest_cleanup_is_not_invented_history(tmp_path, detail, state):
    api = SystemTestAPI(tmp_path)
    with closing(api.connect()) as conn:
        conn.execute("INSERT INTO SystemJobState(job_key,last_run_time,last_run_detail) VALUES (?,?,?)",
                     ("auto_backup_cleanup", "2026-09-10 12:00:00", json.dumps(detail)))
        conn.commit()
        rows, issues = maintenance_records(conn, str(api.backups), api.journal())
        assert len(rows) == 1 and rows[0]["event_source"] == "latest_job_state_only"
        assert rows[0]["status"] == state and rows[0]["record_kind"] == "cleanup_event"
        assert any(row["code"] == "cleanup_latest_state_only" for row in issues)
        _audit(conn, "cleanup")
        rows, _ = maintenance_records(conn, str(api.backups), api.journal())
        assert len(rows) == 1 and rows[0]["event_source"] == "operation_audit"


def test_final_operations_corrupt_journal_is_not_empty_success(tmp_path):
    api = SystemTestAPI(tmp_path)
    record, _ = api.journal().begin("final-operations-record-fixture-0002", "restore", {})
    assert record["state"] == "accepted"
    target = next(api.journal_dir.glob("*.json"))
    target.write_text("{", encoding="utf-8")
    with closing(api.connect()) as conn, pytest.raises((RuntimeError, ValueError)):
        maintenance_records(conn, str(api.backups), api.journal())
    assert target.read_text() == "{"


def test_final_operations_event_filters_never_grant_file_tokens_and_keep_download(tmp_path):
    api = SystemTestAPI(tmp_path)
    filename = api.backup()
    original = Path(filename).read_bytes()
    record, _ = api.journal().begin("final-operations-record-fixture-0003", "restore", {})
    api.journal().record(record, "succeeded", code="verified", target={"filename": Path(filename).name, "sha256": "a" * 64})
    with closing(api.connect()) as conn:
        _audit(conn, "cleanup")
        conn.commit()
    for kind in ("restore", "cleanup"):
        payload = api.read("/backups", type=kind, status="succeeded")
        event, = payload["data"]["rows"]
        assert event["record_kind"] == kind + "_event"
        assert "backup_ref" not in event and "write_context" not in event
        assert all(value is False for value in event["file_capabilities"].values())
        response = api.get("/backups/" + event["event_ref"] + "/download", snapshot_ref=payload["meta"]["snapshot_ref"])
        assert response.status_code == 409
        rejected = api.post("/backups/delete", {"backup_ref": event["event_ref"]}, event["event_ref"], "event-reject-" + kind + "-0001")
        assert rejected.status_code == 409 and Path(filename).read_bytes() == original
    payload = api.read("/backups")
    selected = next(row for row in payload["data"]["rows"] if row["record_kind"] == "backup_file")
    response = api.get("/backups/" + selected["backup_ref"] + "/download", snapshot_ref=payload["meta"]["snapshot_ref"])
    assert response.status_code == 200 and response.data == original


def test_final_operations_unconfigured_journal_keeps_readonly_files_with_explicit_gap(tmp_path):
    api = SystemTestAPI(tmp_path)
    filename = api.backup()
    original = Path(filename).read_bytes()
    api.app.config.pop("WORKBENCH_SYSTEM_JOURNAL_DIR")
    payload = api.read("/backups")
    data = payload["data"]
    assert any(row["code"] == "restore_event_source_unconfigured" for row in data["sources"])
    row, = data["rows"]
    assert row["record_kind"] == "backup_file"
    assert all(data["capabilities"][action] is False for action in ("create", "delete", "restore"))
    response = api.get("/backups/" + row["backup_ref"] + "/download", snapshot_ref=payload["meta"]["snapshot_ref"])
    assert response.status_code == 200 and response.data == original
    empty = api.read("/backups", type="restore")
    assert empty["data"]["page"]["total"] == 0
    assert any(row["code"] == "restore_event_source_unconfigured" for row in empty["data"]["sources"])
