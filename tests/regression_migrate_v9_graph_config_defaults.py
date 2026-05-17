from __future__ import annotations

import json
import sqlite3
from typing import Dict

import pytest

from core.infrastructure.migrations.v9 import run as run_v9

GRAPH_DEFAULTS: Dict[str, str] = {
    "graph_analysis_mode": "off",
    "graph_block_on_cycle": "no",
    "graph_critical_weight": "500",
    "graph_impact_weight": "10",
    "graph_debug_export": "no",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE ScheduleConfig (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def _rows(conn: sqlite3.Connection) -> Dict[str, str]:
    return {
        str(row["config_key"]): str(row["config_value"])
        for row in conn.execute("SELECT config_key, config_value FROM ScheduleConfig ORDER BY config_key")
    }


def test_v9_inserts_graph_defaults_into_existing_schedule_config() -> None:
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO ScheduleConfig(config_key, config_value, description) VALUES (?, ?, ?)",
            ("sort_strategy", "priority_first", "当前排序策略"),
        )

        outcome = run_v9(conn, logger=None)

        assert str(outcome.value) == "applied"
        rows = _rows(conn)
        assert rows["sort_strategy"] == "priority_first"
        for key, value in GRAPH_DEFAULTS.items():
            assert rows[key] == value
    finally:
        conn.close()


def test_v9_patches_preset_payloads_with_graph_defaults() -> None:
    conn = _conn()
    try:
        payload = {"sort_strategy": "priority_first", "priority_weight": 0.4}
        conn.execute(
            "INSERT INTO ScheduleConfig(config_key, config_value, description) VALUES (?, ?, ?)",
            ("preset.demo", json.dumps(payload, ensure_ascii=False), "demo"),
        )

        run_v9(conn, logger=None)

        raw = conn.execute(
            "SELECT config_value FROM ScheduleConfig WHERE config_key = ?",
            ("preset.demo",),
        ).fetchone()[0]
        migrated = json.loads(raw)
        assert migrated["sort_strategy"] == "priority_first"
        for key, value in GRAPH_DEFAULTS.items():
            expected = int(value) if key in {"graph_critical_weight", "graph_impact_weight"} else value
            assert migrated[key] == expected
    finally:
        conn.close()


def test_v9_bad_preset_json_fails_fast() -> None:
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO ScheduleConfig(config_key, config_value, description) VALUES (?, ?, ?)",
            ("preset.bad", "{bad-json", "bad"),
        )

        with pytest.raises(RuntimeError) as exc_info:
            run_v9(conn, logger=None)

        assert "排产配置方案数据已损坏" in str(exc_info.value)
        assert "preset.bad" in str(exc_info.value)
    finally:
        conn.close()


def test_v9_is_idempotent_for_rows_and_preset_payloads() -> None:
    conn = _conn()
    try:
        payload = {"sort_strategy": "priority_first"}
        conn.execute(
            "INSERT INTO ScheduleConfig(config_key, config_value, description) VALUES (?, ?, ?)",
            ("preset.demo", json.dumps(payload, ensure_ascii=False), "demo"),
        )

        run_v9(conn, logger=None)
        first_rows = _rows(conn)
        first_preset = first_rows["preset.demo"]

        run_v9(conn, logger=None)
        second_rows = _rows(conn)
        second_preset = second_rows["preset.demo"]

        assert second_rows == first_rows
        assert second_preset == first_preset
    finally:
        conn.close()
