"""Align indexes with retained readers; complete data contracts run at migration exit."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.single_pass_indexes_schema import ADDED, REMOVED
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        for name in REMOVED:
            conn.execute('DROP INDEX IF EXISTS "' + name + '"')
        for sql in ADDED.values():
            conn.execute(sql)
    return MigrationOutcome.APPLIED
