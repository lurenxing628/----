"""Real app registration and independent material download oracles for HTTP tests."""

import sqlite3
from contextlib import closing
from io import BytesIO

import pytest
from flask import Blueprint

from tests.workbench.material_file_support import file_bytes, verify_download

BASE = "/api/workbench/v1"


def register_actions(app):
    from web.routes.workbench.material_actions import register_material_action_routes

    if not any(rule.rule == BASE + "/imports/material/preview" for rule in app.url_map.iter_rules()):
        bp = Blueprint("material_actions_test", __name__)
        register_material_action_routes(bp)
        app.register_blueprint(bp)
    return app.test_client()


@pytest.fixture
def material_actions_client(db_env):
    # db_env has set every APS path before importing app; never use a user's DB.
    from app import create_app

    return register_actions(create_app())


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return closing(conn)


def snapshot(client):
    with database(client) as conn:
        return list(conn.iterdump())


def without_startup_logs(dump):
    return [line for line in dump if not line.startswith(('INSERT INTO "OperationLogs"',
                                                          'INSERT INTO "sqlite_sequence" VALUES(\'OperationLogs\''))]


def seed(client, count=3):
    with database(client) as conn:
        conn.executemany("INSERT INTO Materials(material_id,name,spec,unit,stock_qty,status,remark,created_at) VALUES (?,?,?,?,?,?,?,?)",
                         [(f"MAT{n:05d}", f"Material {n}", "D25", "kg", n / 4,
                           "active" if n % 2 == 0 else "inactive", "keep", "2020-01-01 10:20:30") for n in range(count)])
        conn.commit()
        return dict(conn.execute("SELECT entity_key,ref FROM WorkbenchEntityRefs WHERE kind='material' AND active=1"))


def listed(client, scope=None, size=20):
    query = {**(scope or {}), "size": size}
    if query.get("status") is None:
        query.pop("status", None)
    response = client.get(BASE + "/entities/material", query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def list_context(client, scope=None, size=20):
    return {"scope": scope or {}, "page_size": size, "snapshot_ref": listed(client, scope, size)["meta"]["snapshot_ref"]}


def bulk_preview(client, refs, scope=None):
    response = client.post(BASE + "/entities/material/bulk-preview",
                           json={"action": "delete", "refs": refs, **list_context(client, scope)})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def import_preview(client, rows, fmt="csv", headers=("物料编号", "名称")):
    response = upload(client, file_bytes(rows, fmt, headers), fmt)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def upload(client, content, fmt="csv", **fields):
    return client.post(BASE + "/imports/material/preview", data={"file": (BytesIO(content), "local-input." + fmt),
                       "format": fmt, "mode": "upsert", **fields}, content_type="multipart/form-data")


def command_body(preview, key="material-actions-request-0001"):
    return {"request_key": key, "write_token": preview["write_context"]["write_token"],
            "input": {"preview_ref": preview["preview_ref"]}}


def confirm(client, preview, key="material-actions-request-0001", body=None):
    path = "/imports/material/confirm" if preview["operation"] == "material.import" else "/entities/material/bulk-confirm"
    return client.post(BASE + path, json=body or command_body(preview, key))


def export_preview(client, selection, *, scope=None, refs=None):
    body = {"selection": selection, **list_context(client, scope, size=1)}
    if refs is not None:
        body["refs"] = refs
    response = client.post(BASE + "/exports/material/preview", json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def download(client, approved, fmt):
    return client.get(BASE + "/exports/material", query_string={"export_ref": approved["data"]["export_ref"], "format": fmt})


def check_download(response, expected, fmt):
    from core.models.workbench_material_file import MaterialFileDownload

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "materials." + fmt in response.headers["Content-Disposition"]
    mime = "text/csv" if fmt == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.mimetype == mime
    verify_download(MaterialFileDownload("materials." + fmt, mime, response.data,
                                         int(response.headers["X-Workbench-Row-Count"])), expected, fmt)


def expire_contexts(client):
    from web import public_token_registry

    with client.application.app_context():
        for scope in public_token_registry._registry().values():
            for entry in scope["tokens"].values():
                entry["expires_at"] = 0


def assert_failure(response, code=None, *, committed=False):
    assert response.status_code >= 400, response.get_data(as_text=True)
    body = response.get_json()
    assert body["ok"] is False and body["committed"] == committed
    assert "data" not in body and response.headers["Cache-Control"] == "no-store"
    if code:
        assert body["error"]["code"] == code, body
    return body
