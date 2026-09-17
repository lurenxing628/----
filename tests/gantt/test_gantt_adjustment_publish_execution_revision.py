"""回归测试：甘特调整模拟方案的执行快照契约（schema v17 新增 execution_snapshot_* 列、v16→v17 迁移补列）——保存方案只记录执行快照不写正式表；发布时重核快照，现场状态变更或已开工工序被挪动则报错回滚（code 6003）不写 OperationLogs，正常发布则把快照写入 ScheduleHistory.result_summary；保存/发布路由不向用户暴露 scenario_id/status 等内部字段。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from tests.gantt.gantt_legacy_schema_support import (
    assert_legacy_business_data_preserved,
    seed_legacy_scenario,
    snapshot_legacy_business_data,
    strip_later_schema,
)
from tests.gantt.test_gantt_scenario_publish import (
    SCHEMA_PATH,
    _connect,
    _seed_base,
    _seed_baseline_best_selection,
)


def _snapshot_columns(conn: sqlite3.Connection) -> set:
    return {str(row["name"]) for row in conn.execute("PRAGMA table_info(ScheduleAdjustmentScenario)").fetchall()}


def _scenario_snapshot(conn: sqlite3.Connection, scenario_id: str):
    row = conn.execute(
        """
        SELECT execution_snapshot_revision, execution_snapshot_op_ids, execution_snapshot_op_count
        FROM ScheduleAdjustmentScenario
        WHERE scenario_id = ?
        """,
        (scenario_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


def test_v17_schema_and_migration_add_scenario_execution_snapshot_columns(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {
            "execution_snapshot_revision",
            "execution_snapshot_op_ids",
            "execution_snapshot_op_count",
        } <= _snapshot_columns(conn)
        assert detect_schema_is_current(conn)
    finally:
        conn.close()

    db_path = tmp_path / "legacy_v16_without_snapshot.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        strip_later_schema(conn, version=16)
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion(id, version) VALUES (1, 16);
            DROP TABLE ScheduleAdjustmentScenarioRow;
            DROP TABLE ScheduleAdjustmentScenario;
            CREATE TABLE ScheduleAdjustmentScenario (
                scenario_id        TEXT PRIMARY KEY,
                source_draft_id    TEXT NOT NULL UNIQUE,
                base_version       INTEGER NOT NULL,
                base_plan_role     TEXT NOT NULL CHECK(base_plan_role IN ('adopted', 'baseline_best', 'critical_best')),
                base_source_table  TEXT NOT NULL,
                base_candidate_id  INTEGER,
                base_candidate_key TEXT,
                scenario_name      TEXT,
                status             TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'discarded', 'published', 'expired')),
                validation_status  TEXT NOT NULL CHECK(validation_status IN ('valid', 'warning')),
                issue_count        INTEGER NOT NULL DEFAULT 0,
                issues_json        TEXT,
                row_count          INTEGER NOT NULL DEFAULT 0,
                created_by         TEXT,
                published_version  INTEGER,
                published_by       TEXT,
                published_reason   TEXT,
                published_at       DATETIME,
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE ScheduleAdjustmentScenarioRow (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id         TEXT NOT NULL,
                source_table        TEXT NOT NULL,
                source_row_id       INTEGER,
                op_id               INTEGER NOT NULL,
                machine_id          TEXT,
                operator_id         TEXT,
                start_time          DATETIME NOT NULL,
                end_time            DATETIME NOT NULL,
                lock_status         TEXT,
                is_changed          TEXT NOT NULL DEFAULT 'no' CHECK(is_changed IN ('yes', 'no')),
                change_summary_json TEXT,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(scenario_id) REFERENCES ScheduleAdjustmentScenario(scenario_id) ON DELETE CASCADE,
                FOREIGN KEY(op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE
            );
            CREATE INDEX idx_schedule_adjustment_scenario_base
            ON ScheduleAdjustmentScenario(base_version, base_plan_role, status);
            CREATE INDEX idx_schedule_adjustment_scenario_draft
            ON ScheduleAdjustmentScenario(source_draft_id);
            CREATE UNIQUE INDEX idx_schedule_adjustment_scenario_row_op
            ON ScheduleAdjustmentScenarioRow(scenario_id, op_id);
            CREATE INDEX idx_schedule_adjustment_scenario_row_time
            ON ScheduleAdjustmentScenarioRow(scenario_id, start_time, end_time);
            """
        )
        _seed_base(conn)
        _seed_baseline_best_selection(conn)
        seed_legacy_scenario(conn, version=16)
        before = snapshot_legacy_business_data(conn)
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 16
        assert len(before["OperationExecutionEvents"]["rows"]) == 1
        assert "execution_snapshot_revision" not in _snapshot_columns(conn)
        assert not {
            "execution_snapshot_revision", "execution_snapshot_op_ids", "execution_snapshot_op_count"
        } & _snapshot_columns(conn)
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {
            "execution_snapshot_revision",
            "execution_snapshot_op_ids",
            "execution_snapshot_op_count",
        } <= _snapshot_columns(conn)
        assert detect_schema_is_current(conn)
        assert_legacy_business_data_preserved(conn, before)
        assert _scenario_snapshot(conn, "legacy-scenario") == {
            "execution_snapshot_revision": None,
            "execution_snapshot_op_ids": None,
            "execution_snapshot_op_count": 0,
        }
    finally:
        conn.close()


