"""Time-query repositories support plain connections without unrelated re-registration."""

import sqlite3

import pytest

from data.repositories.base_repo import BaseRepository
from data.repositories.calendar_facts_repo import CalendarFactsRepository
from data.repositories.machine_downtime_repo import MachineDowntimeRepository
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.schedule_repo import ScheduleRepository
from data.repositories.supplier_repo import SupplierRepository
from data.repositories.workbench_run_input_repo import WorkbenchRunInputRepository


@pytest.mark.parametrize("repository", [ScheduleRepository, SchedulePlanQueryRepository, WorkbenchRunInputRepository,
                                       CalendarFactsRepository, MachineDowntimeRepository])
def test_plain_connection_has_strict_time_parser(repository):
    conn = sqlite3.connect(":memory:")
    try:
        repository(conn)
        assert conn.execute("SELECT aps_parse_dt('2024-02-29 12:00'),aps_parse_dt('2024-02-30')").fetchone() == (
            "2024-02-29 12:00:00", None)
    finally:
        conn.close()


def test_unrelated_repository_can_be_created_while_time_query_is_running():
    conn = sqlite3.connect(":memory:")
    try:
        ScheduleRepository(conn)
        cursor = conn.execute("SELECT aps_parse_dt(day) FROM (SELECT '2024-02-29' AS day UNION ALL SELECT '2024-03-01')")
        # Replacing a function while SQLite is evaluating it raises OperationalError.
        BaseRepository(conn)
        SupplierRepository(conn)
        assert len(cursor.fetchall()) == 2
    finally:
        conn.close()
