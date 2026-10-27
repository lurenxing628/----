from __future__ import annotations

import datetime
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from .database_bootstrap import (
    build_schema_exec_script as _build_schema_exec_script,
)
from .migration_common import fallback_log
from .migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
)
from .migration_state import (
    build_outdated_schema_version_error as _build_outdated_schema_version_error,
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
    create_fixed_file_exclusive,
    guard_fixed_file_open_target,
)
from .schema_declaration import load_schema_sql, resolve_schema_path
from .schema_probe import table_exists

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
    if guard_fixed_file_open_target(db_path) is not None:
        return
    fd = create_fixed_file_exclusive(db_path)
    os.close(fd)


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    is_memory_db = db_path.strip() == ":memory:"
    connect_target = db_path
    connect_kwargs = {}
    if not is_memory_db:
        _ensure_sqlite_db_target_ready(db_path)
        connect_target = _sqlite_file_uri(db_path)
        connect_kwargs["uri"] = True
    # 恢复 sqlite3 的类型探测：保持 DATE/TIMESTAMP 等隐式转换行为一致。
    # 例如：声明为 DATE 的列在查询时会自动转换为 datetime.date（而不是 str）。
    conn = sqlite3.connect(
        connect_target,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
        **connect_kwargs,
    )
    try:
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


def _ensure_no_user_tables_db_can_bootstrap(
    conn: sqlite3.Connection, initial_version: int, *, full_data: bool
) -> None:
    if not full_data and int(initial_version) == 0 and not table_exists(conn, "SchemaVersion"):
        return
    raise MigrationContractError(
        " ".join(
            [
                f"检测到数据库没有任何业务表（SchemaVersion={int(initial_version)}）。",
                "只有普通首次启动允许初始化全新空库；恢复校验不会用当前 schema.sql 静默补齐成新库。",
                "请恢复完整备份，或重建与当前程序版本匹配的数据库后再重试。",
            ]
        )
    )


def ensure_schema(
    db_path: str, logger=None, schema_path: Optional[str] = None, *, full_data: bool = False
) -> None:
    """
    确保数据库表结构存在且符合当前版本契约。

    新库按声明建表并直接提升至 CURRENT_SCHEMA_VERSION；当前版本验证结构（full_data=True 时验证完整数据合同）；
    低版本非空库直接抛 MigrationContractError 阻断启动，不执行历史增量迁移。
    """
    schema_path = resolve_schema_path(schema_path)

    conn = get_connection(db_path)
    try:
        try:
            sql = load_schema_sql(schema_path)

            initial_version = _get_schema_version(conn)
            _ensure_schema_version_not_newer(initial_version, supported_version=CURRENT_SCHEMA_VERSION)
            if initial_version == CURRENT_SCHEMA_VERSION:
                # One unchanged current-schema validation owns one transaction.
                conn.execute("BEGIN")
                _ensure_current_schema_contract(conn, schema_version=initial_version, schema_sql=sql, full_data=full_data)
                current_version = initial_version
            elif _has_no_user_tables(conn):
                _ensure_no_user_tables_db_can_bootstrap(conn, initial_version, full_data=full_data)
                conn.executescript(_build_schema_exec_script(sql))
                current_version = _ensure_schema_version(conn, logger=logger, schema_sql=sql, full_data=full_data)
                _ensure_schema_version_not_newer(current_version, supported_version=CURRENT_SCHEMA_VERSION)
            elif initial_version <= 0:
                current_version = _ensure_schema_version(conn, logger=logger, schema_sql=sql, full_data=full_data)
                _ensure_schema_version_not_newer(current_version, supported_version=CURRENT_SCHEMA_VERSION)
            else:
                current_version = initial_version

            if current_version < CURRENT_SCHEMA_VERSION:
                err = _build_outdated_schema_version_error(current_version, supported_version=CURRENT_SCHEMA_VERSION)
                fallback_log(logger, "error", str(err))
                raise err

            conn.commit()
            fallback_log(logger, "info", "数据库结构检查完成（已确保所有表存在）。")
        except Exception as init_exc:
            # 失败尽最大努力回滚，避免半初始化状态
            _rollback_failed_schema_initialization(conn, init_exc, logger=logger)
            raise
    finally:
        try:
            conn.close()
        except Exception as e:
            fallback_log(logger, "warning", f"数据库连接关闭失败：{e}")
