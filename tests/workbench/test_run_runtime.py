"""The host dispatches a real HTTP run and persists explicit worker failures."""

import threading

from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import BASE, intent, paused_compute
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from tests.workbench.run_runtime_support import runtime_api as _runtime_api  # noqa: F401


def test_http_202_single_background_worker_real_engine_and_replay(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    with paused_compute(monkeypatch) as (entered, release, calls):
        response = client.post(BASE + "/runs", json=value)
        assert response.status_code == 202, response.get_json()
        ref = response.get_json()["run_ref"]
        assert entered.wait(timeout=15)
        assert calls[0] != threading.get_ident()
        assert client.get(BASE + "/runs/" + ref).get_json()["data"]["state"] == "running"
        assert client.post(BASE + "/runs", json=value).get_json()["replayed"] is True
        for _ in range(10):
            runtime(ref)
        release.set()
        assert runtime.wait_idle(timeout=20)
    final = client.get(BASE + "/runs/" + ref).get_json()["data"]
    assert final["state"] == "complete" and final["result_persisted"]
    assert len(final["candidates"]) == 4 and len(calls) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 4
    assert client.get(BASE + "/requests/" + value["request_key"]).get_json()["data"]["run"] == final

    redundant_calls = []

    def forbidden(_worker, _ref):
        redundant_calls.append(_ref)
        raise AssertionError("terminal run must not invoke the worker again")

    monkeypatch.setattr(WorkbenchRunWorker, "execute", forbidden)
    runtime(ref)
    assert runtime.wait_idle(timeout=5)
    assert redundant_calls == []


def test_compute_exception_is_logged_with_original_ref_and_durable_failure(runtime_api, monkeypatch, caplog):
    client, case, runtime = runtime_api
    value = intent(client, case)

    def fail(_self, _row):
        raise ValueError("BN explicit compute failure")

    monkeypatch.setattr(WorkbenchRunWorker, "_compute", fail)
    response = client.post(BASE + "/runs", json=value)
    ref = response.get_json()["run_ref"]
    assert response.status_code == 202 and runtime.wait_idle(timeout=15)
    final = client.get(BASE + "/runs/" + ref).get_json()["data"]
    assert final["state"] == "failed"
    assert ref in caplog.text and "BN explicit compute failure" in caplog.text
    replay = client.post(BASE + "/runs", json=value)
    assert replay.get_json()["replayed"] is True
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
