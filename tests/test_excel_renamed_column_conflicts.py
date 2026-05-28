from __future__ import annotations

import importlib
import io
import os
import re
import sys
from html import unescape
from pathlib import Path

import openpyxl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.services.common.excel_column_renames import normalize_renamed_column, renamed_column_conflict_message
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.process.op_type_excel_import_service import OpTypeExcelImportService
from core.services.process.supplier_excel_import_service import SupplierExcelImportService


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=os.path.join(str(REPO_ROOT), "schema.sql"), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _make_xlsx(headers, rows) -> bytes:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None
        ws.title = "Sheet1"
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    finally:
        wb.close()


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    return unescape(m.group(1)).strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            vm = re.search(r'value="([^"]*)"', tag)
            return unescape(vm.group(1)).strip() if vm else ""
    raise RuntimeError(f"未能从页面提取隐藏字段：{name}")


def _preview_row(data):
    return ImportPreviewRow(row_num=2, status=RowStatus.NEW, data=dict(data), message="新增")


def test_normalize_renamed_column_keeps_legacy_value_and_reports_conflict() -> None:
    legacy_only = {"工种ID": "OT001", "工种名称": "数车"}
    normalize_renamed_column(legacy_only, current_column="工种编号", legacy_column="工种ID")
    assert legacy_only == {"工种编号": "OT001", "工种名称": "数车"}

    same_value = {"工种编号": "OT001", "工种ID": " OT001 ", "工种名称": "数车"}
    normalize_renamed_column(same_value, current_column="工种编号", legacy_column="工种ID")
    assert same_value == {"工种编号": "OT001", "工种名称": "数车"}

    conflict = {"工种编号": "OT_NEW", "工种ID": "OT_OLD"}
    normalize_renamed_column(conflict, current_column="工种编号", legacy_column="工种ID")
    assert conflict == {"工种编号": "OT_NEW", "工种ID": "OT_OLD"}
    assert "不能同时填写不同值" in (renamed_column_conflict_message(conflict, current_column="工种编号", legacy_column="工种ID") or "")


def test_import_services_reject_renamed_id_column_conflicts(tmp_path) -> None:
    db_path = tmp_path / "aps_test.db"
    ensure_schema(str(db_path), logger=None, schema_path=os.path.join(str(REPO_ROOT), "schema.sql"), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        with pytest.raises(ValidationError, match="不能同时填写不同值"):
            OpTypeExcelImportService(conn).apply_preview_rows(
                [_preview_row({"工种编号": "OT_NEW", "工种ID": "OT_OLD", "工种名称": "冲突工种", "归属": "自制"})],
                mode=ImportMode.OVERWRITE,
                existing_ids=set(),
            )
        with pytest.raises(ValidationError, match="不能同时填写不同值"):
            SupplierExcelImportService(conn).apply_preview_rows(
                [_preview_row({"供应商编号": "SUP_NEW", "供应商ID": "SUP_OLD", "名称": "冲突供应商", "默认周期": 1, "状态": "启用"})],
                mode=ImportMode.OVERWRITE,
                existing_ids=set(),
            )

        op_count = conn.execute("SELECT COUNT(1) FROM OpTypes WHERE op_type_id IN (?, ?)", ("OT_NEW", "OT_OLD")).fetchone()[0]
        supplier_count = conn.execute("SELECT COUNT(1) FROM Suppliers WHERE supplier_id IN (?, ?)", ("SUP_NEW", "SUP_OLD")).fetchone()[0]
        assert int(op_count) == 0
        assert int(supplier_count) == 0
    finally:
        conn.close()


def test_op_type_preview_and_confirm_reject_renamed_id_column_conflict(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    file_bytes = _make_xlsx(["工种编号", "工种ID", "工种名称", "归属"], [["OT_NEW", "OT_OLD", "冲突工种", "自制"]])
    expected_message = (
        "“工种编号”和旧列“工种ID”不能同时填写不同值："
        "当前“工种编号”为“OT_NEW”，“工种ID”为“OT_OLD”。"
        "请保留一个编号列，或把两个值改成一致后重新导入。"
    )

    preview_resp = client.post(
        "/process/excel/op-types/preview",
        data={"mode": ImportMode.OVERWRITE.value, "file": (io.BytesIO(file_bytes), "op_types.xlsx")},
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert expected_message in preview_html
    assert "已识别旧列“工种ID”，本次按“工种编号”处理" in preview_html

    confirm_resp = client.post(
        "/process/excel/op-types/confirm",
        data={
            "mode": ImportMode.OVERWRITE.value,
            "filename": "op_types.xlsx",
            "raw_rows_json": _extract_raw_rows_json(preview_html),
            "preview_baseline": _extract_hidden_input(preview_html, "preview_baseline"),
        },
        follow_redirects=True,
    )
    confirm_html = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "导入被拒绝：Excel 存在 1 行错误。" in confirm_html
    assert expected_message in confirm_html

    verify_conn = get_connection(db_path)
    try:
        rows = verify_conn.execute("SELECT op_type_id FROM OpTypes WHERE op_type_id IN (?, ?)", ("OT_NEW", "OT_OLD")).fetchall()
        assert rows == []
    finally:
        verify_conn.close()


def test_supplier_preview_and_confirm_reject_renamed_id_column_conflict(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    file_bytes = _make_xlsx(
        ["供应商编号", "供应商ID", "名称", "默认周期", "状态", "备注"],
        [["SUP_NEW", "SUP_OLD", "冲突供应商", 1, "启用", ""]],
    )
    expected_message = (
        "“供应商编号”和旧列“供应商ID”不能同时填写不同值："
        "当前“供应商编号”为“SUP_NEW”，“供应商ID”为“SUP_OLD”。"
        "请保留一个编号列，或把两个值改成一致后重新导入。"
    )

    preview_resp = client.post(
        "/process/excel/suppliers/preview",
        data={"mode": ImportMode.OVERWRITE.value, "file": (io.BytesIO(file_bytes), "suppliers.xlsx")},
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert expected_message in preview_html
    assert "已识别旧列“供应商ID”，本次按“供应商编号”处理" in preview_html

    confirm_resp = client.post(
        "/process/excel/suppliers/confirm",
        data={
            "mode": ImportMode.OVERWRITE.value,
            "filename": "suppliers.xlsx",
            "raw_rows_json": _extract_raw_rows_json(preview_html),
            "preview_baseline": _extract_hidden_input(preview_html, "preview_baseline"),
        },
        follow_redirects=True,
    )
    confirm_html = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "导入被拒绝：Excel 存在 1 行错误。" in confirm_html
    assert expected_message in confirm_html

    verify_conn = get_connection(db_path)
    try:
        rows = verify_conn.execute("SELECT supplier_id FROM Suppliers WHERE supplier_id IN (?, ?)", ("SUP_NEW", "SUP_OLD")).fetchall()
        assert rows == []
    finally:
        verify_conn.close()


def test_machine_preview_and_confirm_accept_legacy_machine_headers(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    file_bytes = _make_xlsx(["机器编号", "机器名称", "状态"], [["MC_ALIAS_001", "旧列名设备", "可用"]])

    preview_resp = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": ImportMode.OVERWRITE.value, "file": (io.BytesIO(file_bytes), "machines_alias.xlsx")},
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert "已识别旧列“机器编号/机器名称”，本次按“设备编号/设备名称”处理" in preview_html
    assert "“设备编号”不能为空" not in preview_html

    confirm_resp = client.post(
        "/equipment/excel/machines/confirm",
        data={
            "mode": ImportMode.OVERWRITE.value,
            "filename": "machines_alias.xlsx",
            "raw_rows_json": _extract_raw_rows_json(preview_html),
            "preview_baseline": _extract_hidden_input(preview_html, "preview_baseline"),
        },
        follow_redirects=True,
    )
    confirm_html = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "导入完成" in confirm_html

    verify_conn = get_connection(db_path)
    try:
        row = verify_conn.execute(
            "SELECT machine_id, name, status FROM Machines WHERE machine_id=?",
            ("MC_ALIAS_001",),
        ).fetchone()
        assert row is not None
        assert row["name"] == "旧列名设备"
        assert row["status"] == "active"
    finally:
        verify_conn.close()


def test_machine_preview_and_confirm_reject_legacy_machine_header_conflicts(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    file_bytes = _make_xlsx(
        ["设备编号", "机器编号", "设备名称", "机器名称", "状态"],
        [["MC_NEW", "MC_OLD", "新设备名", "旧设备名", "可用"]],
    )
    expected_id_message = (
        "“设备编号”和旧列“机器编号”不能同时填写不同值："
        "当前“设备编号”为“MC_NEW”，“机器编号”为“MC_OLD”。"
        "请保留一个编号列，或把两个值改成一致后重新导入。"
    )

    preview_resp = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": ImportMode.OVERWRITE.value, "file": (io.BytesIO(file_bytes), "machines_conflict.xlsx")},
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert expected_id_message in preview_html

    confirm_resp = client.post(
        "/equipment/excel/machines/confirm",
        data={
            "mode": ImportMode.OVERWRITE.value,
            "filename": "machines_conflict.xlsx",
            "raw_rows_json": _extract_raw_rows_json(preview_html),
            "preview_baseline": _extract_hidden_input(preview_html, "preview_baseline"),
        },
        follow_redirects=True,
    )
    confirm_html = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "导入被拒绝：Excel 存在 1 行错误。" in confirm_html
    assert expected_id_message in confirm_html

    verify_conn = get_connection(db_path)
    try:
        rows = verify_conn.execute("SELECT machine_id FROM Machines WHERE machine_id IN (?, ?)", ("MC_NEW", "MC_OLD")).fetchall()
        assert rows == []
    finally:
        verify_conn.close()


def test_machine_preview_reports_name_header_conflict_with_name_hint(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    file_bytes = _make_xlsx(
        ["设备编号", "机器编号", "设备名称", "机器名称", "状态"],
        [["MC001", "MC001", "新设备名", "旧设备名", "可用"]],
    )
    expected_name_message = (
        "“设备名称”和旧列“机器名称”不能同时填写不同值："
        "当前“设备名称”为“新设备名”，“机器名称”为“旧设备名”。"
        "请保留一个名称列，或把两个值改成一致后重新导入。"
    )

    preview_resp = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": ImportMode.OVERWRITE.value, "file": (io.BytesIO(file_bytes), "machines_name_conflict.xlsx")},
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert expected_name_message in preview_html
