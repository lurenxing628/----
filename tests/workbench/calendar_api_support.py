"""Isolated real Flask/SQLite calendar fixtures; no production paths or fake service."""

import sqlite3
import uuid
from contextlib import contextmanager

import pytest

BASE = "/api/workbench/v1/calendar"
NIGHT = "2026-09-09"
WORK = {"type": "work", "hours": 8, "eff": 100, "allowNormal": "yes", "allowUrgent": "yes"}


class CalendarApi:
    def __init__(self, client):
        self.client = client

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.client.application.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def state(self):
        with self.db() as conn:
            return list(conn.iterdump())

    def month(self, year=2026, month=9, **query):
        response = self.client.get(BASE + "/month", query_string={"year": year, "month": month, **query})
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.headers["Cache-Control"] == "no-store"
        return response.get_json()

    def day(self, day=NIGHT):
        return next(item for item in self.month(int(day[:4]), int(day[5:7]))["data"]["days"] if item["date"] == day)

    def day_body(self, day=NIGHT, fields=None, *, action="upsert"):
        payload = {"date": day}
        if action == "upsert":
            payload["fields"] = fields or {}
        return {"request_key": uuid.uuid4().hex, "write_token": self.day(day)["write_context"]["write_token"], "input": payload}

    def save(self, fields, day=NIGHT):
        return self.client.post(BASE + "/upsert", json=self.day_body(day, fields))

    def preview_response(self, **changes):
        payload = {"start_date": "2026-12-28", "end_date": "2027-01-03", "scope": "all", "operation": "upsert", "fields": WORK.copy(), **changes}
        return self.client.post(BASE + "/range/preview", json={"input": payload})

    def preview(self, **changes):
        response = self.preview_response(**changes)
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()["data"]

    @staticmethod
    def confirm_body(preview):
        return {"request_key": uuid.uuid4().hex, "write_token": preview["write_context"]["write_token"],
                "input": {"preview_ref": preview["preview_ref"]}}

    def confirm(self, preview):
        body = self.confirm_body(preview)
        return self.client.post(BASE + "/range/confirm", json=body), body

    def row(self, day=NIGHT):
        with self.db() as conn:
            value = conn.execute("SELECT * FROM WorkCalendar WHERE date=?", (day,)).fetchone()
            return dict(value) if value else None


def seed_calendars(api):
    from core.services.scheduler.calendar.service import CalendarService

    with api.db() as conn:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('CAL-O','Calendar operator')")
        conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES ('CAL-SP','Night','2026-09-01',1)")
        conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES ('CAL-SP',0,0,'21:15','05:15')")
        conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('CAL-O','CAL-SP')")
    with api.db() as conn:
        calendar = CalendarService(conn)
        calendar._admin.repo.upsert_many([
            calendar._admin._build_work_calendar(
                date_value=NIGHT, shift_start="22:30", shift_end="06:30", efficiency=0.875,
                allow_normal="no", allow_urgent="yes", remark="Original night"
            )
        ])
        calendar._admin.operator_calendar_repo.upsert_many([
            calendar._admin._build_operator_calendar(
                operator_id="CAL-O", date_value=NIGHT, shift_start="23:15", shift_end="07:45",
                efficiency=0.625, allow_normal="yes", allow_urgent="no", remark="Personal exception"
            )
        ])


@pytest.fixture(name="calendar_api")
def calendar_api_fixture(app_client):
    # db_env sets APS_* before app import; production factory supplies g.db/error handling.
    from flask import Blueprint

    from web.routes.workbench import calendars

    if not any(rule.rule == BASE + "/month" for rule in app_client.application.url_map.iter_rules()):
        bp = Blueprint("calendar_api_test", __name__)
        calendars.register_calendar_routes(bp)
        app_client.application.register_blueprint(bp)
    api = CalendarApi(app_client)
    seed_calendars(api)
    return api


def assert_error(response, code, status=409, committed=False):
    assert response.status_code == status, response.get_data(as_text=True)
    result = response.get_json()
    assert result["ok"] is False and result["error"]["code"] == code
    assert result["committed"] == committed
    return result


def deny_table_reads(app, table):
    """此后每个请求的连接都拒读 table；仓储把 SQLite 的拒绝翻成 AppError，与真实读库失败走同一条路。"""
    from flask import g

    @app.before_request
    def deny():
        g.db.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY
                            if action == sqlite3.SQLITE_READ and name == table else sqlite3.SQLITE_OK)


def assert_read_failure(response):
    """只读预览读库失败：明确没有写入，也不给回执线索。"""
    result = assert_error(response, "storage_failure", 500)
    assert result["committed"] is False
    assert not {"request_key", "result_target"} & set(result["error"])
    return result
