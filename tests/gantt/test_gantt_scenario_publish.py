"""回归测试：GanttAdjustmentPublishService.publish_scenario 正式采用调整方案——v13 迁移补齐 published_* 列且按列缺失判定 schema 不达标，发布生成新正式版本并写审计日志/路由用服务端 operator(web)，且拒绝对比方案、操作日志失败回滚、缺确认语/原因、重复采用、陈旧依据版本与发布前需重校验等场景，失败时不留任何正式写入。"""

from __future__ import annotations

from pathlib import Path
from typing import Set

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v13 import _ADJUSTMENT_SCENARIO_SQL
from tests._support.paths import REPO_ROOT
from tests.gantt.gantt_legacy_schema_support import (
    assert_legacy_business_data_preserved,
    seed_legacy_scenario,
    snapshot_legacy_business_data,
    strip_later_schema,
)

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 5
PUBLISH_COLUMNS = {
    "published_version": "INTEGER",
    "published_by": "TEXT",
    "published_reason": "TEXT",
    "published_at": "DATETIME",
}


def _connect(tmp_path: Path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_columns(conn, table: str) -> Set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _recreate_scenario_without_column(conn, missing_column: str) -> None:
    conn.executescript(
        """
        DROP TABLE ScheduleAdjustmentScenarioRow;
        DROP TABLE ScheduleAdjustmentScenario;
        """
    )
    conn.executescript(_ADJUSTMENT_SCENARIO_SQL)
    for column_name, column_type in PUBLISH_COLUMNS.items():
        if column_name != missing_column:
            conn.execute(f"ALTER TABLE ScheduleAdjustmentScenario ADD COLUMN {column_name} {column_type}")
    conn.commit()


def _seed_base(conn) -> None:
    conn.executescript(
        f"""
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '设备一', 'active'), ('M2', '设备二', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '人员一', 'active'), ('O2', '人员二', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一'), ('P002', '零件二');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES
          ('B1', 'P001', '零件一', 1, '2026-05-20', 'normal', 'yes', 'scheduled'),
          ('B2', 'P002', '零件二', 1, '2026-05-20', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES
          (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled'),
          (20, 'OP20', 'B1', 'piece-a', 20, '钻孔', 'internal', 'scheduled'),
          (30, 'OP30', 'B2', 'piece-b', 10, '铣削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES ({VERSION});

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
          (70, 10, 'M1', 'O1', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION}),
          (80, 20, 'M1', 'O1', '2026-05-04 10:00:00', '2026-05-04 11:00:00', 'unlocked', {VERSION}),
          (90, 30, 'M2', 'O2', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION});

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES ({VERSION}, 'priority_first', 2, 3, 'success', '{{}}', 'pytest');
        """
    )
    conn.commit()


def _seed_baseline_best_selection(conn) -> None:
    conn.execute(
        """
        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES (?, 'adopted', '正式采用', 'baseline', 'completed', 'no', 'no')
        """,
        (VERSION,),
    )
    adopted_candidate_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES (?, 'baseline_best', '原算法代表方案', 'baseline', 'completed', 'no', 'yes')
        """,
        (VERSION,),
    )
    baseline_candidate_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (?, 'adopted', ?, 'schedule')
        """,
        (VERSION, adopted_candidate_id),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (?, 'baseline_best', ?, 'candidate_rows')
        """,
        (VERSION, baseline_candidate_id),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status)
        SELECT version, ?, op_id, machine_id, operator_id, start_time, end_time, lock_status
          FROM Schedule
         WHERE version = ?
        """,
        (baseline_candidate_id, VERSION),
    )
    conn.commit()


def test_publish_schema_columns_exist_and_v13_migrates(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {"published_version", "published_by", "published_reason", "published_at"} <= _table_columns(
            conn, "ScheduleAdjustmentScenario"
        )
        assert detect_schema_is_current(conn)
    finally:
        conn.close()

    db_path = tmp_path / "legacy_v13.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        strip_later_schema(conn, version=13)
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion(id, version) VALUES (1, 13);
            DROP TABLE ScheduleAdjustmentScenarioRow;
            DROP TABLE ScheduleAdjustmentScenario;
            """
        )
        conn.executescript(_ADJUSTMENT_SCENARIO_SQL)
        _seed_base(conn)
        _seed_baseline_best_selection(conn)
        seed_legacy_scenario(conn, version=13)
        before = snapshot_legacy_business_data(conn)
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 13
        assert not detect_schema_is_current(conn)
        assert "published_version" not in _table_columns(conn, "ScheduleAdjustmentScenario")
        assert not set(PUBLISH_COLUMNS) & _table_columns(conn, "ScheduleAdjustmentScenario")
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        assert int(conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()["version"]) == CURRENT_SCHEMA_VERSION
        assert {"published_version", "published_by", "published_reason", "published_at"} <= _table_columns(
            conn, "ScheduleAdjustmentScenario"
        )
        assert detect_schema_is_current(conn)
        assert_legacy_business_data_preserved(conn, before)
        assert tuple(conn.execute(
            "SELECT published_version, published_by, published_reason, published_at "
            "FROM ScheduleAdjustmentScenario WHERE scenario_id = 'legacy-scenario'"
        ).fetchone()) == (None, None, None, None)
    finally:
        conn.close()


def test_schema_detection_requires_every_publish_column(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        for column_name in PUBLISH_COLUMNS:
            _recreate_scenario_without_column(conn, column_name)
            assert not detect_schema_is_current(conn), column_name
    finally:
        conn.close()


