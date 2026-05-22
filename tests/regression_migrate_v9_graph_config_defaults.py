from __future__ import annotations

import json
import sqlite3
from typing import Dict, Optional

import pytest

from core.infrastructure.migrations.common import MigrationOutcome
from core.infrastructure.migrations.v9 import run as run_v9

_GRAPH_DEFAULTS = {
    "graph_analysis_mode": "on",
    "graph_block_on_cycle": "no",
    "graph_candidate_weight_count": "5",
    "graph_critical_weight": "500",
    "graph_overdue_tolerance_count": "1",
    "graph_impact_weight": "10",
    "graph_selection_policy": "balanced",
    "graph_tardiness_tolerance_ratio": "0.1",
    "graph_debug_export": "no",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_schedule_config_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE ScheduleConfig(
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            description TEXT
        )
        """
    )
    conn.commit()


def _upsert_config(conn: sqlite3.Connection, key: str, value: str, description: Optional[str] = None) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO ScheduleConfig(config_key, config_value, description)
        VALUES (?, ?, ?)
        """,
        (key, value, description),
    )


def _fetch_config_values(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute(
        """
        SELECT config_key, config_value
        FROM ScheduleConfig
        ORDER BY config_key
        """
    ).fetchall()
    return {str(row["config_key"]): str(row["config_value"]) for row in rows}


def _fetch_preset(conn: sqlite3.Connection, key: str) -> Dict[str, object]:
    row = conn.execute("SELECT config_value FROM ScheduleConfig WHERE config_key = ?", (key,)).fetchone()
    assert row is not None, f"未找到配置项：{key}"
    payload = json.loads(str(row["config_value"]))
    assert isinstance(payload, dict)
    return payload


@pytest.mark.parametrize("existing_mode", ["off", "report"])
def test_v9_inserts_graph_config_defaults_without_overwriting_existing_graph_analysis_mode(existing_mode: str) -> None:
    conn = _conn()
    try:
        _seed_schedule_config_table(conn)
        _upsert_config(conn, "graph_analysis_mode", existing_mode, "existing graph mode")
        conn.commit()

        outcome = run_v9(conn, logger=None)

        values = _fetch_config_values(conn)
        assert outcome == MigrationOutcome.APPLIED
        assert values["graph_analysis_mode"] == existing_mode
        assert values["graph_block_on_cycle"] == "no"
        assert values["graph_candidate_weight_count"] == "5"
        assert values["graph_critical_weight"] == "500"
        assert values["graph_overdue_tolerance_count"] == "1"
        assert values["graph_impact_weight"] == "10"
        assert values["graph_selection_policy"] == "balanced"
        assert values["graph_tardiness_tolerance_ratio"] == "0.1"
        assert values["graph_debug_export"] == "no"
        row = conn.execute("SELECT description FROM ScheduleConfig WHERE config_key='graph_analysis_mode'").fetchone()
        assert row["description"] == "existing graph mode"
    finally:
        conn.close()


def test_v9_patches_preset_json_with_graph_defaults() -> None:
    conn = _conn()
    try:
        _seed_schedule_config_table(conn)
        _upsert_config(conn, "preset.simple", json.dumps({"sort_strategy": "fifo"}, ensure_ascii=False))
        conn.commit()

        outcome = run_v9(conn, logger=None)

        payload = _fetch_preset(conn, "preset.simple")
        assert outcome == MigrationOutcome.APPLIED
        assert payload["sort_strategy"] == "fifo"
        for key, default in _GRAPH_DEFAULTS.items():
            assert payload[key] == default
    finally:
        conn.close()


def test_v9_preserves_existing_preset_graph_values() -> None:
    conn = _conn()
    try:
        _seed_schedule_config_table(conn)
        original = {
            "graph_analysis_mode": "on",
            "graph_block_on_cycle": "yes",
            "graph_critical_weight": 700,
            "graph_impact_weight": 20,
            "graph_debug_export": "yes",
        }
        _upsert_config(conn, "preset.graph", json.dumps(original, ensure_ascii=False))
        conn.commit()

        outcome = run_v9(conn, logger=None)

        payload = _fetch_preset(conn, "preset.graph")
        assert outcome == MigrationOutcome.APPLIED
        for key, value in original.items():
            assert payload[key] == value
        assert payload["graph_candidate_weight_count"] == "5"
        assert payload["graph_selection_policy"] == "balanced"
        assert payload["graph_overdue_tolerance_count"] == "1"
        assert payload["graph_tardiness_tolerance_ratio"] == "0.1"
    finally:
        conn.close()


def test_v9_rejects_bad_preset_json_without_silent_skip() -> None:
    conn = _conn()
    try:
        _seed_schedule_config_table(conn)
        _upsert_config(conn, "preset.bad", "{bad-json")
        conn.commit()

        with pytest.raises(RuntimeError, match="排产配置方案数据已损坏"):
            run_v9(conn, logger=None)
    finally:
        conn.close()
