from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_service import ScheduleService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _message(exc: ValidationError) -> str:
    return getattr(exc, "message", str(exc))


def test_operation_edit_external_days_required() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_EXT", "外协件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B_EXT", "P_EXT", "外协件", 1, "2026-03-10", "normal", "yes", "pending"),
        )
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, default_days, status) VALUES (?, ?, ?, ?)",
            ("SUP001", "外协厂", 2.0, "active"),
        )
        cur = conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_name, source, supplier_id, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_EXT_10", "B_EXT", "P1", 10, "外协工序", "external", "SUP001", 3.0, "pending"),
        )
        assert cur.lastrowid is not None
        op_id = int(cur.lastrowid)
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=None)
        with pytest.raises(ValidationError) as exc_info:
            svc.update_external_operation(op_id=op_id, supplier_id="SUP001", ext_days="")

        assert "不能为空" in _message(exc_info.value)
        row = conn.execute("SELECT ext_days FROM BatchOperations WHERE id=?", (op_id,)).fetchone()
        assert row is not None
        assert abs(float(row["ext_days"] or 0.0) - 3.0) < 1e-9
    finally:
        conn.close()
