"""Admission must preserve existing audit/receipt handling and fail closed."""

import sqlite3

import pytest
from flask import Flask, Response

from core.services.workbench.system_journal import SystemMaintenanceJournal
from tests.workbench.test_request_lifecycle_support import PATHS
from tests.workbench.test_request_lifecycle_support import request_case as _request_case  # noqa: F401
from web.bootstrap.workbench_request_lifecycle import (
    install_workbench_request_lifecycle,
    track_workbench_request_connection,
)
from web.routes.workbench.api_responses import api_endpoint


def test_journal_readiness_error_still_uses_business_audit_boundary(request_case, tmp_path, caplog):
    case = request_case
    directory = tmp_path / "maintenance-results"
    directory.mkdir()
    journal = SystemMaintenanceJournal(str(directory), case.path)
    journal.begin("cf-journal-pending-000001", "create", {})
    case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = False

    @case.app.post("/api/workbench/v1/maintenance-audit")
    @api_endpoint
    def guarded():
        journal.assert_ready()
        raise AssertionError("pending journal must reject the business operation")

    response = case.app.test_client().post("/api/workbench/v1/maintenance-audit", buffered=True)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "maintenance_active"
    assert "code=maintenance_active" in caplog.text
    assert case.gate.status["state"] == "accepting" and len(case.opened) == 1
    case.release.set()
    assert case.app.test_client().post(PATHS[0], buffered=True).status_code == 200
    assert case.counts() == (1, 1) and case.gate.shutdown()


def test_container_mount_failure_before_g_db_still_closes_registered_connection(db_path):
    app = Flask("cf-mount-failure")
    app.config.update(DATABASE_PATH=db_path, TESTING=True)
    gate = install_workbench_request_lifecycle(app)

    @app.before_request
    def fail_mount():
        conn = track_workbench_request_connection(sqlite3.connect(db_path))
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','not-mounted')")
        raise SyntaxError("CF explicit container failure")

    with pytest.raises(SyntaxError, match="explicit container failure"):
        app.test_client().get("/any-business-path")
    assert gate.shutdown() and gate.status["active"] == 0
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM OpTypes WHERE op_type_id='CF'").fetchone()[0] == 0


def test_foreign_app_and_unregistered_connections_never_count_as_success(request_case):
    case = request_case
    foreign = Flask("cf-foreign-extension")
    foreign.config["DATABASE_PATH"] = case.path
    foreign.extensions["workbench_request_lifecycle"] = object()
    with pytest.raises(RuntimeError, match="foreign"):
        install_workbench_request_lifecycle(foreign)

    @case.app.get("/missing-hook")
    def missing_hook():
        from flask import g

        # Simulate a mount/teardown integration that forgot to register a fresh DB.
        case.replacement = sqlite3.connect(case.path)
        g.db = case.replacement
        return "ok"

    assert case.app.test_client().get("/missing-hook", buffered=True).status_code == 200
    assert case.gate.shutdown() is False
    assert case.gate.status["active"] == 0 and case.gate.status["cleanup_failures"] == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        case.replacement.execute("SELECT 1")


def test_response_close_callback_failure_rolls_back_and_releases_only_once(request_case):
    case, callbacks = request_case, []

    @case.app.get("/response-close-error")
    def response_close_error():
        response = Response("ok")

        @response.call_on_close
        def close():
            conn = track_workbench_request_connection(sqlite3.connect(case.path))
            conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','close-callback')")
            callbacks.append(True)
            raise SyntaxError("CF response close callback failure")

        return response

    response = case.app.test_client().get("/response-close-error", buffered=False)
    assert case.gate.status["active"] == 1
    with pytest.raises(SyntaxError, match="close callback failure"):
        response.close()
    response.close()
    assert callbacks == [True] and case.gate.status["active"] == 0
    assert case.gate.shutdown() and case.counts() == (0, 0)
