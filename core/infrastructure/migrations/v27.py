"""Install new trial and template-copy evidence without backfilling old facts."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_template_lineage_schema import install_template_lineage
from core.infrastructure.workbench_trial_schema import install_workbench_trial_schema


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_template_lineage(conn)
        install_workbench_trial_schema(conn)
    return MigrationOutcome.APPLIED
