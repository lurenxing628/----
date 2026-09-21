"""个人工作日历文件的真实 HTTP 合同：路由确实注册进了应用，导出既按日期范围也能只导选中的人。"""

import json
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from tests.workbench.calendar_file_support import decode, file_bytes

BASE = "/api/workbench/v1/calendar-files"
KIND = "operator_calendar"
DAY = "2026-10-05"
OTHER = "2026-10-06"
HEADERS = ("工号", "日期", "类型", "班次开始", "班次结束", "效率（%）", "允许普通件", "允许急件", "备注",
           "人员姓名（只读）", "可排工时（小时）（只读）")
WRITABLE = HEADERS[:9]


@pytest.fixture(name="client")
def operator_calendar_file_client(db_env):
    from app import create_app

    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert BASE + "/<kind>/preview" in rules and BASE + "/<kind>/export-preview" in rules
    client = app.test_client()
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('OT1','车','internal')")
        conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')",
                         [("OP001", "张三"), ("OP002", "李四")])
        conn.commit()
    # 第一次读库的请求会补写排产配置等默认行。先跑一次只读的预检把这些补完，之后的日历快照才有可比性。
    preview_ok(client, [("OP001", DAY, "工作日", "09:00", "", "", "", "", "")])
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return closing(conn)


def days(client):
    with database(client) as conn:
        return {(row["operator_id"], row["date"]): (row["shift_start"], row["shift_hours"])
                for row in conn.execute("SELECT * FROM OperatorCalendar")}


def ref_of(client, code):
    with database(client) as conn:
        row = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='operator' AND entity_key=? AND active=1",
                           (code,)).fetchone()
        assert row is not None, code
        return row["ref"]


def preview_ok(client, rows, fmt="csv"):
    fields = {"file": (BytesIO(file_bytes(rows, fmt, WRITABLE)), "operator." + fmt), "format": fmt, "mode": "upsert"}
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def confirm(client, preview, key="operator-calendar-file-00001"):
    return client.post(BASE + "/" + KIND + "/confirm", json={
        "request_key": key, "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})


def export_preview(client, body):
    return client.post(BASE + "/" + KIND + "/export-preview", json=body)


def test_preview_does_not_write_and_confirm_commits_once(client):
    preview = preview_ok(client, [("OP001", DAY, "工作日", "09:00", "17:30", "90", "是", "否", "早班"),
                                  ("OP002", DAY, "假期", "", "", "", "否", "否", "")])
    assert days(client) == {}
    assert preview["operation"] == KIND + ".import" and preview["commit_policy"] == "atomic"
    assert preview["can_confirm"] and preview["mode"] == "upsert"
    assert [row["result"] for row in preview["rows"]] == ["new", "new"]
    assert [row["business_code"] for row in preview["rows"]] == ["OP001 / " + DAY, "OP002 / " + DAY]
    assert [item["label"] for item in preview["columns"]] == list(HEADERS)
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)

    first = confirm(client, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["result"] == "committed"
    assert days(client) == {("OP001", DAY): ("09:00", 8.5), ("OP002", DAY): ("08:00", 0.0)}

    replay = confirm(client, preview)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True
    assert days(client) == {("OP001", DAY): ("09:00", 8.5), ("OP002", DAY): ("08:00", 0.0)}


def test_rejected_rows_block_confirmation(client):
    preview = preview_ok(client, [("OP001", DAY, "工作日", "09:00", "", "", "", "", ""),
                                  ("OP404", OTHER, "工作日", "09:00", "", "", "", "", "")])
    assert preview["can_confirm"] is False
    assert preview["write_context"]["capabilities"][KIND + ".import"] is False
    assert [row["result"] for row in preview["rows"]] == ["new", "rejected"]
    assert confirm(client, preview).status_code != 200
    assert days(client) == {}


def test_every_row_says_it_overrides_the_shift_rotation(client):
    preview = preview_ok(client, [("OP001", DAY, "工作日", "09:00", "", "", "", "", "")])
    row = preview["rows"][0]
    assert row["requires_confirmation"] and any("班次轮换" in note for note in row["notes"])
    assert confirm(client, preview).status_code == 200


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_download_has_headers_only(client, fmt):
    response = client.get(BASE + "/" + KIND + "/template", query_string={"format": fmt})
    assert response.status_code == 200 and response.headers["X-Workbench-Row-Count"] == "0"
    assert response.headers["Cache-Control"] == "no-store"

    class Download:
        content = response.get_data()

    headers, rows = decode(Download(), fmt)
    assert headers == list(HEADERS) and rows == []


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_by_date_range_round_trips(client, fmt):
    assert confirm(client, preview_ok(client, [("OP001", DAY, "工作日", "09:00", "17:30", "", "", "", "")])
                   ).status_code == 200
    prepared = export_preview(client, {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}})
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    data = prepared.get_json()["data"]
    assert data["row_count"] == 1 and data["formats"] == ["csv", "xlsx"]
    assert data["range"] == {"start_date": "2026-10-01", "end_date": "2026-10-31"}

    download = client.get(BASE + "/" + KIND + "/export",
                          query_string={"export_ref": data["export_ref"], "format": fmt})
    assert download.status_code == 200 and download.headers["X-Workbench-Row-Count"] == "1"

    class Download:
        content = download.get_data()

    headers, rows = decode(Download(), fmt)
    assert headers == list(HEADERS)
    assert [str(value) for value in rows[0][:4]] == ["OP001", DAY, "工作日", "09:00"]
    assert rows[0][9] == "张三" and str(rows[0][10]) == "8.5"

    fields = {"file": (BytesIO(download.get_data()), "back." + fmt), "format": fmt, "mode": "upsert"}
    again = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert again.status_code == 200, again.get_data(as_text=True)
    assert [row["result"] for row in again.get_json()["data"]["rows"]] == ["unchanged"]


def test_export_can_be_limited_to_selected_people(client):
    rows = [("OP001", DAY, "工作日", "09:00", "", "", "", "", ""),
            ("OP002", DAY, "工作日", "07:00", "", "", "", "", "")]
    assert confirm(client, preview_ok(client, rows)).status_code == 200
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    assert export_preview(client, body).get_json()["data"]["row_count"] == 2

    scoped = export_preview(client, {**body, "scope": {"operator_refs": [ref_of(client, "OP002")]}})
    assert scoped.status_code == 200, scoped.get_data(as_text=True)
    data = scoped.get_json()["data"]
    assert data["row_count"] == 1
    download = client.get(BASE + "/" + KIND + "/export",
                          query_string={"export_ref": data["export_ref"], "format": "csv"})
    assert download.status_code == 200 and download.headers["X-Workbench-Row-Count"] == "1"
    assert "OP001" not in download.get_data().decode("utf-8-sig")


def test_export_scope_of_nobody_downloads_an_empty_file(client):
    assert confirm(client, preview_ok(client, [("OP001", DAY, "工作日", "09:00", "", "", "", "", "")])
                   ).status_code == 200
    prepared = export_preview(client, {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"},
                                       "scope": {"operator_refs": []}})
    assert prepared.status_code == 200 and prepared.get_json()["data"]["row_count"] == 0


def test_export_preview_reuses_a_matching_snapshot(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    first = export_preview(client, body)
    assert first.status_code == 200
    reference = first.get_json()["meta"]["snapshot_ref"]
    again = export_preview(client, {**body, "snapshot_ref": reference})
    assert again.status_code == 200 and again.get_json()["meta"]["snapshot_ref"] == reference


def test_export_preview_rejects_a_snapshot_from_another_scope(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    reference = export_preview(client, body).get_json()["meta"]["snapshot_ref"]
    scoped = export_preview(client, {**body, "snapshot_ref": reference,
                                     "scope": {"operator_refs": [ref_of(client, "OP001")]}})
    assert scoped.status_code != 200


def test_export_preview_rejects_a_snapshot_from_a_changed_range(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    reference = export_preview(client, body).get_json()["meta"]["snapshot_ref"]
    assert confirm(client, preview_ok(client, [("OP001", DAY, "工作日", "09:00", "", "", "", "", "")])
                   ).status_code == 200
    assert export_preview(client, {**body, "snapshot_ref": reference}).status_code != 200


@pytest.mark.parametrize("scope", ({"machine_refs": []}, {"operator_refs": [], "extra": 1}, []))
def test_export_scope_of_the_wrong_shape_is_rejected(client, scope):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}, "scope": scope}
    assert export_preview(client, body).status_code == 400


@pytest.mark.parametrize("refs", ("all", [1], ["not-a-ref"]))
def test_export_scope_with_bad_references_is_rejected(client, refs):
    """编号本身不合法交给资源层的统一判据，所以是 422 而不是路由的 400。"""
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}, "scope": {"operator_refs": refs}}
    assert export_preview(client, body).status_code == 422


def test_global_calendar_does_not_accept_an_operator_scope(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"},
            "scope": {"operator_refs": [ref_of(client, "OP001")]}}
    assert client.post(BASE + "/work_calendar/export-preview", json=body).status_code == 400


def test_an_export_reference_cannot_be_used_on_the_other_calendar(client):
    body = {"range": {"start_date": "2026-10-01", "end_date": "2026-10-31"}}
    reference = export_preview(client, body).get_json()["data"]["export_ref"]
    crossed = client.get(BASE + "/work_calendar/export",
                         query_string={"export_ref": reference, "format": "csv"})
    assert crossed.status_code != 200


@pytest.mark.parametrize("form", ({"format": "csv"}, {"format": "json", "mode": "upsert"},
                                  {"format": "csv", "mode": "replace"}))
def test_bad_upload_form_is_rejected(client, form):
    fields = {"file": (BytesIO(file_bytes([("OP001", DAY, "工作日", "09:00", "", "", "", "", "")], "csv", WRITABLE)),
                       "operator.csv")}
    fields.update(form)
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 400
    assert days(client) == {}
