"""HTTP method/input boundaries, original-key recovery and unknown ACK response."""

import json

import pytest
from flask import g, request

from core.errors import AppError, ErrorCode
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import valid_data_context_ref
from core.services.workbench.facts.run_data_context import RunDataContext, restored_context_ref
from core.services.workbench.trial.adoption import WorkbenchTrialAdoptionService
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
    case.conn.execute("DELETE FROM ScheduleHistory WHERE version=?", (version,))
    case.conn.commit()
    missing, _ = WorkbenchTrialAdoptionHistoryService(case.conn).read(saved["scenario_ref"])
    entry = missing["items"][0]
    assert entry["current_state"] == "unavailable" and entry["official_plan"] is None
    assert {issue["code"] for issue in entry["evidence_gaps"]} == {"audit_missing", "official_identity_unavailable"}


def test_http_adoption_recovery_distinguishes_replaced_context_and_replays_receipt(trial_case, monkeypatch):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200
    checked = response.get_json()["data"]
    context = checked["data_context_ref"]
    assert valid_data_context_ref(context)
    other_context = restored_context_ref("another-database", [])
    assert valid_data_context_ref(other_context) and other_context != context
    command_path = path + "/adoption-commands/" + KEY
    before = snapshot(case.conn)
    for query in ({}, {"data_context_ref": context}):
        response = client.get(command_path, query_string=query)
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        assert response.get_json()["data"] == {
            "state": "not_observed", "receipt": None, "may_be_in_flight": True, "can_retry_automatically": False}
    for target, query in (
        (command_path, {"data_context_ref": other_context}),
        (BASE + "f" * 48 + "/adoption-commands/" + KEY, {}),
    ):
        response = client.get(target, query_string=query)
        assert response.status_code == 200
        assert response.get_json()["data"] == {
            "state": "not_observed", "receipt": None, "may_be_in_flight": False, "can_retry_automatically": False}
    assert snapshot(case.conn) == before

    adopted = client.post(path + "/adopt", json={"write_token": checked["write_context"]["write_token"],
        "request_key": KEY, "input": INTENT})
    assert adopted.status_code == 200
    context_reads = []
    original_ref = RunDataContext.ref

    def tracked_context(data_context):
        context_reads.append(data_context.database_path)
        return original_ref(data_context)

    monkeypatch.setattr(RunDataContext, "ref", tracked_context)
    response = client.get(command_path, query_string={"data_context_ref": other_context})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    result = response.get_json()
    assert result["ok"] is True and result["schema_version"] == 1
    assert set(result["data"]) == {"state", "receipt"} and result["data"]["state"] == "committed"
    assert result["data"]["receipt"]["receipt_ref"] == adopted.get_json()["receipt_ref"]
    assert result["data"]["receipt"]["replayed"] is True
    assert context_reads == []


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


@pytest.mark.parametrize("injected", [AppError(ErrorCode.DB_QUERY_ERROR, "注入的存储失败"), RuntimeError("注入的未预期失败")])
def test_http_adopt_failure_after_binding_key_points_to_original_receipt(trial_case, monkeypatch, injected):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]

    def fail(*_args, **_kwargs):
        raise injected

    monkeypatch.setattr(WorkbenchTrialAdoptionService, "preview", fail)
    read = client.post(path + "/adopt-preview", json={})
    assert read.status_code == 500
    assert read.get_json()["committed"] is False and "request_key" not in read.get_json()["error"]
    monkeypatch.setattr(WorkbenchTrialAdoptionService, "adopt", fail)
    response = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    error = response.get_json()["error"]
    assert response.get_json()["committed"] == "unknown" and error["code"] == "storage_failure" and error["retryable"] is False
    assert error["request_key"] == KEY and error["result_target"] == path + "/adoption-commands/" + KEY
