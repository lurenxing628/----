"""跨午夜重叠班段只计算一次，当前班段优先。"""

from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.infrastructure.database import get_connection
from core.models.calendar_periods import decode_periods
from core.services.scheduler.calendar import engine as engine_module
from core.services.scheduler.calendar.day_policy import DayPolicy
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.period_offsets import period_offsets
from core.services.scheduler.calendar.service import CalendarService
from core.services.workbench.facts.production_capture import ProductionFactsCapture


def dt(text):
    return datetime.fromisoformat('2026-10-' + text)


def engine(today_normal='yes', previous_normal='yes', *, start='05:00', end='13:00', efficiency=1):
    result = CalendarEngine(None)

    def resolve(date_str, op_id=None):
        night = date_str == '2026-10-05'
        s = '22:00' if night else start
        e = '06:00' if night else end
        return SimpleNamespace(date=date_str, day_type='workday', efficiency=efficiency,
                               allow_normal=previous_normal if night else today_normal, allow_urgent='yes',
                               periods_json=f'[{{"start":"{s}","end":"{e}","day_offset":0}}]')
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
    conn.execute(
        "INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,periods_json) "
        "VALUES ('S',0,0,?)",
        ('[{"start":"09:00","end":"12:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',),
    )
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES (?,'S')", [("O1",), ("O2",)])
    service = CalendarService(conn)
    service._admin.repo.upsert_many([
        service._admin._build_work_calendar(
            date_value="2026-10-12",
            periods=[{"start": "08:00", "end": "16:00", "day_offset": 0}],
            context=service.normalization_context(),
        )
    ])
    conn.commit()
    service._engine.clear_policy_cache()
    cal, counts = service._engine, {}
    built, build = [], service._engine._policy_from_calendar

    def build_policy(row):
        built.append((row.date, type(row)))
        return build(row)

    monkeypatch.setattr(cal, "_policy_from_calendar", build_policy)
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
        assert [cal._policy_for_date(day, who).hours for day in days] == [7, 7, 7]
    assert len(built) == 3
    assert counts == {"public": 3, "personal": 6, "profile": 2, "pattern": 1}
    assert parsed == [
        '[{"start":"08:00","end":"16:00","day_offset":0}]',
        '[{"start":"09:00","end":"12:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',
    ]
    defaults = cal.default_periods()
    assert cal.default_periods() is defaults
    assert cal._public_policy_cache[days[0]].hours == 8

    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                 ('[{"start":"09:00","end":"15:00","day_offset":0}]',))
    conn.execute("UPDATE WorkbenchShiftProfiles SET anchor_date='2026-10-13' WHERE profile_id='S'")
    conn.execute(
        "UPDATE WorkbenchShiftPatternDays SET periods_json=? WHERE profile_id='S'",
        ('[{"start":"10:00","end":"12:00","day_offset":0},{"start":"13:00","end":"16:00","day_offset":0}]',),
    )
    service._admin.repo.upsert_many([
        service._admin._build_work_calendar(
            date_value="2026-10-12",
            periods=[{"start": "08:00", "end": "12:00", "day_offset": 0}],
            context=service.normalization_context(),
        )
    ])
    conn.commit()
    service._engine.clear_policy_cache()
    assert not cal._policy_operator_keys
    for who in ("O1", "O2"):
        policies = [cal._policy_for_date(day, who) for day in days]
        assert [policy.hours for policy in policies] == [4, 5, 5]
        assert all(policy.work_window()[0].hour == 10 for policy in policies)
    assert len(built) == 6
    assert counts == {"public": 6, "personal": 12, "profile": 4, "pattern": 2}
    assert len(parsed) == 4
    assert cal.default_periods() == [{"start": "09:00", "end": "15:00", "day_offset": 0}]
    assert cal.default_periods() is not defaults
    service._admin.operator_calendar_repo.upsert_many(
        [service._admin._build_operator_calendar(
            operator_id="O2",
            date_value="2026-10-13",
            periods=[{"start": "11:00", "end": "13:00", "day_offset": 0}],
            context=service.normalization_context(),
        )]
    )
    conn.commit()
    service._engine.clear_policy_cache()
    assert cal._policy_for_date("2026-10-13", "O2").hours == 2
    assert len(built) == 7


def test_independent_day_policy_keeps_legacy_stop_and_night():
    common = {"date_str": "2026-10-12", "day_type": "workday", "hours": 4,
              "efficiency": 1, "allow_normal": "no", "allow_urgent": "yes"}
    stopped = DayPolicy(**common, periods_json="[]", _period_offsets=period_offsets([]))
    assert stopped._period_offsets == () and stopped.work_windows() == ()
    raw = '[{"start":"22:00","end":"01:00","day_offset":0},{"start":"02:00","end":"06:00","day_offset":1}]'
    night = DayPolicy(**common, periods_json=raw, _period_offsets=period_offsets(decode_periods(raw)))
    assert night._period_offsets == ((1320, 1500), (1560, 1800))
    for day in (12, 13, 14):
        policy = replace(night, date_str="2026-10-" + str(day))
        expected = ((datetime(2026, 10, day, 22), datetime(2026, 10, day + 1, 1)),
                    (datetime(2026, 10, day + 1, 2), datetime(2026, 10, day + 1, 3)))
        assert policy.work_windows() == expected and policy.work_windows() == expected
        assert not policy.is_priority_allowed("normal") and policy.is_priority_allowed("urgent")


def test_captured_rows_keep_live_null_override_cycle_defaults_and_source_errors(db_path, request):
    conn = get_connection(db_path)
    request.addfinalizer(conn.close)
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [("O1", "甲"), ("O2", "乙"), ("O3", "丙")])
    conn.execute(
        "INSERT INTO WorkCalendar(date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
        "VALUES ('2026-10-12','workday',1,'yes','yes','[{\"start\":\"08:00\",\"end\":\"16:00\",\"day_offset\":0}]')"
    )
    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                 ('[{"start":"09:00","end":"12:00","day_offset":0},{"start":"13:00","end":"18:00","day_offset":0}]',))
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES ('S','班次','2026-10-12',12)")
    conn.executemany(
        "INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,periods_json) "
        "VALUES ('S',?,?,?)",
        [(day, int(day == 11), "[]" if day == 11 else '[{"start":"22:00","end":"06:00","day_offset":0}]') for day in range(12)],
    )
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES (?,'S')", [("O1",), ("O2",)])
    conn.execute(
        "INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
        "VALUES ('O2','2026-10-13','workday',0.75,'yes','yes','[{\"start\":\"11:00\",\"end\":\"13:00\",\"day_offset\":0}]')"
    )
    conn.commit()

    def calendars():
        return CalendarService(conn), CalendarService(conn, capture=ProductionFactsCapture(conn))

    live, captured = calendars()
    for who in (None, "O1", "O2", "O3"):
        for day in ("2026-10-12", "2026-10-13", "2026-10-14", "2026-10-23"):
            assert captured._engine._policy_for_date(day, who) == live._engine._policy_for_date(day, who)
    assert captured._engine._policy_for_date("2026-10-12", "O3").work_window()[0].hour == 8
    assert captured._engine._policy_for_date("2026-10-13", "O2").hours == 2
    assert captured._engine._policy_for_date("2026-10-23", "O1").hours == 0
    assert captured.certified_decode_checkpoint_snapshot() == live.certified_decode_checkpoint_snapshot()


def test_add_hours_preserves_microsecond_remainders_exact_shift_fit_and_min_positive_step():
    # 1. 微秒级余量不被 1e-9 小时（3.6 µs）容差吞没，低效率班段同样精确跨午休
    cal = CalendarEngine(None)
    cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=1.0,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:00","end":"12:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',
    )
    morning_start = datetime(2026, 10, 12, 8, 0)
    for extra_us in (1, 2, 3):
        hours = (4 * 3_600_000_000 + extra_us) / 3_600_000_000.0
        end = cal.add_working_hours(morning_start, hours)
        assert end == datetime(2026, 10, 12, 13, 0, 0, extra_us)
        assert cal.working_hours_between(morning_start, end) == hours

    low_eff_cal = CalendarEngine(None)
    low_eff_cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=0.3,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:00","end":"09:00","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',
    )
    eff_hours = ((1 * 3_600_000_000 + 10) * 0.3) / 3_600_000_000.0
    assert low_eff_cal.add_effective_hours(morning_start, eff_hours) == datetime(2026, 10, 12, 13, 0, 0, 10)

    # 2. 200 / 60.0 与 0.1 + 0.2 等二进制尾数微超整分钟的工时刚好装入早班，不误跨午休
    split_cal = CalendarEngine(None)
    split_cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=1.0,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:30","end":"11:50","day_offset":0},{"start":"13:00","end":"17:20","day_offset":0}]',
    )
    assert split_cal.add_working_hours(datetime(2026, 10, 12, 8, 30), 200 / 60.0) == datetime(2026, 10, 12, 11, 50)

    short_cal = CalendarEngine(None)
    short_cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=1.0,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:00","end":"08:18","day_offset":0},{"start":"13:00","end":"17:00","day_offset":0}]',
    )
    assert short_cal.add_working_hours(morning_start, 0.1 + 0.2) == datetime(2026, 10, 12, 8, 18)

    # 3. 正剩余跨入高效率班次至少占 1 µs，不退化为零长点事件
    jump_cal = CalendarEngine(None)
    jump_cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=0.5 if date_str == "2026-10-12" else 1.0,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:00","end":"09:00","day_offset":0}]',
    )
    near_end = datetime(2026, 10, 12, 8, 59, 59, 999900)  # 早班剩 100 µs 墙钟 = 50 µs 有效工时
    jumped_end = jump_cal.add_effective_hours(near_end, 50.3 / 3_600_000_000.0)
    assert jumped_end == datetime(2026, 10, 13, 8, 0, 0, 1)


def test_capacity_hours_between_accumulates_microseconds_without_piecewise_drift():
    cal = CalendarEngine(None)
    cal._resolve_calendar_row = lambda date_str, op_id=None: SimpleNamespace(
        date=date_str,
        day_type="workday",
        efficiency=0.85 if date_str < "2026-11-01" else 0.75,
        allow_normal="yes",
        allow_urgent="yes",
        periods_json='[{"start":"08:30","end":"11:50","day_offset":0},{"start":"13:00","end":"17:20","day_offset":0}]',
    )
    # 30 天 × 460 分钟/天 × 0.85 = 195.5 小时整，消除逐段 / 3600 累加产生的 1e-13 漂移
    oct_start = datetime(2026, 10, 1, 0, 0)
    oct_end = datetime(2026, 10, 31, 0, 0)
    assert cal.capacity_hours_between(oct_start, oct_end) == 195.5

    # 30 天 × 460 分钟/天 × 0.75 = 172.5 小时整，整段与逐日求和 0 误差
    nov_start = datetime(2026, 11, 1, 0, 0)
    nov_end = datetime(2026, 12, 1, 0, 0)
    daily_sum = sum(
        cal.capacity_hours_between(nov_start + timedelta(days=i), nov_start + timedelta(days=i + 1))
        for i in range(30)
    )
    assert cal.capacity_hours_between(nov_start, nov_end) == 172.5
    assert daily_sum == 172.5
