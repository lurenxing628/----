"""CF-only temporary SQLite, real Flask/HTTP and caller-owned lock fixtures."""

import http.client
import json
import sqlite3
import threading
from contextlib import contextmanager

import pytest
from flask import Flask, g, request
from werkzeug.serving import make_server

from core.models.workbench_command import WorkbenchCommandOutcome
from core.services.workbench.commands import WorkbenchCommandService
from web.bootstrap.workbench_request_lifecycle import (
    WorkbenchRequestHandler,
    close_workbench_request_connection,
    install_workbench_request_lifecycle,
    track_workbench_request_connection,
)

KEY = "cf-request-lifecycle-000001"
PATHS = ("/api/workbench/v1/scheduling/candidates/example/adopt",
         "/api/workbench/v1/execution/tasks/example/reports",
         "/api/workbench/v1/execution/files/confirm",
         "/api/workbench/v1/entities/batch/import-confirm", "/workbench")


class LifecycleCase:
    def __init__(self, path):
        self.path = str(path)
        self.app = Flask("cf-request-lifecycle")
        self.app.config.update(DATABASE_PATH=self.path, TESTING=True)
        self.gate = install_workbench_request_lifecycle(self.app)
        self.opened, self.closed, self.statements = [], [], []
        self.entered, self.release = threading.Event(), threading.Event()
        self.close_entered, self.close_release = threading.Event(), threading.Event()
        self.close_release.set()
        self.rollback = False
        self.connection_factory = sqlite3.Connection
        self._bind()

    def _bind(self):
        @self.app.before_request
        def open_db():
            conn = sqlite3.connect(self.path, timeout=10, factory=self.connection_factory)
            track_workbench_request_connection(conn)
            conn.row_factory = sqlite3.Row
            conn.set_trace_callback(self.statements.append)
            g.db = conn
            self.opened.append(request.path)

        @self.app.teardown_appcontext
        def close_db(_error):
            conn = g.pop("db", None)
            if conn is not None:
                self.close_entered.set()
                assert self.close_release.wait(10), "fixture did not release DB close"
                try:
                    close_workbench_request_connection(conn)
                except Exception:
                    self.app.logger.exception("factory-style logged close failure")
                self.closed.append(conn)

        for index, path in enumerate(PATHS):
            self.app.add_url_rule(path, "write_" + str(index), self.write, methods=["POST", "GET"])

    def write(self):
        def mutate(_context):
            g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','Lifecycle')")
            self.entered.set()
            assert self.release.wait(10), "fixture did not release HTTP transaction"
            if self.rollback:
                raise sqlite3.OperationalError("CF injected transaction rollback")
            return WorkbenchCommandOutcome("committed", {"code": "CF"})
        return WorkbenchCommandService(g.db).execute(
            request_key=KEY, action="op_type.create", context_ref="op_type.collection",
            normalized_input={"code": "CF"}, guard=lambda: None, mutate=mutate)

    def counts(self):
        with sqlite3.connect(self.path) as conn:
            return (conn.execute("SELECT COUNT(*) FROM OpTypes WHERE op_type_id='CF'").fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE request_key=?", (KEY,)).fetchone()[0])


@pytest.fixture(name="request_case")
def request_case(db_path):
    case = LifecycleCase(db_path)
    try:
        yield case
    finally:
        case.release.set()
        case.close_release.set()


@contextmanager
def http_server(app):
    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
    assert server.server_port not in (63938, 51093)
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join(10)
        server.server_close()
        assert not thread.is_alive()


def http_json(port, path, body=None, method="POST"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        conn.request(method, path, body=json.dumps(body or {}), headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        return response.status, json.loads(data) if data.startswith(b"{") else data
    finally:
        conn.close()


@contextmanager
def production_server(app, monkeypatch):
    from web.bootstrap import factory

    original = factory.make_server
    created, errors, ready = [], [], threading.Event()

    def make(*args, **kwargs):
        server = original(*args, **kwargs)
        created.append(server)
        ready.set()
        return server

    def serve():
        try:
            factory.serve_runtime_app(app, "127.0.0.1", 0)
        except BaseException as exc:
            errors.append(exc)
            ready.set()

    monkeypatch.setattr(factory, "make_server", make)
    thread = threading.Thread(target=serve)
    thread.start()
    try:
        assert ready.wait(10) and not errors, errors
        server = created[0]
        assert server.RequestHandlerClass is WorkbenchRequestHandler
        assert server.server_port not in (63938, 51093)
        yield server.server_port
    finally:
        if created:
            created[0].shutdown()
        thread.join(10)
        if created:
            created[0].server_close()
        assert not thread.is_alive() and not errors, errors
