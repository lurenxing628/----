from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict

from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.personnel.operator_excel_import_service import OperatorExcelImportService

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _pr(data: Dict[str, Any], *, status: RowStatus = RowStatus.NEW, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def test_operator_excel_import_strips_name_and_normalizes_remark() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = OperatorExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [
                _pr(
                    {"工号": " OP001 ", "姓名": "  张三  ", "状态": "Active", "备注": "  示例备注  "},
                    row_num=2,
                ),
                _pr(
                    {"工号": "OP002", "姓名": "李四", "状态": "INACTIVE", "备注": "   "},
                    row_num=3,
                ),
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        assert int(stats.get("total_rows", 0)) == 2, stats
        assert int(stats.get("new_count", 0)) == 2, stats
        assert int(stats.get("error_count", 0)) == 0, stats

        r1 = conn.execute(
            "SELECT operator_id, name, status, remark FROM Operators WHERE operator_id=?",
            ("OP001",),
        ).fetchone()
        assert r1 is not None
        assert r1["operator_id"] == "OP001"
        assert r1["name"] == "张三"
        assert r1["status"] == "active"
        assert r1["remark"] == "示例备注"

        r2 = conn.execute(
            "SELECT operator_id, name, status, remark FROM Operators WHERE operator_id=?",
            ("OP002",),
        ).fetchone()
        assert r2 is not None
        assert r2["operator_id"] == "OP002"
        assert r2["name"] == "李四"
        assert r2["status"] == "inactive"
        assert r2["remark"] is None
    finally:
        try:
            conn.close()
        except Exception:
            pass

