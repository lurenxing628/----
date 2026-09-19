"""Prevent incidental database writes without replacing a caller's authorizer."""

from contextlib import contextmanager

from core.infrastructure.connection_guards import query_only
from core.infrastructure.transaction import TransactionManager


@contextmanager
def candidate_read_snapshot(conn):
    with query_only(conn):
        with TransactionManager(conn).transaction():
            yield
