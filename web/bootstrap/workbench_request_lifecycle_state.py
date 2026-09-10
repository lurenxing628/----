"""In-process DB admission state, independent of workers and launcher locks."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Protocol, Set, TypeVar

from flask import Flask, has_request_context

_LOCAL = threading.local()


def current_frame() -> Optional[RequestFrame]:
    return getattr(_LOCAL, "frame", None)


def reject_request_wait():
    if has_request_context() or current_frame() is not None:
        raise RuntimeError("Request threads cannot shutdown/drain HTTP requests")


class RequestConnection(Protocol):
    def close(self) -> None:
        ...


_ConnectionT = TypeVar("_ConnectionT", bound=RequestConnection)


@dataclass
class ConnectionState:
    connection: RequestConnection
    closed: bool = False


class RequestTicket:
    def __init__(self, app: Flask):
        self.app = app
        self.thread = threading.get_ident()
        self.connections: List[ConnectionState] = []
        self.finished = False
        self.failures: List[str] = []

    @property
    def connections_closed(self) -> bool:
        return all(item.closed for item in self.connections)


class WorkbenchRequestLifecycle:
    """One barrier per normalized DB; each app/request owns a distinct ticket.

    True from shutdown/drain proves only HTTP quiescence. The host MUST then
    join its existing run runtime before backup or launcher-lock release.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self._condition = threading.Condition(threading.RLock())
        self._active: Set[RequestTicket] = set()
        self._state = "accepting"
        self._failures = 0
        self._owner: Optional[MaintenanceOwner] = None

    @property
    def status(self):
        with self._condition:
            return {"database_path": self.db_path, "state": self._state,
                    "active": len(self._active), "cleanup_failures": self._failures,
                    "drained": self._state != "accepting" and not self._active and not self._failures}

    def admit(self, app: Flask) -> Optional[RequestTicket]:
        with self._condition:
            if self._state != "accepting":
                return None
            ticket = RequestTicket(app)
            self._active.add(ticket)
            return ticket

    def release(self, ticket: RequestTicket) -> None:
        if not isinstance(ticket, RequestTicket):
            raise RuntimeError("Invalid request lifecycle ticket")
        with self._condition:
            if ticket.finished:
                return
            if ticket not in self._active:
                raise RuntimeError("Foreign request ticket cannot release this database")
            ticket.finished = True
            self._active.remove(ticket)
            if ticket.failures or not ticket.connections_closed:
                self._failures += 1
                self._state = "stopping"
            self._condition.notify_all()

    def shutdown(self, wait=True, timeout=None):
        """Irreversibly stop admission; False never authorizes lock release.

        May run on any non-request lifecycle thread. A timeout leaves admission
        closed. No thread is killed, and no transaction is ended by this call.
        """
        reject_request_wait()
        with self._condition:
            if any(ticket.thread == threading.get_ident() for ticket in self._active):
                raise RuntimeError("Request threads cannot shutdown/drain their unclosed HTTP response")
            self._state = "stopping"
            self._condition.notify_all()
            return self._wait(wait, timeout)

    def drain(self, wait=True, timeout=None):
        return self.shutdown(wait=wait, timeout=timeout)

    def _wait(self, wait, timeout, owner: Optional[RequestTicket] = None):
        deadline = None if timeout is None else time.monotonic() + max(0, timeout)
        while self._active.difference({owner} if owner else set()):
            remaining = None if deadline is None else deadline - time.monotonic()
            if not wait or (remaining is not None and remaining <= 0):
                return False
            self._condition.wait(remaining)
        return not self._failures

    def maintenance_owner(self):
        """Explicit current-request capability, NOT an endpoint/DB-wide bypass.

        The future restore host must first finish business validation/auditing,
        acquire this lease, close its own registered DB connections, and check
        lease.drain(). It must also quiesce workers and own the existing file
        maintenance window. This API performs none of those restore actions.
        """
        frame = current_frame()
        ticket = None if frame is None or frame.gate is not self else frame.ticket
        with self._condition:
            if ticket is None or ticket not in self._active or ticket.thread != threading.get_ident():
                raise RuntimeError("Maintenance requires this DB's exact active request owner")
            if self._state != "accepting" or self._owner is not None:
                raise RuntimeError("Request lifecycle is already stopping or under maintenance")
            self._owner = MaintenanceOwner(self, ticket)
            self._state = "maintenance"
            return self._owner


class MaintenanceOwner:
    """Exclude exactly one admitted request, never subtract a guessed count.

    Request-thread readiness is nonblocking. A non-request coordinator may wait.
    No newly arriving HTTP request can borrow this capability, even in the same
    app or on the same thread. Owner completion does not automatically reopen.
    """

    def __init__(self, gate: WorkbenchRequestLifecycle, ticket: RequestTicket):
        self._gate, self._ticket = gate, ticket

    def _validate(self):
        gate, ticket = self._gate, self._ticket
        if (gate._owner is not self or gate._state != "maintenance"
                or ticket not in gate._active or ticket.finished):
            raise RuntimeError("Maintenance owner is expired or lifecycle is stopping")
        frame = current_frame()
        if frame is not None and frame.ticket is not ticket:
            raise RuntimeError("Another request cannot borrow the maintenance owner")
        if has_request_context() and frame is None:
            raise RuntimeError("Foreign request context cannot borrow the maintenance owner")

    def drain(self, wait=False, timeout=None):
        if wait:
            reject_request_wait()
            if self._ticket.thread == threading.get_ident():
                raise RuntimeError("Request threads cannot wait for their maintenance response")
        gate, ticket = self._gate, self._ticket
        with gate._condition:
            self._validate()
            if not ticket.connections_closed or ticket.failures:
                return False
            result = gate._wait(wait, timeout, owner=ticket)
            self._validate()
            return result and ticket.connections_closed and not ticket.failures

    def resume(self):
        """Only the original request may explicitly reopen after verified work.

        Never use this in a finally block: unresolved maintenance must stay shut.
        A shutdown that raced with maintenance cannot be undone by this lease.
        """
        gate, ticket = self._gate, self._ticket
        with gate._condition:
            self._validate()
            frame = current_frame()
            if frame is None or frame.ticket is not ticket:
                raise RuntimeError("Only the original maintenance request can resume admission")
            if not self.drain():
                raise RuntimeError("Maintenance has not drained all request connections")
            gate._owner = None
            gate._state = "accepting"
            gate._condition.notify_all()


class RequestFrame:
    """Typed request ownership and connection cleanup, without WSGI imports."""

    def __init__(self, app: Flask, gate: WorkbenchRequestLifecycle):
        self.app, self.gate = app, gate
        self.ticket: Optional[RequestTicket] = None

    def _active_ticket(self) -> RequestTicket:
        ticket = self.ticket
        if not isinstance(ticket, RequestTicket) or ticket.finished:
            raise RuntimeError("DB connection opened outside an admitted HTTP request")
        if ticket.app is not self.app or ticket not in self.gate._active:
            raise RuntimeError("Foreign request ticket cannot own this request frame")
        return ticket

    def track(self, conn: _ConnectionT) -> _ConnectionT:
        ticket = self._active_ticket()
        if not any(item.connection is conn for item in ticket.connections):
            ticket.connections.append(ConnectionState(conn))
        return conn

    def close_connection(self, conn: RequestConnection) -> None:
        ticket = self._active_ticket()
        entry = next((item for item in ticket.connections if item.connection is conn), None)
        if entry is None:
            ticket.failures.append("unregistered_connection")
            self.track(conn)
            entry = ticket.connections[-1]
        if not entry.closed:
            try:
                conn.close()
            except BaseException:
                ticket.failures.append("connection_close_failed")
                raise
            entry.closed = True

    def finish(self) -> None:
        ticket = self.ticket
        if ticket is None:
            return
        if not isinstance(ticket, RequestTicket):
            raise RuntimeError("Invalid request lifecycle ticket")
        if ticket.finished:
            return
        ticket = self._active_ticket()
        try:
            for entry in ticket.connections:
                if not entry.closed:
                    try:
                        self.close_connection(entry.connection)
                    except BaseException:
                        self.app.logger.exception("HTTP request DB cleanup failed; lifecycle drain is unsafe")
        finally:
            self.gate.release(ticket)
