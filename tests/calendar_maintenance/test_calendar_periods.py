"""生产日历保留午休与跨午夜分段。"""

from datetime import date, datetime

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_windows import policy_projection
from core.services.scheduler.calendar.service import CalendarService

DAY = "2026-10-05"
LUNCH = [{"start": "08:00", "end": "12:00", "day_offset": 0},
         {"start": "13:00", "end": "17:00", "day_offset": 0}]


def dt(clock, day=DAY):
    return datetime.fromisoformat(day + "T" + clock)


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
