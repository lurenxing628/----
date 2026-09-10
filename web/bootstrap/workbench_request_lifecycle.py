"""Host hooks for local HTTP/SQLite shutdown, not business readiness policy.

Factory integration (register before ANY DB-opening before_request hook):
    install_workbench_request_lifecycle(app)
    track_workbench_request_connection(conn)  # immediately after get_connection
    close_workbench_request_connection(conn)  # mount failure AND _close_db
    make_server(..., request_handler=WorkbenchRequestHandler)  # disconnect cleanup

Shutdown order in entrypoint finally AND atexit backup/lock-release guards:
    require stop_workbench_requests_for_database(db_path, wait=True) is True
    require existing run runtime.shutdown(wait=True) is True
    only then backup or release the original launcher locks

All HTTP paths participate, including old report/import/scheduler writes and
GETs that run automatic maintenance. Normal admission does not consult runtime
readiness or SystemMaintenanceJournal, so existing errors/receipts remain in
their business audit path. No endpoint is privileged during maintenance.
Installation/lookup never opens a DB or acquires/replaces a launcher lock.
"""

import os
import threading

from .launcher_paths import _normalize_db_path_for_runtime
from .workbench_request_lifecycle_server import WorkbenchRequestHandler
from .workbench_request_lifecycle_state import WorkbenchRequestLifecycle
from .workbench_request_lifecycle_wsgi import (
    close_workbench_request_connection,
    install_admission_hook,
    track_workbench_request_connection,
    wrap_wsgi,
)

__all__ = ["install_workbench_request_lifecycle", "lookup_workbench_request_lifecycle",
           "stop_workbench_requests_for_database", "track_workbench_request_connection",
           "close_workbench_request_connection", "WorkbenchRequestLifecycle", "WorkbenchRequestHandler"]

_INSTALL_LOCK = threading.RLock()
_GATES = {}
_EXTENSION = "workbench_request_lifecycle"


def _database_key(path):
    if not isinstance(path, (str, os.PathLike)):
        raise ValueError("Request lifecycle requires an explicit file database path")
    raw = os.fspath(path).strip()
    if not raw or raw == ":memory:" or raw.startswith("file:") or "\x00" in raw:
        raise ValueError("Request lifecycle requires an explicit file database path")
    return _normalize_db_path_for_runtime(raw)


def lookup_workbench_request_lifecycle(db_path):
    """Exact normalized lookup; valid unregistered DB returns None, never a guess."""
    key = _database_key(db_path)
    with _INSTALL_LOCK:
        return _GATES.get(key)


def stop_workbench_requests_for_database(db_path, wait=True, timeout=None):
    """Fail closed when a backup/lock cannot be associated with a registered DB."""
    gate = lookup_workbench_request_lifecycle(db_path)
    if gate is None:
        raise RuntimeError("No request lifecycle registered for the specified database")
    return gate.shutdown(wait=wait, timeout=timeout)


def install_workbench_request_lifecycle(app):
    """Install before DB-opening hooks; same live app is idempotent.

    Concurrent apps for the SAME DB share the barrier, not request identities.
    Closed apps/DBs cannot reopen in this process, including fresh app objects:
    allowing replacement could admit writes between drain and backup/lock release.
    """
    key = _database_key(app.config.get("DATABASE_PATH"))
    with _INSTALL_LOCK:
        existing = app.extensions.get(_EXTENSION)
        if existing is not None:
            if not isinstance(existing, WorkbenchRequestLifecycle) or existing.db_path != key:
                raise RuntimeError("Request lifecycle already foreign or database changed")
            if existing.status["state"] != "accepting":
                raise RuntimeError("Request lifecycle already closed or under maintenance")
            return existing
        if app.before_request_funcs.get(None) or app._got_first_request:
            raise RuntimeError("Install request lifecycle before DB-opening before_request hooks")
        gate = _GATES.get(key)
        if gate is not None and gate.status["state"] != "accepting":
            raise RuntimeError("Database request lifecycle is stopping, closed or cleanup failed")
        if gate is None:
            gate = WorkbenchRequestLifecycle(key)
        install_admission_hook(app, gate, _database_key)
        wrap_wsgi(app, gate)
        app.extensions[_EXTENSION] = gate
        _GATES[key] = gate
        return gate
