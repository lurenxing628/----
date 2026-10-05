from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

from .database_bootstrap import (
    build_schema_exec_script as _build_schema_exec_script,
)
from .database_bootstrap import (
    load_schema_sql as _load_schema_sql,
)
from .migration_common import fallback_log
from .migration_runner import migrate_with_backup as _migrate_with_backup_impl
from .migration_runner import preflight_migration_contract as _preflight_migration_contract_impl
from .migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
)
from .migration_state import (
    ensure_current_schema_contract as _ensure_current_schema_contract,
)
from .migration_state import (
    ensure_schema_version as _ensure_schema_version,
)
from .migration_state import (
    ensure_schema_version_not_newer as _ensure_schema_version_not_newer,
)
from .migration_state import (
    get_schema_version as _get_schema_version,
)
from .migration_state import (
    has_no_user_tables as _has_no_user_tables,
)
from .safe_files import (
    UnsafeFixedFileError,
    create_fixed_file_exclusive,
    guard_fixed_file_open_target,
    stat_regular_file,
)
from .schema_declaration import resolve_schema_path as _resolve_schema_path_impl

_LOGGER = logging.getLogger(__name__)


def _convert_stored_date(value: bytes):
    """DATE 列沿用 sqlite3 默认写法转成日期；转不了的原样返回文本。

    默认转换器遇到 `2026/10/01`、`2026-02-30` 这类旧值会在取数时直接抛 ValueError，
    读取端写好的"日期无效"提示就到不了用户面前，只剩一个 500。
    """
    text = value.decode("utf-8")
    try:
        return datetime.date(*map(int, value.split(b"-")))
    except (TypeError, ValueError):
        return text


sqlite3.register_converter("DATE", _convert_stored_date)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MigrationContractError",
    "get_connection",
    "ensure_schema",
]


def _sqlite_file_uri(db_path: str) -> str:
    return f"{Path(os.path.abspath(db_path)).as_uri()}?mode=rw"


def _ensure_sqlite_db_target_ready(db_path: str) -> None:
    guard_fixed_file_open_target(db_path, ensure_parent=True)
    try:
        stat_regular_file(db_path)
        return
    except FileNotFoundError:
        pass
    fd = create_fixed_file_exclusive(db_path, ensure_parent=True)
    try:
        stat_regular_file(db_path)
    finally:
        os.close(fd)


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    is_memory_db = str(db_path or "").strip() == ":memory:"
    # 防御：db_path 可能仅是文件名（dirname 为空串时 makedirs 会报错）
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    connect_target = db_path
    connect_kwargs = {}
    if not is_memory_db:
        _ensure_sqlite_db_target_ready(db_path)
        connect_target = _sqlite_file_uri(db_path)
        connect_kwargs["uri"] = True
    # 恢复 sqlite3 的类型探测：保持 DATE/TIMESTAMP 等隐式转换行为一致。
    # 例如：声明为 DATE 的列在查询时会自动转换为 datetime.date（而不是 str）。
    try:
        conn = sqlite3.connect(
            connect_target,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
            **connect_kwargs,
        )
    except sqlite3.OperationalError as exc:
        if not is_memory_db:
            try:
                stat_regular_file(db_path)
            except UnsafeFixedFileError as guard_exc:
                raise guard_exc from exc
        raise
    try:
        if not is_memory_db:
            stat_regular_file(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except Exception:
        conn.close()
        raise


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


def _has_schema_version_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='SchemaVersion' LIMIT 1"
    ).fetchone()
    return row is not None


def _ensure_no_user_tables_db_can_bootstrap(conn: sqlite3.Connection, initial_version: int) -> None:
    if int(initial_version) == 0 and not _has_schema_version_table(conn):
        return
    raise MigrationContractError(
        " ".join(
            [
                f"检测到数据库只有 SchemaVersion={int(initial_version)}，但没有任何业务表。",
                "这不是连 SchemaVersion 都不存在的全新空库，系统不会用当前 schema.sql 静默补齐成新库。",
                "请恢复完整备份，或先用能正确迁移该数据库的程序版本修复结构后再重试。",
            ]
        )
    )


def _resolve_schema_path(schema_path: Optional[str]) -> str:
    # 纯路径解析（无 DB / 无 logger / 无副作用）：源码根 → frozen exe 同目录 → cwd 兜底；实现归 schema_declaration。
    return _resolve_schema_path_impl(schema_path)


def ensure_schema(
    db_path: str, logger=None, schema_path: Optional[str] = None, backup_dir: Optional[str] = None
) -> None:
    """
    确保数据库表结构存在。

    说明：使用 IF NOT EXISTS 方式建表，因此可重复执行。
    """
    schema_path = _resolve_schema_path(schema_path)

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
            initial_version = _get_schema_version(conn)
            _ensure_schema_version_not_newer(initial_version, supported_version=CURRENT_SCHEMA_VERSION)
            if initial_version == CURRENT_SCHEMA_VERSION:
                # One unchanged current-schema validation owns one transaction.
                conn.execute("BEGIN")
                _ensure_current_schema_contract(conn, schema_version=initial_version, schema_sql=sql)
            elif _has_no_user_tables(conn):
                _ensure_no_user_tables_db_can_bootstrap(conn, initial_version)
                conn.executescript(script)

            # 确保 SchemaVersion 表存在，并获取当前版本
            if initial_version == CURRENT_SCHEMA_VERSION:
                current_version = initial_version
            else:
                _ensure_schema_version(conn, logger=logger, schema_sql=sql)
                current_version = _get_schema_version(conn)
                _ensure_schema_version_not_newer(current_version, supported_version=CURRENT_SCHEMA_VERSION)
                _ensure_current_schema_contract(conn, schema_version=current_version, schema_sql=sql)
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
