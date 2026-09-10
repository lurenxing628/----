"""Production factory hooks, real domain writes/receipts and exit backup."""

import socket
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from flask import Response, g, stream_with_context

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.services.process.op_type_service import OpTypeService
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.request_lifecycle_support import PATHS, http_json, http_server, production_server
from web.bootstrap import factory
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_request_lifecycle import lookup_workbench_request_lifecycle

BASE = "/api/workbench/v1/entities/op_type"
KEY = "cf-production-http-000001"


@pytest.fixture(name="production_app")
def production_app(db_env, tmp_path, monkeypatch):
    monkeypatch.setenv("APS_ENV", "production")
    scope = str(tmp_path / "production-launcher")
    acquire_runtime_lock(scope, db_path=db_env)
    app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                  enable_security_headers=False, enable_session_cookie_hardening=False)
    app.config["TESTING"] = True
    gate = lookup_workbench_request_lifecycle(db_env)
    assert gate is not None
    adapter = app.url_map.bind("localhost")
    for path in PATHS:
        adapter.match(path, method="GET" if path == "/workbench" else "POST")
    with closing(get_connection(db_env)) as conn:
        conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES ('auto_backup_enabled','yes')")
        conn.commit()
    try:
        yield app, gate, scope
    finally:
        if gate.shutdown(timeout=10):
            release_runtime_lock(scope, db_path=db_env)


@pytest.mark.parametrize("rollback", [False, True])
def test_production_receipt_and_connection_finish_before_exit_backup(production_app, tmp_path, monkeypatch, rollback):
    app, gate, scope = production_app
    db_path = app.config["DATABASE_PATH"]
    entered, proceed, backed_up = threading.Event(), threading.Event(), threading.Event()
    original_create, original_connect = OpTypeService.create, factory.get_connection
    opened, statements = [], []

    def connect(path):
        conn = original_connect(path)
        opened.append(conn)
        conn.set_trace_callback(statements.append)
        return conn

    def create(service, *args, **kwargs):
        result = original_create(service, *args, **kwargs)
        entered.set()
        assert proceed.wait(15)
        if rollback:
            raise sqlite3.OperationalError("CF production command rollback")
        return result

    monkeypatch.setattr(factory, "get_connection", connect)
    monkeypatch.setattr(OpTypeService, "create", create)
    manager = BackupManager(db_path, str(tmp_path / "actual-exit-backups"), logger=app.logger)
    lock = Path(db_scope_lock_path(db_path))
    original_lock = lock.read_bytes()

    def backup_and_release():
        assert factory._run_exit_backup(manager) is True
        release_runtime_lock(scope, db_path=db_path)
        backed_up.set()

    with http_server(app) as port, ThreadPoolExecutor(2) as pool:
        status, data = http_json(port, BASE, method="GET")
        assert status == 200
        body = {"request_key": KEY, "write_token": data["data"]["create_context"]["write_token"],
                "input": {"business_code": "CF-PRODUCTION", "label": "CF", "fields": {"category": "internal"}}}
        write = pool.submit(http_json, port, BASE + "/create", body)
        try:
            assert entered.wait(10)
            assert gate.shutdown(wait=False) is False
            backup = pool.submit(backup_and_release)
            assert not backed_up.wait(0.1) and lock.read_bytes() == original_lock
            before = len(opened), len(statements)
            for path in PATHS:
                assert http_json(port, path)[0] == 503
            assert (len(opened), len(statements)) == before
        finally:
            proceed.set()
        status, result = write.result(15)
        assert status == (500 if rollback else 200)
        if rollback:
            assert result["committed"] == "unknown" and result["error"]["request_key"] == KEY
        else:
            assert result["result"] == "committed" and result["receipt_ref"]
        backup.result(15)
    assert backed_up.is_set() and not lock.exists()
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            conn.execute("SELECT 1")
    backups = list((tmp_path / "actual-exit-backups").glob("*.db"))
    assert len(backups) == 1
    with closing(get_connection(str(backups[0]))) as conn:
        receipt = WorkbenchCommandService(conn).lookup(KEY)
        assert bool(receipt) is (not rollback)
        assert conn.execute("SELECT COUNT(*) FROM OpTypes WHERE op_type_id='CF-PRODUCTION'").fetchone()[0] == int(not rollback)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_factory_logged_db_close_failure_cannot_authorize_backup_or_unlock(production_app, tmp_path, monkeypatch, caplog):
    app, gate, _scope = production_app
    db_path = app.config["DATABASE_PATH"]

    class CloseFailure(sqlite3.Connection):
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise sqlite3.OperationalError("CF factory db.close failure")
            super().close()

    def connect(path):
        conn = sqlite3.connect(path, factory=CloseFailure)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(factory, "get_connection", connect)
    response = app.test_client().get(BASE, buffered=True)
    assert response.status_code == 200
    assert "CF factory db.close failure" in caplog.text
    assert gate.status["active"] == 0 and gate.shutdown() is False
    manager = BackupManager(db_path, str(tmp_path / "forbidden-backup"), logger=app.logger)
    assert factory._run_exit_backup(manager) is False
    assert Path(db_scope_lock_path(db_path)).exists()
    assert not list((tmp_path / "forbidden-backup").glob("*.db"))


def test_actual_production_server_disconnect_finishes_stream_and_sqlite_rollback(production_app, monkeypatch):
    app, gate, _scope = production_app
    waiting, release, finalized = threading.Event(), threading.Event(), threading.Event()
    db_path = app.config["DATABASE_PATH"]
    lock = Path(db_scope_lock_path(db_path))

    @app.get("/api/workbench/v1/cf-production-stream")
    def stream():
        @stream_with_context
        def rows():
            try:
                g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF-STREAM','uncommitted')")
                yield b"first\n"
                waiting.set()
                assert release.wait(10)
                yield b"x" * (4 * 1024 * 1024)
            finally:
                finalized.set()
        return Response(rows(), content_type="text/plain")

    with production_server(app, monkeypatch) as port:
        client = socket.create_connection(("127.0.0.1", port), timeout=10)
        client.sendall(b"GET /api/workbench/v1/cf-production-stream HTTP/1.1\r\nHost: localhost\r\n\r\n")
        try:
            assert waiting.wait(10)
            client.recv(512)
            client.shutdown(socket.SHUT_RDWR)
            client.close()
            assert gate.shutdown(timeout=0.05) is False and lock.exists()
        finally:
            client.close()
            release.set()
        assert gate.shutdown(timeout=10), gate.status
    assert finalized.is_set() and gate.status["active"] == 0
    with closing(get_connection(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM OpTypes WHERE op_type_id='CF-STREAM'").fetchone()[0] == 0
