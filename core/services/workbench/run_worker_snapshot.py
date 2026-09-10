"""Release the original SQLite read lock before long candidate computation."""

from contextlib import contextmanager

from core.infrastructure.database import get_connection


@contextmanager
def computation_database(source):
    if source.in_transaction:
        raise RuntimeError("Candidate database snapshot requires no active source transaction")
    snapshot = get_connection(":memory:")
    try:
        # SQLite Backup API supplies one consistent database, including permanent refs.
        source.backup(snapshot)
        yield snapshot
    finally:
        snapshot.close()
