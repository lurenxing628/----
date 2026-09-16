"""Exported reference columns remain readable when importing into an older backup."""

import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from core.errors import ValidationError
from core.models.workbench_material import normalize_material_input
from core.models.workbench_resource_file import READONLY
from core.services.material.material_service import MaterialService
from core.services.workbench.material_files import WorkbenchMaterialFileService
from core.services.workbench.resource_entities import WorkbenchResourceService
from core.services.workbench.resource_files import WorkbenchResourceFileService
from tests.workbench.batch_support import batch_database, detail, ref_for, state
from tests.workbench.material_actions_api_support import material_actions_client, upload
from tests.workbench.material_file_support import confirm_import, export_file, file_bytes
from tests.workbench.material_support import material_row
from tests.workbench.resource_file_support import (
    SCOPES,
    confirm,
    exported,
    ref,
    resource_database,
    scope,
)
from tests.workbench.resource_file_support import (
    file_bytes as resource_bytes,
)
from tests.workbench.test_batch_files import BASE, list_data, uploaded
from tests.workbench.test_batch_files import confirm as confirm_batch

_resource_fixture = resource_database
_batch_fixture = batch_database
_material_api_fixture = material_actions_client


def backup_before_record(conn):
    backup = sqlite3.connect(":memory:")
    backup.row_factory = sqlite3.Row
    backup.execute("PRAGMA foreign_keys=ON")
    conn.backup(backup)
    return closing(backup)


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_material_original_export_can_import_after_restore_without_backdating(schema_conn, fmt):
    with backup_before_record(schema_conn) as restored:
        MaterialService(schema_conn).create("RESTORE-CHECK", "隔离恢复校验物料", unit="件", stock_qty=7)
        schema_conn.execute("UPDATE Materials SET created_at='2001-01-01 01:02:03'")
        schema_conn.commit()
        download = export_file(schema_conn, fmt, scope={})
        preview = WorkbenchMaterialFileService(restored).preview_import(download.content, file_format=fmt, scope={})
        row = preview.as_dict()["rows"][0]
        assert row["result"] == "new" and row["reference_fields"] == ["created_at"]
        assert "created_at" not in row["input"]["fields"]
        assert confirm_import(restored, preview, download.content, fmt)["result"] == "committed"
        created = material_row(restored, "RESTORE-CHECK")
        original = material_row(schema_conn, "RESTORE-CHECK")
        assert {k: v for k, v in created.items() if k != "created_at"} == {k: v for k, v in original.items() if k != "created_at"}
        assert created["created_at"] != original["created_at"]


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_material_reference_timestamp_never_overwrites_existing_fact(schema_conn, fmt):
    MaterialService(schema_conn).create("EXISTING", "原物料", stock_qty=7)
    before = material_row(schema_conn, "EXISTING")
    content = file_bytes([["EXISTING", "改名", "2099-01-01"]], fmt, headers=("物料编号", "名称", "创建时间"))
    preview = WorkbenchMaterialFileService(schema_conn).preview_import(content, file_format=fmt, scope={})
    assert preview.as_dict()["rows"][0]["reference_fields"] == ["created_at"]
    confirm_import(schema_conn, preview, content, fmt)
    assert material_row(schema_conn, "EXISTING") == {**before, "name": "改名"}
    with pytest.raises(ValidationError):
        normalize_material_input("update", {"fields": {"created_at": "2099-01-01"}})


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_material_http_preview_explains_reference_without_system_value_in_new_record(material_actions_client, fmt):
    content = file_bytes([["ROUNDTRIP", "回导", "2001-01-01"]], fmt, headers=("物料编号", "名称", "创建时间"))
    response = upload(material_actions_client, content, fmt)
    assert response.status_code == 200, response.get_json()
    document = response.get_json()["data"]
    assert document["can_confirm"]
    assert document["rows"][0]["reference_fields"] == ["created_at"]
    assert "created_at" not in document["rows"][0]["after"]


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("kind,category", SCOPES)
def test_resource_original_export_can_import_after_restore_without_reference_writes(resource_conn, fmt, kind, category):
    with backup_before_record(resource_conn) as restored:
        headers = ["business_code", "label", "category" if kind == "op_type" else "status"]
        values = ["ROUNDTRIP", "回导 " + kind, category or "active"]
        if kind == "supplier":
            headers.append("default_days")
            values.append(2)
        content = resource_bytes([values], fmt, headers)
        service = WorkbenchResourceFileService(resource_conn, kind)
        preview = service.preview_import(content, file_format=fmt, scope=scope(category))
        confirm(resource_conn, kind, preview, content, fmt)
        download = exported(resource_conn, kind, fmt, category=category, selected_refs=[ref(resource_conn, kind, "ROUNDTRIP")])
        preview = WorkbenchResourceFileService(restored, kind).preview_import(download.content, file_format=fmt, scope=scope(category))
        row = preview.as_dict()["rows"][0]
        assert row["result"] == "new", row["errors"]
        assert "created_at" in row["reference_fields"]
        assert not set(row["input"]["fields"]) & set(READONLY[kind])
        authorization_before = list(restored.execute("SELECT * FROM OperatorMachine"))
        assert confirm(restored, kind, preview, download.content, fmt)["result"] == "committed"
        assert list(restored.execute("SELECT * FROM OperatorMachine")) == authorization_before
        reread = WorkbenchResourceFileService(restored, kind).preview_import(download.content, file_format=fmt, scope=scope(category))
        assert reread.as_dict()["summary"]["unchanged"] == 1


@pytest.mark.parametrize("kind,code", (("machine", "M1"), ("operator", "O1")))
def test_reference_authorizations_cannot_change_permissions_and_unknown_columns_reject(resource_conn, kind, code):
    headers = ("business_code", "label", "machine_authorizations")
    content = resource_bytes([[code, "新名称", '[{"machine_code":"ATTACK","operator_code":"ATTACK","is_primary":"yes"}]']], headers=headers)
    service = WorkbenchResourceFileService(resource_conn, kind)
    preview = service.preview_import(content, file_format="csv", scope={})
    row = preview.as_dict()["rows"][0]
    assert row["result"] == "update" and row["reference_fields"] == ["machine_authorizations"]
    assert not row["input"].get("relationships")
    before = [tuple(item) for item in resource_conn.execute("SELECT * FROM OperatorMachine")]
    confirm(resource_conn, kind, preview, content)
    assert [tuple(item) for item in resource_conn.execute("SELECT * FROM OperatorMachine")] == before
    with pytest.raises(ValidationError):
        WorkbenchResourceService(resource_conn, kind).normalize_input("update", {"fields": {"machine_authorizations": []}})
    with pytest.raises(ValidationError):
        service.preview_import(resource_bytes([[code, "ATTACK"]], headers=("business_code", "grant_machine")), file_format="csv", scope={})


def test_batch_actual_export_reimports_status_as_reference(batch_client):
    client = batch_client
    listed = list_data(client)
    approved = client.post(BASE + "/export-preview", json={"selection": "selected", "refs": [ref_for(client)],
        "scope": {"size": 20, "snapshot_ref": listed["meta"]["snapshot_ref"]}}).get_json()["data"]
    export = client.get(BASE + "/export", query_string={"export_ref": approved["export_ref"]})
    assert export.status_code == 200
    before = state(client)
    document = uploaded(client, [], content=export.data).get_json()["data"]
    assert document["can_confirm"] and state(client) == before
    assert document["warnings"] == [{"code": "reference_column_ignored", "message": "文件中的“状态”仅供参考，不导入；已有批次保留当前状态，新批次从待排开始。"}]
    assert "status" not in document["rows"][0]["input"]["fields"]
    original = detail(client)["data"]["status"]
    assert confirm_batch(client, document).status_code == 200
    assert detail(client)["data"]["status"] == original


def test_batch_reference_status_cannot_create_completed_state_or_accept_unknown_column(batch_client):
    import openpyxl

    from core.models.workbench_batch_file import HEADERS

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADERS + ("状态",))
    sheet.append(["FROM-EXPORT", "P1", 7, None, "普通", "齐套", None, "回导", "已完成"])
    content = BytesIO()
    workbook.save(content)
    document = uploaded(batch_client, [], content=content.getvalue()).get_json()["data"]
    assert document["can_confirm"]
    assert confirm_batch(batch_client, document).status_code == 200
    assert detail(batch_client, ref_for(batch_client, key="FROM-EXPORT"))["data"]["status"] == "pending"
    sheet.cell(1, 9, "write_status")
    content = BytesIO()
    workbook.save(content)
    before = state(batch_client)
    response = uploaded(batch_client, [], content=content.getvalue())
    assert response.status_code == 422 and state(batch_client) == before
    workbook.close()
