from __future__ import annotations

import sqlite3
from typing import List, Optional

from .migrations.common import MigrationOutcome, column_exists, fallback_log

CURRENT_SCHEMA_VERSION = 7


class MigrationContractError(RuntimeError):
    """迁移契约不满足：允许补缺失整表，但不允许静默吞掉复杂残缺库。"""


def build_contract_error(
    *,
    missing_tables: Optional[List[str]] = None,
    blocked_version: Optional[int] = None,
    blocked_outcome: Optional[MigrationOutcome] = None,
    bootstrap_error: Optional[Exception] = None,
) -> MigrationContractError:
    parts = ["检测到非空数据库存在不受支持的残缺结构。"]
    if missing_tables:
        parts.append(f"已识别缺失整表：{', '.join(missing_tables)}。")
    parts.append("系统只会自动补齐缺失整表；现有表结构残缺请先人工修复或恢复到完整备份后再重试。")
    if bootstrap_error is not None:
        parts.append(f"缺失整表预补齐失败：{bootstrap_error}")
    elif blocked_version is not None and blocked_outcome is not None:
        parts.append(f"迁移预检在 v{blocked_version} 返回 {blocked_outcome.value}。")
    return MigrationContractError(" ".join(parts))


def ensure_schema_version(conn: sqlite3.Connection, logger=None) -> None:
    """
    确保 SchemaVersion 表存在，并写入/修正版本号。

    兼容策略：
    - 老库可能没有 SchemaVersion：插入 version=0
    - 新库可能由 schema.sql 初始化为 version=0：若检测到结构已满足当前版本且库中仍无业务数据，则直接将版本提升到 CURRENT_SCHEMA_VERSION
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0)")

    version = get_schema_version(conn)
    if version <= 0 and detect_schema_is_current(conn) and is_truly_empty_db(conn):
        set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        if logger:
            fallback_log(
                logger, "info", f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。"
            )


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if not row:
            return 0
        return int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        # 仅在“表/列不存在”等可预期场景回落 0；其它错误必须可观测（向上抛出）
        if "no such table" in msg or "no such column" in msg:
            return 0
        raise


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (int(version),))


def is_truly_empty_db(conn: sqlite3.Connection) -> bool:
    for name in list_user_tables(conn):
        quoted_name = '"' + str(name).replace('"', '""') + '"'
        row = conn.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1").fetchone()
        if row is not None:
            return False
    return True


def list_user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name <> 'SchemaVersion'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]


def has_no_user_tables(conn: sqlite3.Connection) -> bool:
    return len(list_user_tables(conn)) == 0


def detect_schema_is_current(conn: sqlite3.Connection) -> bool:
    """
    用“结构特征”判断当前 DB 是否已经包含当前 schema.sql 的关键字段，
    用于 brand-new 空库初始化后的版本快进。
    """
    needed = [
        ("ResourceTeams", "team_id"),
        ("Operators", "team_id"),
        ("Machines", "category"),
        ("Machines", "team_id"),
        ("Batches", "ready_date"),
        ("MachineDowntimes", "scope_type"),
        ("MachineDowntimes", "scope_value"),
        ("WorkCalendar", "shift_start"),
        ("WorkCalendar", "shift_end"),
        ("OperatorCalendar", "operator_id"),
        ("OperatorMachine", "skill_level"),
        ("OperatorMachine", "is_primary"),
    ]
    for table, col in needed:
        if not column_exists(conn, table, col):
            return False
    return _has_system_management_tables(conn) and _has_schedule_unique_index(conn)


def _has_system_management_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('SystemConfig','SystemJobState')"
    ).fetchall()
    names = {r[0] if not isinstance(r, sqlite3.Row) else r["name"] for r in row}
    return "SystemConfig" in names and "SystemJobState" in names


def _has_schedule_unique_index(conn: sqlite3.Connection) -> bool:
    index_row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='index'
          AND name='idx_schedule_version_op_unique'
          AND tbl_name='Schedule'
        LIMIT 1
        """
    ).fetchone()
    return index_row is not None
