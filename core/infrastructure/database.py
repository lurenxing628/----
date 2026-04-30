from __future__ import annotations

import logging
import os
import sqlite3
import sys
from typing import List, Optional

from .database_bootstrap import (
    bootstrap_missing_tables_from_schema as _bootstrap_missing_tables_from_schema_impl,
)
from .database_bootstrap import (
    build_schema_exec_script as _build_schema_exec_script,
)
from .database_bootstrap import (
    load_schema_sql as _load_schema_sql,
)
from .migration_runner import migrate_with_backup as _migrate_with_backup_impl
from .migration_runner import preflight_migration_contract as _preflight_migration_contract_impl
from .migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
)
from .migration_state import (
    detect_schema_is_current as _detect_schema_is_current,
)
from .migration_state import (
    ensure_schema_version as _ensure_schema_version,
)
from .migration_state import (
    get_schema_version as _get_schema_version,
)
from .migration_state import (
    has_no_user_tables as _has_no_user_tables,
)
from .migration_state import (
    is_truly_empty_db as _is_truly_empty_db,
)
from .migration_state import (
    list_user_tables as _list_user_tables,
)
from .migrations.common import fallback_log

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MigrationContractError",
    "get_connection",
    "ensure_schema",
]


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    # 防御：db_path 可能仅是文件名（dirname 为空串时 makedirs 会报错）
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    # 恢复 sqlite3 的类型探测：保持 DATE/TIMESTAMP 等隐式转换行为一致。
    # 例如：声明为 DATE 的列在查询时会自动转换为 datetime.date（而不是 str）。
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _bootstrap_missing_tables_from_schema(conn: sqlite3.Connection, schema_sql: str, logger=None) -> List[str]:
    return _bootstrap_missing_tables_from_schema_impl(conn, schema_sql, logger=logger)


def _rollback_failed_schema_initialization(conn: sqlite3.Connection, init_exc: Exception, logger=None) -> None:
    try:
        conn.rollback()
    except Exception as rollback_exc:
        fallback_log(
            logger or _LOGGER,
            "error",
            f"数据库结构初始化失败后的回滚也失败，数据库状态不可信：init={init_exc}; rollback={rollback_exc}",
        )
        raise RuntimeError("数据库结构初始化失败，且回滚失败；数据库状态不可信") from rollback_exc


def ensure_schema(
    db_path: str, logger=None, schema_path: Optional[str] = None, backup_dir: Optional[str] = None
) -> None:
    """
    确保数据库表结构存在。

    说明：使用 IF NOT EXISTS 方式建表，因此可重复执行。
    """
    if not schema_path:
        # 默认优先：仓库根目录（源码运行）
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql"),
        ]
        # PyInstaller onedir：schema.sql 与 exe 同目录（在 app.py 中也会显式传入，这里再做兜底）
        try:
            if getattr(sys, "frozen", False):
                candidates.append(os.path.join(os.path.dirname(sys.executable), "schema.sql"))
        except Exception:
            pass
        # 最后兜底：当前工作目录
        candidates.append(os.path.join(os.getcwd(), "schema.sql"))

        for p in candidates:
            ap = os.path.abspath(p)
            if os.path.exists(ap):
                schema_path = ap
                break

    if not schema_path:
        raise FileNotFoundError("找不到数据库结构文件：schema.sql（请确认工作目录或打包参数包含该文件）")

    schema_path = os.path.abspath(schema_path)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"找不到数据库结构文件：{schema_path}")

    conn = get_connection(db_path)
    # 防御：确保即使未来 try 内出现局部异常吞掉，也不会在迁移判断处引用未定义变量
    current_version: int = 0
    try:
        try:
            sql = _load_schema_sql(schema_path)
            script = _build_schema_exec_script(sql)

            # 仅在库中不存在任何业务表时才执行 schema.sql 建表。
            # 旧 schema 的空表库不能走这里，否则 CREATE TABLE IF NOT EXISTS
            # 不会修正既有表结构，后续索引/新列依赖会直接失败。
            if _has_no_user_tables(conn):
                conn.executescript(script)

            # 确保 SchemaVersion 表存在，并获取当前版本
            _ensure_schema_version(conn, logger=logger)
            current_version = _get_schema_version(conn)
            conn.commit()
            if logger:
                fallback_log(logger, "info", "数据库结构检查完成（已确保所有表存在）。")
        except Exception as init_exc:
            # 失败尽最大努力回滚，避免半初始化状态
            _rollback_failed_schema_initialization(conn, init_exc, logger=logger)
            raise
    finally:
        try:
            conn.close()
        except Exception as e:
            if logger:
                fallback_log(logger, "warning", f"数据库连接关闭失败：{e}")

    # 需要迁移（ALTER TABLE / 数据清洗等）：迁移前先备份，失败可回滚
    if current_version < CURRENT_SCHEMA_VERSION:
        try:
            _preflight_migration_contract(
                db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=sql,
            )
        except MigrationContractError as e:
            if logger:
                fallback_log(logger, "error", str(e))
            raise
        _migrate_with_backup(
            db_path,
            from_version=current_version,
            to_version=CURRENT_SCHEMA_VERSION,
            backup_dir=backup_dir,
            schema_sql=sql,
            logger=logger,
        )


def _preflight_migration_contract(
    db_path: str,
    *,
    to_version: int,
    schema_sql: str,
) -> None:
    _preflight_migration_contract_impl(
        db_path,
        to_version=to_version,
        schema_sql=schema_sql,
        connection_factory=get_connection,
    )


def _migrate_with_backup(
    db_path: str,
    from_version: int,
    to_version: int,
    backup_dir: Optional[str] = None,
    *,
    schema_sql: Optional[str] = None,
    logger=None,
) -> None:
    """
    迁移入口（带强制备份）。

    安全约束：只要进入迁移流程，就必须在迁移前获得一个可用备份；否则直接阻断迁移。
    原因：SQLite 的 DDL/DML 在异常时可能导致“半迁移”，没有备份将无法回滚到一致状态。
    """
    _migrate_with_backup_impl(
        db_path,
        from_version=from_version,
        to_version=to_version,
        backup_dir=backup_dir,
        schema_sql=schema_sql,
        logger=logger,
        connection_factory=get_connection,
    )
