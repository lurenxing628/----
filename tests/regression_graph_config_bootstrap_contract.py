"""回归测试：全新库经 ensure_schema 后调用 ConfigService.ensure_defaults()，应把全部 graph_* 图分析配置项以约定默认值写入 ScheduleConfig（如 graph_analysis_mode=on、graph_selection_policy=balanced、graph_critical_weight=500 等），多一项少一项都视为契约破坏。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.infrastructure.database import ensure_schema
from core.services.scheduler.config.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"

EXPECTED_GRAPH_DEFAULTS = {
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


def test_fresh_db_ensure_defaults_inserts_graph_config_defaults(tmp_path) -> None:
    db_path = tmp_path / "graph_config_bootstrap.db"

    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        ConfigService(conn, logger=None, op_logger=None).ensure_defaults()
        rows = {
            str(row["config_key"]): str(row["config_value"])
            for row in conn.execute(
                "SELECT config_key, config_value FROM ScheduleConfig WHERE config_key LIKE 'graph_%' ORDER BY config_key"
            )
        }
    finally:
        conn.close()

    assert rows == EXPECTED_GRAPH_DEFAULTS
