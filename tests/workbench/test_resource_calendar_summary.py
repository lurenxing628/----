"""New fixture databases only: real global policy, local clock and no repair writes."""

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler.calendar_service import CalendarService
from core.services.workbench.resource_calendar_summary import resource_calendar_summary
from tests.workbench.resource_metrics_support import stored_state


def summary(conn, value=datetime(2026, 9, 9, 12, 0)):
    return resource_calendar_summary(conn, clock=lambda: value)


def test_unconfigured_days_are_actual_service_defaults_not_explicit_or_standard_hours(schema_conn):
    before = stored_state(schema_conn)
    value = summary(schema_conn)
    assert value["factory_today"] == "2026-09-09"
    assert (value["week_start"], value["week_end"]) == ("2026-09-07", "2026-09-13")
    assert value["standard_hours"]["status"] == "not_configured"
    assert value["standard_hours"]["value"] is None
    assert value["holiday_default_efficiency"]["status"] == "not_configured"
    service = CalendarService(schema_conn)
    for day in value["days"]:
        policy = service.policy_for_datetime(datetime.fromisoformat(day["date"] + "T12:00:00"))
        assert not day["explicit"] and day["source"] == "service_default"
        assert day["effective"]["hours"] == policy.shift_hours
        assert day["effective"]["efficiency"] == policy.efficiency
    assert value["stats"]["work_days"] == 5 and value["stats"]["rest_days"] == 2
    assert value["stats"]["configured_days"] == 0 and value["stats"]["default_days"] == 7
    assert stored_state(schema_conn) == before


@pytest.mark.parametrize("now,start,end", [
    (datetime(2026, 12, 31, 23, 59, 59), "2026-12-28", "2027-01-03"),
    (datetime(2027, 1, 3, 23, 59, 59), "2026-12-28", "2027-01-03"),
    (datetime(2027, 1, 4), "2027-01-04", "2027-01-10"),
    (datetime(2024, 2, 29), "2024-02-26", "2024-03-03"),
])
def test_real_week_boundaries_leap_year_and_cross_year(schema_conn, now, start, end):
    value = summary(schema_conn, now)
    assert (value["week_start"], value["week_end"]) == (start, end)
    assert [day["date"] for day in value["days"]] == [
        (datetime.fromisoformat(start) + timedelta(days=index)).date().isoformat() for index in range(7)]
    assert [day["date"] for day in value["days"] if day["is_today"]] == [now.date().isoformat()]


def test_default_clock_reads_factory_local_day_each_request(schema_conn, monkeypatch):
    import importlib

    module = importlib.import_module("core.services.workbench.resource_calendar_summary")
    now = [datetime(2026, 9, 13, 23, 59, 59)]
    monkeypatch.setattr(module, "factory_now", lambda: now[0])
    assert module.resource_calendar_summary(schema_conn)["week_start"] == "2026-09-07"
    now[0] += timedelta(seconds=1)
    assert module.resource_calendar_summary(schema_conn)["week_start"] == "2026-09-14"
    now[0] = datetime.now()
    assert module.resource_calendar_summary(schema_conn)["factory_today"] == datetime.now().date().isoformat()
    with pytest.raises(ValueError, match="工厂本地"):
        summary(schema_conn, datetime(2026, 9, 9, tzinfo=timezone.utc))


def test_night_shift_efficiency_permissions_and_explicit_zero_have_distinct_meaning(schema_conn):
    service = CalendarService(schema_conn)
    service.upsert("2026-09-09", day_type="holiday", shift_start="22:30", shift_end="06:30", efficiency=.875,
                   allow_normal="no", allow_urgent="yes")
    service.upsert("2026-09-10", shift_start="00:00", shift_hours=0, efficiency=1, allow_normal="yes", allow_urgent="yes")
    service.upsert("2026-09-11", shift_hours=9, efficiency=.5, allow_normal="no", allow_urgent="no")
    service.upsert("2026-09-12", shift_start="06:00", shift_end="06:00", efficiency=.5, allow_normal="yes", allow_urgent="no")
    before = stored_state(schema_conn)
    value = summary(schema_conn)
    night, zero, disabled, saturday = [day["effective"] for day in value["days"][2:6]]
    assert night["hours"] == 8 and night["effective_hours"] == 7
    assert night["normal_effective_hours"] == 0 and night["urgent_effective_hours"] == 7
    assert night["crosses_midnight"] and night["window_end"] == "2026-09-10T06:30:00"
    assert service.policy_for_datetime(datetime(2026, 9, 10, 1)).date_str == "2026-09-09"
    assert zero["window_start"] == "2026-09-10T00:00:00" and zero["rest_reason"] == "zero_hours"
    assert disabled["hours"] == 9 and disabled["effective_hours"] == 0 and disabled["rest_reason"] == "priorities_disabled"
    assert saturday["hours"] == 24 and saturday["effective_hours"] == 12 and saturday["is_working"]
    assert value["stats"]["configured_days"] == 4
    assert value["stats"]["work_days"] == 4 and value["stats"]["rest_days"] == 3
    assert stored_state(schema_conn) == before


@pytest.mark.parametrize("field,bad", [("efficiency", "broken"), ("efficiency", 0), ("shift_hours", -1),
                                        ("shift_start", "25:90"), ("shift_end", "garbage"),
                                        ("allow_normal", "perhaps"), ("day_type", "unknown")])
def test_bad_day_does_not_invalidate_other_dates_or_turn_partial_week_into_totals(schema_conn, field, bad):
    schema_conn.execute("INSERT INTO WorkCalendar(date) VALUES ('2026-09-09')")
    schema_conn.execute("UPDATE WorkCalendar SET " + field + "=? WHERE date='2026-09-09'", (bad,))
    schema_conn.commit()
    before = stored_state(schema_conn)
    value = summary(schema_conn)
    assert value["status"] == "partial"
    assert value["days"][2]["status"] == "unavailable" and value["days"][2]["effective"] is None
    assert value["days"][2]["issues"][0]["code"] == "calendar_day_unavailable"
    assert all(day["status"] == "known" for index, day in enumerate(value["days"]) if index != 2)
    assert value["stats"]["unavailable_days"] == 1 and value["stats"]["known_days"] == 6
    assert value["stats"]["effective_hours"] is None and value["stats"]["rest_days"] is None
    assert stored_state(schema_conn) == before


def test_damaged_previous_sunday_does_not_poison_monday_date_key(schema_conn):
    schema_conn.execute("INSERT INTO WorkCalendar(date,efficiency) VALUES ('2026-09-06','bad')")
    schema_conn.commit()
    assert summary(schema_conn)["status"] == "known"


def test_empty_stored_fields_expose_real_service_defaults_without_repairs(schema_conn):
    schema_conn.execute("INSERT INTO WorkCalendar(date,shift_hours,efficiency,allow_normal) VALUES ('2026-09-09',NULL,NULL,NULL)")
    schema_conn.commit()
    before = stored_state(schema_conn)
    day = summary(schema_conn)["days"][2]
    assert day["explicit"] and day["source"] == "explicit" and day["status"] == "known"
    assert day["effective"]["hours"] == CalendarService(schema_conn).get("2026-09-09").shift_hours
    assert "shift_hours" in day["issues"][0]["fields"]
    assert stored_state(schema_conn) == before


@pytest.mark.parametrize("raw,status,value", [("0.625", "known", .625), ("0", "unavailable", None),
                                               ("bad", "unavailable", None), ("", "unavailable", None),
                                               ("inf", "unavailable", None)])
def test_global_config_is_strict_read_only_and_not_applied_retroactively(schema_conn, raw, status, value):
    schema_conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES ('holiday_default_efficiency',?)", (raw,))
    schema_conn.commit()
    before = stored_state(schema_conn)
    result = summary(schema_conn)
    assert result["holiday_default_efficiency"]["status"] == status
    assert result["holiday_default_efficiency"]["value"] == value
    assert result["days"][2]["effective"]["efficiency"] == 1
    assert result["status"] == "known"
    assert stored_state(schema_conn) == before


def test_calendar_personal_rules_are_excluded_and_changes_refresh_without_process_cache(schema_conn):
    service = CalendarService(schema_conn)
    schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O','test')")
    schema_conn.commit()
    service.upsert_operator_calendar("O", "2026-09-09", shift_hours=0)
    first = summary(schema_conn)
    service.upsert("2026-09-09", shift_hours=6.5, efficiency=.8)
    changed = summary(schema_conn)
    assert first["days"][2]["effective"]["hours"] == 8
    assert changed["days"][2]["effective"]["effective_hours"] == pytest.approx(5.2)
    service.delete("2026-09-09")
    assert summary(schema_conn)["days"][2] == first["days"][2]


def test_database_errors_are_not_reported_as_unconfigured_calendar(schema_conn):
    schema_conn.execute("DROP TABLE WorkCalendar")
    with pytest.raises(AppError):
        summary(schema_conn)


def test_actual_connection_date_converter_keeps_explicit_row_presence(schema_conn, tmp_path):
    from core.infrastructure.database import get_connection

    path = tmp_path / "calendar-summary.sqlite"
    with sqlite3.connect(str(path)) as target:
        schema_conn.backup(target)
    conn = get_connection(str(path))
    try:
        CalendarService(conn).upsert("2026-09-09", shift_start="22:30", shift_end="06:30", efficiency=.875)
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
        before = stored_state(conn)
        value = summary(conn)
        assert value["stats"]["configured_days"] == 1
        assert value["days"][2]["explicit"] is True and value["days"][2]["source"] == "explicit"
        assert value["days"][2]["effective"]["window_end"] == "2026-09-10T06:30:00"
        assert stored_state(conn) == before
    finally:
        conn.close()


def test_overflowing_week_sum_is_unknown_without_discarding_good_daily_facts(schema_conn):
    schema_conn.executemany("INSERT INTO WorkCalendar(date,efficiency) VALUES (?,?)", [
        ("2026-09-0" + str(day), 1e307) for day in (7, 8, 9)])
    schema_conn.commit()
    value = summary(schema_conn)
    assert value["status"] == "partial" and value["stats"]["effective_hours"] is None
    assert value["stats"]["issues"][0]["code"] == "calendar_week_total_unavailable"
    assert value["stats"]["known_days"] == 7 and value["stats"]["work_days"] == 5
    assert value["days"][0]["effective"]["effective_hours"] == 8e307
