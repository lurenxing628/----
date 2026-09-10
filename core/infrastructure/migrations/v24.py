"""Install permanent plan/arrangement identities without rewriting source facts."""

from __future__ import annotations

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.infrastructure.workbench_process_schema import optimize_process_identity_triggers


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        optimize_process_identity_triggers(conn)
        install_plan_identity(conn)
    return MigrationOutcome.APPLIED
