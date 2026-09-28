"""Add optional multiple work periods; preserve all legacy calendar meanings."""

from core.infrastructure.calendar_periods_schema import install
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install(conn)
    return MigrationOutcome.APPLIED
