"""Reuse verified evidence only inside one explicitly read-only SQLite snapshot."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from .connection_guards import data_version, query_only

T = TypeVar("T")
_CURRENT: ContextVar[Optional[Tuple[Any, Dict[Any, Any], int, int]]] = ContextVar("aps_read_evidence", default=None)


def _version(conn):
    version = data_version(conn)
    if version is None:
        raise RuntimeError("Evidence read snapshot metadata unavailable")
    return version


@contextmanager
def read_evidence_scope(conn):
    if not conn.in_transaction:
        raise RuntimeError("Evidence reuse requires an existing read transaction")
    cache: Dict[Any, Any] = {}
    token = _CURRENT.set((conn, cache, conn.total_changes, _version(conn)))
    try:
        with query_only(conn):
            yield
    finally:
        _CURRENT.reset(token)
        cache.clear()


def verified_read(conn, key: Any, load: Callable[[], T]) -> T:
    current = _CURRENT.get()
    if current is None or current[0] is not conn:
        return load()
    _, cache, changes, version = current
    if not conn.in_transaction or conn.total_changes != changes or _version(conn) != version:
        raise RuntimeError("Evidence read snapshot changed")
    if key not in cache:
        cache[key] = load()
    return cache[key]
