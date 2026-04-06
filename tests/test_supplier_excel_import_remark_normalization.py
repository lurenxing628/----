from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict

from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.process.supplier_excel_import_service import SupplierExcelImportService

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _pr(data: Dict[str, Any], *, status: RowStatus = RowStatus.NEW, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def test_supplier_excel_import_normalizes_remark_text() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = SupplierExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [
                _pr({"供应商ID": " S001 ", "名称": " 外协-标印厂 ", "默认周期": 2, "状态": None, "备注": "  abc  "}, row_num=2),
                _pr({"供应商ID": "S002", "名称": "外协-热处理厂", "默认周期": 1.0, "状态": "启用", "备注": "   "}, row_num=3),
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        assert int(stats.get("total_rows", 0)) == 2, stats
        assert int(stats.get("new_count", 0)) == 2, stats
        assert int(stats.get("error_count", 0)) == 0, stats

        r1 = conn.execute(
            "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
            ("S001",),
        ).fetchone()
        assert r1 is not None
        assert r1["supplier_id"] == "S001"
        assert r1["name"] == "外协-标印厂"
        assert float(r1["default_days"] or 0) == 2.0
        assert r1["status"] == "active"
        assert r1["remark"] == "abc"

        r2 = conn.execute(
            "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
            ("S002",),
        ).fetchone()
        assert r2 is not None
        assert r2["supplier_id"] == "S002"
        assert r2["name"] == "外协-热处理厂"
        assert float(r2["default_days"] or 0) == 1.0
        assert r2["status"] == "active"
        assert r2["remark"] is None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, default_days, status, remark) VALUES (?, ?, ?, ?, ?)",
            ("S001", "旧供应商", 2.0, "inactive", "keep me"),
        )
        conn.commit()

        svc = SupplierExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [_pr({"供应商ID": "S001", "名称": "新供应商", "默认周期": 3.5}, status=RowStatus.UPDATE, row_num=2)],
            mode=ImportMode.OVERWRITE,
            existing_ids={"S001"},
        )
        assert int(stats.get("total_rows", 0)) == 1, stats
        assert int(stats.get("update_count", 0)) == 1, stats
        assert int(stats.get("error_count", 0)) == 0, stats

        row = conn.execute(
            "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
            ("S001",),
        ).fetchone()
        assert row is not None
        assert row["supplier_id"] == "S001"
        assert row["name"] == "新供应商"
        assert float(row["default_days"] or 0) == 3.5
        assert row["status"] == "inactive"
        assert row["remark"] == "keep me"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_supplier_excel_import_rejects_blank_default_days() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = SupplierExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [_pr({"供应商ID": "S003", "名称": "空白周期供应商", "默认周期": ""}, row_num=2)],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        assert int(stats.get("total_rows", 0)) == 1, stats
        assert int(stats.get("new_count", 0)) == 0, stats
        assert int(stats.get("error_count", 0)) == 1, stats
        errors_sample = stats.get("errors_sample") or []
        assert errors_sample and "默认周期" in str(errors_sample[0].get("message") or "")

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Suppliers WHERE supplier_id=?", ("S003",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0
    finally:
        conn.close()

