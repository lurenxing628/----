"""Production entrypoint ordering around actual SQLite/HTTP/background computation."""

import logging
import os
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.infrastructure.database import get_connection
from core.services.workbench import run_worker
from tests.workbench.run_entrypoint_support import EntryHarness, accept_via_http
from tests.workbench.run_entrypoint_support import entrypoint_case as _job_case_fixture  # noqa: F401
from web.bootstrap import factory, workbench_run_runtime
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.workbench_run_lifecycle import release_runtime_after_jobs


def test_real_entrypoint_enables_http_worker_then_joins_before_unlock(job_case, tmp_path, monkeypatch):
    observed = {}

    def serve(app, _host, _port):
        runtime = app.extensions["workbench_run_runtime"]
        observed["runtime"] = runtime
        assert runtime.ready and Path(db_scope_lock_path(str(job_case.path))).exists()
        client = app.test_client()
        accepted, body = accept_via_http(client, job_case)
        repeated = client.post("/api/workbench/v1/scheduling/runs", json=body)
        assert repeated.status_code == 202 and repeated.get_json()["replayed"] is True
        assert repeated.get_json()["run_ref"] == accepted["run_ref"]
        assert runtime.wait_idle(timeout=15)
        result = client.get("/api/workbench/v1/scheduling/runs/" + accepted["run_ref"])
        assert result.status_code == 200, result.get_json()
        data = result.get_json()["data"]
        assert data["state"] == "complete" and data["result_persisted"] is True
        assert len(data["candidates"]) == 4
        with get_connection(str(job_case.path)) as conn:
            for table in ("Schedule", "ScheduleHistory", "ScheduleVersionSeq", "ScheduleCandidate"):
                assert conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
        observed["run_ref"] = data["run_ref"]

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        runtime = observed["runtime"]
        assert runtime.status["closed"] and not runtime.ready
        assert Path(db_scope_lock_path(str(job_case.path))).exists()
        names = [callback.__name__ for callback, _, _ in harness.handlers]
        assert names.index("release_runtime_after_jobs") < names.index("_run_exit_backup") < names.index("stop_run_runtime")
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
        assert harness.events == ["create-under-db-lock"]
    finally:
        harness.cleanup()


def test_server_return_waits_for_active_computation_and_keeps_lock(job_case, tmp_path, monkeypatch):
    started, proceed = threading.Event(), threading.Event()
    original = run_worker.compute_prepared_candidate_run
    monitors, failures = [], []

    def compute(*args, **kwargs):
        started.set()
        assert proceed.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(run_worker, "compute_prepared_candidate_run", compute)

    def serve(app, _host, _port):
        runtime = app.extensions["workbench_run_runtime"]
        accept_via_http(app.test_client(), job_case, "entrypoint-close-active-0001")
        assert started.wait(5)

        def release_compute():
            deadline = time.monotonic() + 5
            while not runtime.status["closed"] and time.monotonic() < deadline:
                time.sleep(.01)
            try:
                assert runtime.status["closed"]
                assert Path(db_scope_lock_path(str(job_case.path))).exists()
                assert runtime._thread.is_alive()
            except BaseException as exc:
                failures.append(exc)
            finally:
                proceed.set()

        thread = threading.Thread(target=release_compute)
        monitors.append(thread)
        thread.start()

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        for thread in monitors:
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert failures == []
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "complete"
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        proceed.set()
        harness.cleanup()


def test_missing_lock_receipt_rejected_before_factory_or_serving(job_case, tmp_path, monkeypatch):
    called = []
    harness = EntryHarness(job_case, tmp_path, monkeypatch, lambda *_: called.append("serve"))
    harness.deps = replace(harness.deps, acquire_runtime_lock=lambda *_args, **_kwargs: None,
                           create_app=lambda: called.append("create"))
    assert harness.run() == 13
    assert called == [] and harness.handlers == []


def test_failed_recovery_does_not_open_server_and_stops_before_unlock(job_case, tmp_path, monkeypatch):
    stopped, served = [], []
    runtime = SimpleNamespace(ready=False, status={"reason": "awaiting_reconciliation"},
                              shutdown=lambda **_kwargs: stopped.append("stop") or True)
    harness = EntryHarness(job_case, tmp_path, monkeypatch, lambda *_: served.append(True))
    harness.deps = replace(harness.deps, install_run_runtime=lambda *_args, **_kwargs: runtime)
    try:
        assert harness.run() == 14
        assert served == [] and stopped == ["stop"]
        assert Path(db_scope_lock_path(str(job_case.path))).exists()
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        harness.cleanup()


@pytest.mark.parametrize("result", [False, RuntimeError("shutdown uncertain")])
def test_unconfirmed_shutdown_blocks_exit_backup_and_lock_release(tmp_path, monkeypatch, caplog, result):
    path = str(tmp_path / "guarded.db")

    def shutdown(**_kwargs):
        if isinstance(result, BaseException):
            raise result
        return result

    runtime = SimpleNamespace(shutdown=shutdown)
    monkeypatch.setitem(workbench_run_runtime._RUNTIMES, path, runtime)
    touched = []
    monkeypatch.setattr(factory, "_is_exit_backup_enabled", lambda *_: touched.append("config-read") or True)
    manager = SimpleNamespace(db_path=path, logger=logging.getLogger("entrypoint-guard"),
                              backup=lambda **_kwargs: touched.append("backup"))
    assert factory._run_exit_backup(manager) is False
    assert touched == []
    assert "退出自动备份已跳过" in caplog.text
    deps = SimpleNamespace(release_runtime_lock=lambda *_: touched.append("unlock"))
    with pytest.raises(RuntimeError):
        release_runtime_after_jobs(deps, {"runtime": runtime}, str(tmp_path), os.getpid(), path)
    assert touched == []
