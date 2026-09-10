"""Add generic external handling without rewriting outsourcing or dashboard facts."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_dashboard_external_schema import install


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install(conn)
    return MigrationOutcome.APPLIED
