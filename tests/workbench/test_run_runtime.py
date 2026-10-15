"""The host dispatches a real HTTP run and persists explicit worker failures."""

import json
import threading
from unittest.mock import Mock

from core.services.workbench.run import worker as run_worker
from core.services.workbench.run.jobs import WorkbenchRunService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import BASE, intent, paused_compute
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from tests.workbench.run_runtime_support import runtime_api as _runtime_api  # noqa: F401
from web.bootstrap import workbench_run_runtime as run_runtime
from web.bootstrap.workbench_run_runtime_lock import RunRuntimeLockProof


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
    assert 1 <= len(final["candidates"]) <= 3 and len(calls) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == sum(
        row["task_count"] for row in final["candidates"])
    receipt = json.loads(case.conn.execute(
        "SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (ref,)).fetchone()[0])
    selection = receipt["selection"]
    assert selection["selected_candidate_ref"] == next(row["candidate_ref"] for row in final["candidates"] if row["selected"])
    assert set(selection["objective_winners"]) == set(selection["target_objectives"])
    assert set(selection["objective_winners"].values()) <= {row["candidate_ref"] for row in final["candidates"]}
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

    def fail(_self, _row, _admission):
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


def test_schedule_lock_wait_skips_connections_and_reads_until_release_or_stop(owned_case, monkeypatch):
    case = owned_case
    release_ref = case.accept("lock-release-request-0001")["run_ref"]
    stop_ref = case.accept("lock-stop-request-0000001")["run_ref"]
    runtime = run_runtime.WorkbenchRunRuntime(case.app)
    runtime.proof = RunRuntimeLockProof(runtime.db_path, case.lock_payload)

    class ControlledLock:
        def __init__(self):
            self.lock = threading.Lock()
            self.waits = 0
            self.waited = threading.Event()

        def acquire(self, *args, **kwargs):
            acquired = self.lock.acquire(*args, **kwargs)
            if kwargs.get("timeout") == 0.1 and not acquired:
                self.waits += 1
                if self.waits >= 3:
                    self.waited.set()
            return acquired

        def release(self):
            self.lock.release()

    lock = ControlledLock()
    connect = Mock(wraps=run_runtime.get_connection)
    read = Mock(wraps=WorkbenchRunService.get)
    execute = Mock(wraps=WorkbenchRunWorker.execute)
    verify = Mock(wraps=runtime._verify)
    monkeypatch.setattr(run_runtime, "RUN_SCHEDULE_LOCK", lock)
    monkeypatch.setattr(run_worker, "RUN_SCHEDULE_LOCK", lock)
    monkeypatch.setattr(run_runtime, "get_connection", connect)
    monkeypatch.setattr(WorkbenchRunService, "get", lambda service, run_ref: read(service, run_ref))
    monkeypatch.setattr(WorkbenchRunWorker, "execute", lambda worker, run_ref, **kwargs: execute(worker, run_ref, **kwargs))
    monkeypatch.setattr(runtime, "_verify", verify)
    errors = []

    def dispatch():
        try:
            runtime._execute(ref)
        except Exception as exc:
            errors.append(exc)

    # Repeated real timeout cycles must stay ahead of ownership checks and DB reads.
    for stop, ref in ((False, release_ref), (True, stop_ref)):
        lock.waits = 0
        lock.waited.clear()
        before = (connect.call_count, read.call_count, execute.call_count, verify.call_count)
        assert lock.acquire(blocking=False)
        held = True
        thread = threading.Thread(target=dispatch, daemon=True)
        thread.start()
        try:
            assert lock.waited.wait(timeout=5)
            waiting = (connect.call_count, read.call_count, execute.call_count, verify.call_count)
            print(f"R08 waiting stop={stop} cycles={lock.waits} counts={waiting}")
            assert waiting == before
            if stop:
                runtime._stop.set()
                thread.join(timeout=1)
                assert not thread.is_alive()
                assert (connect.call_count, read.call_count, execute.call_count, verify.call_count) == before
                row = case.conn.execute("SELECT state,stage FROM WorkbenchRunJobs WHERE run_ref=?", (ref,)).fetchone()
                assert tuple(row) == ("queued", "queued")
            else:
                held = False
                lock.release()
                thread.join(timeout=15)
                assert not thread.is_alive()
                assert (connect.call_count, read.call_count, execute.call_count, verify.call_count) == (1, 1, 1, 1)
                assert case.conn.execute("SELECT state FROM WorkbenchRunJobs WHERE run_ref=?", (ref,)).fetchone()[0] == "complete"
            assert errors == []
        finally:
            if held:
                lock.release()
            thread.join(timeout=15)
        returned = (connect.call_count, read.call_count, execute.call_count, verify.call_count)
        print(f"R08 returned stop={stop} counts={returned}")
