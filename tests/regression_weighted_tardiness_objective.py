from __future__ import annotations

import sqlite3
from pathlib import Path

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_weighted_tardiness_objective_contract() -> None:
    metrics_a = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=30.0,
    )
    metrics_b = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=20.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=20.0,
    )

    assert objective_score("min_tardiness", metrics_a) < objective_score("min_tardiness", metrics_b)
    assert objective_score("min_weighted_tardiness", metrics_b) < objective_score("min_weighted_tardiness", metrics_a)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        cfg = ConfigService(conn)
        cfg.ensure_defaults()
        cfg.set_objective("min_weighted_tardiness")
        snap = cfg.get_snapshot()
        assert snap.objective == "min_weighted_tardiness"
        assert cfg.get("objective") == "min_weighted_tardiness"
    finally:
        conn.close()
