"""Real Flask/SQLite entity commands; every database is the isolated app fixture."""

from __future__ import annotations

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService

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


def test_same_intent_different_input_and_stale_windows_are_rejected(app_client):
    saved, body = _create(app_client)
    ref = saved["data"]["entity_ref"]
    stale = _detail(app_client, ref)["write_context"]
    changed = {**body, "input": {**body["input"], "label": "Conflict"}}
    response = app_client.post(BASE + "/create", json=changed)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "request_key_conflict"
    first = _write(app_client, ref, "update", stale, {"label": "First"}, "api-update-first-0001")
    assert first.status_code == 200
    second = _write(app_client, ref, "update", stale, {"label": "Second"}, "api-update-second-0001")
    assert second.status_code == 409 and second.get_json()["error"]["code"] == "stale_write"
    assert second.get_json()["committed"] is False and _detail(app_client, ref)["label"] == "First"


def test_unchanged_intent_has_receipt_without_rewriting_entity(app_client):
    saved, _ = _create(app_client)
    ref = saved["data"]["entity_ref"]
    detail = _detail(app_client, ref)
    with _database(app_client) as conn:
        before = tuple(conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE ref=?", (ref,)).fetchone())
    response = _write(app_client, ref, "update", detail["write_context"], {"label": "Original"}, "api-unchanged-request-0001")
    assert response.status_code == 200 and response.get_json()["result"] == "unchanged"
    with _database(app_client) as conn:
        assert tuple(conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE ref=?", (ref,)).fetchone()) == before
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 2


def test_referenced_material_blocks_delete_but_allows_careful_update(app_client):
    saved, _ = _create(app_client)
    ref = saved["data"]["entity_ref"]
    original_context = _detail(app_client, ref)["write_context"]
    with _database(app_client) as conn:
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('part','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('batch','part',1)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty) VALUES ('batch','M / %001',2,1)")
    detail = _detail(app_client, ref)
    assert detail["relationships"]["batch_requirement_count"] == 1
    assert detail["write_context"]["capabilities"] == {"material.update": True, "material.delete": False}
    assert detail["write_context"]["blocked_reasons"]
    response = _write(app_client, ref, "delete", original_context, {}, "api-referenced-delete-0001")
    assert response.status_code == 409 and response.get_json()["committed"] is False
    with _database(app_client) as conn:
        before = [tuple(row) for row in conn.execute("SELECT * FROM BatchMaterials")]
    response = _write(app_client, ref, "update", detail["write_context"], {"fields": {"stock_qty": 100}}, "api-referenced-update-0001")
    assert response.status_code == 200
    with _database(app_client) as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM BatchMaterials")] == before


def test_paginated_snapshot_does_not_silently_change_after_write(app_client):
    _create(app_client, code="M1", request_key="api-create-material-0001")
    _create(app_client, code="M2", request_key="api-create-material-0002")
    first = _list(app_client, size=1)
    token = first["meta"]["snapshot_ref"]
    second = _list(app_client, size=1, page=2, snapshot_ref=token)
    assert second["data"]["entities"][0]["business_code"] == "M2"
    assert second["meta"]["as_of"] == first["meta"]["as_of"]
    ref = first["data"]["entities"][0]["ref"]
    context = first["data"]["entities"][0]["write_context"]
    assert _write(app_client, ref, "update", context, {"label": "New"}, "api-snapshot-update-0001").status_code == 200
    for query in ({"page": 2, "size": 1}, {"query": "M2", "size": 1}):
        response = app_client.get(BASE, query_string={**query, "snapshot_ref": token})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert _list(app_client, size=1)["meta"]["snapshot_ref"] != token


def test_read_failures_never_return_demo_or_invoke_automatic_maintenance(app_client, monkeypatch):
    from core.services.system import SystemMaintenanceService
    from core.services.workbench.material_queries import WorkbenchMaterialQueryService

    maintenance = []
    monkeypatch.setattr(SystemMaintenanceService, "run_if_due", lambda *args, **kwargs: maintenance.append("run"))
    with _database(app_client) as conn:
        before = list(conn.iterdump())
    assert _list(app_client)["data"]["entities"] == []
    missing = app_client.get("/api/workbench/v1/commands/not-recorded-request-0001")
    assert missing.status_code == 200 and missing.get_json()["may_be_in_flight"] is True
    with _database(app_client) as conn:
        assert list(conn.iterdump()) == before

    def broken(_):
        raise RuntimeError("private-read-detail")

    monkeypatch.setattr(WorkbenchMaterialQueryService, "state_fingerprint", broken)
    failed = app_client.get(BASE)
    assert failed.status_code == 500 and failed.get_json()["committed"] is False
    assert "data" not in failed.get_json() and "private-read-detail" not in failed.get_data(as_text=True)
    assert maintenance == []


@pytest.mark.parametrize("query", ({"page": "0"}, {"page": "true"}, {"page": "1.5"}, {"size": "201"},
                                    {"sort": "revision"}, {"source": "demo"}, {"query": "x" * 201}))
def test_bad_query_contract_is_explicit_400(app_client, query):
    response = app_client.get(BASE, query_string=query)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("payload", ({"business_code": "X", "label": ""},
                                      {"business_code": "X", "label": "Y", "fields": {"stock_qty": True}},
                                      {"business_code": "X", "label": "Y", "fields": {"stock_qty": -1}},
                                      {"business_code": "X", "label": "Y", "fields": {"status": "low_stock"}},
                                      {"business_code": "X", "label": "Y", "fields": {"quantity": 1}}))
def test_bad_command_never_writes_or_allocates_receipt(app_client, payload):
    token = _list(app_client)["data"]["create_context"]["write_token"]
    response = app_client.post(BASE + "/create", json={"input": payload, "write_token": token, "request_key": "api-invalid-request-0001"})
    assert response.status_code in (400, 422)
    assert response.get_json()["ok"] is False and response.get_json()["committed"] is False
    with _database(app_client) as conn:
        assert conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0


def test_unknown_command_result_points_to_persisted_receipt(app_client, monkeypatch):
    saved, body = _create(app_client)

    def uncertain(*args, **kwargs):
        raise WorkbenchCommandUncertain(body["request_key"])

    monkeypatch.setattr(WorkbenchCommandService, "execute", uncertain)
    response = app_client.post(BASE + "/create", json=body)
    assert response.status_code == 500 and response.get_json()["committed"] == "unknown"
    result = app_client.get(response.get_json()["error"]["result_target"])
    assert result.status_code == 200 and result.get_json() == {**saved, "replayed": True}


def test_routing_and_maintenance_failures_keep_api_contract(app_client):
    from core.infrastructure.backup import maintenance_window

    assert app_client.get(BASE + "/create").status_code == 404
    for response in (app_client.put(BASE), app_client.get("/api/workbench/v1/missing"),
                     app_client.post(BASE + "/create", data="not-json")):
        assert response.status_code >= 400 and response.is_json
        assert response.get_json()["committed"] is False and response.headers["Cache-Control"] == "no-store"
    with maintenance_window(app_client.application.config["DATABASE_PATH"], action="test-workbench-gate"):
        for method, url in (("get", BASE), ("post", BASE + "/create"), ("get", "/api/workbench/v1/commands/maintenance-test-0001")):
            response = getattr(app_client, method)(url)
            assert response.status_code == 503 and response.get_json()["committed"] is False
    assert app_client.get(BASE).status_code == 200
