"""Shared migration outcomes and SQLite helpers owned by the infrastructure parent layer."""

from __future__ import annotations

import re
import sqlite3
from enum import Enum

from core.infrastructure.logging import safe_log

from .schema_probe import table_columns, table_exists


class MigrationOutcome(str, Enum):
    APPLIED = "applied"
    SKIPPED = "skipped"
    PARTIAL = "partial"


def merge_outcomes(*outcomes: MigrationOutcome) -> MigrationOutcome:
    filtered = [o for o in outcomes if o is not None]
    if not filtered:
        return MigrationOutcome.SKIPPED
    first = filtered[0]
    if all(o == first for o in filtered[1:]):
        return first
    return MigrationOutcome.PARTIAL


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    判断指定表是否存在指定列。
    """
    t = _normalize_sqlite_identifier(table, kind="表名")
    col = _normalize_sqlite_identifier(column, kind="列名")
    return col in table_columns(conn, t)


def _normalize_sqlite_identifier(value: str, *, kind: str) -> str:
    text = value.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        raise ValueError(f"非法 SQLite {kind}：{value!r}")
    return text


def add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    ddl: str,
    *,
    migration_label: str,
    logger=None,
    log_added: bool = False,
) -> MigrationOutcome:
    if not table_exists(conn, table):
        fallback_log(logger, "warning", f"数据库迁移 {migration_label}：{table} 表不存在，已跳过 {column} 补列。")
        return MigrationOutcome.SKIPPED
    if column_exists(conn, table, column):
        return MigrationOutcome.APPLIED
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    if log_added:
        fallback_log(logger, "info", f"数据库迁移 {migration_label}：已为 {table}.{column} 补列。")
    return MigrationOutcome.APPLIED


def fallback_log(logger, level: str, message: str) -> None:
    if not logger:
        return
    safe_log(logger, level, str(message))


__all__ = [
    "MigrationOutcome",
    "add_column_if_missing",
    "column_exists",
    "fallback_log",
    "merge_outcomes",
]
