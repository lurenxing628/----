"""Reuse verified evidence only inside one explicitly read-only SQLite snapshot."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from .connection_guards import query_only

T = TypeVar("T")
_Scope = Tuple[Any, Dict[Any, Any], int]
_CURRENT: ContextVar[Tuple[_Scope, ...]] = ContextVar("aps_read_evidence", default=())


def _scope_for(conn) -> Optional[_Scope]:
    return next((scope for scope in _CURRENT.get() if scope[0] is conn), None)


@contextmanager
def read_evidence_scope(conn):
    if not conn.in_transaction:
        raise RuntimeError("Evidence reuse requires an existing read transaction")
    if _scope_for(conn) is not None:
        yield
        return
    cache: Dict[Any, Any] = {}
    token = _CURRENT.set(_CURRENT.get() + ((conn, cache, conn.total_changes),))
    try:
        with query_only(conn):
            yield
    finally:
        _CURRENT.reset(token)
        cache.clear()


def verified_read(conn, key: Any, load: Callable[[], T]) -> T:
    current = _scope_for(conn)
    if current is None:
        return load()
    _, cache, changes = current
    if not conn.in_transaction or conn.total_changes != changes:
        raise RuntimeError("Evidence read snapshot changed")
    if key not in cache:
        cache[key] = load()
    return cache[key]
