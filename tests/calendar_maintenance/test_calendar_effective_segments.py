"""跨午夜重叠班段只计算一次，当前班段优先。"""

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.services.scheduler.calendar import engine as engine_module
from core.services.scheduler.calendar.engine import CalendarEngine, DayPolicy
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.calendar.sgs_certificate import _NativePolicyReader


def dt(text):
    return datetime.fromisoformat('2026-10-' + text)


def engine(today_normal='yes', previous_normal='yes', *, start='05:00', end='13:00', efficiency=1):
    result = CalendarEngine(None)

    def resolve(day, _):
        night = day == '2026-10-05'
        return SimpleNamespace(date=day, day_type='workday', shift_hours=8, shift_start='22:00' if night else start,
                               shift_end='06:00' if night else end, efficiency=efficiency,
                               allow_normal=previous_normal if night else today_normal, allow_urgent='yes')
    result._resolve_calendar_row = resolve
    return result


@pytest.mark.parametrize('priority', ["normal"])
@pytest.mark.parametrize('efficiency', [1])
def test_overlap_is_counted_once_and_calendar_hours_are_not_efficiency_weighted(priority, efficiency):
    cal = engine(efficiency=efficiency)
    start = dt('06T04:00')
    assert cal.working_hours_between(start, dt('06T06:00'), priority) == 2
    for hours in (.25, 2, 9, 15):
        end = cal.add_working_hours(start, hours, priority)
        assert cal.working_hours_between(start, end, priority) == pytest.approx(hours)
        assert cal.working_hours_between(end, start, priority) == pytest.approx(-hours)


def test_current_window_priority_wins_and_tail_resumes_after_short_current_window():
    cal = engine(today_normal='no', start='05:00', end='05:30')
    assert cal.add_working_hours(dt('06T04:00'), 1.5, 'normal') == dt('06T06:00')
    assert cal.adjust_to_working_time(dt('06T05:00'), 'normal') == dt('06T05:30')
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'normal') == 1.5
    assert cal.working_hours_between(dt('06T04:00'), dt('06T06:00'), 'urgent') == 2


def test_people_share_public_dates_and_shift_facts_then_maintenance_reloads(schema_conn, monkeypatch):
    conn = schema_conn
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [("O1", "甲"), ("O2", "乙")])
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES ('S','班次','2026-10-12',1)")
    conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES ('S',0,0,'09:00','17:00')")
    conn.execute("INSERT INTO WorkbenchShiftDayPeriods(profile_id,day_offset,periods_json) VALUES ('S',0,?)",
                 ('[{"start":"09:00","end":"12:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',))
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES (?,'S')", [("O1",), ("O2",)])
    service = CalendarService(conn)
    service.upsert("2026-10-12", shift_hours=8)
    cal, counts = service._engine, {}
    parsed, decode = [], engine_module.decode_periods

    def parse(raw):
        parsed.append(raw)
        return decode(raw)

    monkeypatch.setattr(engine_module, "decode_periods", parse)
    for name, repo, method in (("public", cal.repo, "get"), ("personal", cal.operator_calendar_repo, "get"),
                              ("profile", cal.operator_shift_calendar.repo, "profile_for_operator"),
                              ("pattern", cal.operator_shift_calendar.repo, "pattern_day")):
        def count(*args, _name=name, _original=getattr(repo, method)):
            counts[_name] = counts.get(_name, 0) + 1
            return _original(*args)
        monkeypatch.setattr(repo, method, count)
    days = ("2026-10-12", "2026-10-13", "2026-10-14")
    for who in ("O1", "O2"):
        assert [cal._policy_for_date(day, who).shift_hours for day in days] == [7, 7, 7]
    assert counts == {"public": 3, "personal": 6, "profile": 2, "pattern": 1}
    assert parsed == ['[{"start":"09:00","end":"12:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]']
    defaults = cal.default_periods()
    assert cal.default_periods() is defaults
    assert service.certified_sgs_policy_snapshot("O1") is not None
    assert cal._sgs_policy_content_tokens

    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                 ('[{"start":"09:00","end":"15:00","day_offset":0}]',))
    conn.execute("UPDATE WorkbenchShiftProfiles SET anchor_date='2026-10-13' WHERE profile_id='S'")
    conn.execute("UPDATE WorkbenchShiftPatternDays SET shift_start='10:00',shift_end='16:00' WHERE profile_id='S'")
    conn.execute("UPDATE WorkbenchShiftDayPeriods SET periods_json=? WHERE profile_id='S'",
                 ('[{"start":"10:00","end":"12:00","day_offset":0},{"start":"13:00","end":"16:00","day_offset":0}]',))
    service.upsert("2026-10-12", shift_hours=4)
    assert not cal._sgs_policy_content_tokens and not cal._policy_operator_keys
    for who in ("O1", "O2"):
        policies = [cal._policy_for_date(day, who) for day in days]
        assert [policy.shift_hours for policy in policies] == [4, 5, 5]
        assert all(policy.shift_start.hour == 10 for policy in policies)
    assert counts == {"public": 6, "personal": 12, "profile": 4, "pattern": 2}
    assert len(parsed) == 2
    assert cal.default_periods() == [{"start": "09:00", "end": "15:00", "day_offset": 0}]
    assert cal.default_periods() is not defaults
    service.upsert_operator_calendar("O2", "2026-10-13", shift_start="11:00", shift_end="13:00")
    assert cal._policy_for_date("2026-10-13", "O2").shift_hours == 2


def test_policy_snapshot_uses_person_keys_keeps_explicit_order_and_detects_content_change(schema_conn):
    service = CalendarService(schema_conn)
    cal = service._engine
    for who in ("O1", "O2"):
        for day in ("2026-10-12", "2026-10-13", "2026-10-14"):
            cal._policy_for_date(day, who)

    class PersonReads(dict):
        def __init__(self, policies):
            super().__init__(policies)
            self.read_keys = []

        def items(self):
            raise AssertionError("person snapshot must consume its key group")

        def get(self, key):
            self.read_keys.append(key)
            return super().get(key)

    policies = PersonReads(cal._policy_cache)
    reader = _NativePolicyReader(policies, cal._sgs_policy_content_tokens, cal._policy_operator_keys)
    first = reader.snapshot("O1")
    assert policies.read_keys == [("O1", day) for day in ("2026-10-12", "2026-10-13", "2026-10-14")]
    keys = [("O1", "2026-10-14"), ("O2", "2026-10-12"), ("O1", "2026-10-12")]
    assert [key for key, _ in reader.snapshot("O1", keys)] == [keys[0], keys[2]]
    cal._policy_cache[("O1", "2026-10-12")].efficiency = 0.75
    assert reader.snapshot("O1") != first
    scalar_changed = reader.snapshot("O1")
    policy = cal._policy_cache[("O1", "2026-10-12")]
    policy._period_offsets = ((510, 700), (810, 1050))
    offsets_changed = reader.snapshot("O1")
    assert offsets_changed != scalar_changed
    policy._period_offsets = ((510, 710), (810, 1050))
    assert reader.snapshot("O1") != offsets_changed


def test_independent_day_policy_prepares_once_and_keeps_legacy_stop_and_night(monkeypatch):
    decoded, decode = [], engine_module.decode_periods

    def parse(raw):
        decoded.append(raw)
        return decode(raw)

    monkeypatch.setattr(engine_module, "decode_periods", parse)
    common = {"date_str": "2026-10-12", "day_type": "workday", "shift_hours": 4,
              "efficiency": 1, "allow_normal": "no", "allow_urgent": "yes"}
    legacy = DayPolicy(**common)
    assert legacy.work_windows() == ((datetime(2026, 10, 12, 8), datetime(2026, 10, 12, 12)),)
    stopped = DayPolicy(**common, periods_json="[]")
    assert stopped._period_offsets == () and stopped.work_windows() == ()
    raw = '[{"start":"22:00","end":"01:00","day_offset":0},{"start":"02:00","end":"06:00","day_offset":1}]'
    night = DayPolicy(**common, periods_json=raw)
    assert night._period_offsets == ((1320, 1500), (1560, 1800))
    for day in (12, 13, 14):
        policy = replace(night, date_str="2026-10-" + str(day))
        expected = ((datetime(2026, 10, day, 22), datetime(2026, 10, day + 1, 1)),
                    (datetime(2026, 10, day + 1, 2), datetime(2026, 10, day + 1, 3)))
        assert policy.work_windows() == expected and policy.work_windows() == expected
        assert not policy.is_priority_allowed("normal") and policy.is_priority_allowed("urgent")
    assert decoded == ["[]", raw]
