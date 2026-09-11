"""Build pre-workbench migration fixtures from the frozen legacy bootstrap DDL."""

import sqlite3

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migrations import run_migration
from tests._support.paths import REPO_ROOT


def load_legacy_migration_schema(conn: sqlite3.Connection, version: int) -> None:
    assert version in (0, 1, 6), version
    assert not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    schema = REPO_ROOT / "tests" / "migration_db" / "fixtures" / "schema-v4.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 0
    for target_version in range(1, version + 1):
        outcome = run_migration(conn, target_version=target_version, logger=None)
        assert outcome in (MigrationOutcome.APPLIED, MigrationOutcome.PARTIAL), (target_version, outcome)
        conn.execute("UPDATE SchemaVersion SET version=? WHERE id=1", (target_version,))
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name GLOB 'wb_*'").fetchall()
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == version
    conn.commit()
