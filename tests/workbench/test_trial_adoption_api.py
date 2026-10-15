"""HTTP method/input boundaries, original-key recovery and unknown ACK response."""

import json

import pytest
from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial.adoption_history import WorkbenchTrialAdoptionHistoryService
from tests.workbench.trial_adoption_support import BASE, INTENT, KEY, api, saved_scenario
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import CommitFailureConnection, snapshot
from web.routes.workbench.read_context import bind_read_snapshot


def test_real_http_preview_confirm_and_receipt(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    before = snapshot(case.conn)
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    preview = response.get_json()["data"]
    assert preview["scenario_ref"] == saved["scenario_ref"] and preview["draft_ref"] == saved["draft_ref"]
    assert preview["validation"]["can_adopt"] and snapshot(case.conn) == before
    body = {"write_token": preview["write_context"]["write_token"], "request_key": KEY, "input": INTENT}
    response = client.post(path + "/adopt", json=body)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    receipt = client.get(path + "/adoption-commands/" + KEY).get_json()["data"]
    assert receipt["state"] == "committed" and receipt["receipt"]["receipt_ref"] == result["receipt_ref"]
    statements = []
    before, changes = snapshot(case.conn), case.conn.total_changes
    case.conn.set_trace_callback(statements.append)
    try:
        history, history_state = WorkbenchTrialAdoptionHistoryService(case.conn).read(saved["scenario_ref"])
    finally:
        case.conn.set_trace_callback(None)
    queries = [sql.upper() for sql in statements if sql.upper().startswith("SELECT")]
    receipt_queries = [sql for sql in queries if "FROM WORKBENCHCOMMANDRECEIPTS" in sql]
    adopted_receipts = [sql for sql in receipt_queries if "WHERE ACTION=" in sql and "CONTEXT_REF=" in sql]
    assert len(adopted_receipts) == 1
    assert "ORDER BY COMMITTED_AT_UTC DESC,REQUEST_KEY DESC LIMIT 1001" in adopted_receipts[0]
    assert all("WHERE" in sql for sql in receipt_queries)
    assert not any("LENGTH(" in sql or "COUNT(" in sql or "SUM(" in sql for sql in receipt_queries)
    assert not any("LENGTH(" in sql and "PAYLOAD_JSON" in sql for sql in queries)
    assert sum("FROM WORKBENCHTRIALSCENARIOS WHERE SCENARIO_REF=" in sql for sql in queries) == 1
    assert sum("FROM WORKBENCHTRIALSCENARIOROWS WHERE SCENARIO_REF=" in sql for sql in queries) == 1
    assert sum("FROM WORKBENCHTRIALDRAFTS WHERE DRAFT_REF=" in sql for sql in queries) == 1
    selected_histories = [sql for sql in queries if "FROM SCHEDULEHISTORY WHERE VERSION=" in sql and "RESULT_SUMMARY" in sql]
    assert len(selected_histories) == 1 and "LIMIT 2" in selected_histories[0]
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    with case.app.app_context():
        token = bind_read_snapshot(history["scope"], history_state)["snapshot_ref"]
    entry = history["items"][0]
    assert entry["adoption"]["reason"] == INTENT["reason"]
    assert entry["adoption"]["declared_operator"] == INTENT["declared_operator"]
    assert not any(gap["code"].startswith("audit_") for gap in entry["evidence_gaps"])
    summary = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?",
                        (result["data"]["official_plan"]["version"],)).fetchone()[0])
    assert set(summary["proof"]) == {"proof_version", "scenario_ref", "draft_ref", "scenario_revision", "baseline_ref", "baseline_version"}
    assert summary["proof"]["proof_version"] == "content_refs_v1"
    assert client.get(path + "/adopt").status_code == 405
    unknown = client.get(path + "/adoption-commands/not-yet-seen-request").get_json()["data"]
    assert unknown == {"state": "not_observed", "receipt": None, "may_be_in_flight": True, "can_retry_automatically": False}
    version = result["data"]["official_plan"]["version"]
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) "
                      "VALUES (?, 'duplicate-history', 'success', NULL, '2026-09-10 13:00:00')", (version,))
    case.conn.commit()
    duplicate, changed_state = WorkbenchTrialAdoptionHistoryService(case.conn).read(saved["scenario_ref"])
    with case.app.app_context(), pytest.raises(WorkbenchCommandRejected) as stale:
        bind_read_snapshot(history["scope"], changed_state, token)
    assert stale.value.code == "snapshot_stale"
    entry = duplicate["items"][0]
    assert any(gap["code"] == "audit_missing" for gap in entry["evidence_gaps"])
    assert entry["adoption"] == dict.fromkeys(("reason", "declared_operator", "application_operator", "adopted_at"))
    from core.services.workbench.trial.adoption_history_policy import load_history
    from data.repositories.workbench_trial_adoption_history import TrialAdoptionHistoryRepository

    case.conn.execute("DELETE FROM ScheduleHistory WHERE version=?", (version,))
    case.conn.commit()
    assert load_history(TrialAdoptionHistoryRepository(case.conn), version) is None


def test_http_ack_unknown_points_to_original_scenario_and_key(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case, factory=CommitFailureConnection)
    path = BASE + saved["scenario_ref"]

    @case.app.before_request
    def lose_ack():
        if request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    response = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == KEY
    assert value["error"]["result_target"] == path + "/adoption-commands/" + KEY
    assert value["error"]["retryable"] is False
    receipt = client.get(value["error"]["result_target"]).get_json()["data"]
    assert receipt["state"] == "committed" and receipt["receipt"]["data"]["scenario_ref"] == saved["scenario_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2
