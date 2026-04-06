from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.scheduler.batch_service import BatchService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_batch_excel_import_rejects_part_change_without_rebuild() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_OLD", "旧件", "yes"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_NEW", "新件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "P_OLD", "旧件", 1, "2026-03-10", "normal", "yes", "pending"),
        )
        conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("B001_10", "B001", "P1", 10, "工序A", "internal", "pending"),
        )
        conn.commit()

        svc = BatchService(conn, logger=None, op_logger=None)
        preview_rows = [
            ImportPreviewRow(
                row_num=2,
                status=RowStatus.UPDATE,
                data={
                    "批次号": "B001",
                    "图号": "P_NEW",
                    "数量": 1,
                    "交期": "2026-03-12",
                    "优先级": "normal",
                    "齐套": "yes",
                    "齐套日期": None,
                    "备注": "变更图号",
                },
                message="将更新",
            )
        ]

        with pytest.raises(ValidationError) as exc_info:
            svc.import_from_preview_rows(
                preview_rows=preview_rows,
                mode=ImportMode.OVERWRITE,
                parts_cache={
                    "P_OLD": SimpleNamespace(part_name="旧件"),
                    "P_NEW": SimpleNamespace(part_name="新件"),
                },
                auto_generate_ops=False,
                strict_mode=False,
                existing_ids={"B001"},
            )

        message = getattr(exc_info.value, "message", str(exc_info.value))
        assert "开启自动生成工序" in message

        batch_row = conn.execute("SELECT part_no, part_name FROM Batches WHERE batch_id='B001'").fetchone()
        op_count = int(conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id='B001'").fetchone()["cnt"] or 0)
        assert batch_row is not None
        assert str(batch_row["part_no"] or "") == "P_OLD"
        assert str(batch_row["part_name"] or "") == "旧件"
        assert op_count == 1
    finally:
        conn.close()
