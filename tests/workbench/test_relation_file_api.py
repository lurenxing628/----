"""可操作设备关系文件的真实 HTTP 合同：路由确实注册进了应用，预检不写库，拒绝行不能确认。"""

import json
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from tests.workbench.relation_file_support import decode, file_bytes

BASE = "/api/workbench/v1/relation-files"
KIND = "operator_machine"


@pytest.fixture(name="client")
def relation_client(db_env):
    # db_env 已经把所有 APS 路径指向临时库；这里不手工注册蓝图，用来锁住真实注册路径。
    from app import create_app

    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert BASE + "/<kind>/preview" in rules and BASE + "/<kind>/template" in rules
    client = app.test_client()
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('OT1','车','internal')")
        conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')",
                         [("OP001", "张三"), ("OP002", "李四")])
        conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,'OT1','active')",
                         [("M001", "车床一"), ("M002", "车床二")])
        conn.commit()
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return closing(conn)


def snapshot(client):
    with database(client) as conn:
        return [line for line in conn.iterdump() if not line.startswith('INSERT INTO "OperationLogs"')]


def links(client):
    with database(client) as conn:
        return {(row["operator_id"], row["machine_id"]): (row["skill_level"], row["is_primary"])
                for row in conn.execute("SELECT * FROM OperatorMachine")}


def upload(client, rows, fmt="csv"):
    fields = {"file": (BytesIO(file_bytes(rows, fmt)), "input." + fmt), "format": fmt, "mode": "upsert"}
    return client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")


def preview_ok(client, rows, fmt="csv"):
    response = upload(client, rows, fmt)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def confirm(client, preview, key="relation-api-request-00001"):
    return client.post(BASE + "/" + KIND + "/confirm", json={
        "request_key": key, "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})


def test_preview_does_not_write_and_confirm_commits_once(client):
    before = snapshot(client)
    preview = preview_ok(client, [("OP001", "M001", "熟练", "是"), ("OP002", "M002", "普通", "否")])
    assert snapshot(client) == before
    assert preview["operation"] == KIND + ".import" and preview["commit_policy"] == "atomic"
    assert preview["can_confirm"] and preview["mode"] == "upsert" and preview["format"] == "csv"
    assert [row["result"] for row in preview["rows"]] == ["new", "new"]
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)

    first = confirm(client, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["result"] == "committed"
    assert links(client) == {("OP001", "M001"): ("expert", "yes"), ("OP002", "M002"): ("normal", "no")}

    after = snapshot(client)
    replay = confirm(client, preview)
    assert replay.status_code == 200
    assert replay.get_json()["replayed"] is True and first.get_json()["replayed"] is False
    assert {k: v for k, v in replay.get_json().items() if k != "replayed"} == \
           {k: v for k, v in first.get_json().items() if k != "replayed"}
    assert snapshot(client) == after


def test_rejected_rows_block_confirmation(client):
    preview = preview_ok(client, [("OP001", "M001", "普通", "否"), ("OP001", "NOPE", "普通", "否")])
    assert preview["can_confirm"] is False
    assert preview["write_context"]["capabilities"][KIND + ".import"] is False
    assert preview["write_context"]["blocked_reasons"][0]["code"] == "constraint_conflict"
    assert [row["result"] for row in preview["rows"]] == ["new", "rejected"]
    response = confirm(client, preview)
    assert response.status_code != 200
    assert links(client) == {}


def test_primary_handover_note_is_public(client):
    seed = preview_ok(client, [("OP001", "M001", "普通", "是")])
    assert confirm(client, seed).status_code == 200
    preview = preview_ok(client, [("OP001", "M002", "普通", "是")])
    row = preview["rows"][0]
    assert row["requires_confirmation"] and any("M001" in note for note in row["notes"])
    assert confirm(client, preview, key="relation-api-request-00002").status_code == 200
    assert links(client) == {("OP001", "M001"): ("normal", "no"), ("OP001", "M002"): ("normal", "yes")}


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_download_has_headers_only(client, fmt):
    response = client.get(BASE + "/" + KIND + "/template", query_string={"format": fmt})
    assert response.status_code == 200
    assert response.headers["X-Workbench-Row-Count"] == "0"
    assert "%E5%8F%AF%E6%93%8D%E4%BD%9C%E8%AE%BE%E5%A4%87" in response.headers["Content-Disposition"]

    class Download:
        content = response.get_data()

    headers, rows = decode(Download(), fmt)
    assert headers == ["工号", "设备编号", "技能等级", "主操设备", "人员姓名（只读）", "设备名称（只读）"]
    assert rows == []


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_round_trip_reports_no_change(client, fmt):
    assert confirm(client, preview_ok(client, [("OP001", "M001", "熟练", "是")])).status_code == 200
    listing = client.get("/api/workbench/v1/entities/operator", query_string={"size": 20})
    assert listing.status_code == 200, listing.get_data(as_text=True)
    body = {"selection": "all", "scope": {}, "snapshot_ref": listing.get_json()["meta"]["snapshot_ref"]}
    prepared = client.post(BASE + "/" + KIND + "/export-preview", json=body)
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    data = prepared.get_json()["data"]
    assert data["row_count"] == 1 and data["formats"] == ["csv", "xlsx"]

    download = client.get(BASE + "/" + KIND + "/export",
                          query_string={"export_ref": data["export_ref"], "format": fmt})
    assert download.status_code == 200 and download.headers["X-Workbench-Row-Count"] == "1"
    fields = {"file": (BytesIO(download.get_data()), "back." + fmt), "format": fmt, "mode": "upsert"}
    again = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert again.status_code == 200, again.get_data(as_text=True)
    assert [row["result"] for row in again.get_json()["data"]["rows"]] == ["unchanged"]


@pytest.mark.parametrize("kind", ("operator_skill", "../operator_machine", "OPERATOR_MACHINE"))
def test_unknown_relation_kind_is_rejected(client, kind):
    assert client.get(BASE + "/" + kind + "/template", query_string={"format": "csv"}).status_code in (400, 404)


@pytest.mark.parametrize("form", ({"format": "csv"}, {"format": "json", "mode": "upsert"},
                                  {"format": "csv", "mode": "replace"}))
def test_bad_upload_form_is_rejected(client, form):
    fields = {"file": (BytesIO(file_bytes([("OP001", "M001")])), "input.csv")}
    fields.update(form)
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 400
    assert links(client) == {}
