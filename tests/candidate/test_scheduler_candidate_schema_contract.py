"""回归测试：ScheduleCandidate/Rows/Selection 三张候选方案表及其索引随 schema 建库/迁移到位，约束生效（同版本 candidate_key 唯一、status 与 selection.role/source_table 取值受 CHECK 限制、删除候选级联清空 Rows 与 Selection），且候选表外键不指向 ScheduleHistory、与正式历史保持独立。"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
# Verbatim schema.sql from 196d7e56ecc2f7cfc2ea6b2140227b73cb2e1fed (runtime schema version 9).
# Original Git blob: 524c344e14533fb26b96254435c873552429732f.
SCHEMA_V9_PATH = REPO_ROOT / "tests" / "migration_db" / "fixtures" / "schema-v9.sql"
SCHEMA_V9_SHA256 = "f2451893212a29118dc1378770dbac18b33d3f5b10a44b8d87d9bf8aeef255a4"


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _index_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
        """
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _foreign_targets(conn: sqlite3.Connection, table: str) -> Set[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    return {str(row["table"]) for row in rows}


def _insert_candidate(conn: sqlite3.Connection, *, version: int, key: str, status: str = "completed") -> int:
    cur = conn.execute(
        """
        INSERT INTO ScheduleCandidate (
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (?, ?, ?, 'baseline', ?, 'no', 'no')
        """,
        (int(version), key, key, status),
    )
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


def test_candidate_schema_exists_in_fresh_database_with_expected_constraints(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION

        assert {"ScheduleCandidate", "ScheduleCandidateRows", "ScheduleCandidateSelection"} <= _table_names(conn)
        assert {
            "idx_schedule_version_time",
            "idx_schedule_history_version",
            "idx_schedule_candidate_version",
            "idx_schedule_candidate_version_kind",
            "idx_schedule_candidate_rows_version_candidate",
            "idx_schedule_candidate_rows_version_candidate_time",
            "idx_schedule_candidate_rows_time",
            "idx_schedule_candidate_selection_version",
        } <= _index_names(conn)

        candidate_id = _insert_candidate(conn, version=1, key="baseline")
        conn.execute(
            """
            INSERT INTO ScheduleCandidateRows (
                version, candidate_id, op_id, machine_id, operator_id, start_time, end_time
            )
            VALUES (1, ?, 10, 'M1', 'O1', '2026-05-01 08:00', '2026-05-01 09:00')
            """,
            (candidate_id,),
        )
        conn.execute(
            """
            INSERT INTO ScheduleCandidateSelection (version, role, candidate_id, source_table)
            VALUES (1, 'baseline_best', ?, 'candidate_rows')
            """,
            (candidate_id,),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            _insert_candidate(conn, version=1, key="baseline")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_candidate(conn, version=1, key="bad-status", status="adopted")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO ScheduleCandidateSelection (version, role, candidate_id, source_table)
                VALUES (1, 'preview', ?, 'candidate_rows')
                """,
                (candidate_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO ScheduleCandidateSelection (version, role, candidate_id, source_table)
                VALUES (1, 'critical_best', ?, 'schedule_candidate_rows')
                """,
                (candidate_id,),
            )

        conn.execute("DELETE FROM ScheduleCandidate WHERE id = ?", (candidate_id,))
        assert conn.execute("SELECT COUNT(*) AS count FROM ScheduleCandidateRows").fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) AS count FROM ScheduleCandidateSelection").fetchone()["count"] == 0
    finally:
        conn.close()


def test_candidate_schema_migration_keeps_candidate_tables_independent_from_schedule_history(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v9.db"
    legacy_schema = SCHEMA_V9_PATH.read_bytes()
    assert hashlib.sha256(legacy_schema).hexdigest() == SCHEMA_V9_SHA256
    conn = get_connection(str(db_path))
    try:
        conn.executescript(
            legacy_schema.decode("utf-8")
            + """
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            DELETE FROM SchemaVersion;
            INSERT INTO SchemaVersion (id, version) VALUES (1, 9);
            """
        )
        conn.commit()
        assert [row[0] for row in conn.execute("SELECT version FROM SchemaVersion WHERE id=1")] == [9]
        before_tables = _table_names(conn)
        assert not any(name.startswith(("Workbench", "ScheduleCandidate")) for name in before_tables)
        assert not conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'wb_%'").fetchall()
        legacy_rows = [tuple(row) for row in conn.execute("SELECT * FROM LegacyRows ORDER BY id")]
        assert legacy_rows == [(1, "keep-me")]
    finally:
        conn.close()

    backup_dir = tmp_path / "legacy_backups"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(backup_dir))

    conn = get_connection(str(db_path))
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleCandidate", "ScheduleCandidateRows", "ScheduleCandidateSelection"} <= _table_names(conn)
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidate")
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidateRows")
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidateSelection")
        assert conn.execute("SELECT name FROM LegacyRows WHERE id = 1").fetchone()["name"] == "keep-me"
        assert [tuple(row) for row in conn.execute("SELECT * FROM LegacyRows ORDER BY id")] == legacy_rows
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()

    backup_path, = backup_dir.glob(f"aps_backup_*_before_migrate_v9_to_v{CURRENT_SCHEMA_VERSION}.db")
    backup_bytes = backup_path.read_bytes()
    with closing(sqlite3.connect(backup_path.resolve().as_uri() + "?mode=ro", uri=True)) as backup_conn:
        backup_conn.row_factory = sqlite3.Row
        assert [row[0] for row in backup_conn.execute("PRAGMA integrity_check")] == ["ok"]
        assert [row[0] for row in backup_conn.execute("SELECT version FROM SchemaVersion WHERE id=1")] == [9]
        assert _table_names(backup_conn) == before_tables
        assert [tuple(row) for row in backup_conn.execute("SELECT * FROM LegacyRows ORDER BY id")] == legacy_rows
    assert backup_path.read_bytes() == backup_bytes
