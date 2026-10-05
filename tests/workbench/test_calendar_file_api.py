"""全局工作日历导入预检保持只读，确认写入一次并复用回执。"""

import json
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from tests.workbench.calendar_file_support import HEADERS, file_bytes

BASE = "/api/workbench/v1/calendar-files"
PERIOD_HEADERS = ["工作时段数"] + ["第" + str(index) + "段" + field for index in range(2, 9) for field in ("开始", "结束", "开始日期")]
KIND = "work_calendar"
DAY = "2026-10-01"
OTHER = "2026-10-02"


@pytest.fixture(name="client")
def calendar_file_client(db_env):
    from app import create_app

    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert BASE + "/<kind>/preview" in rules and BASE + "/<kind>/export-preview" in rules
    client = app.test_client()
    # 第一次读库的请求会补写排产配置等默认行。先跑一次只读的预检把这些补完，之后的整库快照才有可比性。
    preview_ok(client, [(DAY, "工作日", "8", "", "", "", "")])
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return closing(conn)


def snapshot(client):
    with database(client) as conn:
        return [line for line in conn.iterdump() if not line.startswith('INSERT INTO "OperationLogs"')]


def days(client):
    with database(client) as conn:
        return {row["date"]: (row["day_type"], row["shift_hours"]) for row in conn.execute("SELECT * FROM WorkCalendar")}


def preview_ok(client, rows, fmt="csv"):
    fields = {"file": (BytesIO(file_bytes(rows, fmt)), "calendar." + fmt), "format": fmt, "mode": "upsert"}
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def confirm(client, preview, key="calendar-file-request-00001"):
    return client.post(BASE + "/" + KIND + "/confirm", json={
        "request_key": key, "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})


def test_preview_does_not_write_and_confirm_commits_once(client):
    preview = preview_ok(client, [(DAY, "工作日", "8", "100", "是", "是", "调休"),
                                  (OTHER, "假期", "0", "", "否", "否", "")])
    # 只比日历表：应用启动后还会陆续补建与本功能无关的表和触发器，整库快照在首几次请求间本来就会变。
    assert days(client) == {}
    assert preview["operation"] == KIND + ".import" and preview["commit_policy"] == "atomic"
    assert preview["can_confirm"] and preview["mode"] == "upsert"
    assert [row["result"] for row in preview["rows"]] == ["new", "new"]
    assert [item["label"] for item in preview["columns"]] == list(HEADERS) + ["班次开始", "班次结束"] + PERIOD_HEADERS
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)

    first = confirm(client, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["result"] == "committed"
    assert days(client) == {DAY: ("workday", 8.0), OTHER: ("holiday", 0.0)}

    after = snapshot(client)
    replay = confirm(client, preview)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True
    assert snapshot(client) == after
