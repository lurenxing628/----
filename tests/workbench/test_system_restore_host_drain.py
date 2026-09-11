"""Actual factory HTTP response/connection and actual compute worker drain."""

import socket
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest
from flask import Response, g, request, stream_with_context

from core.infrastructure.backup import BackupManager, current_thread_holds_maintenance_window
from core.infrastructure.database import get_connection
from core.services.scheduler import schedule_service
from core.services.workbench.run_jobs import WorkbenchRunService
from tests.workbench.run_runtime_support import paused_compute
from tests.workbench.system_restore_host_support import BASE, KEY, http_json, http_server, seed_worker
from tests.workbench.system_restore_host_support import restore_host as _restore_host  # noqa: F401
from web.bootstrap import factory


@pytest.mark.parametrize("legacy_request", [False, True])
def test_restore_waits_for_response_iteration_and_real_worker_before_protection(restore_host, monkeypatch, legacy_request):
    case = restore_host
    held_path = "/dh-held-response" if legacy_request else "/api/workbench/v1/dh-held-response"
    stream_entered, stream_release, finalized = threading.Event(), threading.Event(), threading.Event()
    draining, protecting = threading.Event(), threading.Event()

    @case.app.get(held_path)
    def held_response():
        @stream_with_context
        def rows():
            try:
                g.db.execute("SELECT config_value FROM SystemConfig WHERE config_key='DH'").fetchone()
                yield b"first\n"
                stream_entered.set()
                assert stream_release.wait(15)
                yield b"last\n"
            finally:
                finalized.set()
        return Response(rows(), content_type="text/plain")

    body = case.intent()
    ref = seed_worker(case)["run_ref"]
    drain, backup = case.host._drain, BackupManager.backup
    def drain_probe(lease):
        draining.set()
        return drain(lease)
    def backup_probe(manager, suffix=None):
        if suffix and "before_restore" in suffix:
            assert finalized.is_set()
            assert not case.runtime._thread.is_alive()
            assert schedule_service._RUN_SCHEDULE_LOCK.locked()
            assert current_thread_holds_maintenance_window(case.path)
            case.assert_locks_held()
            protecting.set()
        return backup(manager, suffix)
    monkeypatch.setattr(case.host, "_drain", drain_probe)
    monkeypatch.setattr(BackupManager, "backup", backup_probe)
    with paused_compute(monkeypatch) as (worker_entered, worker_release, calls):
        case.runtime(ref)
        assert worker_entered.wait(10)
        with http_server(case.app) as port, ThreadPoolExecutor(2) as pool:
            stream = pool.submit(http_json, port, held_path, method="GET")
            restoring = None
            try:
                assert stream_entered.wait(10)
                restoring = pool.submit(http_json, port, BASE + "/backups/restore", body)
                assert draining.wait(10)
                assert not protecting.wait(0.1)
                assert http_json(port, "/scheduler/", method="GET")[0] == 503
                assert http_json(port, BASE + "/results/" + KEY, method="GET")[1]["data"]["operation"]["terminal"] is False
                worker_release.set()
                assert case.runtime.shutdown(timeout=10)
                assert not protecting.wait(0.1), "response iterator is still active"
            finally:
                worker_release.set()
                stream_release.set()
            assert stream.result(10)[0] == 200
            status, payload = restoring.result(15)
            assert status == 200 and payload["data"]["operation"]["state"] == "succeeded", payload
    result = payload["data"]["operation"]
    with closing(get_connection(str(case.backups / result["protection_filename"]))) as conn:
        run = WorkbenchRunService(conn).get(ref)
        assert run["state"] == ("failed" if legacy_request else "complete")
        if legacy_request:
            assert run["error"]["code"] == "snapshot_stale"
    assert len(calls) == 1 and protecting.is_set()


def test_restore_waits_for_other_request_database_close(restore_host, monkeypatch):
    case = restore_host
    close_entered, close_release, draining = threading.Event(), threading.Event(), threading.Event()
    @case.app.get("/dh-held-close")
    def held():
        return {"ok": True}
    body = case.intent()
    original, drain = factory.get_connection, case.host._drain
    class HeldClose(sqlite3.Connection):
        def close(self):
            close_entered.set()
            assert close_release.wait(15)
            super().close()
    def connect(path):
        if request.path != "/dh-held-close":
            return original(path)
        conn = sqlite3.connect(path, factory=HeldClose)
        conn.row_factory = sqlite3.Row
        return conn
    def drain_probe(lease):
        draining.set()
        return drain(lease)
    monkeypatch.setattr(factory, "get_connection", connect)
    monkeypatch.setattr(case.host, "_drain", drain_probe)
    with http_server(case.app) as port, ThreadPoolExecutor(2) as pool:
        other = pool.submit(http_json, port, "/dh-held-close", method="GET")
        restoring = None
        try:
            assert close_entered.wait(10)
            restoring = pool.submit(http_json, port, BASE + "/backups/restore", body)
            assert draining.wait(10)
            assert not restoring.done()
            assert not list(case.backups.glob("*before_restore.db"))
            case.assert_locks_held()
        finally:
            close_release.set()
        assert other.result(10)[0] == 200
        assert restoring.result(10)[1]["data"]["operation"]["state"] == "succeeded"


@pytest.mark.parametrize("audit_connection", [False, True])
def test_restore_connection_close_failure_stays_stopped(restore_host, monkeypatch, audit_connection):
    case = restore_host
    body = case.intent()
    class FailedClose(sqlite3.Connection):
        attempts = 0
        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise sqlite3.OperationalError("DH close failure")
            super().close()
    def connect(path):
        conn = sqlite3.connect(path, factory=FailedClose)
        conn.row_factory = sqlite3.Row
        return conn
    if audit_connection:
        monkeypatch.setattr("web.bootstrap.workbench_system_restore.get_connection", connect)
    else:
        hook = next(item for item in case.app.before_request_funcs[None] if item.__name__ == "_open_db")
        monkeypatch.setitem(hook.__globals__, "get_connection", connect)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["operation"]["state"] == "recovery_required"
    assert case.gate.shutdown(timeout=0) is False
    assert not case.runtime.ready
    assert case.marker() == ("selected" if audit_connection else "current")
    assert case.journal.lookup(KEY)["state"] == "recovery_required"
    assert case.client.get("/workbench", buffered=True).status_code == 503


def test_client_disconnect_loses_http_ack_but_not_durable_restore_result(restore_host, monkeypatch):
    import json
    case = restore_host
    body = case.intent()
    entered, release = threading.Event(), threading.Event()
    backup = BackupManager.backup
    def pause(manager, suffix=None):
        if suffix and "before_restore" in suffix:
            entered.set()
            assert release.wait(15)
        return backup(manager, suffix)
    monkeypatch.setattr(BackupManager, "backup", pause)
    with http_server(case.app) as port:
        client = socket.create_connection(("127.0.0.1", port), timeout=10)
        content = json.dumps(body).encode("ascii")
        headers = ("POST " + BASE + "/backups/restore HTTP/1.1\r\nHost: localhost\r\n"
                   "Content-Type: application/json\r\nContent-Length: " + str(len(content)) + "\r\n\r\n")
        client.sendall(headers.encode("ascii") + content)
        try:
            assert entered.wait(10)
            client.shutdown(socket.SHUT_RDWR)
            client.close()
        finally:
            client.close()
            release.set()
        with case.gate._condition:
            assert case.gate._condition.wait_for(lambda: case.gate.status["active"] == 0, timeout=15)
        status, result = http_json(port, BASE + "/results/" + KEY, method="GET")
        assert status == 200 and result["data"]["operation"]["state"] == "succeeded", result
        assert http_json(port, BASE + "/backups/restore", body)[0] == 503
        assert len(list(case.backups.glob("*before_restore.db"))) == 1
    assert case.marker() == "selected"
    case.assert_locks_held()
