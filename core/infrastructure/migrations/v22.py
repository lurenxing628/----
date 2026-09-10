"""Add persistent template identities without inferring workflow confirmations."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_process_schema import install_process


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_process(conn)
    return MigrationOutcome.APPLIED
