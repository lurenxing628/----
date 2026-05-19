from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Set

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"


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
            "idx_schedule_candidate_version",
            "idx_schedule_candidate_version_kind",
            "idx_schedule_candidate_rows_version_candidate",
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
    conn = get_connection(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO SchemaVersion (id, version) VALUES (1, 9);
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
        assert {"ScheduleCandidate", "ScheduleCandidateRows", "ScheduleCandidateSelection"} <= _table_names(conn)
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidate")
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidateRows")
        assert "ScheduleHistory" not in _foreign_targets(conn, "ScheduleCandidateSelection")
        assert conn.execute("SELECT name FROM LegacyRows WHERE id = 1").fetchone()["name"] == "keep-me"
    finally:
        conn.close()
