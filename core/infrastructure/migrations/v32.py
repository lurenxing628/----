"""Add explicit outsourcing source confirmations and report-void facts atomically."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_void_schema import install_execution_voids
from core.infrastructure.workbench_outsourcing_source_schema import install as install_sources


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_sources(conn)
        install_execution_voids(conn)
    return MigrationOutcome.APPLIED
