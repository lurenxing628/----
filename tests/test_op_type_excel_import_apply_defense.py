from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict

from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.process.op_type_excel_import_service import OpTypeExcelImportService

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _pr(data: Dict[str, Any], *, status: RowStatus = RowStatus.NEW, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = OpTypeExcelImportService(conn)
        preview_rows = [
            _pr({"工种ID": "OT001", "工种名称": "数车", "归属": "内部"}, row_num=2),
            _pr({"工种ID": "OT002", "工种名称": "数铣", "归属": "BAD"}, row_num=3),
            _pr({"工种ID": "OT003", "工种名称": "", "归属": "internal"}, row_num=4),
        ]

        stats = svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())
        assert int(stats.get("total_rows", 0)) == 3, stats
        assert int(stats.get("new_count", 0)) == 1, stats
        assert int(stats.get("error_count", 0)) == 2, stats

        rows = conn.execute("SELECT op_type_id, name, category FROM OpTypes ORDER BY op_type_id").fetchall()
        assert [(r["op_type_id"], r["name"], r["category"]) for r in rows] == [("OT001", "数车", "internal")]
    finally:
        try:
            conn.close()
        except Exception:
            pass

