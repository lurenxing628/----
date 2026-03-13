from __future__ import annotations

import sqlite3

from .common import column_exists, fallback_log, table_exists


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str, logger=None) -> None:
    if not table_exists(conn, table):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v6：{table} 表不存在，已跳过 {column} 补列。")
        return
    if column_exists(conn, table, column):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    if logger:
        fallback_log(logger, "info", f"数据库迁移 v6：已为 {table}.{column} 补列。")


def _create_index_if_possible(conn: sqlite3.Connection, table: str, column: str, sql: str, logger=None) -> None:
    if not table_exists(conn, table):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v6：{table} 表不存在，已跳过索引创建。")
        return
    if not column_exists(conn, table, column):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v6：{table}.{column} 列不存在，已跳过索引创建。")
        return
    conn.execute(sql)


def run(conn: sqlite3.Connection, logger=None) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ResourceTeams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _add_column_if_missing(conn, "Operators", "team_id", "team_id TEXT", logger=logger)
    _add_column_if_missing(conn, "Machines", "team_id", "team_id TEXT", logger=logger)
    _create_index_if_possible(
        conn,
        "Operators",
        "team_id",
        "CREATE INDEX IF NOT EXISTS idx_operators_team_id ON Operators(team_id)",
        logger=logger,
    )
    _create_index_if_possible(
        conn,
        "Machines",
        "team_id",
        "CREATE INDEX IF NOT EXISTS idx_machines_team_id ON Machines(team_id)",
        logger=logger,
    )
