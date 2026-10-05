"""Real Flask/SQLite entity commands; every database is the isolated app fixture."""

from __future__ import annotations

import sqlite3

BASE = "/api/workbench/v1/entities/material"


def _database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _list(client, **query):
    response = client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _create(client, *, code="M / %001", request_key="api-create-request-00001"):
    context = _list(client)["data"]["create_context"]
    body = {"request_key": request_key, "write_token": context["write_token"],
            "input": {"business_code": code, "label": "Original", "fields": {
                "spec": "round", "stock_qty": 12.5, "unit": "kg", "remark": "keep-me"}}}
    response = client.post(BASE + "/create", json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json(), body


def _detail(client, ref):
    response = client.get(BASE + "/" + ref)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def _write(client, ref, action, context, payload, key):
    body = {"request_key": key, "write_token": context["write_token"], "input": payload}
    return client.post(BASE + "/" + ref + "/" + action, json=body)


def test_real_create_read_update_clear_delete_and_replay_keep_hidden_fields(app_client):
    saved, create_body = _create(app_client)
    assert saved["result"] == "committed" and saved["replayed"] is False
    assert set(saved["data"]) == {"entity_ref", "business_code"}
    ref = saved["data"]["entity_ref"]
    assert len(ref) == 48 and ref != "M / %001"
    detail = _detail(app_client, ref)
    assert detail["fields"] == {"spec": "round", "unit": "kg", "stock_qty": 12.5, "remark": "keep-me"}
    with _database(app_client) as conn:
        original = dict(conn.execute("SELECT * FROM Materials").fetchone())
    changed = _write(app_client, ref, "update", detail["write_context"], {"label": "Changed", "fields": {"spec": None}}, "api-update-request-00001")
    assert changed.status_code == 200 and changed.get_json()["result"] == "committed"
    fresh = _detail(app_client, ref)
    assert fresh["label"] == "Changed" and fresh["fields"]["spec"] is None
    with _database(app_client) as conn:
        actual = dict(conn.execute("SELECT * FROM Materials").fetchone())
        assert actual == {**original, "name": "Changed", "spec": None}
    replay = app_client.post(BASE + "/create", json=create_body).get_json()
    assert replay == {**saved, "replayed": True}
    deleted = _write(app_client, ref, "delete", fresh["write_context"], {}, "api-delete-request-00001")
    assert deleted.status_code == 200 and deleted.get_json()["result"] == "committed"
    assert app_client.get(BASE + "/" + ref).status_code == 404
    repeated = _write(app_client, ref, "delete", fresh["write_context"], {}, "api-delete-request-00001").get_json()
    assert repeated == {**deleted.get_json(), "replayed": True}
    with _database(app_client) as conn:
        assert conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 3
