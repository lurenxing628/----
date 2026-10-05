"""Default-calendar rules stay read-only before confirmation and persist across services."""

import pytest

from core.models.calendar_periods import DEFAULT_WORK_PERIODS
from core.services.scheduler.calendar.service import CalendarService
from tests.workbench.calendar_api_support import BASE, calendar_api_fixture  # noqa: F401

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
        service = CalendarService(conn)
        assert service.get("2026-09-10").shift_hours == 7
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCalendarDefaults").fetchone()[0] == 1
