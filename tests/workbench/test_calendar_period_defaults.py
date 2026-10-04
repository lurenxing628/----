"""Real default-calendar commands, protected against stale drafts and replay."""

import pytest

from core.models.calendar_periods import DEFAULT_WORK_PERIODS
from core.services.scheduler.calendar.service import CalendarService
from tests.workbench.calendar_api_support import BASE, calendar_api_fixture

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


def test_replay_and_stale_defaults_never_duplicate_or_overwrite(calendar_api):
    initial = read(calendar_api)
    assert write(calendar_api, initial).get_json()["replayed"] is False
    assert write(calendar_api, initial).get_json()["replayed"] is True
    stale = write(calendar_api, initial, DEFAULT_WORK_PERIODS, key="calendar-defaults-stale-0001")
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "stale_write"
    assert read(calendar_api)["periods"] == PERIODS


def test_changing_defaults_invalidates_an_open_day_edit(calendar_api):
    day = calendar_api.day("2026-09-10")
    assert write(calendar_api, read(calendar_api)).status_code == 200
    response = calendar_api.client.post(BASE + "/upsert", json={"request_key": "calendar-old-default-draft",
        "write_token": day["write_context"]["write_token"],
        "input": {"date": day["date"], "fields": {"note": "旧草稿"}}})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "stale_write"


@pytest.mark.parametrize("periods", [None, [], [{"start": "09:00", "end": "13:00"}, {"start": "12:00", "end": "17:00"}]])
def test_invalid_defaults_do_not_change_saved_rules(calendar_api, periods):
    initial = read(calendar_api)
    before = calendar_api.state()
    response = write(calendar_api, initial, periods)
    assert response.status_code in (400, 422), response.get_data(as_text=True)
    assert calendar_api.state() == before


def test_overnight_defaults_make_last_representable_day_a_clear_input_error(calendar_api):
    """默认工作时间跨夜后，9999-12-31 的班次会跨出系统能表示的日期：月视图和范围预览都给出中文说明，不报服务器错误。"""
    assert write(calendar_api, read(calendar_api), [{"start": "22:00", "end": "06:00", "day_offset": 0}]).status_code == 200
    assert calendar_api.month(9999, 11)["data"]["next_month"] == {"year": 9999, "month": 12}
    month = calendar_api.client.get(BASE + "/month", query_string={"year": 9999, "month": 12})
    preview = calendar_api.client.post(BASE + "/range/preview", json={"input": {
        "start_date": "9999-12-30", "end_date": "9999-12-31", "scope": "all", "operation": "upsert", "fields": {"note": "夜班"}}})
    for response in (month, preview):
        assert response.status_code == 422, response.get_data(as_text=True)
        assert "9999-12-31 的工作时段超出了系统能处理的最后日期" in response.get_json()["error"]["message"]
