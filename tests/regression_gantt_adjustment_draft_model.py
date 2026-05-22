from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.infrastructure.migration_state import detect_schema_is_current
from core.models.schedule_adjustment import DRAFT_STATUS_DISCARDED
from core.services.scheduler.gantt_adjustment_draft_service import GanttAdjustmentDraftService
from data.repositories import ScheduleAdjustmentRepository, ScheduleHistoryRepository

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _index_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    return {str(row["name"]) for row in rows}


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(1) AS count FROM {table}").fetchone()
    return int(row["count"])


def _max_version_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM ScheduleVersionSeq").fetchone()
    return int(row["version"])


def _seq_versions(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT version FROM ScheduleVersionSeq ORDER BY version").fetchall()
    return [int(row["version"]) for row in rows]


def _formal_schedule_rows(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """
        SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        FROM Schedule
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _formal_candidate_counts(conn: sqlite3.Connection) -> dict:
    return {
        "candidate": _count(conn, "ScheduleCandidate"),
        "candidate_rows": _count(conn, "ScheduleCandidateRows"),
        "candidate_selection": _count(conn, "ScheduleCandidateSelection"),
    }


def _seed_history_only(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ScheduleVersionSeq(version) VALUES (5);
        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (5, 'priority_first', 1, 1, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def _seed_formal_schedule(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name)
        VALUES ('M-OLD', '旧设备'), ('M-NEW', '新设备');

        INSERT INTO Operators(operator_id, name)
        VALUES ('O-OLD', '旧人员'), ('O-NEW', '新人员');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-02', 'normal', 'pending');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (5);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (70, 10, 'M-OLD', 'O-OLD', '2026-05-01 08:00', '2026-05-01 09:00', 'unlocked', 5);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (5, 'priority_first', 1, 1, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def _insert_candidate(conn: sqlite3.Connection, *, key: str, label: str, detail_saved: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO ScheduleCandidate(
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (5, ?, ?, 'baseline', 'completed', 'no', ?)
        """,
        (key, label, detail_saved),
    )
    return int(cur.lastrowid)


def test_adjustment_draft_schema_exists_in_fresh_database(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentDraft", "ScheduleAdjustmentChange"} <= _table_names(conn)
        assert {
            "idx_schedule_adjustment_draft_base",
            "idx_schedule_adjustment_draft_status",
            "idx_schedule_adjustment_change_draft_op",
        } <= _index_names(conn)
    finally:
        conn.close()


def test_schema_current_detection_requires_schedule_version_sequence(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE ScheduleVersionSeq")
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_adjustment_draft_migration_preserves_existing_v11_data(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v11.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            """
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion (id, version) VALUES (1, 11);
            DROP TABLE ScheduleAdjustmentChange;
            DROP TABLE ScheduleAdjustmentDraft;
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            """
        )
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentDraft", "ScheduleAdjustmentChange"} <= _table_names(conn)
        assert conn.execute("SELECT name FROM LegacyRows WHERE id = 1").fetchone()["name"] == "keep-me"
    finally:
        conn.close()


def test_adjustment_draft_records_changes_without_touching_formal_schedule(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_formal_schedule(conn)
        history_repo = ScheduleHistoryRepository(conn)
        service = GanttAdjustmentDraftService(conn)

        before = {
            "schedule": _count(conn, "Schedule"),
            "history": _count(conn, "ScheduleHistory"),
            "seq": _max_version_seq(conn),
            "seq_rows": _seq_versions(conn),
            "latest": history_repo.get_latest_version(),
            "versions": history_repo.list_versions(limit=10),
            "schedule_rows": _formal_schedule_rows(conn),
            "candidate_counts": _formal_candidate_counts(conn),
        }

        draft = service.create_draft(base_version=5, base_plan_role="adopted", created_by="planner")
        service.record_time_change(
            draft_id=draft.draft_id,
            schedule_id=70,
            op_id=10,
            from_start="2026-05-01 08:00",
            from_end="2026-05-01 09:00",
            to_start="2026-05-01 10:00",
            to_end="2026-05-01 11:00",
        )
        service.record_resource_change(
            draft_id=draft.draft_id,
            schedule_id=70,
            op_id=10,
            from_machine_id="M-OLD",
            to_machine_id="M-NEW",
            from_operator_id="O-OLD",
            to_operator_id="O-NEW",
        )

        repo = ScheduleAdjustmentRepository(conn)
        refreshed = repo.get_draft(draft.draft_id)
        assert refreshed is not None
        assert refreshed.base_version == 5
        assert refreshed.base_plan_role == "adopted"
        assert refreshed.change_count == 2
        assert [change.change_type for change in repo.list_changes(draft.draft_id)] == ["move_time", "change_resource"]

        after = {
            "schedule": _count(conn, "Schedule"),
            "history": _count(conn, "ScheduleHistory"),
            "seq": _max_version_seq(conn),
            "seq_rows": _seq_versions(conn),
            "latest": history_repo.get_latest_version(),
            "versions": history_repo.list_versions(limit=10),
            "schedule_rows": _formal_schedule_rows(conn),
            "candidate_counts": _formal_candidate_counts(conn),
        }
        assert after == before
        schedule_row = conn.execute("SELECT machine_id, operator_id, start_time, end_time FROM Schedule WHERE id=70").fetchone()
        assert dict(schedule_row) == {
            "machine_id": "M-OLD",
            "operator_id": "O-OLD",
            "start_time": "2026-05-01 08:00",
            "end_time": "2026-05-01 09:00",
        }
    finally:
        conn.close()


def test_discard_and_delete_draft_do_not_remove_formal_schedule(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_formal_schedule(conn)
        service = GanttAdjustmentDraftService(conn)
        repo = ScheduleAdjustmentRepository(conn)
        draft = service.create_draft(base_version=5, base_plan_role="adopted", created_by="planner")
        service.record_resource_change(draft_id=draft.draft_id, schedule_id=70, op_id=10, to_machine_id="M-NEW")
        before_versions = ScheduleHistoryRepository(conn).list_versions(limit=10)

        discarded = service.discard_draft(draft_id=draft.draft_id, reason="不采用")
        assert discarded.status == DRAFT_STATUS_DISCARDED
        assert repo.delete_draft(draft.draft_id) == 1
        assert _count(conn, "ScheduleAdjustmentChange") == 0
        assert _count(conn, "Schedule") == 1
        assert _count(conn, "ScheduleHistory") == 1
        assert _max_version_seq(conn) == 5
        assert ScheduleHistoryRepository(conn).get_latest_version() == 5
        assert ScheduleHistoryRepository(conn).list_versions(limit=10) == before_versions
        schedule_row = conn.execute("SELECT machine_id, operator_id, start_time, end_time FROM Schedule WHERE id=70").fetchone()
        assert dict(schedule_row) == {
            "machine_id": "M-OLD",
            "operator_id": "O-OLD",
            "start_time": "2026-05-01 08:00",
            "end_time": "2026-05-01 09:00",
        }
    finally:
        conn.close()


def test_discarded_or_missing_draft_rejects_new_changes(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_formal_schedule(conn)
        service = GanttAdjustmentDraftService(conn)
        draft = service.create_draft(base_version=5, base_plan_role="adopted", created_by="planner")
        service.discard_draft(draft_id=draft.draft_id, reason="不采用")

        with pytest.raises(ValidationError, match="只有编辑中的调整草稿"):
            service.record_resource_change(draft_id=draft.draft_id, op_id=10, to_machine_id="M-NEW")
        with pytest.raises(ValidationError, match="调整草稿不存在"):
            service.record_time_change(draft_id="draft-missing", op_id=10)
    finally:
        conn.close()


def test_adjustment_draft_rejects_invalid_base_role(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        service = GanttAdjustmentDraftService(conn)
        with pytest.raises(ValidationError, match="基准方案角色不正确"):
            service.create_draft(base_version=5, base_plan_role="preview", created_by="planner")
    finally:
        conn.close()


def test_adjustment_draft_rejects_blank_role_and_float_version(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_formal_schedule(conn)
        service = GanttAdjustmentDraftService(conn)
        with pytest.raises(ValidationError, match="基准方案角色不能为空"):
            service.create_draft(base_version=5, base_plan_role="", created_by="planner")
        with pytest.raises(ValidationError, match="基准版本不正确"):
            service.create_draft(base_version=5.5, base_plan_role="adopted", created_by="planner")
    finally:
        conn.close()


def test_adjustment_draft_requires_existing_base_version_and_role(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        service = GanttAdjustmentDraftService(conn)
        with pytest.raises(ValidationError, match="基准版本不存在"):
            service.create_draft(base_version=999, base_plan_role="adopted", created_by="planner")

        _seed_formal_schedule(conn)
        with pytest.raises(ValidationError, match="基准方案不存在"):
            service.create_draft(base_version=5, base_plan_role="baseline_best", created_by="planner")
    finally:
        conn.close()


def test_adjustment_draft_requires_real_base_plan_rows(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        service = GanttAdjustmentDraftService(conn)
        _seed_history_only(conn)
        with pytest.raises(ValidationError, match="基准方案明细不存在"):
            service.create_draft(base_version=5, base_plan_role="adopted", created_by="planner")
    finally:
        conn.close()


def test_adjustment_draft_requires_saved_candidate_rows(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_formal_schedule(conn)
        adopted_id = _insert_candidate(conn, key="adopted", label="最终采用", detail_saved="no")
        baseline_id = _insert_candidate(conn, key="baseline", label="原算法最好", detail_saved="no")
        conn.executemany(
            """
            INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
            VALUES (5, ?, ?, ?)
            """,
            (
                ("adopted", adopted_id, "schedule"),
                ("baseline_best", baseline_id, "candidate_rows"),
            ),
        )
        conn.commit()

        service = GanttAdjustmentDraftService(conn)
        with pytest.raises(ValidationError, match="基准方案明细不存在"):
            service.create_draft(base_version=5, base_plan_role="baseline_best", created_by="planner")

        conn.execute("UPDATE ScheduleCandidate SET detail_saved = 'yes' WHERE id = ?", (baseline_id,))
        conn.commit()
        with pytest.raises(ValidationError, match="基准方案明细不存在"):
            service.create_draft(base_version=5, base_plan_role="baseline_best", created_by="planner")
    finally:
        conn.close()
