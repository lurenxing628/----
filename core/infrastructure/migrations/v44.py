"""Index existing run-time expressions and operation foreign-key child columns."""

from core.infrastructure.efficiency_indexes_schema import ADDED
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        for sql in ADDED.values():
            conn.execute(sql)
    return MigrationOutcome.APPLIED
