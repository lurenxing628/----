"""Actual Flask registration, frozen scope, no-write previews and receipt replay."""

import json
from io import BytesIO

import pytest
from flask import Blueprint

from tests.workbench.material_actions_api_support import database, expire_contexts, snapshot, without_startup_logs
from tests.workbench.resource_file_support import exported, file_bytes

BASE = "/api/workbench/v1"


def registered(app):
    from web.routes.workbench.resource_actions import register_resource_action_routes
    if not any(rule.rule == BASE + "/imports/<kind>/preview" for rule in app.url_map.iter_rules()):
        bp = Blueprint("resource_actions_test", __name__)
        register_resource_action_routes(bp)
        app.register_blueprint(bp)
    return app.test_client()


@pytest.fixture
def client(db_env):
    from app import create_app
    return registered(create_app())


def upload(client, kind, rows, *, category=None, fmt="csv", headers=None, extra=None):
    headers = headers or (("business_code", "label", "category") if kind == "op_type" else ("business_code", "label", "status"))
    fields = {"file": (BytesIO(file_bytes(rows, fmt, headers)), "input." + fmt), "format": fmt, "mode": "upsert"}
    if category is not None:
        fields["category"] = category
    fields.update(extra or {})
    return client.post(BASE + "/imports/" + kind + "/preview", data=fields, content_type="multipart/form-data")


def command(client, kind, preview, *, key="resource-api-request-00001", operation="import", extra=None):
    body = {"request_key": key, "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}
    body.update(extra or {})
    path = "/imports/" + kind + "/confirm" if operation == "import" else "/entities/" + kind + "/bulk-confirm"
    return client.post(BASE + path, json=body)


def new_preview(client, kind, category=None):
    headers = ["business_code", "label", "category" if kind == "op_type" else "status"]
    rows = [["R1", "Resource 1", category or "active"], ["R2", "Resource 2", category or "active"]]
    if kind == "supplier":
        headers.append("default_days")
        rows = [row + [2.5] for row in rows]
    response = upload(client, kind, rows, category=category, headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result["meta"]["snapshot_ref"] and result["data"]["can_confirm"]
    return result["data"]


@pytest.mark.parametrize('kind,category', [('op_type', 'external')])
def test_real_registration_public_preview_and_committed_restart_replay(client, kind, category):
    before = snapshot(client)
    preview = new_preview(client, kind, category)
    assert preview["write_context"]["write_token"] == preview["preview_ref"]
    assert preview["write_context"]["expires_at"] == preview["expires_at"]
    assert snapshot(client) == before
    assert preview["operation"] == kind + ".import" and preview["commit_policy"] == "atomic"
    assert preview["scope"]["category"] == category
    if category:
        assert preview["category"] == category
    row = preview["rows"][0]
    assert set(row) == {"row", "business_code", "entity_ref", "action", "result", "before", "after", "changes", "errors", "requires_confirmation", "reference_count", "reference_fields"}
    assert set(row["after"]) <= {item["key"] for item in preview["columns"]}
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)
    first = command(client, kind, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    with database(client) as conn:
        conn.executemany("UPDATE OpTypes SET remark=? WHERE op_type_id=?", [("", "R1"), ("keep", "R2")])
        conn.commit()
        content = exported(conn, kind, "csv", category=category).content
    response = client.post(BASE + "/imports/" + kind + "/preview", data={
        "file": (BytesIO(content), "input.csv"), "format": "csv", "mode": "upsert", "category": category},
        content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    roundtrip = response.get_json()["data"]
    assert all(row["errors"] == [] and row["result"] == "unchanged" for row in roundtrip["rows"])
    response = upload(client, kind, [("R2", "'")], category=category, headers=("business_code", "remark"))
    assert response.status_code == 200, response.get_data(as_text=True)
    row = response.get_json()["data"]["rows"][0]
    assert row["errors"] == [] and row["changes"] == {} and row["result"] == "unchanged"
    assert row["after"]["remark"] == "keep"
    expire_contexts(client)
    replay = command(client, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    from app import create_app
    restarted = registered(create_app())
    before = without_startup_logs(snapshot(restarted))
    replay = command(restarted, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    assert without_startup_logs(snapshot(restarted)) == before


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_file_is_written_after_the_read_snapshot_is_released(client, monkeypatch, fmt):
    """整份导出行在读快照里读完；生成文件时读事务已结束，不挡别人提交写入。资源、物料两条下载路由同一做法。"""
    from flask import g

    from core.services.workbench.material import files as material_files
    from core.services.workbench.resource import files as resource_files
    from tests.workbench.material_actions_api_support import export_preview, register_actions, seed

    register_actions(client.application)
    assert command(client, "machine", new_preview(client, "machine")).status_code == 200
    seed(client)
    seen = []

    def spy(module, name, kind):
        original = getattr(module, name)

        def wrapped(*args, **kwargs):
            seen.append((kind, g.db.in_transaction))
            return original(*args, **kwargs)
        monkeypatch.setattr(module, name, wrapped)

    spy(resource_files.WorkbenchResourceFileService, "export_rows", "read")
    spy(resource_files, "write_resource_file", "write")
    spy(material_files.WorkbenchMaterialFileService, "export_rows", "read")
    spy(material_files, "write_material_file", "write")
    listed = client.get(BASE + "/entities/machine", query_string={"size": 200})
    assert listed.status_code == 200, listed.get_data(as_text=True)
    approved = client.post(BASE + "/exports/machine/preview", json={
        "selection": "all", "scope": {}, "page_size": 200, "snapshot_ref": listed.get_json()["meta"]["snapshot_ref"]}).get_json()
    result = client.get(BASE + "/exports/machine", query_string={"export_ref": approved["data"]["export_ref"], "format": fmt})
    assert result.status_code == 200, result.get_json()
    assert int(result.headers["X-Workbench-Row-Count"]) == approved["data"]["row_count"] > 0
    assert seen == [("read", True), ("write", False)]
    seen.clear()
    approved = export_preview(client, "all")
    result = client.get(BASE + "/exports/material", query_string={"export_ref": approved["data"]["export_ref"], "format": fmt})
    assert result.status_code == 200, result.get_json()
    assert seen == [("read", True), ("write", False)]
