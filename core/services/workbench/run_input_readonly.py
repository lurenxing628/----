"""Prevent incidental database writes without replacing a caller's authorizer."""

from contextlib import contextmanager

from core.infrastructure.transaction import TransactionManager


@contextmanager
def candidate_read_snapshot(conn):
    query_only = conn.execute("PRAGMA query_only").fetchone()[0]
    try:
        conn.execute("PRAGMA query_only=ON")
        with TransactionManager(conn).transaction():
            yield
    finally:
        conn.execute("PRAGMA query_only=" + ("ON" if query_only else "OFF"))
