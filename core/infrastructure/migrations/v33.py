"""Freeze current external contexts without modifying operations or saved plans."""

from core.infrastructure.batch_external_context_schema import install
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install(conn)
    return MigrationOutcome.APPLIED
