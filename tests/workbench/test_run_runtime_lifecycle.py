"""Registration/shutdown races retain explicit per-app ownership boundaries."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import new_run_ref
from core.services.scheduler import schedule_service
from core.services.workbench.run_jobs import WorkbenchRunService
from core.services.workbench.run_worker import WorkbenchRunWorker
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.test_run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_run_runtime_support import (
    BASE,
    install,
    intent,
    paused_compute,
)
from tests.workbench.test_run_runtime_support import (
    owned_case as _owned_case,  # noqa: F401
)
from tests.workbench.test_run_runtime_support import (
    runtime_api as _runtime_api,
)
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime


def test_concurrent_install_same_app_returns_one_live_runtime(owned_case):
    case = owned_case
    start = threading.Barrier(6)

    def setup(_index):
        start.wait(timeout=10)
        return install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)

    with ThreadPoolExecutor(max_workers=6) as pool:
        runtimes = list(pool.map(setup, range(6)))
    assert len({id(runtime) for runtime in runtimes}) == 1
    assert runtimes[0].ready


def test_shutdown_timeout_does_not_allow_second_app_to_recover_live_worker(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    other = Flask("runtime-shutdown-contender")
    other.config["DATABASE_PATH"] = str(case.path)
    with paused_compute(monkeypatch) as (entered, release, _calls):
        ref = client.post(BASE + "/runs", json=value).get_json()["run_ref"]
        assert entered.wait(timeout=15)
        assert runtime.shutdown(timeout=0.01) is False
        with pytest.raises(RuntimeError, match="already has"):
            install_workbench_run_runtime(other, runtime_lock=case.lock_payload)
        assert WorkbenchRunService(case.conn).get(ref)["state"] == "running"
        release.set()
        assert runtime.shutdown(timeout=20)
    second = install_workbench_run_runtime(other, runtime_lock=case.lock_payload)
    try:
        assert second.ready and second.recovery["recovered"] == []
        assert WorkbenchRunService(case.conn).get(ref)["state"] == "complete"
    finally:
        assert second.shutdown()


def test_shutdown_while_waiting_old_lock_leaves_queued_without_compute(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    attempted = threading.Event()
    actual = WorkbenchRunWorker.execute

    def execute(worker, ref):
        attempted.set()
        return actual(worker, ref)

    monkeypatch.setattr(WorkbenchRunWorker, "execute", execute)
    with schedule_service._RUN_SCHEDULE_LOCK:
        ref = client.post(BASE + "/runs", json=value).get_json()["run_ref"]
        assert attempted.wait(timeout=10)
        assert runtime.shutdown(timeout=5)
    row = WorkbenchRunService(case.conn).get(ref)
    assert row["state"] == "queued" and row["started_at"] is None
    assert row["candidates"] == []


def test_running_awaiting_record_is_not_submitted_to_worker_again(owned_case, monkeypatch):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        WorkbenchRunRepository(case.conn).claim(ref, new_run_ref(), "2000-01-01T00:00:00")
    WorkbenchRunService(case.conn).recover_unfinished_runs()

    redundant_calls = []

    def forbidden(_worker, _ref):
        redundant_calls.append(_ref)
        raise AssertionError("a persisted running/awaiting run must never re-enter the worker")

    monkeypatch.setattr(WorkbenchRunWorker, "execute", forbidden)
    runtime(ref)
    assert runtime.wait_idle(timeout=5)
    row = WorkbenchRunService(case.conn).get(ref)
    assert row["state"] == "running" and row["stage"] == "awaiting_reconciliation"
    assert redundant_calls == [] and not runtime.ready


def test_thread_start_failure_disables_and_shutdown_is_safe(owned_case, monkeypatch):
    def fail(_thread):
        raise RuntimeError("BN unable to start OS thread")

    monkeypatch.setattr(threading.Thread, "start", fail)
    runtime = install_workbench_run_runtime(owned_case.app, runtime_lock=owned_case.lock_payload)
    assert not runtime.ready and "unable to start" in runtime.status["reason"]
    assert runtime.shutdown()


def test_unclaimed_worker_failure_reconciles_original_and_stops_dispatch(runtime_api, monkeypatch, caplog):
    client, case, runtime = runtime_api
    value = intent(client, case)

    def fail(_worker, _ref):
        raise OSError("BN failure before claim")

    monkeypatch.setattr(WorkbenchRunWorker, "execute", fail)
    response = client.post(BASE + "/runs", json=value)
    ref = response.get_json()["run_ref"]
    assert response.status_code == 202 and runtime.wait_idle(timeout=10)
    assert not runtime.ready
    state = client.get(BASE + "/runs/" + ref).get_json()["data"]
    assert state["state"] == "interrupted" and state["candidates"] == []
    assert ref in caplog.text and "failure before claim" in caplog.text
    assert client.post(BASE + "/runs", json=value).get_json()["replayed"]


def test_foreign_callable_dispatcher_is_never_silently_replaced(owned_case):
    app = owned_case.app
    def foreign(ref):
        return None
    app.extensions["workbench_run_dispatcher"] = foreign
    app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
    with pytest.raises(RuntimeError, match="outside managed runtime"):
        install_workbench_run_runtime(app, runtime_lock=owned_case.lock_payload)
    assert app.config["WORKBENCH_RUN_JOBS_ENABLED"] is False
    assert app.extensions["workbench_run_dispatcher"] is foreign
