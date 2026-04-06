from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.batch_service import BatchService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_batch_service_update_rejects_part_change_without_rebuild_and_preserves_existing_data() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_OLD", "旧件", "yes"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_NEW", "新件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "P_OLD", "旧件", 1, "2026-03-10", "normal", "yes", "pending", "原备注"),
        )
        conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("B001_10", "B001", "P1", 10, "工序A", "internal", "pending"),
        )
        conn.commit()

        svc = BatchService(conn, logger=None, op_logger=None)

        with pytest.raises(ValidationError) as exc_info:
            svc.update(
                batch_id="B001",
                part_no="P_NEW",
                part_name="新件-不应写入",
                quantity=9,
                due_date="2026-03-20",
                remark="不应写入",
            )

        message = getattr(exc_info.value, "message", str(exc_info.value))
        assert "开启自动生成工序" in message

        batch_row = conn.execute(
            "SELECT part_no, part_name, quantity, due_date, remark FROM Batches WHERE batch_id='B001'"
        ).fetchone()
        op_count = int(conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id='B001'").fetchone()["cnt"] or 0)

        assert batch_row is not None
        assert str(batch_row["part_no"] or "") == "P_OLD"
        assert str(batch_row["part_name"] or "") == "旧件"
        assert int(batch_row["quantity"] or 0) == 1
        assert str(batch_row["due_date"] or "") == "2026-03-10"
        assert str(batch_row["remark"] or "") == "原备注"
        assert op_count == 1
    finally:
        conn.close()
