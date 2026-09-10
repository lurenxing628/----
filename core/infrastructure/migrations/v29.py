"""Install quota-adoption evidence and dashboard source maps without changing facts."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install as install_calibration_adoption
from core.infrastructure.workbench_dashboard_schema import install_workbench_dashboard_schema


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        install_calibration_adoption(conn)
        install_workbench_dashboard_schema(conn)
    return MigrationOutcome.APPLIED
