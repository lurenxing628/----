"""Add explicit outsourcing facts and preserve plan references against replacement."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_outsourcing_schema import install_workbench_outsourcing_schema
from core.infrastructure.workbench_plan_identity_write_guard import install_plan_identity_write_guards


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_plan_identity_write_guards(conn)
        install_workbench_outsourcing_schema(conn)
    return MigrationOutcome.APPLIED
