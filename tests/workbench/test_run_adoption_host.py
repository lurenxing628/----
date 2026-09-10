"""Managed launcher + HTTP admission + actual adoption, not standalone switches."""

import threading
import time
from pathlib import Path

from core.infrastructure.database import get_connection
from core.services.workbench import run_candidate_adoption
from tests.workbench.run_entrypoint_support import EntryHarness, accept_via_http
from tests.workbench.run_entrypoint_support import entrypoint_case as _case  # noqa: F401
from web.bootstrap.launcher_paths import db_scope_lock_path

BASE = "/api/workbench/v1/scheduling/candidates/"


def ready_adoption(app, case, key):
    client = app.test_client()
    accepted, _ = accept_via_http(client, case, "run-" + key)
    assert app.extensions["workbench_run_runtime"].wait_idle(timeout=15)
    run = client.get("/api/workbench/v1/scheduling/runs/" + accepted["run_ref"]).get_json()["data"]
    ref = run["candidates"][0]["candidate_ref"]
    checked = client.post(BASE + ref + "/adopt-preview", json={})
    preview = checked.get_json()
    assert checked.status_code == 200 and preview["data"]["validation"]["can_adopt"], preview
    return ref, {"write_token": preview["data"]["write_context"]["write_token"], "request_key": key,
                 "input": {"confirm": True, "reason": "Managed host integration", "declared_operator": "Planner"}}


def test_managed_host_adopts_once_without_setting_a_fixture_enable_switch(job_case, tmp_path, monkeypatch):
    observed = {}

    def serve(app, *_):
        assert app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] is True
        ref, body = ready_adoption(app, job_case, "host-adoption-once-0001")
        client = app.test_client()
        response = client.post(BASE + ref + "/adopt", json=body)
        receipt = response.get_json()
        assert response.status_code == 200 and receipt["ok"] is True, receipt
        repeated = client.post(BASE + ref + "/adopt", json=body).get_json()
        assert repeated["replayed"] is True and repeated["receipt_ref"] == receipt["receipt_ref"]
        plan = receipt["data"]["official_plan"]
        assert plan["version"] == 1 and plan["is_current_official"] is True
        plans = client.get("/api/workbench/v1/plans").get_json()
        official = next(row for row in plans["data"]["plans"] if row["plan_ref"] == plan["plan_ref"])
        assert official["is_current_official"] is True and official["capabilities"]["view"] is True
        workspace = client.get("/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace").get_json()
        assert workspace["ok"] is True and workspace["data"]["task_count"] == 1, workspace
        observed.update(app=app, plan=plan)

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        assert observed["app"].config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] is False
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT count(*) FROM ScheduleHistory").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM Schedule WHERE version=1").fetchone()[0] == 1
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        harness.cleanup()


def test_server_return_waits_for_http_adoption_commit_before_worker_stop_and_unlock(job_case, tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    threads, failures, receipts = [], [], []
    original = run_candidate_adoption.persist_adoption_in_tx

    def persist(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(run_candidate_adoption, "persist_adoption_in_tx", persist)

    def serve(app, *_):
        ref, body = ready_adoption(app, job_case, "host-adoption-drain-0001")
        gate, runtime = app.extensions["workbench_request_lifecycle"], app.extensions["workbench_run_runtime"]

        def write():
            try:
                response = app.test_client().post(BASE + ref + "/adopt", json=body)
                data = response.get_json()
                assert response.status_code == 200 and data["ok"] is True, data
                receipts.append(data)
            except BaseException as exc:
                failures.append(exc)

        def finish_when_stopping():
            try:
                deadline = time.monotonic() + 5
                while gate.status["state"] == "accepting" and time.monotonic() < deadline:
                    time.sleep(.01)
                assert gate.status["state"] == "stopping" and gate.status["active"] >= 1
                assert not runtime.status["closed"]
                assert Path(db_scope_lock_path(str(job_case.path))).exists()
            except BaseException as exc:
                failures.append(exc)
            finally:
                release.set()

        writer = threading.Thread(target=write)
        threads.append(writer)
        writer.start()
        assert entered.wait(5)
        monitor = threading.Thread(target=finish_when_stopping)
        threads.append(monitor)
        monitor.start()

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert not failures and len(receipts) == 1
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT count(*) FROM ScheduleHistory").fetchone()[0] == 1
        assert Path(db_scope_lock_path(str(job_case.path))).exists()
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=5)
        harness.cleanup()
