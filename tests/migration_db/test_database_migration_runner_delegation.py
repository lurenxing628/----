"""单元测试：数据库 bootstrap/迁移委托链的失败传播——补表 commit 失败必须上抛、database 包装层不得重复 commit、初始化失败且回滚失败抛“数据库状态不可信”、migrate_with_backup 在迁移失败后还原失败/备份缺失/还原成功各分支保留正确的原始错误。"""

from __future__ import annotations

import os
import sqlite3
from typing import List

import pytest


def test_ensure_schema_refuses_symlink_db_path_without_touching_target(tmp_path):
    from core.infrastructure.database import ensure_schema
    from core.infrastructure.safe_files import UnsafeFixedFileError
    from tests._support.paths import REPO_ROOT

    db_path = tmp_path / "app.db"
    outside_target = tmp_path / "outside.db"
    try:
        os.symlink(outside_target, db_path)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建软链接")

    with pytest.raises(UnsafeFixedFileError):
        ensure_schema(str(db_path), schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)

    assert db_path.is_symlink()
    assert not outside_target.exists()


def test_ensure_schema_refuses_hardlinked_db_path_without_touching_target(tmp_path):
    from core.infrastructure.database import ensure_schema
    from core.infrastructure.safe_files import UnsafeFixedFileError
    from tests._support.paths import REPO_ROOT

    db_path = tmp_path / "app.db"
    outside_target = tmp_path / "outside.db"
    outside_target.write_text("OUTSIDE-UNCHANGED", encoding="utf-8")
    try:
        os.link(outside_target, db_path)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建硬链接")

    with pytest.raises(UnsafeFixedFileError):
        ensure_schema(str(db_path), schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)

    assert db_path.exists()
    assert outside_target.read_text(encoding="utf-8") == "OUTSIDE-UNCHANGED"


def test_get_connection_race_to_dangling_symlink_does_not_create_outside_target(tmp_path, monkeypatch):
    from core.infrastructure import database as database_mod
    from core.infrastructure.safe_files import UnsafeFixedFileError

    db_path = tmp_path / "app.db"
    outside_target = tmp_path / "outside.db"
    try:
        probe = tmp_path / "probe"
        os.symlink(outside_target, probe)
        probe.unlink()
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建软链接")

    original_connect = sqlite3.connect
    swapped = {"done": False}

    def replace_db_with_symlink_before_sqlite_connect(database, *args, **kwargs):
        if not swapped["done"] and str(database).startswith("file:"):
            swapped["done"] = True
            if db_path.exists() or db_path.is_symlink():
                db_path.unlink()
            os.symlink(outside_target, db_path)
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(database_mod.sqlite3, "connect", replace_db_with_symlink_before_sqlite_connect)

    with pytest.raises(UnsafeFixedFileError):
        database_mod.get_connection(str(db_path))

    assert swapped["done"] is True
    assert db_path.is_symlink()
    assert not outside_target.exists()


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


def test_migrate_with_backup_raises_when_restore_fails(monkeypatch, tmp_path):
    from core.infrastructure import backup as backup_mod
    from core.infrastructure import migration_runner as runner_mod

    db_path = tmp_path / "app.db"
    db_path.write_text("db", encoding="utf-8")
    backup_path = tmp_path / "before.db"
    backup_path.write_text("backup", encoding="utf-8")

    class _Window:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _BackupManager:
        def __init__(self, *args, **kwargs):
            return None

        def backup(self, suffix):
            return str(backup_path)

    monkeypatch.setattr(backup_mod, "maintenance_window", lambda *args, **kwargs: _Window())
    monkeypatch.setattr(backup_mod, "BackupManager", _BackupManager)
    monkeypatch.setattr(runner_mod, "_apply_migrations", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("migration fail")))
    monkeypatch.setattr(
        runner_mod,
        "restore_db_file_from_backup",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("restore fail")),
    )

    with pytest.raises(runner_mod.MigrationRollbackError, match="数据库迁移失败，且备份恢复失败；数据库状态不可信") as exc_info:
        runner_mod.migrate_with_backup(
            str(db_path),
            from_version=1,
            to_version=2,
            backup_dir=str(tmp_path / "backups"),
            connection_factory=lambda path: sqlite3.connect(path),
        )

    assert isinstance(exc_info.value.__cause__, runner_mod.MigrationRollbackError)


def test_migrate_with_backup_raises_when_backup_missing_after_migration_failure(monkeypatch, tmp_path):
    from core.infrastructure import backup as backup_mod
    from core.infrastructure import migration_runner as runner_mod

    db_path = tmp_path / "app.db"
    db_path.write_text("db", encoding="utf-8")
    missing_backup = tmp_path / "missing_before.db"

    class _Window:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _BackupManager:
        def __init__(self, *args, **kwargs):
            return None

        def backup(self, suffix):
            return str(missing_backup)

    monkeypatch.setattr(backup_mod, "maintenance_window", lambda *args, **kwargs: _Window())
    monkeypatch.setattr(backup_mod, "BackupManager", _BackupManager)
    monkeypatch.setattr(runner_mod, "_apply_migrations", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("migration fail")))

    with pytest.raises(runner_mod.MigrationRollbackError, match="数据库迁移失败，且备份恢复失败；数据库状态不可信"):
        runner_mod.migrate_with_backup(
            str(db_path),
            from_version=1,
            to_version=2,
            backup_dir=str(tmp_path / "backups"),
            connection_factory=lambda path: sqlite3.connect(path),
        )


def test_migrate_with_backup_preserves_migration_error_when_restore_succeeds(monkeypatch, tmp_path):
    from core.infrastructure import backup as backup_mod
    from core.infrastructure import migration_runner as runner_mod

    db_path = tmp_path / "app.db"
    db_path.write_text("db", encoding="utf-8")
    backup_path = tmp_path / "before.db"
    backup_path.write_text("backup", encoding="utf-8")
    restored = []

    class _Window:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _BackupManager:
        def __init__(self, *args, **kwargs):
            return None

        def backup(self, suffix):
            return str(backup_path)

    monkeypatch.setattr(backup_mod, "maintenance_window", lambda *args, **kwargs: _Window())
    monkeypatch.setattr(backup_mod, "BackupManager", _BackupManager)
    monkeypatch.setattr(runner_mod, "_apply_migrations", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("migration fail")))
    monkeypatch.setattr(runner_mod, "restore_db_file_from_backup", lambda *args, **kwargs: restored.append(args))

    with pytest.raises(RuntimeError, match="migration fail"):
        runner_mod.migrate_with_backup(
            str(db_path),
            from_version=1,
            to_version=2,
            backup_dir=str(tmp_path / "backups"),
            connection_factory=lambda path: sqlite3.connect(path),
        )

    assert restored


def test_restore_db_file_refuses_broken_symlink_rollback_tmp(tmp_path):
    from core.infrastructure.migration_backup import restore_db_file_from_backup
    from core.infrastructure.safe_files import UnsafeFixedFileError

    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "before.db"
    rollback_tmp = tmp_path / "app.db.rollback_tmp"
    outside_target = tmp_path / "outside.db"
    db_path.write_text("current-db", encoding="utf-8")
    backup_path.write_text("backup-db", encoding="utf-8")
    try:
        os.symlink(outside_target, rollback_tmp)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建软链接")

    with pytest.raises(UnsafeFixedFileError):
        restore_db_file_from_backup(str(backup_path), str(db_path), retries=1)

    assert db_path.read_text(encoding="utf-8") == "current-db"
    assert not outside_target.exists()
    assert rollback_tmp.is_symlink()


def test_restore_db_file_refuses_symlink_sqlite_sidecar_before_replace(tmp_path):
    from core.infrastructure.migration_backup import restore_db_file_from_backup
    from core.infrastructure.safe_files import UnsafeFixedFileError

    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "before.db"
    sidecar_path = tmp_path / "app.db-wal"
    outside_target = tmp_path / "outside.wal"
    db_path.write_text("current-db", encoding="utf-8")
    backup_path.write_text("backup-db", encoding="utf-8")
    outside_target.write_text("outside", encoding="utf-8")
    try:
        os.symlink(outside_target, sidecar_path)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建软链接")

    with pytest.raises(UnsafeFixedFileError):
        restore_db_file_from_backup(str(backup_path), str(db_path), retries=1)

    assert db_path.read_text(encoding="utf-8") == "current-db"
    assert outside_target.read_text(encoding="utf-8") == "outside"
    assert sidecar_path.is_symlink()


def test_restore_db_file_refuses_hardlinked_sqlite_sidecar_before_replace(tmp_path):
    from core.infrastructure.migration_backup import restore_db_file_from_backup
    from core.infrastructure.safe_files import UnsafeFixedFileError

    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "before.db"
    sidecar_path = tmp_path / "app.db-shm"
    outside_target = tmp_path / "outside.shm"
    db_path.write_text("current-db", encoding="utf-8")
    backup_path.write_text("backup-db", encoding="utf-8")
    outside_target.write_text("sidecar", encoding="utf-8")
    try:
        os.link(outside_target, sidecar_path)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建硬链接")

    with pytest.raises(UnsafeFixedFileError):
        restore_db_file_from_backup(str(backup_path), str(db_path), retries=1)

    assert db_path.read_text(encoding="utf-8") == "current-db"
    assert outside_target.exists()
    assert sidecar_path.exists()
