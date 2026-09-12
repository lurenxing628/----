"""BN fixtures use real disk SQLite, launcher locks, Flask and engine inputs."""

import threading
from contextlib import contextmanager

import pytest
from flask import Blueprint, g

from core.infrastructure.database import get_connection
from core.services.workbench import run_worker
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

BASE = "/api/workbench/v1/scheduling"


@pytest.fixture(name="owned_case")
def owned_case(job_case, tmp_path):
    case = job_case
    case.conn.execute("PRAGMA journal_mode=DELETE")
    case.app.config["DATABASE_PATH"] = str(case.path)
    case.runtime_dir = str(tmp_path / "launcher")
    case.lock_payload = acquire_runtime_lock(case.runtime_dir, db_path=str(case.path))
    try:
        yield case
    finally:
        runtime = case.app.extensions.get("workbench_run_runtime")
        if runtime is not None:
            assert runtime.shutdown(timeout=30), runtime.status
        release_runtime_lock(case.runtime_dir, db_path=str(case.path))


def install(case):
    runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert runtime.ready, runtime.status
    return runtime


@pytest.fixture(name="runtime_api")
def runtime_api(owned_case):
    case = owned_case
    bp = Blueprint("bn_run_runtime", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = get_connection(str(case.path))

    @case.app.teardown_request
    def close(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    runtime = install(case)
    return case.app.test_client(), case, runtime


def intent(client, case, key="runtime-request-00000001"):
    response = client.post(BASE + "/preflight", json=case.settings())
    assert response.status_code == 200, response.get_json()
    ref = response.get_json()["data"]["input_ref"]
    preview = client.post(BASE + "/runs/preview", json={"input_ref": ref})
    assert preview.status_code == 200, preview.get_json()
    token = preview.get_json()["data"]["write_context"]["write_token"]
    return {"input_ref": ref, "write_token": token, "request_key": key}


@contextmanager
def paused_compute(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = run_worker.compute_candidate_run

    def compute(conn, settings, projections):
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(timeout=20), "test did not release compute"
        return original(conn, settings, projections)

    monkeypatch.setattr(run_worker, "compute_candidate_run", compute)
    try:
        yield entered, release, calls
    finally:
        release.set()
