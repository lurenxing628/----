"""Actual launcher ownership and HTTP drain; only the socket server is replaced."""

import threading
import time
from pathlib import Path

from core.infrastructure.database import get_connection
from core.services.workbench import trial_adoption
from tests.workbench.run_entrypoint_support import EntryHarness, accept_via_http
from tests.workbench.run_entrypoint_support import entrypoint_case as _case  # noqa: F401
from tests.workbench.trial_adoption_support import BASE, INTENT
from web.bootstrap.launcher_paths import db_scope_lock_path


def ready(app, case, key):
    client = app.test_client()
    accepted, _ = accept_via_http(client, case, "run-" + key)
    assert app.extensions["workbench_run_runtime"].wait_idle(timeout=15)
    run = client.get("/api/workbench/v1/scheduling/runs/" + accepted["run_ref"]).get_json()["data"]
    source = {"base": {"candidate_ref": run["candidates"][0]["candidate_ref"]}}
    preview = client.post("/api/workbench/v1/trial/drafts/preview", json=source)
    assert preview.status_code == 200, preview.get_json()
    created = client.post("/api/workbench/v1/trial/drafts", json={"input": source, "request_key": "create-" + key,
        "write_token": preview.get_json()["data"]["write_context"]["write_token"]})
    assert created.status_code == 200, created.get_json()
    draft = created.get_json()["data"]
    task = draft["tasks"][0]
    changed = client.post("/api/workbench/v1/trial/drafts/" + draft["draft_ref"] + "/change", json={
        "input": {"task_ref": task["task_ref"], "machine_ref": task["machine_ref"], "operator_ref": task["operator_ref"],
                  "start": "2026-09-09T13:00:00"}, "request_key": "change-" + key,
        "write_token": draft["write_context"]["write_token"]})
    assert changed.status_code == 200, changed.get_json()
    draft = changed.get_json()["data"]
    response = client.post("/api/workbench/v1/trial/drafts/" + draft["draft_ref"] + "/save", json={
        "input": {"name": "Host saved scenario"}, "request_key": "save-" + key,
        "write_token": draft["write_context"]["write_token"]})
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()["data"]
    response = client.post(BASE + saved["scenario_ref"] + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_json()
    preview = response.get_json()["data"]
    assert preview["validation"]["can_adopt"], preview
    return saved, {"input": INTENT, "request_key": key, "write_token": preview["write_context"]["write_token"]}


def test_real_managed_host_adopts_saved_arrangement_without_fixture_enable_flag(job_case, tmp_path, monkeypatch):
    observed = {}

    def serve(app, *_):
        assert app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] is True
        assert any(rule.endpoint == "workbench.trial_adopt" for rule in app.url_map.iter_rules())
        saved, body = ready(app, job_case, "cq-host-adopt-0001")
        client = app.test_client()
        path = BASE + saved["scenario_ref"]
        response = client.post(path + "/adopt", json=body)
        assert response.status_code == 200, response.get_json()
        data = response.get_json()
        again = client.post(path + "/adopt", json=body).get_json()
        assert again["replayed"] and again["receipt_ref"] == data["receipt_ref"]
        plan = data["data"]["official_plan"]
        workspace = client.get("/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace").get_json()
        assert workspace["ok"] and workspace["data"]["task_count"] == 1, workspace
        assert client.get(path).get_json()["data"] == saved
        observed.update(app=app, plan=plan)

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        assert observed["app"].config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] is False
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT start_time FROM Schedule").fetchone()[0] == "2026-09-09 13:00:00"
            assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        harness.cleanup()


def test_host_drains_inflight_scenario_before_worker_shutdown_or_unlock(job_case, tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    threads, failures, receipts = [], [], []
    original = trial_adoption.persist_trial_adoption_in_tx

    def persist(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(trial_adoption, "persist_trial_adoption_in_tx", persist)

    def serve(app, *_):
        saved, body = ready(app, job_case, "cq-host-drain-0001")
        gate, runtime = app.extensions["workbench_request_lifecycle"], app.extensions["workbench_run_runtime"]

        def write():
            try:
                response = app.test_client().post(BASE + saved["scenario_ref"] + "/adopt", json=body)
                assert response.status_code == 200, response.get_json()
                receipts.append(response.get_json())
            except BaseException as exc:
                failures.append(exc)

        def drain():
            try:
                deadline = time.monotonic() + 5
                while gate.status["state"] == "accepting" and time.monotonic() < deadline:
                    time.sleep(.01)
                assert gate.status["state"] == "stopping" and gate.status["active"] >= 1
                assert not runtime.status["closed"]
                assert Path(db_scope_lock_path(str(job_case.path))).exists()
                rejected = app.test_client().post(BASE + saved["scenario_ref"] + "/adopt", json=body)
                assert rejected.status_code == 503
            except BaseException as exc:
                failures.append(exc)
            finally:
                release.set()

        writer = threading.Thread(target=write)
        threads.append(writer)
        writer.start()
        assert entered.wait(5)
        monitor = threading.Thread(target=drain)
        threads.append(monitor)
        monitor.start()

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert not failures and len(receipts) == 1, failures
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1
        assert Path(db_scope_lock_path(str(job_case.path))).exists()
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=5)
        harness.cleanup()
