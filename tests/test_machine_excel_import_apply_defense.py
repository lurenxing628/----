from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict

import pytest

from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.equipment.machine_excel_import_service import MachineExcelImportService

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _pr(data: Dict[str, Any], *, status: RowStatus = RowStatus.NEW, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def _count_machines(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(1) AS n FROM Machines").fetchone()
    assert row is not None
    return int(row["n"] or 0)


def test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = MachineExcelImportService(conn)
        preview_rows = [
            _pr({"设备编号": "MC001", "设备名称": "CNC-01", "状态": "active"}, row_num=2),
            _pr({"设备编号": "MC002", "设备名称": "CNC-02", "状态": "BAD"}, row_num=3),
        ]

        with pytest.raises(ValidationError):
            svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

        # continue_on_app_error=False：任何 AppError 均应触发外层事务回滚
        assert _count_machines(conn) == 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_apply_preview_rows_missing_name_raises_validation_error() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = MachineExcelImportService(conn)
        preview_rows = [
            _pr({"设备编号": "MC001", "设备名称": "", "状态": "active"}, row_num=2),
        ]

        with pytest.raises(ValidationError):
            svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

        assert _count_machines(conn) == 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_apply_preview_rows_missing_status_raises_specific_message() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = MachineExcelImportService(conn)
        preview_rows = [
            _pr({"设备编号": "MC001", "设备名称": "CNC-01", "状态": ""}, row_num=2),
        ]

        with pytest.raises(ValidationError) as e:
            svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

        assert "“状态”不能为空" in str(e.value.message or ""), e.value.message
        assert _count_machines(conn) == 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_apply_preview_rows_valid_rows_commit_and_trim_fields() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        svc = MachineExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [
                _pr({"设备编号": " MC001 ", "设备名称": " CNC-01 ", "状态": "可用"}, row_num=2),
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        assert int(stats.get("total_rows", 0)) == 1, stats
        assert int(stats.get("new_count", 0)) == 1, stats
        assert int(stats.get("error_count", 0)) == 0, stats

        row = conn.execute(
            "SELECT machine_id, name, op_type_id, status FROM Machines WHERE machine_id=?",
            ("MC001",),
        ).fetchone()
        assert row is not None
        assert row["machine_id"] == "MC001"
        assert row["name"] == "CNC-01"
        assert row["op_type_id"] is None
        assert row["status"] == "active"
    finally:
        try:
            conn.close()
        except Exception:
            pass

