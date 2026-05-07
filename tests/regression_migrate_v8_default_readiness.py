from __future__ import annotations

import json
import sqlite3
from typing import Optional

import pytest

from core.infrastructure.migrations.v8 import run as run_v8


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_v8_tables(conn: sqlite3.Connection, *, preset_value: Optional[str] = None) -> None:
    conn.execute("CREATE TABLE Batches(batch_id TEXT PRIMARY KEY, ready_status TEXT, ready_date DATE)")
    conn.execute("CREATE TABLE BatchMaterials(id INTEGER PRIMARY KEY, required_qty REAL, available_qty REAL, ready_status TEXT)")
    conn.execute("CREATE TABLE ScheduleConfig(config_key TEXT PRIMARY KEY, config_value TEXT)")
    conn.execute("INSERT INTO Batches(batch_id, ready_status, ready_date) VALUES ('B001', 'no', '2099-01-01')")
    conn.execute("INSERT INTO BatchMaterials(id, required_qty, available_qty, ready_status) VALUES (1, 10, 0, 'no')")
    conn.execute("INSERT INTO ScheduleConfig(config_key, config_value) VALUES ('enforce_ready_default', 'yes')")
    if preset_value is not None:
        conn.execute("INSERT INTO ScheduleConfig(config_key, config_value) VALUES ('preset.custom', ?)", (preset_value,))
    conn.commit()


def _seed_batch_material(conn: sqlite3.Connection, *, row_id: int, required_qty: float, available_qty: Optional[float], ready_status: str) -> None:
    conn.execute(
        "INSERT INTO BatchMaterials(id, required_qty, available_qty, ready_status) VALUES (?, ?, ?, ?)",
        (int(row_id), float(required_qty), available_qty, str(ready_status)),
    )


def test_v8_migrates_existing_readiness_data_to_default_ready() -> None:
    conn = _conn()
    try:
        _seed_v8_tables(conn, preset_value=json.dumps({"enforce_ready_default": "yes", "sort_strategy": "fifo"}, ensure_ascii=False))

        run_v8(conn, logger=None)

        batch = conn.execute("SELECT ready_status, ready_date FROM Batches WHERE batch_id='B001'").fetchone()
        material = conn.execute("SELECT required_qty, available_qty, ready_status FROM BatchMaterials WHERE id=1").fetchone()
        enforce_ready = conn.execute("SELECT config_value FROM ScheduleConfig WHERE config_key='enforce_ready_default'").fetchone()
        preset = conn.execute("SELECT config_value FROM ScheduleConfig WHERE config_key='preset.custom'").fetchone()

        assert batch["ready_status"] == "yes"
        assert batch["ready_date"] is None
        assert float(material["available_qty"]) == 10.0
        assert material["ready_status"] == "yes"
        assert enforce_ready["config_value"] == "no"
        assert json.loads(preset["config_value"])["enforce_ready_default"] == "no"
    finally:
        conn.close()


def test_v8_clamps_batch_material_available_qty_without_lowering_surplus() -> None:
    conn = _conn()
    try:
        _seed_v8_tables(conn)
        _seed_batch_material(conn, row_id=2, required_qty=10, available_qty=None, ready_status="no")
        _seed_batch_material(conn, row_id=3, required_qty=10, available_qty=12, ready_status="no")
        conn.commit()

        run_v8(conn, logger=None)

        rows = conn.execute(
            """
            SELECT id, available_qty, ready_status
            FROM BatchMaterials
            ORDER BY id
            """
        ).fetchall()
        by_id = {int(row["id"]): row for row in rows}
        assert float(by_id[1]["available_qty"]) == 10.0
        assert float(by_id[2]["available_qty"]) == 10.0
        assert float(by_id[3]["available_qty"]) == 12.0
        assert {row["ready_status"] for row in rows} == {"yes"}
    finally:
        conn.close()


def test_v8_rejects_bad_preset_json_without_silent_skip() -> None:
    conn = _conn()
    try:
        _seed_v8_tables(conn, preset_value="{bad-json")

        with pytest.raises(RuntimeError, match="排产配置方案数据已损坏"):
            run_v8(conn, logger=None)
    finally:
        conn.close()
