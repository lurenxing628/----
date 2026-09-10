"""Store explicit resource semantics without inferring legacy skill/group/shift facts."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_resource_schema import install_resources


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_resources(conn)
    return MigrationOutcome.APPLIED
