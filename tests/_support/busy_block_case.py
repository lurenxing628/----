"""Real SQLite calendars and a one-switch, pre-skip estimator oracle."""

import sqlite3
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.algorithm_runtime import internal_slot
from core.services.scheduler.calendar_service import CalendarService

BASE = datetime(2026, 9, 8, 8)
SCHEMA = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")


def at(hours=0):
    return BASE + timedelta(hours=hours)


def spans(*pairs):
    return [(at(start), at(end)) for start, end in pairs]


def day_row(day=0, **overrides):
    row = dict(
        date=(BASE + timedelta(days=day)).date().isoformat(), day_type="workday",
        shift_start="08:00", shift_end="16:00", shift_hours=8.0,
        efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="busy-block-test",
    )
    row.update(overrides)
    return row


@contextmanager
def native_calendar(rows=(), operator_rows=(), calendar_type=CalendarService):
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('O1', 'Test operator')")
        days = {day_row(day)["date"]: day_row(day) for day in range(14)}
        days.update({row["date"]: row for row in rows})
        for row in days.values():
            conn.execute(
                "INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, "
                "efficiency, allow_normal, allow_urgent, remark) VALUES "
                "(:date, :day_type, :shift_start, :shift_end, :shift_hours, :efficiency, "
                ":allow_normal, :allow_urgent, :remark)", row,
            )
        for row in operator_rows:
            conn.execute(
                "INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_start, shift_end, "
                "shift_hours, efficiency, allow_normal, allow_urgent, remark) VALUES "
                "('O1', :date, :day_type, :shift_start, :shift_end, :shift_hours, :efficiency, "
                ":allow_normal, :allow_urgent, :remark)", row,
            )
        conn.commit()
        conn.execute("PRAGMA query_only = ON")
        before = conn.total_changes
        yield calendar_type(conn)
        assert conn.total_changes == before, "Scheduling wrote to the calendar fixture"
    finally:
        conn.close()


def slot_case(hours=0.25, *, machine=(), operator=(), downtime=(), priority="normal", **overrides):
    case = dict(
        op=SimpleNamespace(
            id=1, op_code="OP1", batch_id="B1", seq=1, source="internal",
            machine_id="M1", operator_id="O1", setup_hours=hours, unit_hours=0.0, op_type_name="TURN",
        ),
        batch=SimpleNamespace(
            batch_id="B1", quantity=1, priority=priority, due_date=None,
            ready_status="yes", ready_date=None, created_at=None,
        ),
        machine_id="M1", operator_id="O1", base_time=BASE, prev_end=BASE,
        machine_timeline=list(machine), operator_timeline=list(operator), machine_downtimes=list(downtime),
        end_dt_exclusive=None, abort_after=None, last_op_type_by_machine={"M1": "MILL"},
    )
    case.update(overrides)
    return case


def legacy_shift(calendar, *, shift_to, **unused):
    # Keep the production estimator, overlap lookup and native calendar unchanged.
    return shift_to


@contextmanager
def counted_attempts(legacy=False):
    with ExitStack() as stack:
        if legacy:
            stack.enter_context(patch.object(internal_slot, "advance_busy_block", side_effect=legacy_shift))
        attempts = stack.enter_context(patch.object(
            internal_slot, "_estimate_attempt", wraps=internal_slot._estimate_attempt,
        ))
        yield attempts


def run_estimate(calendar, case, *, legacy=False):
    before = deepcopy(case)
    try:
        with counted_attempts(legacy) as attempts:
            result = internal_slot.estimate_internal_slot(calendar=calendar, **case)
        return result, attempts.call_count
    finally:
        assert case == before, "Slot estimation changed its input"


def equivalent_slot(case, *, rows=(), operator_rows=(), calendar_type=CalendarService):
    outputs = []
    for legacy in (True, False):
        with native_calendar(rows, operator_rows, calendar_type) as calendar:
            outputs.append(run_estimate(calendar, case, legacy=legacy))
    (expected, old_count), (actual, new_count) = outputs
    assert actual == expected, (case, expected, actual)
    assert new_count <= old_count
    return actual, old_count, new_count
