"""Default-calendar rules stay read-only before confirmation and persist across services."""

import pytest

from core.models.calendar_periods import DEFAULT_WORK_PERIODS
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_capture
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from tests.workbench.calendar_api_support import (
    BASE,
    WORK,
    assert_error,
    assert_read_failure,
    calendar_api_fixture,  # noqa: F401
    deny_table_reads,
)

PERIODS = [{"start": "09:00", "end": "12:00", "day_offset": 0},
           {"start": "14:00", "end": "18:00", "day_offset": 0}]


def read(api):
    response = api.client.get(BASE + "/defaults")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def write(api, state, periods=PERIODS, key="calendar-defaults-test-00001"):
    return api.client.post(BASE + "/defaults", json={"request_key": key,
        "write_token": state["write_context"]["write_token"], "input": {"periods": periods}})


def test_default_periods_are_readonly_until_confirmed_and_persist_across_services(calendar_api):
    before = calendar_api.state()
    initial = read(calendar_api)
    assert initial["periods"] == DEFAULT_WORK_PERIODS and initial["hours"] == pytest.approx(22 / 3)
    assert calendar_api.state() == before
    explicit = calendar_api.row()
    saved = write(calendar_api, initial)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    assert saved.get_json()["result"] == "committed"
    assert calendar_api.row() == explicit
    assert read(calendar_api)["periods"] == PERIODS
    day = calendar_api.day("2026-09-10")
    assert day["effective"]["window_start"] == "2026-09-10T09:00:00"
    assert day["fields"]["hours"] == 7 and day["fields"]["periods"] == PERIODS
    with calendar_api.db() as conn:
        engine = CalendarEngine(calendar_inputs_from_capture(ProductionFactsCapture(conn)))
        assert engine._policy_for_date("2026-09-10").hours == 7
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCalendarDefaults").fetchone()[0] == 1
    sep = calendar_api.month(2026, 9)
    assert calendar_api.month(2026, 9, snapshot_ref=sep["meta"]["snapshot_ref"])["data"] == sep["data"]
    assert calendar_api.save(WORK, day="2026-10-01").status_code == 200
    stale = calendar_api.client.get(BASE + "/month", query_string={
        "year": 2026, "month": 9, "snapshot_ref": sep["meta"]["snapshot_ref"]})
    assert_error(stale, "snapshot_stale")


def test_unconfigured_weekend_saves_note_only_as_holiday(calendar_api):
    saturday = "2026-09-12"
    assert calendar_api.row(saturday) is None
    saved = calendar_api.save({"note": "只改备注"}, day=saturday)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    assert saved.get_json()["result"] == "committed"
    # 默认周末按假期存：不上班，两个优先级都不可排产，备注是这次填的。
    assert calendar_api.row(saturday) == {"date": saturday, "day_type": "holiday", "efficiency": 1.0,
                                          "allow_normal": "no", "allow_urgent": "no", "remark": "只改备注",
                                          "periods_json": "[]"}


def test_range_preview_read_failure_reports_nothing_committed(calendar_api):
    deny_table_reads(calendar_api.client.application, "WorkCalendar")
    assert_read_failure(calendar_api.preview_response())


def test_range_preview_takes_one_reading_of_the_app_clock_across_midnight(calendar_api):
    from datetime import datetime, timedelta

    from web.runtime_host import install_wall_clock

    readings = []

    def clock():
        # Every reading moves one second on, crossing midnight after the first.
        readings.append(datetime(2026, 10, 7, 23, 59, 59, 900000) + timedelta(seconds=len(readings)))
        return readings[-1]

    install_wall_clock(calendar_api.client.application, clock)
    response = calendar_api.preview_response()
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert len(readings) == 1
    assert body["data"]["created_at"] == body["meta"]["as_of"] == "2026-10-07T23:59:59"
    assert body["data"]["expires_at"] == "2026-10-08T00:14:59"
