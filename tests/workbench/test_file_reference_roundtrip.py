"""Exported reference columns remain readable when importing into an older backup."""

import csv
import sqlite3
from contextlib import closing
from io import BytesIO, StringIO

import openpyxl
import pytest

from core.errors import ValidationError
from core.models.workbench_material import normalize_material_input
from core.models.workbench_resource_file import READONLY
from core.services.material.material_service import MaterialService
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.resource.entities import WorkbenchResourceService
from core.services.workbench.resource.files import WorkbenchResourceFileService
from tests.workbench.batch_support import batch_database, detail, ref_for, state
from tests.workbench.identity_metadata_support import business_snapshot, insert_row
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
    conn = client.batch_conn
    conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES(51,17)")
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES(51,'1900-01-01',16.5)")
    conn.commit()
    listed = list_data(client)
    selected = ref_for(client, key="B1")
    approved = client.post(BASE + "/export-preview", json={"selection": "selected", "refs": [selected],
        "scope": {"size": 20, "snapshot_ref": listed["meta"]["snapshot_ref"]}}).get_json()["data"]
    export = client.get(BASE + "/export", query_string={"export_ref": approved["export_ref"]})
    assert export.status_code == 200
    before = state(client)
    document = uploaded(client, [], content=export.data).get_json()["data"]
    assert document["can_confirm"] and state(client) == before
    # 两列只读记录都不导入；导出的「填写说明」表另有只读第一张表的告知。
    assert [item["code"] for item in document["warnings"]] == [
        "first_sheet_only", "reference_column_ignored", "reference_column_ignored"]
    references = document["warnings"][1:]
    assert "“状态”" in references[0]["message"]
    assert "“当前有效齐套（只读）”" in references[1]["message"]
    # 两列只读记录不导入，其余各格和导出时一样：整行判为不变、确认时不写，有效齐套不会写进维护标记。
    row = document["rows"][0]
    assert row["action"] == "unchanged" and row["input"] is None
    original = detail(client, selected)["data"]
    assert original["display_ready_status"] == "yes" and original["fields"]["ready_status"] == "no"
    saved = confirm_batch(client, document)
    assert saved.status_code == 200 and saved.get_json()["result"] == "unchanged", saved.get_json()
    after = detail(client, selected)["data"]
    assert after["status"] == original["status"]
    assert after["fields"]["ready_status"] == original["fields"]["ready_status"]
    assert state(client)[1]["Batches"] == before[1]["Batches"]


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


# openpyxl 的数字格只留 16 位有效数字，CSV 原来又写成 7.0、1e-07；现在两种文件都写成页面上的最短十进制。
STOCKS = {"MAT-THIRD": (10 / 3, "3.3333333333333335"), "MAT-SUM": (0.1 + 0.2, "0.30000000000000004"),
          "MAT-TINY": (1e-07, "0.0000001"), "MAT-SEVEN": (7.0, "7"), "MAT-HUGE": (1e20, "100000000000000000000")}
DAYS = {"S-SUM": (1.1 + 2.2, "3.3000000000000003"), "S-TWO": (2.0, "2")}


def _written(content, fmt, column):
    """文件里每个编号那一格写的文字，以及它是不是文本格（CSV 数字不加防公式撇号）。"""
    if fmt == "csv":
        rows = list(csv.reader(StringIO(content.decode("utf-8-sig"))))[1:]
        return {row[0].lstrip("'"): (row[column], True) for row in rows}
    book = openpyxl.load_workbook(BytesIO(content))
    try:
        return {row[0].value: (row[column].value, (row[column].data_type, row[column].number_format) == ("s", "@"))
                for row in book.worksheets[0].iter_rows(min_row=2)}
    finally:
        book.close()


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_numbers_are_written_as_exact_page_text_and_round_trip_unchanged(resource_conn, fmt):
    conn = resource_conn
    for code, (stock, _) in STOCKS.items():
        insert_row(conn, "Materials", {"material_id": code, "name": code, "stock_qty": stock, "status": "active"})
    for code, (days, _) in DAYS.items():
        insert_row(conn, "Suppliers", {"supplier_id": code, "name": code, "op_type_id": "EXT", "default_days": days, "status": "active"})
    conn.commit()
    before = business_snapshot(conn)
    material, supplier = export_file(conn, fmt, scope={}), exported(conn, "supplier", fmt)
    written = _written(material.content, fmt, 4)
    assert {code: written[code] for code in STOCKS} == {code: (text, True) for code, (_, text) in STOCKS.items()}
    written = _written(supplier.content, fmt, 3)
    assert {code: written[code] for code in DAYS} == {code: (text, True) for code, (_, text) in DAYS.items()}
    preview = WorkbenchMaterialFileService(conn).preview_import(material.content, file_format=fmt, scope={})
    assert preview.as_dict()["summary"]["unchanged"] == material.row_count
    assert confirm_import(conn, preview, material.content, fmt)["result"] == "unchanged"
    preview = WorkbenchResourceFileService(conn, "supplier").preview_import(supplier.content, file_format=fmt, scope={})
    assert preview.as_dict()["summary"]["unchanged"] == supplier.row_count
    assert confirm(conn, "supplier", preview, supplier.content, fmt)["result"] == "unchanged"
    assert business_snapshot(conn) == before


# 最后一个值换算北京时间会越过 9999 年（OverflowError，不是 ValueError），同样原样写出。
@pytest.mark.parametrize("created", ("2026-01-01", "2026/01/01 08:00:00", "", "2026-02-30 08:00:00", "9999-12-31 16:00:00"))
def test_unrecognized_legacy_created_at_is_exported_as_is_not_500(resource_conn, created):
    conn = resource_conn
    insert_row(conn, "Materials", {"material_id": "MAT-OLD", "name": "旧物料", "stock_qty": 1, "status": "active", "created_at": created})
    insert_row(conn, "Suppliers", {"supplier_id": "S-OLD", "name": "旧供应商", "op_type_id": "EXT", "default_days": 2,
                                   "status": "active", "created_at": created})
    conn.commit()
    material = export_file(conn, "csv", scope={})
    rows = {row[0]: row for row in csv.reader(StringIO(material.content.decode("utf-8-sig")))}
    assert rows["'MAT-OLD"][7] == "'" + created
    preview = WorkbenchMaterialFileService(conn).preview_import(material.content, file_format="csv", scope={})
    assert preview.as_dict()["summary"]["unchanged"] == material.row_count
    supplier = exported(conn, "supplier", "csv")
    rows = {row[0]: row for row in csv.reader(StringIO(supplier.content.decode("utf-8-sig")))}
    assert rows["'S-OLD"][-1] == "'" + created
