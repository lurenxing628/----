"""The actual host dispatches accepted HTTP runs off-thread using the real engine."""

import threading
from contextlib import closing

import pytest

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.services.scheduler import schedule_service
from core.services.workbench.run_jobs import WorkbenchRunService
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_run_runtime_support import (
    BASE,
    intent,
    paused_compute,
)
from tests.workbench.test_run_runtime_support import (
    owned_case as _owned_case,  # noqa: F401
)
from tests.workbench.test_run_runtime_support import (
    runtime_api as _runtime_api,
)


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


def test_old_schedule_lock_keeps_accepted_run_queued_until_released(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    attempted = threading.Event()
    execute = WorkbenchRunWorker.execute

    def worker(self, ref):
        attempted.set()
        return execute(self, ref)

    monkeypatch.setattr(WorkbenchRunWorker, "execute", worker)
    with schedule_service._RUN_SCHEDULE_LOCK:
        response = client.post(BASE + "/runs", json=value)
        ref = response.get_json()["run_ref"]
        assert response.status_code == 202 and attempted.wait(timeout=10)
        row = client.get(BASE + "/runs/" + ref).get_json()["data"]
        assert (row["state"], row["stage"]) == ("queued", "queued")
        assert row["started_at"] is None
        assert runtime.wait_idle(timeout=0.15) is False
    assert runtime.wait_idle(timeout=20)
    assert client.get(BASE + "/runs/" + ref).get_json()["data"]["state"] == "complete"


def test_shutdown_stops_admission_and_waits_for_active_worker(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    with paused_compute(monkeypatch) as (entered, release, _calls):
        response = client.post(BASE + "/runs", json=value)
        ref = response.get_json()["run_ref"]
        assert entered.wait(timeout=15)
        assert runtime.shutdown(timeout=0.05) is False
        assert case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] is False
        assert "workbench_run_dispatcher" not in case.app.extensions
        with pytest.raises(RuntimeError, match="unavailable"):
            runtime(ref)
        with closing(get_connection(str(case.path))) as reader:
            assert WorkbenchRunService(reader).get(ref)["state"] == "running"
        release.set()
        assert runtime.shutdown(timeout=20) is True
    assert client.get(BASE + "/runs/" + ref).get_json()["data"]["state"] == "complete"


def test_delete_journal_http_backup_and_commit_reachable_during_compute(runtime_api, monkeypatch, tmp_path):
    client, case, runtime = runtime_api
    value = intent(client, case)
    with paused_compute(monkeypatch) as (entered, release, _calls):
        response = client.post(BASE + "/runs", json=value)
        ref = response.get_json()["run_ref"]
        assert entered.wait(timeout=15)
        with closing(get_connection(str(case.path))) as writer:
            assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            writer.execute("PRAGMA busy_timeout=200")
            writer.execute("UPDATE Machines SET name='changed while computing'")
            writer.commit()
        backup = BackupManager(str(case.path), str(tmp_path / "backups")).backup("running")
        with closing(get_connection(backup)) as reader:
            assert WorkbenchRunService(reader).get(ref)["state"] == "running"
            assert reader.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert client.get(BASE + "/runs/" + ref).get_json()["data"]["state"] == "running"
        release.set()
        assert runtime.wait_idle(timeout=20)
    final = client.get(BASE + "/runs/" + ref).get_json()["data"]
    assert final["state"] == "failed" and final["error"]["code"] == "snapshot_stale"
    assert runtime.ready


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
