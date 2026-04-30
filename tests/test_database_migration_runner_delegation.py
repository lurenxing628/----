from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Tuple


def test_ensure_schema_delegates_migration_to_runner(monkeypatch, tmp_path):
    from core.infrastructure import database as database_mod

    db_path = tmp_path / "legacy.db"
    backup_dir = tmp_path / "backups"
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE LegacyTable (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO LegacyTable (id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()

    calls: List[Tuple[str, int, int]] = []

    def _fake_preflight(db_path_arg, *, to_version, schema_sql, connection_factory):
        calls.append(("preflight", 0, int(to_version)))
        assert db_path_arg == str(db_path)
        assert "CREATE TABLE" in schema_sql
        assert connection_factory is database_mod.get_connection

    def _fake_migrate(
        db_path_arg,
        from_version,
        to_version,
        backup_dir=None,
        *,
        schema_sql=None,
        logger=None,
        connection_factory,
    ):
        calls.append(("migrate", int(from_version), int(to_version)))
        assert db_path_arg == str(db_path)
        assert backup_dir == str(backup_dir_arg)
        assert schema_sql is not None and "CREATE TABLE" in schema_sql
        assert logger is None
        assert connection_factory is database_mod.get_connection

    backup_dir_arg = backup_dir
    monkeypatch.setattr(database_mod, "_preflight_migration_contract_impl", _fake_preflight)
    monkeypatch.setattr(database_mod, "_migrate_with_backup_impl", _fake_migrate)

    database_mod.ensure_schema(
        str(db_path),
        logger=None,
        schema_path=str(schema_path),
        backup_dir=str(backup_dir_arg),
    )

    assert calls == [
        ("preflight", 0, database_mod.CURRENT_SCHEMA_VERSION),
        ("migrate", 0, database_mod.CURRENT_SCHEMA_VERSION),
    ]
