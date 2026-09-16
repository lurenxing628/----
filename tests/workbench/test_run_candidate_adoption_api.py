"""Standalone registration, JSON boundaries and existing receipt lookup route."""

import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

import pytest
from flask import g, request

from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger
from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService
from tests.workbench.run_candidate_adoption_support import (
    BASE,
    INTENT,
    KEY,
    CommitFailureConnection,
    api,
    candidate,
    rewrite_candidate,
    snapshot,
)
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401


def test_preview_and_adopt_independent_post_routes(candidate_case):
    case = candidate_case
    ref = candidate(case)
    client = api(case)
    before = snapshot(case.conn)
    response = client.post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()["data"]
    assert data["validation"]["can_adopt"] is True and snapshot(case.conn) == before
    result = client.post(BASE + ref + "/adopt", json={"request_key": KEY,
        "write_token": data["write_context"]["write_token"], "input": INTENT})
    assert result.status_code == 200, result.get_data(as_text=True)
    assert result.get_json()["data"]["official_plan"]["kind"] == "official"
    receipt = client.get("/api/workbench/v1/commands/" + KEY)
    assert receipt.status_code == 200
    assert receipt.get_json()["receipt_ref"] == result.get_json()["receipt_ref"]
    assert client.get(BASE + ref + "/adopt").status_code == 405


@pytest.mark.parametrize("ready_day,earlier", [("2026-09-08", False), ("2026-09-09", False), ("2026-09-10", True)])
def test_sqlite_date_conversion_preserves_adoption_ready_date_constraint(candidate_case, ready_day, earlier):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET ready_date=?", (ready_day,))
    case.conn.commit()
    ref = candidate(case)
    if earlier:
        def move_before_ready(row):
            for field in ("start_time", "end_time"):
                row[field] = (datetime.fromisoformat(row[field]) - timedelta(days=1)).isoformat()
        rewrite_candidate(case, ref, move_before_ready)
    # Use the same DECLTYPES connection factory as the running application.
    conn = get_connection(str(case.path))
    try:
        assert type(conn.execute("SELECT ready_date FROM Batches").fetchone()[0]) is date
    finally:
        conn.close()
    client = api(case, connection_factory=get_connection)
    before = snapshot(case.conn)
    response = client.post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert snapshot(case.conn) == before
    assert data["validation"]["can_adopt"] is (not earlier), data
    if earlier:
        assert data["validation"]["issues"][0]["code"] == "candidate_before_ready_date"
        assert data["write_context"]["write_token"] is None
    else:
        response = client.post(BASE + ref + "/adopt", json={"request_key": KEY,
            "write_token": data["write_context"]["write_token"], "input": INTENT})
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()["data"]["official_plan"]["kind"] == "official"


def test_restart_startup_and_audit_logs_do_not_expire_completed_candidate(candidate_case):
    case = candidate_case
    ref = candidate(case)
    archive = tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone())
    script = """
import sys
from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger
conn = get_connection(sys.argv[1])
assert OperationLogger(conn).info('plugins', 'load', target_type='runtime', target_id='plugins', detail={'loaded_at': 'restart'})
conn.close()
"""
    completed = subprocess.run([sys.executable, "-c", script, str(case.path)], capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    client = api(case, connection_factory=get_connection)
    response = client.post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert data["validation"]["can_adopt"] is True, data
    assert OperationLogger(case.conn).info("system", "backup", detail={"filename": "audit-only.db"})
    result = client.post(BASE + ref + "/adopt", json={"request_key": KEY,
        "write_token": data["write_context"]["write_token"], "input": INTENT})
    assert result.status_code == 200, result.get_data(as_text=True)
    assert tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone()) == archive
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action IN ('load','backup')").fetchone()[0] == 2


def test_default_capability_remains_disabled(candidate_case):
    case = candidate_case
    ref = candidate(case)
    client = api(case, enabled=False)
    response = client.post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 200
    assert response.get_json()["data"]["validation"]["can_adopt"] is False
    assert WorkbenchRunCandidateAdoptionService(case.conn).preview(ref)["write_context"]["write_token"] is None
    result = client.post(BASE + ref + "/adopt", json={"request_key": KEY, "write_token": "fake", "input": INTENT})
    assert result.status_code == 409 and result.get_json()["committed"] is False
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 0


def test_stale_http_409_and_extra_client_scope_rejected(candidate_case):
    case = candidate_case
    ref = candidate(case)
    client = api(case)
    assert client.post(BASE + ref + "/adopt-preview", json={"plan_ref": ref}).status_code == 400
    assert client.post(BASE + ref + "/adopt-preview?source=demo", json={}).status_code == 400
    result = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]
    case.conn.execute("UPDATE Machines SET name='drift'")
    case.conn.commit()
    response = client.post(BASE + ref + "/adopt", json={"request_key": KEY,
        "write_token": result["write_context"]["write_token"], "input": INTENT})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "snapshot_stale"
    assert response.get_json()["committed"] is False


def test_lost_http_commit_ack_points_at_original_receipt(candidate_case):
    case = candidate_case
    ref = candidate(case)

    def connection(path):
        conn = sqlite3.connect(str(path), factory=CommitFailureConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    client = api(case, connection_factory=connection)

    @case.app.before_request
    def inject_ack_loss():
        if request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    token = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    response = client.post(BASE + ref + "/adopt", json={"request_key": KEY, "write_token": token, "input": INTENT})
    assert response.status_code == 500
    error = response.get_json()
    assert error["committed"] == "unknown" and error["error"]["request_key"] == KEY
    receipt = client.get(error["error"]["result_target"])
    assert receipt.status_code == 200 and receipt.get_json()["replayed"] is True
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1
