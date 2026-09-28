"""Support additional machine work types without changing any legacy assignment."""

from core.infrastructure.machine_capabilities_schema import install
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install(conn)
    return MigrationOutcome.APPLIED
