"""Add durable candidate runs without executing or adopting any schedule."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_run_schema import install_workbench_run_schema


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_workbench_run_schema(conn)
    return MigrationOutcome.APPLIED
