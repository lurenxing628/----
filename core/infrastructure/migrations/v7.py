from __future__ import annotations

import sqlite3

from .common import MigrationOutcome, fallback_log, table_exists


def _duplicate_schedule_rows(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT version, op_id, COUNT(1) AS cnt
        FROM Schedule
        GROUP BY version, op_id
        HAVING COUNT(1) > 1
        ORDER BY version, op_id
        LIMIT 10
        """
    ).fetchall()


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    if not table_exists(conn, "Schedule"):
        if logger:
            fallback_log(logger, "warning", "数据库迁移 v7：Schedule 表不存在，已跳过唯一索引创建。")
        return MigrationOutcome.SKIPPED

    duplicates = _duplicate_schedule_rows(conn)
    if duplicates:
        samples = []
        for row in duplicates:
            version = row["version"] if isinstance(row, sqlite3.Row) else row[0]
            op_id = row["op_id"] if isinstance(row, sqlite3.Row) else row[1]
            cnt = row["cnt"] if isinstance(row, sqlite3.Row) else row[2]
            samples.append(f"version={version},op_id={op_id},count={cnt}")
        raise RuntimeError("Schedule 表存在同一版本同一工序的重复排程，请先人工清理后再迁移：" + "; ".join(samples))

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_version_op_unique ON Schedule(version, op_id)")
    return MigrationOutcome.APPLIED
