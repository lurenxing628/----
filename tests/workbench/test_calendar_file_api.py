"""全局工作日历文件的真实 HTTP 合同：路由确实注册进了应用，导出按日期范围而不是列表筛选。"""

import json
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from tests.workbench.calendar_file_support import HEADERS, decode, file_bytes

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


def test_rejected_rows_block_confirmation(client):
    preview = preview_ok(client, [(DAY, "工作日", "8", "", "", "", ""), (OTHER, "工作日", "99", "", "", "", "")])
    assert preview["can_confirm"] is False
    assert preview["write_context"]["capabilities"][KIND + ".import"] is False
    assert [row["result"] for row in preview["rows"]] == ["new", "rejected"]
    assert confirm(client, preview).status_code != 200
    assert days(client) == {}


def test_holiday_with_hours_carries_a_public_note(client):
    preview = preview_ok(client, [(DAY, "假期", "4", "80", "是", "否", "加班")])
    row = preview["rows"][0]
    assert row["requires_confirmation"] and any("工作日" in note for note in row["notes"])
    assert confirm(client, preview).status_code == 200
    assert days(client) == {DAY: ("holiday", 4.0)}


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_download_has_headers_only(client, fmt):
    response = client.get(BASE + "/" + KIND + "/template", query_string={"format": fmt})
    assert response.status_code == 200 and response.headers["X-Workbench-Row-Count"] == "0"
    assert response.headers["Cache-Control"] == "no-store"

    class Download:
        content = response.get_data()

    headers, rows = decode(Download(), fmt)
    assert headers == list(HEADERS) + ["班次开始", "班次结束"] + PERIOD_HEADERS and rows == []


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_by_date_range_round_trips(client, fmt):
    assert confirm(client, preview_ok(client, [(DAY, "工作日", "8", "100", "是", "是", "")])).status_code == 200
    prepared = client.post(BASE + "/" + KIND + "/export-preview",
                           json={"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}})
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    data = prepared.get_json()["data"]
    assert data["row_count"] == 1 and data["formats"] == ["csv", "xlsx"]
    assert data["range"] == {"start_date": "2026-10-01", "end_date": "2026-10-31"}

    download = client.get(BASE + "/" + KIND + "/export",
                          query_string={"export_ref": data["export_ref"], "format": fmt})
    assert download.status_code == 200 and download.headers["X-Workbench-Row-Count"] == "1"
    fields = {"file": (BytesIO(download.get_data()), "back." + fmt), "format": fmt, "mode": "upsert"}
    again = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert again.status_code == 200, again.get_data(as_text=True)
    assert [row["result"] for row in again.get_json()["data"]["rows"]] == ["unchanged"]


def test_export_preview_reuses_a_matching_snapshot(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    first = client.post(BASE + "/" + KIND + "/export-preview", json=body)
    assert first.status_code == 200
    reference = first.get_json()["meta"]["snapshot_ref"]
    again = client.post(BASE + "/" + KIND + "/export-preview", json={**body, "snapshot_ref": reference})
    assert again.status_code == 200
    assert again.get_json()["meta"]["snapshot_ref"] == reference


def test_export_preview_rejects_a_snapshot_from_a_changed_range(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    reference = client.post(BASE + "/" + KIND + "/export-preview", json=body).get_json()["meta"]["snapshot_ref"]
    assert confirm(client, preview_ok(client, [(DAY, "工作日", "8", "", "", "", "")])).status_code == 200
    stale = client.post(BASE + "/" + KIND + "/export-preview", json={**body, "snapshot_ref": reference})
    assert stale.status_code != 200


@pytest.mark.parametrize("body", (
    {"range": {"start_date": "2026-10-31", "end_date": "2026-10-01"}},
    {"range": {"start_date": "2026-01-01", "end_date": "2030-01-01"}},
    {"range": {"start_date": "2026-10-01"}},
    {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31", "extra": 1}},
    {"range": "2026-10"},
))
def test_bad_export_range_is_rejected(client, body):
    assert client.post(BASE + "/" + KIND + "/export-preview", json=body).status_code == 400


@pytest.mark.parametrize("kind", ("shift_calendar", "work-calendar", "WORK_CALENDAR"))
def test_unsupported_calendar_kind_is_rejected(client, kind):
    assert client.get(BASE + "/" + kind + "/template", query_string={"format": "csv"}).status_code in (400, 404)


@pytest.mark.parametrize("form", ({"format": "csv"}, {"format": "json", "mode": "upsert"},
                                  {"format": "csv", "mode": "replace"}))
def test_bad_upload_form_is_rejected(client, form):
    fields = {"file": (BytesIO(file_bytes([(DAY, "工作日", "8", "", "", "", "")])), "calendar.csv")}
    fields.update(form)
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 400
    assert days(client) == {}
