"""Exact remembered scheduling input, ordinary command receipts and shared input freshness."""

import json

import pytest
from flask import Blueprint, g

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY, normalize_preflight_input
from core.services.workbench.run.jobs_facts import capture_run_facts, run_facts_unchanged
from core.services.workbench.run.preferences import SchedulingPreferencesService
from core.services.workbench.run.preflight_facts import full_facts_content
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.system_config_repo import SystemConfigRepository
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.preflight_support import payload, read_only_snapshot
from tests.workbench.preflight_support import pf as pf_fixture  # noqa: F401
from tests.workbench.run_jobs_support import job_case as job_case_fixture  # noqa: F401
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

ROOT = "/api/workbench/v1/scheduling/preferences"


def read(pf):
    with read_only_snapshot(pf.conn):
        response = pf.get(ROOT)
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()["data"]


def save(pf, value, token, key="scheduling-preferences-0001"):
    return pf.post(ROOT, json={"request_key": key, "write_token": token, "input": value})


def test_default_save_reload_replay_and_unchanged_use_ordinary_command(pf):
    before = read(pf)
    assert before["input"] is None
    assert before["write_context"]["capabilities"] == {"scheduling.preferences.save": True}
    value = payload(pf, hold_window=None, material_strategy="stage")
    value["batch_refs"].append("f" * 48)  # Missing references remain selected for the real preflight to report.
    response = save(pf, value, before["write_context"]["write_token"])
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    expected = normalize_preflight_input(value)
    assert result["result"] == "committed" and result["data"] == {"input": expected, "audit_persisted": True}
    assert read(pf)["input"] == expected
    stored = SystemConfigRepository(pf.conn).get_value(SCHEDULING_PREFERENCES_KEY)
    assert json.loads(stored) == {"version": 1, "input": expected}
    rejected = pf.post("/api/workbench/v1/scheduling/preflight", json=expected)
    assert rejected.status_code == 404 and rejected.get_json()["error"]["code"] == "entity_not_found"

    replayed = save(pf, value, "expired-token-is-not-revalidated").get_json()
    assert replayed["replayed"] is True and replayed["receipt_ref"] == result["receipt_ref"]
    refreshed = read(pf)
    unchanged = save(pf, value, refreshed["write_context"]["write_token"], "scheduling-preferences-0002").get_json()
    assert unchanged["result"] == "unchanged" and unchanged["data"]["audit_persisted"] is False
    assert pf.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_scheduling_preferences_save'").fetchone()[0] == 1


def test_stale_token_and_changed_request_key_content_do_not_overwrite_preferences(pf):
    token = read(pf)["write_context"]["write_token"]
    value = payload(pf)
    assert save(pf, value, token).status_code == 200
    changed = {**value, "end_date": "2026-09-10"}
    stale = save(pf, changed, token, "scheduling-preferences-stale")
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "stale_write"
    conflict = save(pf, changed, read(pf)["write_context"]["write_token"])
    assert conflict.status_code == 409 and conflict.get_json()["error"]["code"] == "request_key_conflict"
    assert read(pf)["input"] == value


@pytest.mark.parametrize("stored", ["not-json", '{"version":2,"input":{}}', '{"version":1,"input":{}}'])
def test_corrupt_or_unknown_saved_document_is_an_explicit_failure(pf, stored):
    SystemConfigRepository(pf.conn).set(SCHEDULING_PREFERENCES_KEY, stored)
    pf.conn.commit()
    response = pf.get(ROOT)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "scheduling_preferences_invalid"
    assert SystemConfigRepository(pf.conn).get_value(SCHEDULING_PREFERENCES_KEY) == stored


def test_preferences_save_does_not_expire_existing_preflight_or_worker_facts(pf):
    checked = pf.post("/api/workbench/v1/scheduling/preflight", json=payload(pf))
    assert checked.status_code == 200, checked.get_json()
    before = full_facts_content(pf.conn)
    captured_hash, captured_text = capture_run_facts(pf.conn)
    assert save(pf, payload(pf), read(pf)["write_context"]["write_token"]).status_code == 200
    assert full_facts_content(pf.conn) == before
    assert run_facts_unchanged(pf.conn, captured_text, captured_hash)
    from web.routes.workbench.preflight import resolve_preflight_input

    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        try:
            assert resolve_preflight_input(pf.conn, checked.get_json()["data"]["input_ref"]) == payload(pf)
        finally:
            pf.conn.rollback()

    # The exclusion is only this one interface preference; normal system configuration stays in the facts.
    SystemConfigRepository(pf.conn).set("auto_backup_enabled", "yes")
    pf.conn.commit()
    assert full_facts_content(pf.conn) != before
    assert not run_facts_unchanged(pf.conn, captured_text, captured_hash)


def test_receipt_failure_rolls_back_preference_and_audit_in_same_transaction(pf, monkeypatch):
    service = SchedulingPreferencesService(pf.conn)
    before, _ = service.snapshot()

    def failed_receipt(*args, **kwargs):
        raise RuntimeError("receipt write failed")

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", failed_receipt)
    with pytest.raises(WorkbenchCommandUncertain):
        service.save(payload(pf), request_key="scheduling-preferences-rollback", validate_context=lambda *args: None)
    assert service.snapshot()[0] == before
    assert not pf.conn.execute("SELECT 1 FROM OperationLogs WHERE action='workbench_scheduling_preferences_save'").fetchone()


@pytest.mark.parametrize("business_change", [False, True])
def test_public_preferences_during_real_worker_keep_admitted_scope_and_business_freshness(job_case, business_change, monkeypatch):
    case = job_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    dispatched = []
    case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
    case.app.extensions["workbench_run_dispatcher"] = dispatched.append
    bp = Blueprint("workbench", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = case.conn

    client = case.app.test_client()
    original, changed = case.settings("B1"), case.settings("B2", end_date="2026-09-26")
    checked = client.post("/api/workbench/v1/scheduling/preflight", json=original)
    assert checked.status_code == 200, checked.get_json()
    checked_data = checked.get_json()["data"]
    admitted_input = checked_data["normalized_input"]
    assert {key: admitted_input[key] for key in original} == original
    assert admitted_input["time_budget_seconds"] == 60
    input_ref = checked_data["input_ref"]
    token = client.get(ROOT).get_json()["data"]["write_context"]["write_token"]
    assert save(client, original, token).status_code == 200
    # Remembering the form after preflight does not invalidate its input_ref or run authorization.
    preview = client.post("/api/workbench/v1/scheduling/runs/preview", json={"input_ref": input_ref})
    assert preview.status_code == 200, preview.get_json()
    context = preview.get_json()["data"]["write_context"]
    assert context["capabilities"]["scheduling.run"] is True
    accepted = client.post("/api/workbench/v1/scheduling/runs", json={"input_ref": input_ref,
        "write_token": context["write_token"], "request_key": "preferences-real-worker-run"})
    assert accepted.status_code == 202, accepted.get_json()
    ref = accepted.get_json()["run_ref"]
    assert dispatched == [ref]
    saved = []

    persist = WorkbenchRunWorker._persist

    def after_real_compute(worker, row, prepared):
        assert row["run_ref"] == ref and 1 <= len(prepared.candidates) <= 3
        selection = json.loads(prepared.result["result_json"])["selection"]
        candidate_refs = {candidate["candidate_ref"] for candidate in prepared.candidates}
        assert selection["selected_candidate_ref"] in candidate_refs
        assert set(selection["objective_winners"]) == set(selection["target_objectives"])
        assert set(selection["objective_winners"].values()) <= candidate_refs
        assert not saved and not case.conn.in_transaction
        token = client.get(ROOT).get_json()["data"]["write_context"]["write_token"]
        response = save(client, changed, token, "preferences-during-real-worker")
        assert response.status_code == 200, response.get_json()
        saved.append(response.get_json())
        if business_change:
            case.config(objective="min_tardiness")
        return persist(worker, row, prepared)

    # Preference changes happen after actual computation and before the real atomic write.
    monkeypatch.setattr(WorkbenchRunWorker, "_persist", after_real_compute)
    worker = WorkbenchRunWorker(case.conn)
    if business_change:
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            worker.execute(ref)
        assert rejected.value.code == "snapshot_stale"
    else:
        assert worker.execute(ref)["state"] == "complete"
    assert len(saved) == 1 and client.get(ROOT).get_json()["data"]["input"] == changed
    stored_input = case.conn.execute("SELECT normalized_input_json FROM WorkbenchRunJobs WHERE run_ref=?", (ref,)).fetchone()[0]
    assert json.loads(stored_input) == admitted_input
    final = client.get("/api/workbench/v1/scheduling/runs/" + ref).get_json()["data"]
    if business_change:
        assert final["state"] == "failed" and final["error"]["code"] == "snapshot_stale"
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 0
    else:
        assert final["state"] == "complete" and final["result_persisted"] and 1 <= len(final["candidates"]) <= 3
        batches = {row[0] for row in case.conn.execute("SELECT DISTINCT b.batch_id FROM WorkbenchRunCandidateTasks t "
            "JOIN WorkbenchPlanSourceRefs r ON r.ref=t.operation_ref "
            "JOIN BatchOperations b ON CAST(b.id AS TEXT)=r.source_key WHERE r.kind='operation'")}
        assert batches == {"B1"}
