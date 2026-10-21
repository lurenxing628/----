"""Real Flask/SQLite entity commands; every database is the isolated app fixture."""

from __future__ import annotations

import sqlite3
from io import BytesIO

from core.services.workbench.material.file_codec import write_material_file
from tests.workbench.material_file_support import codec_rows, file_bytes

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
    for fmt in ("csv", "xlsx"):
        response = app_client.post("/api/workbench/v1/imports/material/preview", data={
            "file": (BytesIO(file_bytes([("M / %001", "   ", "   ", "   ")], fmt,
                                       ("business_code", "spec", "unit", "remark"))), "input." + fmt),
            "format": fmt, "mode": "upsert"}, content_type="multipart/form-data")
        assert response.status_code == 200, response.get_data(as_text=True)
        preview = response.get_json()["data"]
        assert not preview["can_confirm"]
        assert {error["field"] for error in preview["rows"][0]["errors"]} == {"spec", "unit", "remark"}
        assert _detail(app_client, ref)["fields"] == detail["fields"]
    response = app_client.post("/api/workbench/v1/imports/material/preview", data={
        "file": (BytesIO(file_bytes([("M / %001", "'", "'", "'")], "csv",
                                   ("business_code", "spec", "unit", "remark"))), "input.csv"),
        "format": "csv", "mode": "upsert"}, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    preview = response.get_json()["data"]
    assert preview["rows"][0]["errors"] == [] and preview["rows"][0]["result"] == "unchanged"
    assert preview["rows"][0]["changes"] == {} and _detail(app_client, ref)["fields"] == detail["fields"]
    with _database(app_client) as conn:
        # 历史资料允许存空字符串，原样导出的 CSV 回导也必须保持这份原值。
        conn.execute("UPDATE Materials SET unit='' WHERE material_id=?", ("M / %001",))
        original = dict(conn.execute("SELECT * FROM Materials").fetchone())
    detail = _detail(app_client, ref)
    response = app_client.post("/api/workbench/v1/imports/material/preview", data={
        "file": (BytesIO(write_material_file(codec_rows([original]), "csv").content), "input.csv"),
        "format": "csv", "mode": "upsert"}, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    preview = response.get_json()["data"]
    assert preview["rows"][0]["errors"] == [] and preview["rows"][0]["result"] == "unchanged"
    assert preview["rows"][0]["changes"] == {} and _detail(app_client, ref)["fields"]["unit"] == ""
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


def test_material_file_holds_one_batch_preparation_and_export_skips_write_snapshot(app_client, monkeypatch):
    import pytest

    from core.models.workbench_command import WorkbenchCommandUncertain
    from core.services.workbench.material.bulk import WorkbenchMaterialBulkService
    from core.services.workbench.material.files import WorkbenchMaterialFileService
    from data.repositories.material_repo import MaterialRepository
    from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository
    from tests.workbench.material_file_support import confirm_delete, confirm_import

    calls, writes = [], []
    capture, update = WorkbenchMaterialFileRepository.capture, MaterialRepository.update

    def captured(repo, **selection):
        calls.append(selection)
        return capture(repo, **selection)

    def fail_second(repo, code, fields):
        writes.append(code)
        if len(writes) == 2:
            raise OSError("injected second material write failure")
        return update(repo, code, fields)

    def reread(*args, **kwargs):
        pytest.fail("prepared material operations must not reread a write snapshot")

    with _database(app_client) as conn:
        conn.executemany("INSERT INTO Materials(material_id,name,stock_qty) VALUES (?, ?, ?)",
                         [("M1", "first", 1), ("M2", "second", 2)])
        conn.commit()
        content = file_bytes([("M1", 10), ("M2", 20)], "csv", ("business_code", "stock_qty"))
        service = WorkbenchMaterialFileService(conn)
        preview = service.preview_import(content, file_format="csv", scope={})
        monkeypatch.setattr(WorkbenchMaterialFileRepository, "capture", captured)
        monkeypatch.setattr(MaterialRepository, "exists", reread)
        with monkeypatch.context() as patch:
            patch.setattr(MaterialRepository, "update", fail_second)
            with pytest.raises(WorkbenchCommandUncertain):
                confirm_import(conn, preview, content, "csv", key="material-prepared-rollback")
        assert len(calls) == 1 and writes == ["M1", "M2"]
        assert [row[0] for row in conn.execute("SELECT stock_qty FROM Materials ORDER BY material_id")] == [1, 2]
        calls.clear()
        result = confirm_import(conn, preview, content, "csv", key="material-prepared-rollback")
        assert len(calls) == 1 and result["result"] == "committed"
        conn.execute("BEGIN")
        exported = service.export_rows("csv", scope={})
        conn.rollback()
        assert [row["stock_qty"] for row in exported] == [10, 20]
        refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='material' AND active=1 ORDER BY entity_key")]
        delete = WorkbenchMaterialBulkService(conn).preview_delete(refs, scope={})
        calls.clear()
        assert confirm_delete(conn, delete, refs, key="material-prepared-delete")["data"]["deleted_count"] == 2
        assert len(calls) == 1 and conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 0
