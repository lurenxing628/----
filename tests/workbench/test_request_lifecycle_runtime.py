"""Actual run runtime + engine: HTTP acceptance precedes worker shutdown."""

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from flask import Blueprint, g, request

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.services.workbench.run_jobs import WorkbenchRunService
from tests.workbench.request_lifecycle_support import http_json, http_server
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import BASE, install, paused_compute
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import release_runtime_lock
from web.bootstrap.workbench_request_lifecycle import (
    close_workbench_request_connection,
    install_workbench_request_lifecycle,
    stop_workbench_requests_for_database,
    track_workbench_request_connection,
)
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes


def test_real_runtime_http_then_worker_then_backup_and_unlock(owned_case, tmp_path, monkeypatch):
    case = owned_case
    gate = install_workbench_request_lifecycle(case.app)
    bp = Blueprint("workbench", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)
    entered, proceed, drained, exited = [threading.Event() for _ in range(4)]
    saved = {}

    @case.app.before_request
    def open_db():
        g.db = track_workbench_request_connection(get_connection(str(case.path)))
        if request.path == BASE + "/runs":
            entered.set()
            assert proceed.wait(15)

    @case.app.teardown_appcontext
    def close_db(_error):
        conn = g.pop("db", None)
        if conn is not None:
            close_workbench_request_connection(conn)

    runtime = install(case)
    lock = Path(db_scope_lock_path(str(case.path)))
    original_lock = lock.read_bytes()

    def shutdown():
        assert stop_workbench_requests_for_database(case.path, wait=True)
        drained.set()
        assert runtime.shutdown(wait=True, timeout=20)
        saved["backup"] = BackupManager(str(case.path), str(tmp_path / "exit-backups")).backup("exit")
        release_runtime_lock(case.runtime_dir, db_path=str(case.path))
        exited.set()

    with paused_compute(monkeypatch) as (computing, compute_release, calls):
        with http_server(case.app) as port, ThreadPoolExecutor(2) as pool:
            status, preflight = http_json(port, BASE + "/preflight", case.settings())
            assert status == 200
            ref = preflight["data"]["input_ref"]
            status, preview = http_json(port, BASE + "/runs/preview", {"input_ref": ref})
            assert status == 200
            body = {"input_ref": ref, "write_token": preview["data"]["write_context"]["write_token"],
                    "request_key": "cf-shutdown-real-runtime-0001"}
            writer = pool.submit(http_json, port, BASE + "/runs", body)
            try:
                assert entered.wait(10)
                assert gate.shutdown(wait=False) is False
                stopping = pool.submit(shutdown)
                assert not drained.wait(0.05) and runtime.ready
                assert lock.read_bytes() == original_lock
                proceed.set()
                assert computing.wait(15)
                status, accepted = writer.result(10)
                assert status == 202 and accepted.get("dispatch_pending") is not True
                assert drained.wait(10) and not exited.wait(0.05)
                assert lock.read_bytes() == original_lock
                assert runtime._thread.is_alive()
            finally:
                proceed.set()
                compute_release.set()
            stopping.result(25)
    assert exited.is_set() and not lock.exists() and len(calls) == 1
    assert not runtime._thread.is_alive() and gate.status["active"] == 0
    with closing(get_connection(saved["backup"])) as backup:
        result = WorkbenchRunService(backup).lookup(body["request_key"])
        assert result["state"] == "complete" and len(result["candidates"]) == 4
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
