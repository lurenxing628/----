"""Real threaded HTTP waits until SQLite commit/rollback AND response close."""

import socket
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flask import Response, abort, g, stream_with_context

from tests.workbench.test_request_lifecycle_support import PATHS, http_json, http_server
from tests.workbench.test_request_lifecycle_support import request_case as _request_case  # noqa: F401
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock


@pytest.mark.parametrize("rollback", [False, True])
def test_http_transaction_and_close_finish_before_lock_release(request_case, tmp_path, rollback):
    case = request_case
    case.app.config["TESTING"] = False
    case.rollback = rollback
    case.close_release.clear()
    scope = str(tmp_path / "launcher")
    payload = acquire_runtime_lock(scope, db_path=case.path)
    lock = Path(db_scope_lock_path(case.path))
    original = lock.read_bytes()
    done = threading.Event()

    def shutdown():
        assert case.gate.shutdown(wait=True)
        assert case.counts() == ((0, 0) if rollback else (1, 1))
        release_runtime_lock(scope, db_path=case.path)
        done.set()

    try:
        with http_server(case.app) as port, ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(http_json, port, PATHS[0])
            try:
                assert case.entered.wait(10)
                assert case.gate.shutdown(wait=False) is False
                drain = pool.submit(shutdown)
                assert not done.wait(0.1)
                assert lock.read_bytes() == original and Path(payload["path"]).exists()
                opened, statements = len(case.opened), len(case.statements)
                for path in PATHS:
                    status, response = http_json(port, path)
                    assert status == 503
                    if path.startswith("/api/workbench/"):
                        assert set(response) == {"ok", "committed", "error"}
                        assert response["committed"] is False
                        assert response["error"]["code"] == "request_lifecycle_stopping"
                        assert set(response["error"]) == {"code", "message", "fields", "retryable", "request_ref"}
                        assert "未受理" in response["error"]["message"]
                    else:
                        assert "未受理" in response.decode("utf-8")
                assert (len(case.opened), len(case.statements)) == (opened, statements)
                case.release.set()
                assert case.close_entered.wait(10)
                assert not done.wait(0.1) and lock.read_bytes() == original
            finally:
                case.release.set()
                case.close_release.set()
            assert writer.result(10)[0] == (500 if rollback else 200)
            drain.result(10)
        assert done.is_set() and not lock.exists() and case.gate.status["active"] == 0
    finally:
        release_runtime_lock(scope, db_path=case.path)


@pytest.mark.parametrize("teardown_kind", ["request", "appcontext"])
def test_teardown_exception_releases_exactly_once_after_fallback_rollback(request_case, teardown_kind):
    case = request_case

    @case.app.get("/uncommitted")
    def uncommitted():
        g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','unfinished')")
        return "not committed"

    def fail(_error):
        raise RuntimeError("CF teardown interrupted")

    getattr(case.app, "teardown_" + teardown_kind)(fail)
    with pytest.raises(RuntimeError, match="teardown interrupted"):
        case.app.test_client().get("/uncommitted")
    assert case.gate.status["active"] == 0 and case.gate.shutdown() is True
    assert case.counts() == (0, 0)


@pytest.mark.parametrize("status", [400, 404, 500])
def test_http_exception_preserves_error_and_rolls_back(request_case, status):
    case = request_case

    @case.app.get("/error")
    def error():
        g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','unfinished')")
        abort(status)

    response = case.app.test_client().get("/error", buffered=True)
    assert response.status_code == status
    response.close()
    assert case.gate.shutdown() and case.counts() == (0, 0)


def test_stream_close_retains_ticket_and_closes_uncommitted_connection(request_case):
    case = request_case
    stream_closed = threading.Event()

    @case.app.get("/stream")
    def stream():
        @stream_with_context
        def rows():
            try:
                g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','unfinished')")
                yield b"first"
                yield b"second"
            finally:
                stream_closed.set()
        return Response(rows())

    response = case.app.test_client().get("/stream", buffered=False)
    assert case.gate.status["active"] == 1
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(case.gate.shutdown, False).result(5) is False
    response.close()
    response.close()
    assert stream_closed.is_set() and case.gate.shutdown() is True
    assert case.counts() == (0, 0) and case.gate.status["active"] == 0


def test_real_client_disconnect_does_not_abort_accepted_write(request_case):
    case = request_case
    with http_server(case.app) as port:
        client = socket.create_connection(("127.0.0.1", port), timeout=10)
        client.sendall(("POST " + PATHS[0] + " HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n").encode("ascii"))
        try:
            assert case.entered.wait(10)
            client.shutdown(socket.SHUT_RDWR)
            client.close()
            assert case.gate.shutdown(timeout=0.05) is False
        finally:
            client.close()
            case.release.set()
        assert case.gate.shutdown(timeout=10)
    assert case.counts() == (1, 1)


def test_streaming_client_disconnect_closes_generator_and_rolls_back(request_case):
    case = request_case
    waiting, finalized, exhausted = threading.Event(), threading.Event(), threading.Event()

    @case.app.get("/stream-disconnect")
    def stream():
        @stream_with_context
        def rows():
            try:
                g.db.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('CF','stream')")
                yield b"first\n"
                waiting.set()
                assert case.release.wait(10)
                yield b"x" * (4 * 1024 * 1024)
                exhausted.set()
            finally:
                finalized.set()
        return Response(rows(), content_type="text/plain")

    with http_server(case.app) as port:
        client = socket.create_connection(("127.0.0.1", port), timeout=10)
        client.sendall(b"GET /stream-disconnect HTTP/1.1\r\nHost: localhost\r\n\r\n")
        try:
            assert waiting.wait(10)
            client.recv(512)
            client.shutdown(socket.SHUT_RDWR)
            client.close()
            assert case.gate.shutdown(timeout=0.05) is False and not finalized.is_set()
        finally:
            client.close()
            case.release.set()
        assert case.gate.shutdown(timeout=10), (case.gate.status, finalized.is_set(), exhausted.is_set())
    assert finalized.is_set() and not exhausted.is_set()
    assert case.counts() == (0, 0)


def test_close_failure_poison_survives_factory_logging_and_cleanup_retry(request_case):
    case = request_case

    class BrokenClose(sqlite3.Connection):
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise sqlite3.OperationalError("CF injected close failure")
            super().close()

    case.connection_factory = BrokenClose
    case.release.set()
    response = case.app.test_client().post(PATHS[0], buffered=True)
    assert response.status_code == 200
    assert case.gate.status["active"] == 0
    assert case.gate.status["cleanup_failures"] == 1
    assert case.gate.shutdown(timeout=0) is False
    assert case.counts() == (1, 1)
