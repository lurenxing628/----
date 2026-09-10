"""DT-only temporary integration support; fixed DI/DO/v29 fixtures stay intact."""

import pytest

from core.infrastructure.workbench_dashboard_external_schema import install
from tests.workbench.dashboard_external_support import storage


@pytest.fixture(name="external_handling_case")
def external_handling_case(external_case):
    external_case.conn.execute("BEGIN")
    install(external_case.conn)
    external_case.conn.commit()
    with external_case.app.app_context():
        yield external_case


def production_storage(conn):
    return {name: value for name, value in storage(conn).items()
            if not name.startswith("WorkbenchDashboardExternal") and name != "WorkbenchCommandReceipts"}


def ledger_counts(conn):
    return tuple(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in (
        "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory", "WorkbenchCommandReceipts"))


def external_items(case):
    return [row for row in case.read()[0]["items"] if row["category"] == "external"]
