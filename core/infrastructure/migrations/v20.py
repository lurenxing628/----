"""Add stable workbench object identities and atomic command receipts."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import install_metadata


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_metadata(conn)
    return MigrationOutcome.APPLIED
