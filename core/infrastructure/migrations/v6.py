from __future__ import annotations

import sqlite3

from .common import MigrationOutcome, add_column_if_missing, column_exists, fallback_log, merge_outcomes, table_exists


def _create_index_if_possible(conn: sqlite3.Connection, table: str, column: str, sql: str, logger=None) -> MigrationOutcome:
    if not table_exists(conn, table):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v6：{table} 表不存在，已跳过索引创建。")
        return MigrationOutcome.SKIPPED
    if not column_exists(conn, table, column):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v6：{table}.{column} 列不存在，已跳过索引创建。")
        return MigrationOutcome.SKIPPED
    conn.execute(sql)
    return MigrationOutcome.APPLIED


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
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
    return merge_outcomes(
        MigrationOutcome.APPLIED,
        add_column_if_missing(
            conn,
            "Operators",
            "team_id",
            "team_id TEXT",
            migration_label="v6",
            logger=logger,
            log_added=True,
        ),
        add_column_if_missing(
            conn,
            "Machines",
            "team_id",
            "team_id TEXT",
            migration_label="v6",
            logger=logger,
            log_added=True,
        ),
        _create_index_if_possible(
            conn,
            "Operators",
            "team_id",
            "CREATE INDEX IF NOT EXISTS idx_operators_team_id ON Operators(team_id)",
            logger=logger,
        ),
        _create_index_if_possible(
            conn,
            "Machines",
            "team_id",
            "CREATE INDEX IF NOT EXISTS idx_machines_team_id ON Machines(team_id)",
            logger=logger,
        ),
    )
