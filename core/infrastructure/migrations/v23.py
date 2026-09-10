"""Add empty workflow metadata without treating legacy values as confirmations."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_process_schema import optimize_process_identity_triggers
from core.infrastructure.workbench_process_workflow_schema import install_process_workflow


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        optimize_process_identity_triggers(conn)
        install_process_workflow(conn)
    return MigrationOutcome.APPLIED
