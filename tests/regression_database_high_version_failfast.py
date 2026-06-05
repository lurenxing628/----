from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from typing import List, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _version_of(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if row is None:
            raise AssertionError("缺少 SchemaVersion.id=1")
        return int(row[0])
    finally:
        conn.close()


def _before_migrate_backups(backup_dir: str) -> List[str]:
    if not os.path.isdir(backup_dir):
        return []
    return [
        name
        for name in os.listdir(backup_dir)
        if name.startswith("aps_backup_") and "before_migrate" in name and name.endswith(".db")
    ]


def _make_future_db(repo_root: str, db_path: str, backup_dir: str) -> int:
    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema

    schema_path = os.path.join(repo_root, "schema.sql")
    ensure_schema(db_path, logger=None, schema_path=schema_path, backup_dir=backup_dir)
    future_version = CURRENT_SCHEMA_VERSION + 1
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE SchemaVersion SET version=? WHERE id=1", (future_version,))
        conn.execute("CREATE TABLE IF NOT EXISTS FutureOnly (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO FutureOnly (note) VALUES (?)", ("future schema marker",))
        conn.commit()
    finally:
        conn.close()
    return future_version


def _make_sparse_versioned_db(db_path: str, version: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE SchemaVersion (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)")
        conn.execute("INSERT INTO SchemaVersion (id, version) VALUES (1, ?)", (version,))
        conn.commit()
    finally:
        conn.close()


def _assert_future_version_error(exc: Exception, *, future_version: int, supported_version: int) -> None:
    msg = str(exc)
    assert f"SchemaVersion={future_version} 高于当前程序支持版本 {supported_version}" in msg, msg
    assert "不支持数据库降级迁移" in msg, msg
    assert "请升级程序或恢复兼容版本备份" in msg, msg


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure import backup as backup_mod
    from core.infrastructure import migration_runner
    from core.infrastructure.database import (
        CURRENT_SCHEMA_VERSION,
        MigrationContractError,
        ensure_schema,
        get_connection,
    )
    from core.infrastructure.migration_runner import migrate_with_backup, preflight_migration_contract

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_database_high_version_")
    db_path = os.path.join(tmpdir, "future.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    schema_path = os.path.join(repo_root, "schema.sql")
    schema_sql = open(schema_path, "r", encoding="utf-8").read()
    future_version = _make_future_db(repo_root, db_path, backup_dir)

    try:
        ensure_schema(db_path, logger=None, schema_path=schema_path, backup_dir=backup_dir)
    except MigrationContractError as exc:
        _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
    else:
        raise AssertionError("高版本数据库应在 ensure_schema 阶段 fail-fast")

    assert _version_of(db_path) == future_version
    assert _before_migrate_backups(backup_dir) == []

    original_apply_version_range = migration_runner._apply_version_range

    def blocked_after_version_check(*args, **kwargs):
        raise AssertionError("高版本 fail-fast 后不应继续执行迁移")

    migration_runner._apply_version_range = blocked_after_version_check
    try:
        try:
            preflight_migration_contract(
                db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=schema_sql,
                connection_factory=get_connection,
            )
        except MigrationContractError as exc:
            _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
        else:
            raise AssertionError("高版本数据库应在迁移预检阶段 fail-fast")

        try:
            migration_runner._apply_migrations(
                db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=schema_sql,
                logger=None,
                connection_factory=get_connection,
            )
        except MigrationContractError as exc:
            _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
        else:
            raise AssertionError("高版本数据库应在 _apply_migrations 二次保护阶段 fail-fast")
    finally:
        migration_runner._apply_version_range = original_apply_version_range

    assert _version_of(db_path) == future_version
    assert _before_migrate_backups(backup_dir) == []

    sparse_db_path = os.path.join(tmpdir, "sparse_future.db")
    _make_sparse_versioned_db(sparse_db_path, future_version)
    sparse_calls: List[str] = []

    def record_sparse_block(name: str):
        def _blocked(*args, **kwargs):
            sparse_calls.append(name)
            raise AssertionError(f"稀疏高版本数据库应先 fail-fast，不应调用 {name}")

        return _blocked

    migration_runner._apply_version_range = record_sparse_block("_apply_version_range")
    try:
        try:
            preflight_migration_contract(
                sparse_db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=schema_sql,
                connection_factory=get_connection,
            )
        except MigrationContractError as exc:
            _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
        else:
            raise AssertionError("缺业务表的高版本数据库也应在迁移预检阶段 fail-fast")

        try:
            migration_runner._apply_migrations(
                sparse_db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=schema_sql,
                logger=None,
                connection_factory=get_connection,
            )
        except MigrationContractError as exc:
            _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
        else:
            raise AssertionError("缺业务表的高版本数据库也应在 _apply_migrations 二次保护阶段 fail-fast")
    finally:
        migration_runner._apply_version_range = original_apply_version_range

    assert sparse_calls == [], sparse_calls

    sparse_low_version = max(1, CURRENT_SCHEMA_VERSION - 1)
    for sparse_version in (0, sparse_low_version):
        sparse_low_db_path = os.path.join(tmpdir, f"sparse_low_{sparse_version}.db")
        sparse_low_backup_dir = os.path.join(tmpdir, f"sparse_low_{sparse_version}_backups")
        os.makedirs(sparse_low_backup_dir, exist_ok=True)
        _make_sparse_versioned_db(sparse_low_db_path, sparse_version)

        try:
            ensure_schema(
                sparse_low_db_path,
                logger=None,
                schema_path=schema_path,
                backup_dir=sparse_low_backup_dir,
            )
        except MigrationContractError as exc:
            msg = str(exc)
            assert f"只有 SchemaVersion={sparse_version}" in msg, msg
            assert "不会用当前 schema.sql 静默补齐成新库" in msg, msg
        else:
            raise AssertionError("只有 SchemaVersion 的空壳库不能被当成新库初始化")

        conn_sparse_low = sqlite3.connect(sparse_low_db_path)
        try:
            tables = [
                row[0]
                for row in conn_sparse_low.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
        finally:
            conn_sparse_low.close()
        assert tables == ["SchemaVersion"], tables
        assert _before_migrate_backups(sparse_low_backup_dir) == []

    backup_calls: List[Tuple] = []
    original_backup_manager = backup_mod.BackupManager

    class BombBackupManager:
        def __init__(self, *args, **kwargs):
            backup_calls.append(("init", args, kwargs))

        def backup(self, suffix):
            backup_calls.append(("backup", suffix))
            raise AssertionError("高版本 fail-fast 前不应创建迁移备份")

    backup_mod.BackupManager = BombBackupManager
    try:
        try:
            migrate_with_backup(
                db_path,
                from_version=future_version,
                to_version=CURRENT_SCHEMA_VERSION,
                backup_dir=backup_dir,
                schema_sql=schema_sql,
                logger=None,
                connection_factory=get_connection,
            )
        except MigrationContractError as exc:
            _assert_future_version_error(exc, future_version=future_version, supported_version=CURRENT_SCHEMA_VERSION)
        else:
            raise AssertionError("高版本数据库应在 migrate_with_backup 入口 fail-fast")
    finally:
        backup_mod.BackupManager = original_backup_manager

    assert backup_calls == [], backup_calls
    assert _version_of(db_path) == future_version
    assert _before_migrate_backups(backup_dir) == []
    print("OK")


if __name__ == "__main__":
    main()
