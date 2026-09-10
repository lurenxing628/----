"""EY: read-only business status stays independent of real host admission."""

from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from core.services.workbench.preflight import PreflightService
from tests.workbench.preflight_support import (
    deny_writes,
    payload,
    read_only_snapshot,
    ref_for,
    seed,
    snapshot,
)
from tests.workbench.preflight_support import pf as _pf_fixture  # noqa: F401
from tests.workbench.request_lifecycle_support import http_json, http_server
from web.bootstrap import factory
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_request_lifecycle import lookup_workbench_request_lifecycle
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime

BASE = "/api/workbench/v1/scheduling"
STATUS = {"code": "schedule_not_computed", "message": "\u5c1a\u672a\u751f\u6210\u6392\u4ea7\u7ed3\u679c\u3002"}


def assert_preflight_status(data):
    assert data["counts"]["ready_tasks"] == data["eligible_tasks"] == 1
    assert data["counts"]["blocked_tasks"] == 0 and data["blockers"] == []
    assert data["run_blocked"] is True
    assert data["run_blocked_reasons"] == [STATUS]
    assert data["calendar_check"] == "not_evaluated"
    assert data["effective_start_basis"] == "window_lower_bound_not_calendar_slot"
    assert "calendar_not_evaluated" in {row["code"] for row in data["warnings"]}


def test_preflight_run_status_service_has_no_host_or_write_authority(pf):
    with read_only_snapshot(pf.conn):
        data, fingerprint = PreflightService(pf.conn).evaluate(payload(pf))
    assert_preflight_status(data)
    assert fingerprint and "write_context" not in data


@pytest.fixture(name="status_host")
def status_host(db_env, tmp_path, monkeypatch, request):
    monkeypatch.setenv("APS_ENV", "production")
    scope = str(tmp_path / "ey-preflight-launcher")
    lock = acquire_runtime_lock(scope, db_path=db_env)
    app, runtime, gate = None, None, None
    try:
        app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                      enable_security_headers=False, enable_session_cookie_hardening=False)
        app.config["TESTING"] = True
        gate = lookup_workbench_request_lifecycle(db_env)
        assert gate is not None
        with closing(get_connection(db_env)) as conn:
            seed(conn)
            settings = {"batch_refs": [ref_for(conn)], "start_date": "2026-09-09", "end_date": "2026-09-09",
                        "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"}
        if request.param:
            runtime = install_workbench_run_runtime(app, runtime_lock=lock)
            assert runtime.ready, runtime.status
        else:
            assert "workbench_run_dispatcher" not in app.extensions
            assert app.config.get("WORKBENCH_RUN_JOBS_ENABLED") is not True
        yield app, settings, runtime
    finally:
        if runtime is not None:
            assert runtime.shutdown(timeout=10), runtime.status
        if gate is not None:
            assert gate.shutdown(timeout=10), gate.status
        release_runtime_lock(scope, db_path=db_env)


@pytest.mark.parametrize("status_host", [True, False], indirect=True, ids=["service-present", "service-absent"])
def test_preflight_run_status_real_factory_http_keeps_admission_separate(status_host, monkeypatch):
    app, settings, runtime = status_host
    path = app.config["DATABASE_PATH"]
    with closing(get_connection(path)) as conn:
        before = snapshot(conn)
        schema = [tuple(row) for row in conn.execute("SELECT * FROM sqlite_master ORDER BY name")]
    reads, denied = [], []

    def authorize(action, one, two, db, trigger):
        result = deny_writes(action, one, two, db, trigger)
        if result:
            denied.append((action, one))
        return result

    def connect(db_path):
        assert db_path == path
        conn = get_connection(db_path)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT schema_version FROM pragma_schema_version").fetchall()
        conn.execute("SELECT name FROM pragma_table_info('Schedule')").fetchall()
        conn.set_authorizer(authorize)
        reads.append(conn.total_changes)
        return conn

    monkeypatch.setattr(factory, "get_connection", connect)
    with http_server(app) as port:
        assert port not in (53144, 51093, 56264, 52155, 51733)
        status, packet = http_json(port, BASE + "/preflight", settings)
        assert status == 200, packet
        data = packet["data"]
        assert_preflight_status(data)
        context = data["write_context"]
        assert context["capabilities"] == {"scheduling.preflight": True, "scheduling.run": False}
        assert context["write_token"] is None and context["expires_at"] is None
        assert context["blocked_reasons"] == [STATUS]
        status, preview = http_json(port, BASE + "/runs/preview", {"input_ref": data["input_ref"]})
        assert status == 200, preview
        authorization = preview["data"]["write_context"]
        assert preview["data"]["calendar_check"] == "not_evaluated"
        assert authorization["capabilities"]["scheduling.run"] is (runtime is not None)
        if runtime is not None:
            assert authorization["write_token"] and authorization["blocked_reasons"] == []
            assert runtime.ready and runtime.status["pending"] == []
        else:
            assert authorization["write_token"] is None
            assert {row["code"] for row in authorization["blocked_reasons"]} == {"run_worker_not_connected"}
    assert reads == [0, 0] and denied == []
    with closing(get_connection(path)) as conn:
        assert snapshot(conn) == before
        assert [tuple(row) for row in conn.execute("SELECT * FROM sqlite_master ORDER BY name")] == schema
