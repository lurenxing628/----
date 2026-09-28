"""Lunch, split night shifts, projections and native cache certificates agree."""

from datetime import date, datetime

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.calendar_periods import DEFAULT_WORK_PERIODS, decode_periods, normalize_periods
from core.models.workbench_resource_input import normalize_resource_input
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_windows import policy_projection
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.run.optimizer.graph.v2_capacity import _calendar_capacity_hours
from core.services.workbench.resource.calendar_files.files import WorkbenchCalendarFileService
from core.services.workbench.resource.calendars import WorkbenchCalendarService
from data.repositories.workbench_resource_state_repo import WorkbenchResourceStateRepository

DAY = "2026-10-05"
LUNCH = [{"start": "08:00", "end": "12:00", "day_offset": 0},
         {"start": "13:00", "end": "17:00", "day_offset": 0}]


def dt(clock, day=DAY):
    return datetime.fromisoformat(day + "T" + clock)


def test_default_factory_day_matches_confirmed_clock_times_and_preserves_explicit_rows(schema_conn):
    service = CalendarService(schema_conn)
    assert decode_periods(service.get(DAY).periods_json) == DEFAULT_WORK_PERIODS
    assert service.adjust_to_working_time(dt("08:00")) == dt("08:30")
    assert service.adjust_to_working_time(dt("11:50")) == dt("13:30")
    assert service.add_working_hours(dt("11:00"), 2) == dt("14:40")
    assert service.working_hours_between(dt("08:00"), dt("18:00")) == pytest.approx(22 / 3)
    service.upsert(DAY, shift_start="08:00", shift_end="16:00")
    assert service.working_hours_between(dt("08:00"), dt("18:00")) == 8
    assert service.add_working_hours(dt("11:00"), 2) == dt("13:00")


def test_lunch_is_neither_processing_nor_capacity_and_native_slot_stops_at_noon(schema_conn):
    service = CalendarService(schema_conn)
    service.upsert(DAY, periods=LUNCH, efficiency=.8)
    assert service.add_working_hours(dt("11:00"), 2) == dt("14:00")
    assert service.adjust_to_working_time(dt("12:15")) == dt("13:00")
    assert service.working_hours_between(dt("08:00"), dt("17:00")) == 8
    assert service.certified_slot_window(dt("11:00")) == (dt("08:00"), dt("12:00"))
    assert service.certified_slot_window(dt("12:30")) is None
    engine = SnapshotCalendarEngine({"global": [service.get(DAY).to_dict()], "personal": [], "profiles": [], "patterns": []})
    projected = policy_projection(engine, date.fromisoformat(DAY), date.fromisoformat(DAY), dt("00:00"), dt("23:59"))
    assert projected["available_hours"] == 8 and projected["effective_hours"] == 6.4
    assert len(projected["windows"]) == 2
    assert service.certified_multi_start_snapshot() is not None


def test_split_night_uses_explicit_next_day_without_filling_the_break(schema_conn):
    service = CalendarService(schema_conn)
    periods = [{"start": "22:00", "end": "01:00", "day_offset": 0},
               {"start": "02:00", "end": "06:00", "day_offset": 1}]
    service.upsert(DAY, periods=periods)
    start, end = dt("23:00"), dt("04:00", "2026-10-06")
    assert service.add_working_hours(start, 4) == end
    assert service.working_hours_between(start, end) == 4
    assert service.adjust_to_working_time(dt("01:30", "2026-10-06")) == dt("02:00", "2026-10-06")


def test_graph_capacity_uses_actual_night_pieces_and_today_priority_override(schema_conn):
    service = CalendarService(schema_conn)
    service.upsert(DAY, periods=[{"start": "22:00", "end": "01:00", "day_offset": 0},
                                {"start": "02:00", "end": "06:00", "day_offset": 1}], efficiency=.5)
    service.upsert("2026-10-06", shift_start="05:00", shift_end="05:30", allow_normal="no")
    result = _calendar_capacity_hours(service, dt("00:00", "2026-10-06"), dt("06:00", "2026-10-06"),
                                      priority="normal", operator_id=None)
    assert result == 2.25


@pytest.mark.parametrize("periods", ["08:00-12:00", [{"start": "bad", "end": "12:00"}],
    [{"start": "13:00", "end": "17:00"}, {"start": "08:00", "end": "12:00"}],
    [{"start": "08:00", "end": "12:00"}, {"start": "11:00", "end": "17:00"}],
    [{"start": "22:00", "end": "06:00", "day_offset": 1}],
    [{"start": "08:00", "end": "12:00"}, {"start": "13:00", "end": "17:00", "day_offset": 1}]])
def test_ambiguous_overlapping_or_overlong_periods_are_rejected(periods):
    with pytest.raises(ValidationError):
        normalize_periods(periods)


def test_calendar_noop_omission_and_roundtrip_keep_periods(schema_conn):
    CalendarService(schema_conn).upsert(DAY, periods=LUNCH)
    calendar = WorkbenchCalendarService(schema_conn)
    before = calendar.snapshot(DAY)
    after = calendar.proposed_row({"note": "保留午休"}, before)
    assert decode_periods(after["periods_json"]) == LUNCH and after["shift_hours"] == 8
    with pytest.raises(ValidationError, match="逐段"):
        calendar.proposed_row({"hours": 9}, before)
    files = WorkbenchCalendarFileService(schema_conn, "work_calendar")
    with TransactionManager(schema_conn).transaction():
        content = files.export("csv", start_date=DAY, end_date=DAY).content
    preview = files.preview_import(content, file_format="csv").as_dict()
    assert preview["summary"]["unchanged"] == 1, preview
    assert preview["rows"][0]["after"]["period_2_start"] == "13:00"


def test_operator_shift_periods_respect_global_capacity_and_personal_override(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O','测试')")
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES ('S','两段',?,1)", (DAY,))
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('O','S')")
    normalized = normalize_resource_input("shift_profile", "update", {"fields": {"pattern": [
        {"day_offset": 0, "is_rest": False, "periods": LUNCH}]}})
    WorkbenchResourceStateRepository(conn).set_pattern("S", normalized["fields"]["pattern"])
    conn.commit()
    service = CalendarService(conn)
    service.upsert(DAY, shift_hours=5)
    policy = service._engine._policy_for_date(DAY, "O")
    assert policy.work_windows() == ((dt("08:00"), dt("12:00")), (dt("13:00"), dt("14:00")))
    service.upsert_operator_calendar("O", DAY, periods=[{"start": "15:00", "end": "18:00"}])
    assert service.adjust_to_working_time(dt("08:00"), operator_id="O") == dt("15:00")
