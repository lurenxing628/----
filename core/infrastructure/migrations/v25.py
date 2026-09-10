"""Archive legacy execution facts and install the append-only reporting ledger."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_execution_ledger(conn)
    return MigrationOutcome.APPLIED
