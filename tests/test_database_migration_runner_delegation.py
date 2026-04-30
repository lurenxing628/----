from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Tuple

import pytest


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


def test_ensure_schema_uses_database_wrappers(monkeypatch, tmp_path):
    from core.infrastructure import database as database_mod

    db_path = tmp_path / "legacy_wrapper.db"
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

    def _fake_preflight(db_path_arg, *, to_version, schema_sql):
        calls.append(("preflight_wrapper", 0, int(to_version)))
        assert db_path_arg == str(db_path)
        assert "CREATE TABLE" in schema_sql

    def _fake_migrate(
        db_path_arg,
        from_version,
        to_version,
        backup_dir=None,
        *,
        schema_sql=None,
        logger=None,
    ):
        calls.append(("migrate_wrapper", int(from_version), int(to_version)))
        assert db_path_arg == str(db_path)
        assert backup_dir == str(backup_dir_arg)
        assert schema_sql is not None and "CREATE TABLE" in schema_sql
        assert logger is None

    backup_dir_arg = backup_dir
    monkeypatch.setattr(database_mod, "_preflight_migration_contract", _fake_preflight)
    monkeypatch.setattr(database_mod, "_migrate_with_backup", _fake_migrate)

    database_mod.ensure_schema(
        str(db_path),
        logger=None,
        schema_path=str(schema_path),
        backup_dir=str(backup_dir_arg),
    )

    assert calls == [
        ("preflight_wrapper", 0, database_mod.CURRENT_SCHEMA_VERSION),
        ("migrate_wrapper", 0, database_mod.CURRENT_SCHEMA_VERSION),
    ]


def test_bootstrap_missing_tables_commit_failure_raises(monkeypatch):
    from core.infrastructure import database_bootstrap as bootstrap_mod

    class CommitFailConn:
        def __init__(self) -> None:
            self.scripts: List[str] = []

        def executescript(self, script):
            self.scripts.append(str(script))

        def commit(self):
            raise sqlite3.OperationalError("commit failed")

    conn = CommitFailConn()
    schema_sql = "CREATE TABLE IF NOT EXISTS Foo (id INTEGER PRIMARY KEY);"
    monkeypatch.setattr(bootstrap_mod, "missing_schema_tables", lambda conn_arg, schema_arg: ["Foo"])

    with pytest.raises(sqlite3.OperationalError, match="commit failed"):
        bootstrap_mod.bootstrap_missing_tables_from_schema(conn, schema_sql, logger=None)

    assert conn.scripts


def test_database_bootstrap_wrapper_does_not_commit_twice(monkeypatch):
    from core.infrastructure import database as database_mod

    class CommitBombConn:
        def commit(self):
            raise AssertionError("wrapper must not commit")

    monkeypatch.setattr(
        database_mod,
        "_bootstrap_missing_tables_from_schema_impl",
        lambda conn, schema_sql, logger=None: ["Foo"],
    )

    assert database_mod._bootstrap_missing_tables_from_schema(CommitBombConn(), "CREATE TABLE Foo(id);") == ["Foo"]


def test_ensure_schema_initialization_rollback_failure_raises(monkeypatch, tmp_path):
    from core.infrastructure import database as database_mod

    class RollbackFailConn:
        def rollback(self):
            raise sqlite3.OperationalError("rollback failed")

        def close(self):
            return None

    schema_path = tmp_path / "schema.sql"
    schema_path.write_text("CREATE TABLE Foo (id INTEGER PRIMARY KEY);", encoding="utf-8")

    monkeypatch.setattr(database_mod, "get_connection", lambda _db_path: RollbackFailConn())

    def _load_schema_fail(_schema_path):
        raise RuntimeError("schema load failed")

    monkeypatch.setattr(database_mod, "_load_schema_sql", _load_schema_fail)

    with pytest.raises(RuntimeError, match="数据库结构初始化失败，且回滚失败；数据库状态不可信") as exc_info:
        database_mod.ensure_schema(str(tmp_path / "app.db"), schema_path=str(schema_path))

    assert "rollback failed" in str(exc_info.value.__cause__)
