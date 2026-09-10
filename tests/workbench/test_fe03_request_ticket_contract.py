"""FE-03: concrete request ownership and once-only cleanup, without file DBs."""

import sqlite3
from types import SimpleNamespace
from typing import cast

import pytest
from flask import Flask

from web.bootstrap.workbench_request_lifecycle_state import (
    RequestFrame,
    RequestTicket,
    WorkbenchRequestLifecycle,
    current_frame,
)
from web.bootstrap.workbench_request_lifecycle_wsgi import RequestIterable, frame_scope


def admitted():
    app = Flask("fe03-ticket")
    gate = WorkbenchRequestLifecycle("fe03-no-file-database")
    frame = RequestFrame(app, gate)
    frame.ticket = gate.admit(app)
    assert isinstance(frame.ticket, RequestTicket)
    return gate, frame, frame.ticket


@pytest.mark.parametrize("invalid", [object(), SimpleNamespace(finished=True), SimpleNamespace(finished=False)])
def test_arbitrary_objects_cannot_be_accepted_as_finished_tickets(invalid):
    gate, frame, original = admitted()
    try:
        frame.ticket = cast(RequestTicket, invalid)
        with pytest.raises(RuntimeError, match="Invalid request lifecycle ticket"):
            frame.finish()
        with pytest.raises(RuntimeError, match="Invalid request lifecycle ticket"):
            gate.release(cast(RequestTicket, invalid))
        assert gate.status["active"] == 1 and not original.finished
    finally:
        frame.ticket = original
        frame.finish()
    assert gate.shutdown()


@pytest.mark.parametrize("foreign_app", [False, True])
def test_foreign_gate_or_app_ticket_cannot_close_or_release_another_request(foreign_app):
    gate, frame, original = admitted()
    other_gate = gate if foreign_app else WorkbenchRequestLifecycle("fe03-other-db")
    other = RequestFrame(Flask("fe03-other-app") if foreign_app else frame.app, other_gate)
    other.ticket = other_gate.admit(other.app)
    assert other.ticket is not None
    conn = sqlite3.connect(":memory:")
    try:
        frame.ticket = other.ticket
        for action in (lambda: frame.track(conn), lambda: frame.close_connection(conn), frame.finish):
            with pytest.raises(RuntimeError, match="Foreign request ticket"):
                action()
        assert conn.execute("SELECT 1").fetchone()[0] == 1
        assert not original.finished and not other.ticket.finished
    finally:
        conn.close()
        frame.ticket = original
        frame.finish()
        other.finish()
    assert gate.shutdown() and other_gate.shutdown()


def test_missing_ticket_cannot_track_or_close_a_connection():
    gate, frame, _ticket = admitted()
    frame.finish()
    frame.ticket = None
    conn = sqlite3.connect(":memory:")
    try:
        for action in (lambda: frame.track(conn), lambda: frame.close_connection(conn)):
            with pytest.raises(RuntimeError, match="outside an admitted HTTP request"):
                action()
        frame.finish()
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        conn.close()
    assert gate.shutdown()


def test_tracked_connection_keeps_its_concrete_api_and_rolls_back_once(monkeypatch):
    gate, frame, ticket = admitted()
    calls = []
    original_release = gate.release

    def release(ticket):
        calls.append(ticket)
        original_release(ticket)

    monkeypatch.setattr(gate, "release", release)
    conn = sqlite3.connect(":memory:")
    assert frame.track(conn).execute("SELECT 1").fetchone()[0] == 1
    assert frame.track(conn) is conn
    assert len(ticket.connections) == 1
    frame.finish()
    frame.finish()
    assert len(calls) == 1 and ticket.connections[0].closed
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    assert gate.shutdown()


def test_base_exception_retry_does_not_erase_cleanup_failure():
    gate, frame, ticket = admitted()

    class Connection:
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise KeyboardInterrupt("fe03 cleanup interrupted")

    conn = frame.track(Connection())
    with pytest.raises(KeyboardInterrupt, match="cleanup interrupted"):
        frame.close_connection(conn)
    assert not ticket.connections_closed
    frame.finish()
    frame.finish()
    assert conn.attempts == 2 and ticket.connections_closed
    assert ticket.failures == ["connection_close_failed"]
    assert gate.status["active"] == 0 and gate.status["cleanup_failures"] == 1
    assert gate.shutdown() is False


def test_unregistered_connection_cleanup_poison_is_retained():
    gate, frame, ticket = admitted()
    conn = sqlite3.connect(":memory:")
    frame.close_connection(conn)
    assert ticket.failures == ["unregistered_connection"]
    frame.finish()
    assert gate.status["active"] == 0 and gate.shutdown() is False


def test_iteration_and_close_base_exceptions_restore_frame_and_release_once(monkeypatch):
    gate, frame, _ticket = admitted()
    conn = frame.track(sqlite3.connect(":memory:"))
    events = []
    original_release = gate.release

    def release(ticket):
        events.append("release")
        original_release(ticket)

    class BrokenSource:
        def __iter__(self):
            return self

        def __next__(self):
            assert current_frame() is frame
            raise GeneratorExit("fe03 iteration stopped")

        def close(self):
            assert current_frame() is frame
            events.append("close")
            raise KeyboardInterrupt("fe03 close stopped")

    monkeypatch.setattr(gate, "release", release)
    response = RequestIterable(BrokenSource(), frame)
    assert current_frame() is None
    with pytest.raises(KeyboardInterrupt, match="close stopped"):
        next(response)
    response.close()
    assert current_frame() is None and events == ["close", "release"]
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    assert gate.shutdown()


def test_nested_scope_restores_exact_previous_request_frame():
    gate, frame, _ticket = admitted()
    other_gate, other, _other_ticket = admitted()
    with frame_scope(frame):
        assert current_frame() is frame
        with frame_scope(other):
            assert current_frame() is other
        assert current_frame() is frame
    assert current_frame() is None
    frame.finish()
    other.finish()
    assert gate.shutdown() and other_gate.shutdown()
