"""Standalone registration, JSON boundaries and existing receipt lookup route."""

import sqlite3

from flask import g, request

from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService
from tests.workbench.run_candidate_adoption_support import (
    BASE,
    INTENT,
    KEY,
    CommitFailureConnection,
    api,
    candidate,
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
