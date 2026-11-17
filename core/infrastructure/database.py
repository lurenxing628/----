from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from core.infrastructure.sqlite_udf import DETECT_TYPES, configure_connection

from .database_bootstrap import build_schema_exec_script
from .migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    ensure_current_schema_contract,
    ensure_schema_version_not_newer,
    ensure_schema_version_not_older,
    get_schema_version,
    has_no_user_tables,
)
from .safe_files import (
    create_fixed_file_exclusive,
    guard_fixed_file_open_target,
)
from .schema_declaration import load_schema_sql, resolve_schema_path
from .schema_probe import table_exists

__all__ = [
    "get_connection",
    "ensure_schema",
    "ensure_schema_on_connection",
]


def _sqlite_file_uri(db_path: str) -> str:
    return f"{Path(os.path.abspath(db_path)).as_uri()}?mode=rw"


def _ensure_sqlite_db_target_ready(db_path: str) -> None:
    if guard_fixed_file_open_target(db_path) is not None:
        return
    fd = create_fixed_file_exclusive(db_path)
    os.close(fd)


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取产品读写连接（每请求一个连接，避免跨线程问题）；文件库只按固定文件目标以读写方式打开。
    """
    is_memory_db = db_path.strip() == ":memory:"
    connect_target = db_path
    if not is_memory_db:
        _ensure_sqlite_db_target_ready(db_path)
        connect_target = _sqlite_file_uri(db_path)
    conn = sqlite3.connect(connect_target, detect_types=DETECT_TYPES, check_same_thread=False, uri=not is_memory_db)
    try:
        configure_connection(conn)
        return conn
    except Exception:
        conn.close()
        raise


def _rollback_failed_schema_initialization(
    conn: sqlite3.Connection, init_exc: Exception, logger: logging.Logger
) -> None:
    try:
        conn.rollback()
    except Exception as rollback_exc:
        logger.error(f"数据库结构初始化失败后的回滚也失败，数据库状态不可信：init={init_exc}; rollback={rollback_exc}")
        raise RuntimeError("数据库结构初始化失败，且回滚失败；数据库状态不可信") from rollback_exc


def _ensure_no_user_tables_db_can_bootstrap(
    conn: sqlite3.Connection, initial_version: int, *, full_data: bool
) -> None:
    if not full_data and initial_version == 0 and not table_exists(conn, "SchemaVersion"):
        return
    raise MigrationContractError(
        " ".join(
            [
                f"检测到数据库没有任何业务表（SchemaVersion={initial_version}）。",
                "只有普通首次启动允许初始化全新空库；恢复校验不会用当前 schema.sql 静默补齐成新库。",
                "请恢复完整备份，或重建与当前程序版本匹配的数据库后再重试。",
            ]
        )
    )


def ensure_schema_on_connection(
    conn: sqlite3.Connection, logger: logging.Logger, schema_path: Optional[str] = None, *, full_data: bool = False
) -> None:
    """在已打开的连接上确保数据库表结构存在且符合当前版本契约。"""
    try:
        initial_version = get_schema_version(conn)
        ensure_schema_version_not_newer(initial_version)
        if initial_version == CURRENT_SCHEMA_VERSION:
            # One unchanged current-schema validation owns one transaction.
            conn.execute("BEGIN")
            ensure_current_schema_contract(conn, schema_version=initial_version, full_data=full_data)
            current_version = initial_version
        elif has_no_user_tables(conn):
            _ensure_no_user_tables_db_can_bootstrap(conn, initial_version, full_data=full_data)
            conn.executescript(build_schema_exec_script(load_schema_sql(schema_path)))
            current_version = get_schema_version(conn)
            ensure_schema_version_not_newer(current_version)
        else:
            current_version = initial_version
        ensure_schema_version_not_older(current_version)

        conn.commit()
        logger.info("数据库结构检查完成（已确保所有表存在）。")
    except Exception as init_exc:
        # 失败尽最大努力回滚，避免半初始化状态
        _rollback_failed_schema_initialization(conn, init_exc, logger)
        raise


def ensure_schema(
    db_path: str, logger: logging.Logger, schema_path: Optional[str] = None, *, full_data: bool = False
) -> None:
    """
    确保数据库表结构存在且符合当前版本契约。

    新库按声明建表并直接提升至 CURRENT_SCHEMA_VERSION；当前版本验证结构（full_data=True 时验证完整数据合同）；
    低版本非空库直接抛 MigrationContractError 阻断启动，不执行历史增量迁移。
    """
    schema_path = resolve_schema_path(schema_path)

    conn = get_connection(db_path)
    try:
        ensure_schema_on_connection(
            conn,
            logger,
            schema_path=schema_path,
            full_data=full_data,
        )
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"数据库连接关闭失败：{e}")
