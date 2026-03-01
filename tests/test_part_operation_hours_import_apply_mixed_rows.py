from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, Tuple

import pytest

from core.services.common.excel_service import ImportPreviewRow, RowStatus
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _seed_part_and_internal_op(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
        ("P001", "Part-001", None, "no", None),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (
            part_no, seq, op_type_id, op_type_name, source,
            supplier_id, ext_days, ext_group_id,
            setup_hours, unit_hours, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 1, None, "OP1", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.commit()


def _pr(data: Dict[str, Any], *, status: RowStatus = RowStatus.UPDATE, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def _get_hours(conn: sqlite3.Connection, *, part_no: str, seq: int) -> Tuple[float, float]:
    row = conn.execute(
        "SELECT setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
        (str(part_no), int(seq)),
    ).fetchone()
    assert row is not None
    return float(row["setup_hours"] or 0.0), float(row["unit_hours"] or 0.0)


def test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        _seed_part_and_internal_op(conn)

        svc = PartOperationHoursExcelImportService(conn)
        preview_rows = [
            # 合法写库
            _pr({"图号": "P001", "工序": 1, "换型时间(h)": 2.0, "单件工时(h)": 1.0}, row_num=2),
            # 可解析，但业务错误（工序不存在）→ AppError → 行级错误，不应回滚合法行
            _pr({"图号": "P001", "工序": 999, "换型时间(h)": 0.2, "单件工时(h)": 0.1}, row_num=3),
            # 解析期错误
            _pr({"图号": "P001", "工序": 2, "换型时间(h)": float("nan"), "单件工时(h)": 0.1}, row_num=4),
        ]

        stats = svc.apply_preview_rows(preview_rows)

        assert int(stats.get("total_rows", 0)) == 3, stats
        assert int(stats.get("new_count", 0)) == 0, stats
        assert int(stats.get("update_count", 0)) == 1, stats
        assert int(stats.get("skip_count", 0)) == 0, stats
        assert int(stats.get("error_count", 0)) == 2, stats

        sh, uh = _get_hours(conn, part_no="P001", seq=1)
        assert sh == 2.0
        assert uh == 1.0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_apply_preview_rows_unexpected_exception_rolls_back_all_changes(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        _seed_part_and_internal_op(conn)

        svc = PartOperationHoursExcelImportService(conn)
        sh0, uh0 = _get_hours(conn, part_no="P001", seq=1)

        orig = svc.part_svc.update_internal_hours
        calls = {"n": 0}

        def _wrapped(*args, **kwargs):
            calls["n"] += 1
            if int(calls["n"]) >= 2:
                raise RuntimeError("boom")
            return orig(*args, **kwargs)

        monkeypatch.setattr(svc.part_svc, "update_internal_hours", _wrapped)

        preview_rows = [
            _pr({"图号": "P001", "工序": 1, "换型时间(h)": 2.0, "单件工时(h)": 1.0}, row_num=2),
            _pr({"图号": "P001", "工序": 1, "换型时间(h)": 3.0, "单件工时(h)": 1.0}, row_num=3),
        ]

        with pytest.raises(RuntimeError):
            svc.apply_preview_rows(preview_rows)

        # 外层事务回滚：第一行的成功写入也应被撤销
        sh1, uh1 = _get_hours(conn, part_no="P001", seq=1)
        assert sh1 == sh0
        assert uh1 == uh0
    finally:
        try:
            conn.close()
        except Exception:
            pass

