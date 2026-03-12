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


def _insert_team(conn: sqlite3.Connection, team_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)",
        (team_id, name, "active"),
    )


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


def test_operator_excel_import_update_without_team_column_preserves_existing_team_id() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        _insert_team(conn, "TEAM-01", "车工一组")
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("OP001", "张三", "active", "TEAM-01", "旧备注"),
        )
        conn.commit()

        svc = OperatorExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [
                _pr(
                    {"工号": "OP001", "姓名": "张三-更新", "状态": "active", "备注": "新备注"},
                    status=RowStatus.UPDATE,
                    row_num=2,
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids={"OP001"},
        )
        assert int(stats.get("update_count", 0)) == 1, stats

        row = conn.execute(
            "SELECT name, status, team_id, remark FROM Operators WHERE operator_id=?",
            ("OP001",),
        ).fetchone()
        assert row is not None
        assert row["name"] == "张三-更新"
        assert row["status"] == "active"
        assert row["team_id"] == "TEAM-01"
        assert row["remark"] == "新备注"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_operator_excel_import_team_accepts_id_or_name_and_blank_clears() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        _insert_team(conn, "TEAM-01", "车工一组")
        _insert_team(conn, "TEAM-02", "车工二组")
        conn.commit()

        svc = OperatorExcelImportService(conn)
        svc.apply_preview_rows(
            [
                _pr(
                    {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "TEAM-01", "备注": "首次导入"},
                    row_num=2,
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        row1 = conn.execute(
            "SELECT team_id, remark FROM Operators WHERE operator_id=?",
            ("OP001",),
        ).fetchone()
        assert row1 is not None
        assert row1["team_id"] == "TEAM-01"
        assert row1["remark"] == "首次导入"

        svc.apply_preview_rows(
            [
                _pr(
                    {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "车工二组", "备注": "按名称切换"},
                    status=RowStatus.UPDATE,
                    row_num=3,
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids={"OP001"},
        )
        row2 = conn.execute(
            "SELECT team_id, remark FROM Operators WHERE operator_id=?",
            ("OP001",),
        ).fetchone()
        assert row2 is not None
        assert row2["team_id"] == "TEAM-02"
        assert row2["remark"] == "按名称切换"

        svc.apply_preview_rows(
            [
                _pr(
                    {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "", "备注": "显式清空"},
                    status=RowStatus.UPDATE,
                    row_num=4,
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids={"OP001"},
        )
        row3 = conn.execute(
            "SELECT team_id, remark FROM Operators WHERE operator_id=?",
            ("OP001",),
        ).fetchone()
        assert row3 is not None
        assert row3["team_id"] is None
        assert row3["remark"] == "显式清空"
    finally:
        try:
            conn.close()
        except Exception:
            pass