"""Real Flask/SQLite entity commands; every database is the isolated app fixture."""

from __future__ import annotations

import sqlite3
from io import BytesIO

import pytest

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
    for flag, numeric in ((True, 1), (False, 0)):
        with _database(app_client) as conn:
            conn.execute("UPDATE Materials SET stock_qty=? WHERE material_id=?", (numeric, "M / %001"))
        response = app_client.post("/api/workbench/v1/imports/material/preview", data={
            "file": (BytesIO(file_bytes([("M / %001", flag)], "xlsx", ("business_code", "stock_qty"))), "input.xlsx"),
            "format": "xlsx", "mode": "upsert"}, content_type="multipart/form-data")
        assert response.status_code == 200, response.get_data(as_text=True)
        bool_preview = response.get_json()["data"]
        assert bool_preview["can_confirm"] is False and bool_preview["rows"][0]["result"] == "rejected"
        assert [error["field"] for error in bool_preview["rows"][0]["errors"]] == ["fields.stock_qty"]
    with _database(app_client) as conn:
        conn.execute("UPDATE Materials SET stock_qty=? WHERE material_id=?", (original["stock_qty"], "M / %001"))
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

    with _database(app_client) as conn:
        conn.executemany("INSERT INTO Materials(material_id,name,stock_qty) VALUES (?, ?, ?)",
                         [("M1", "first", 1), ("M2", "second", 2)])
        conn.commit()
        content = file_bytes([("M1", 10), ("M2", 20)], "csv", ("business_code", "stock_qty"))
        service = WorkbenchMaterialFileService(conn)
        preview = service.preview_import(content, file_format="csv", scope={})
        monkeypatch.setattr(WorkbenchMaterialFileRepository, "capture", captured)
        with monkeypatch.context() as patch:
            patch.setattr(MaterialRepository, "update", fail_second)
            with pytest.raises(WorkbenchCommandUncertain):
                confirm_import(conn, preview, content, "csv", key="material-prepared-rollback")
        assert len(calls) == 1 and writes == ["M1", "M2"]
        assert [row[0] for row in conn.execute("SELECT stock_qty FROM Materials ORDER BY material_id")] == [1, 2]
        calls.clear()
        result = confirm_import(conn, preview, content, "csv", key="material-prepared-rollback")
        assert len(calls) == 1 and result["result"] == "committed"
        with service.reader.read_snapshot():
            exported = service.export_rows("csv", scope={})
        assert [row["stock_qty"] for row in exported] == [10, 20]
        refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='material' AND active=1 ORDER BY entity_key")]
        delete = WorkbenchMaterialBulkService(conn).preview_delete(refs, scope={})
        calls.clear()
        assert confirm_delete(conn, delete, refs, key="material-prepared-delete")["data"]["deleted_count"] == 2
        assert len(calls) == 1 and conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 0


@pytest.mark.parametrize("xml_backend", ("default", "et_xmlfile"))
def test_material_xlsx_export_import_preserves_cr_and_crlf(app_client, monkeypatch, xml_backend):
    import openpyxl

    from tests.workbench.material_actions_api_support import confirm, download, export_preview, upload

    if xml_backend == "et_xmlfile":
        from xml.etree import ElementTree

        import openpyxl.cell._writer as cell_writer
        import openpyxl.worksheet._writer as worksheet_writer
        from et_xmlfile import xmlfile

        # 离线包使用 et_xmlfile；宿主安装的 lxml 不能掩盖其字面 CR 归一化行为。
        monkeypatch.setattr(cell_writer, "Element", ElementTree.Element)
        monkeypatch.setattr(cell_writer, "SubElement", ElementTree.SubElement)
        monkeypatch.setattr(worksheet_writer, "write_cell", cell_writer.etree_write_cell)
        monkeypatch.setattr(worksheet_writer, "xmlfile", xmlfile)

    saved, _ = _create(app_client)
    ref = saved["data"]["entity_ref"]
    expected = {"spec": "规格一\r规格二", "unit": "kg", "stock_qty": 12.5,
                "remark": "第一行\r\n第二行"}
    response = _write(app_client, ref, "update", _detail(app_client, ref)["write_context"],
                      {"fields": expected}, "material-cr-source-update")
    assert response.status_code == 200, response.get_data(as_text=True)
    exported = download(app_client, export_preview(app_client, "all"), "xlsx")
    assert exported.status_code == 200, exported.get_data(as_text=True)
    wb = openpyxl.load_workbook(BytesIO(exported.data), read_only=True, data_only=False)
    try:
        values = next(wb.worksheets[0].iter_rows(min_row=2, max_row=2, values_only=True))
        assert values[2] == expected["spec"] and values[6] == expected["remark"]
    finally:
        wb.close()

    response = _write(app_client, ref, "update", _detail(app_client, ref)["write_context"],
                      {"fields": {"spec": "changed", "remark": None}}, "material-cr-before-import")
    assert response.status_code == 200, response.get_data(as_text=True)
    response = upload(app_client, exported.data, "xlsx")
    assert response.status_code == 200, response.get_data(as_text=True)
    preview = response.get_json()["data"]
    assert preview["can_confirm"] and preview["rows"][0]["errors"] == []
    response = confirm(app_client, preview, key="material-cr-import-confirm")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert _detail(app_client, ref)["fields"] == expected
