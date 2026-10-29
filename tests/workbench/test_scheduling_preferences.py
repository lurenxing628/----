"""Exact remembered scheduling input, ordinary command receipts and shared input freshness."""

import json
import subprocess
from pathlib import Path

import pytest
from flask import Blueprint, g

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY, normalize_preflight_input
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.run.jobs_facts import production_facts_match
from core.services.workbench.run.preferences import SchedulingPreferencesService
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.system_config_repo import SystemConfigRepository
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.node_runtime_support import node_runtime
from tests.workbench.preflight_support import payload, read_only_snapshot
from tests.workbench.preflight_support import pf as pf_fixture  # noqa: F401
from tests.workbench.run_jobs_support import job_case as job_case_fixture  # noqa: F401
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

ROOT = "/api/workbench/v1/scheduling/preferences"
RUN_KEY = "run-" + "a" * 48  # The browser's request key shape.


def read(pf):
    with read_only_snapshot(pf.conn):
        response = pf.get(ROOT)
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()["data"]


def save(pf, value, token, key="scheduling-preferences-0001"):
    return pf.post(ROOT, json={"request_key": key, "write_token": token, "input": value})


def assert_frontend_run_queries(preview, run, lookup, *, input_ref, run_ref, request_key):
    documents = {"input_ref": input_ref, "run_ref": run_ref, "request_key": request_key}
    for name, response in (("preview", preview), ("run", run), ("lookup", lookup)):
        assert response.status_code == 200, response.get_json()
        assert response.headers["Cache-Control"] == "no-store"
        documents[name] = response.get_json()
    script = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), window = {}, context = vm.createContext({window});
for (const name of ['transport.js', 'WorkbenchTerms.js', 'RunGenerationContract.js', 'RunJobAPI.js', 'RunAdoptionAPI.js']) {
  vm.runInContext(fs.readFileSync('frontend/workbench/app/' + name, 'utf8'), context, {filename: name});
}
// The real transport envelope check runs on each actual backend document; only the network is replaced.
const T = window.APSWorkbenchTransport, base = '/api/workbench/v1/scheduling';
T.preview = async (path, body) => { assert.equal(path, base + '/runs/preview'); assert.equal(JSON.stringify(body), JSON.stringify({input_ref: input.input_ref})); return T.envelope(input.preview); };
T.read = async (path, query) => {
  if (path === base + '/runs/' + input.run_ref) return T.envelope(input.run);
  assert.equal(path, base + '/requests/' + input.request_key);
  assert.equal(JSON.stringify(query), JSON.stringify({data_context_ref: input.preview.data.data_context_ref}));
  return T.envelope(input.lookup);
};
(async () => {
  const preview = await window.RunJobAPI.preview(input.input_ref);
  const run = await window.RunJobAPI.get(input.run_ref);
  const found = await window.RunJobAPI.lookup({schema_version: 2, input_ref: input.input_ref, request_key: input.request_key,
    run_ref: input.run_ref, data_context_ref: preview.data_context_ref});
  assert.equal(found.found, true);
  assert.equal(found.run.state, run.state);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node_runtime(), "-e", script], input=json.dumps(documents),
        text=True, encoding="utf-8", capture_output=True, cwd=str(Path(__file__).resolve().parents[2]), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


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
    assert stored is not None
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


@pytest.mark.parametrize(("patch", "message"), [
    ({"material_strategy": "split"}, "请选择整批齐套或按工序齐套。"),
    ({"material_strategy": "stage", "ready_check": False}, "按工序齐套需要开启齐套检查。"),
])
def test_material_strategy_accepts_only_whole_batch_or_stage_release(pf, patch, message):
    assert normalize_preflight_input(payload(pf, material_strategy="strict", ready_check=False))["material_strategy"] == "strict"
    with pytest.raises(WorkbenchCommandRejected) as error:
        normalize_preflight_input(payload(pf, **patch))
    assert (error.value.code, error.value.status, str(error.value)) == ("invalid_input", 422, message)


def _facts_content(conn):
    with TransactionManager(conn).transaction():
        return ProductionFactsCapture(conn).content()


def test_preferences_save_does_not_expire_existing_preflight_or_worker_facts(pf):
    checked = pf.post("/api/workbench/v1/scheduling/preflight", json=payload(pf))
    assert checked.status_code == 200, checked.get_json()
    before = _facts_content(pf.conn)
    captured_text = ProductionFactsCapture(pf.conn).content()
    assert save(pf, payload(pf), read(pf)["write_context"]["write_token"]).status_code == 200
    assert _facts_content(pf.conn) == before
    assert production_facts_match(pf.conn, captured_text)
    from web.routes.workbench.preflight import evaluate_preflight_input_prepared

    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        try:
            assert evaluate_preflight_input_prepared(pf.conn, checked.get_json()["data"]["input_ref"]).data["normalized_input"] == payload(pf)
        finally:
            pf.conn.rollback()

    # The exclusion is only this one interface preference; normal system configuration stays in the facts.
    SystemConfigRepository(pf.conn).set("auto_backup_enabled", "yes")
    pf.conn.commit()
    assert _facts_content(pf.conn) != before
    assert not production_facts_match(pf.conn, captured_text)


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
        "write_token": context["write_token"], "request_key": RUN_KEY})
    assert accepted.status_code == 202, accepted.get_json()
    ref = accepted.get_json()["run_ref"]
    assert dispatched == [ref]
    saved = []

    persist = WorkbenchRunWorker._persist

    def after_real_compute(worker, row, prepared, admission):
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
        return persist(worker, row, prepared, admission)

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
    final_response = client.get("/api/workbench/v1/scheduling/runs/" + ref)
    lookup = client.get("/api/workbench/v1/scheduling/requests/" + RUN_KEY,
                        query_string={"data_context_ref": preview.get_json()["data"]["data_context_ref"]})
    assert_frontend_run_queries(preview, final_response, lookup, input_ref=input_ref, run_ref=ref, request_key=RUN_KEY)
    final = final_response.get_json()["data"]
    if business_change:
        assert final["state"] == "failed" and final["error"]["code"] == "snapshot_stale"
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 0
    else:
        assert final["state"] == "complete" and final["result_persisted"] and 1 <= len(final["candidates"]) <= 3
        batches = {row[0] for row in case.conn.execute("SELECT DISTINCT b.batch_id FROM WorkbenchRunCandidateTasks t "
            "JOIN WorkbenchPlanSourceRefs r ON r.ref=t.operation_ref "
            "JOIN BatchOperations b ON CAST(b.id AS TEXT)=r.source_key WHERE r.kind='operation'")}
        assert batches == {"B1"}
