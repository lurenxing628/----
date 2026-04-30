from __future__ import annotations

import os
import sqlite3
import tempfile
from typing import Callable, Optional

from .database_bootstrap import bootstrap_missing_tables_from_schema, cleanup_probe_db, missing_schema_tables
from .migration_backup import release_sqlite_connection_reference, restore_db_file_from_backup
from .migration_state import (
    MigrationContractError,
    build_contract_error,
    ensure_schema_version,
    get_schema_version,
    set_schema_version,
)
from .migrations.common import MigrationOutcome, fallback_log

ConnectionFactory = Callable[[str], sqlite3.Connection]


def preflight_migration_contract(
    db_path: str,
    *,
    to_version: int,
    schema_sql: str,
    connection_factory: ConnectionFactory,
) -> None:
    fd, probe_path = tempfile.mkstemp(prefix="aps_migration_probe_", suffix=".db")
    os.close(fd)
    try:
        _copy_database_to_probe(db_path, probe_path, connection_factory=connection_factory)
        _run_preflight_on_probe(
            probe_path,
            to_version=to_version,
            schema_sql=schema_sql,
            connection_factory=connection_factory,
        )
    finally:
        cleanup_probe_db(probe_path)


def migrate_with_backup(
    db_path: str,
    from_version: int,
    to_version: int,
    backup_dir: Optional[str] = None,
    *,
    schema_sql: Optional[str] = None,
    logger=None,
    connection_factory: ConnectionFactory,
) -> None:
    """
    迁移入口（带强制备份）。

    安全约束：只要进入迁移流程，就必须在迁移前获得一个可用备份；否则直接阻断迁移。
    """
    effective_backup_dir = _resolve_backup_dir(db_path, backup_dir, logger=logger)
    _ensure_backup_dir(effective_backup_dir, logger=logger)

    from core.infrastructure.backup import BackupManager, maintenance_window

    with maintenance_window(db_path, logger=logger, action="migrate"):
        backup_path = _create_migration_backup(
            BackupManager,
            db_path,
            effective_backup_dir,
            from_version=from_version,
            to_version=to_version,
            logger=logger,
        )
        try:
            _apply_migrations(
                db_path,
                to_version=to_version,
                schema_sql=schema_sql,
                logger=logger,
                connection_factory=connection_factory,
            )
        except Exception:
            _rollback_from_backup(db_path, backup_path, logger=logger)
            raise


def _copy_database_to_probe(db_path: str, probe_path: str, *, connection_factory: ConnectionFactory) -> None:
    src = None
    probe = None
    try:
        src = connection_factory(db_path)
        probe = connection_factory(probe_path)
        src.backup(probe)
    finally:
        _close_connection(probe)
        _close_connection(src)


def _run_preflight_on_probe(
    probe_path: str,
    *,
    to_version: int,
    schema_sql: str,
    connection_factory: ConnectionFactory,
) -> None:
    conn = None
    try:
        conn = connection_factory(probe_path)
        missing_tables = _prepare_probe_schema(conn, schema_sql)
        ensure_schema_version(conn, logger=None)
        current = get_schema_version(conn)
        if current >= to_version:
            return
        with conn:
            for version in range(current + 1, to_version + 1):
                outcome = run_migration(conn, target_version=version, logger=None)
                if outcome != MigrationOutcome.APPLIED:
                    raise build_contract_error(
                        missing_tables=missing_tables,
                        blocked_version=version,
                        blocked_outcome=outcome,
                    )
                set_schema_version(conn, version)
    finally:
        _close_connection(conn)


def _prepare_probe_schema(conn: sqlite3.Connection, schema_sql: str):
    missing_tables = missing_schema_tables(conn, schema_sql)
    if missing_tables:
        try:
            bootstrap_missing_tables_from_schema(conn, schema_sql, logger=None)
        except Exception as exc:
            raise build_contract_error(missing_tables=missing_tables, bootstrap_error=exc) from exc
    return missing_tables


def _resolve_backup_dir(db_path: str, backup_dir: Optional[str], *, logger=None) -> str:
    effective_backup_dir = ""
    if backup_dir:
        try:
            effective_backup_dir = str(os.fspath(backup_dir)).strip()  # type: ignore[arg-type]
        except Exception:
            effective_backup_dir = str(backup_dir).strip()
    if effective_backup_dir:
        return effective_backup_dir
    default_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    if logger:
        fallback_log(logger, "warning", f"未提供 backup_dir，迁移将使用默认备份目录：{default_dir}")
    return default_dir


def _ensure_backup_dir(effective_backup_dir: str, *, logger=None) -> None:
    try:
        os.makedirs(effective_backup_dir, exist_ok=True)
    except Exception as exc:
        if logger:
            fallback_log(logger, "error", f"数据库迁移前无法创建备份目录，已阻断迁移：{exc}（dir={effective_backup_dir}）")
        raise


def _create_migration_backup(
    backup_manager_cls,
    db_path: str,
    effective_backup_dir: str,
    *,
    from_version: int,
    to_version: int,
    logger=None,
) -> str:
    try:
        manager = backup_manager_cls(db_path=db_path, backup_dir=effective_backup_dir, keep_days=365, logger=logger)
        return manager.backup(suffix=f"before_migrate_v{from_version}_to_v{to_version}")
    except Exception as exc:
        if logger:
            fallback_log(logger, "error", f"数据库迁移前备份失败，已阻断迁移：{exc}（dir={effective_backup_dir}）")
        raise


def _apply_migrations(
    db_path: str,
    *,
    to_version: int,
    schema_sql: Optional[str],
    logger=None,
    connection_factory: ConnectionFactory,
) -> None:
    conn = None
    try:
        conn = connection_factory(db_path)
        if schema_sql:
            bootstrap_missing_tables_from_schema(conn, schema_sql, logger=logger)
        with conn:
            ensure_schema_version(conn, logger=logger)
            current = get_schema_version(conn)
            if current >= to_version:
                return
            _apply_version_range(conn, current=current, to_version=to_version, logger=logger)
        if logger:
            fallback_log(logger, "info", f"数据库迁移完成：SchemaVersion {current} -> {to_version}")
    finally:
        _close_connection(conn, logger=logger)


def _apply_version_range(conn: sqlite3.Connection, *, current: int, to_version: int, logger=None) -> None:
    applied_upto = current
    for version in range(current + 1, to_version + 1):
        outcome = run_migration(conn, target_version=version, logger=logger)
        if outcome == MigrationOutcome.APPLIED:
            set_schema_version(conn, version)
            applied_upto = version
            continue
        _log_incomplete_migration(version, applied_upto=applied_upto, outcome=outcome, logger=logger)
        raise build_contract_error(blocked_version=version, blocked_outcome=outcome)


def _log_incomplete_migration(
    version: int,
    *,
    applied_upto: int,
    outcome: MigrationOutcome,
    logger=None,
) -> None:
    level = "warning" if outcome == MigrationOutcome.SKIPPED else "error"
    if logger:
        fallback_log(
            logger,
            level,
            f"数据库迁移 v{version} 未完整完成（outcome={outcome.value}），SchemaVersion 保持在 {applied_upto}。",
        )


def _rollback_from_backup(db_path: str, backup_path: str, *, logger=None) -> None:
    if not backup_path or not os.path.exists(backup_path):
        return
    try:
        restore_db_file_from_backup(backup_path, db_path, logger=logger)
        if logger:
            fallback_log(logger, "error", f"数据库迁移失败，已从备份回滚：{backup_path}")
    except Exception as exc:
        if logger:
            fallback_log(logger, "error", f"数据库迁移失败且回滚失败：{exc}（backup={backup_path}）")


def _close_connection(conn, logger=None) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception as exc:
        if logger:
            fallback_log(logger, "warning", f"数据库连接关闭失败（可能导致文件锁未释放）：{exc}")
    finally:
        release_sqlite_connection_reference(conn)


def run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> MigrationOutcome:
    # 迁移实现按版本拆到 core/infrastructure/migrations/*
    from .migrations import run_migration as _run_migration

    return _run_migration(conn, target_version=int(target_version), logger=logger)
