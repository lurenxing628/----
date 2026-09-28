"""Preserve existing requirements as batch-start, undated available material."""

from core.infrastructure.material_stages_schema import install
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install(conn)
    return MigrationOutcome.APPLIED
