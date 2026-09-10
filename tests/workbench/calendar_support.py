"""Only fixture databases and an injected frozen factory-local clock; no app import."""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from time import perf_counter

import pytest

from core.services.scheduler.calendar_service import CalendarService
from core.services.workbench.calendars import WorkbenchCalendarService
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.identity_metadata_support import business_snapshot, table_rows

KEY = "calendar-command-00000001"
NIGHT = "2026-09-09"
WORK = {"type": "work", "hours": 8, "eff": 100, "allowNormal": "yes", "allowUrgent": "yes"}


class FrozenClock:
    def __init__(self):
        self.value = datetime(2024, 2, 29, 12, 34, 56)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture(name="calendar_env")
def calendar_database(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES ('CT', 'calendar fixture', 'internal')")
    conn.execute("INSERT INTO Operators (operator_id, name, remark) VALUES ('CO', 'fixture', 'retained')")
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id) VALUES ('CM', 'fixture', 'CT')")
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES ('CO', 'CM')")
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('CP', 'fixture')")
    conn.execute("INSERT INTO Materials (material_id, name, unit, stock_qty) VALUES ('CX', 'fixture', 'kg', 3.25)")
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity, due_date) VALUES ('CB', 'CP', 2, '2026-10-01')")
    conn.execute("INSERT INTO BatchMaterials (batch_id, material_id, required_qty) VALUES ('CB', 'CX', 7.5)")
    conn.commit()
    domain = CalendarService(conn)
    domain.upsert(NIGHT, shift_start="22:30", shift_end="06:30", efficiency=0.875,
                  allow_normal="no", allow_urgent="yes", remark="night retained")
    domain.upsert_operator_calendar("CO", NIGHT, shift_start="23:15", shift_end="07:45",
                                    efficiency=0.625, allow_urgent="no", remark="personal exception")
    clock = FrozenClock()
    return conn, WorkbenchCalendarService(conn, clock=clock), clock


def stored_state(conn):
    return (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"))


def seed_d06_resources(conn):
    """Install the owner's current resource schema only into the fixture connection."""
    from core.infrastructure.workbench_resource_schema import install_resources

    install_resources(conn)
    conn.execute("INSERT INTO WorkbenchMachineGroups (group_id, name) VALUES ('CG', 'fixture group')")
    conn.execute("INSERT INTO WorkbenchMachineGroupMembers (machine_id, group_id) VALUES ('CM', 'CG')")
    conn.execute("INSERT INTO WorkbenchShiftProfiles (profile_id, name, anchor_date, cycle_days) "
                 "VALUES ('CSP', 'fixture profile', '2026-09-01', 1)")
    conn.execute("INSERT INTO WorkbenchShiftPatternDays (profile_id, day_offset, is_rest, shift_start, shift_end) "
                 "VALUES ('CSP', 0, 0, '21:00', '05:00')")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles (operator_id, shift_profile_id, skills_declared) VALUES ('CO', 'CSP', 1)")
    conn.execute("INSERT INTO Suppliers (supplier_id, name, status) VALUES ('CS', 'fixture supplier', 'inactive')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes (supplier_id, op_type_id) VALUES ('CS', 'CT')")
    conn.execute("INSERT INTO WorkbenchSupplierProfiles (supplier_id, inactive_reason) VALUES ('CS', 'disabled')")
    conn.execute("INSERT INTO WorkbenchOpTypePolicies (op_type_id, default_merge_mode) VALUES ('CT', 'separate')")
    conn.commit()


def row_for(conn, day=NIGHT):
    row = conn.execute("SELECT * FROM WorkCalendar WHERE date = ?", (day,)).fetchone()
    return dict(row) if row else None


def run_day(env, action, payload, *, key=KEY, checked=None, guard=None, command=None):
    conn, adapter, _clock = env
    normalized = adapter.normalize(action, payload)
    if checked is None:
        checked = adapter.snapshot(normalized["date"])
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="calendar." + action, context_ref="calendar:" + normalized["date"],
        normalized_input=normalized, guard=guard or (lambda: checked),
        mutate=lambda current: adapter.apply(action, normalized, current),
    )


def range_input(**changes):
    return {"start_date": "2026-12-28", "end_date": "2027-01-03", "scope": "all",
            "operation": "upsert", "fields": WORK.copy(), **changes}


def run_confirm(env, preview, *, key=KEY, guard=None, command=None):
    conn, adapter, _clock = env
    payload = adapter.normalize("confirm", {"preview_ref": preview.preview_ref})
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="calendar.confirm", context_ref=preview.preview_ref,
        normalized_input=payload, guard=guard or (lambda: preview),
        mutate=lambda current: adapter.apply("confirm", payload, current),
    )


class MeasuredCalendarConnection(sqlite3.Connection):
    """Count connection SQL calls, including transaction/receipt calls, not trigger opcodes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sql_counts = Counter()

    def execute(self, sql, parameters=()):
        self.sql_counts[sql.lstrip().split(None, 1)[0].upper()] += 1
        return super().execute(sql, parameters)

    def commit(self):
        self.sql_counts["COMMIT"] += 1
        return super().commit()

    def rollback(self):
        self.sql_counts["ROLLBACK"] += 1
        return super().rollback()


@pytest.fixture(name="annual_env")
def annual_database(calendar_env, tmp_path):
    source, _, clock = calendar_env
    conn = sqlite3.connect(str(tmp_path / "annual-calendar.db"), factory=MeasuredCalendarConnection)
    try:
        source.backup(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        seed_d06_resources(conn)
        yield conn, WorkbenchCalendarService(conn, clock=clock), clock
    finally:
        conn.close()


def measure_calendar_call(conn, call):
    conn.sql_counts.clear()
    started = perf_counter()
    result = call()
    return result, {"seconds": round(perf_counter() - started, 6),
                    "sql_total": sum(conn.sql_counts.values()), "sql": dict(conn.sql_counts)}


def expected_range_dates(start, end, scope="all"):
    """Independent date oracle; never call the adapter's date-set implementation."""
    current, last = date.fromisoformat(start), date.fromisoformat(end)
    result = []
    while current <= last:
        if scope == "all" or (scope == "weekday" and current.weekday() < 5) or (scope == "weekend" and current.weekday() >= 5):
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def assert_complete_calendar_write(conn, preview, result):
    rows = conn.execute("SELECT * FROM WorkCalendar WHERE date >= ? AND date <= ? ORDER BY date",
                        (preview.request["start_date"], preview.request["end_date"])).fetchall()
    assert [row["date"] for row in rows] == preview.dates
    assert [dict(row) for row in rows] == [item["after"]["row"] for item in preview.days]
    assert [item["date"] for item in result["data"]["dates"]] == preview.dates
    assert all(item["result"] == "committed" for item in result["data"]["dates"])
    refs = conn.execute("SELECT entity_key, ref FROM WorkbenchEntityRefs WHERE kind = 'calendar' AND active = 1 "
                        "AND entity_key >= ? AND entity_key <= ? ORDER BY entity_key",
                        (preview.request["start_date"], preview.request["end_date"])).fetchall()
    assert [row["entity_key"] for row in refs] == preview.dates
    assert [row["ref"] for row in refs] == [item["calendar_ref"] for item in result["data"]["dates"]]


def assert_other_business_unchanged(conn, before):
    after = business_snapshot(conn)
    assert {key: value for key, value in after.items() if key != "WorkCalendar"} == {
        key: value for key, value in before.items() if key != "WorkCalendar"}
