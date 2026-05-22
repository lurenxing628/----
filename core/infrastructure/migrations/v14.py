from __future__ import annotations

import sqlite3

from .common import MigrationOutcome, column_exists

_PUBLISH_COLUMNS = (
    ("published_version", "INTEGER"),
    ("published_by", "TEXT"),
    ("published_reason", "TEXT"),
    ("published_at", "DATETIME"),
)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v14 迁移：给甘特图 Scenario 增加正式采用审计字段。
    """
    for column_name, column_type in _PUBLISH_COLUMNS:
        if not column_exists(conn, "ScheduleAdjustmentScenario", column_name):
            conn.execute(f"ALTER TABLE ScheduleAdjustmentScenario ADD COLUMN {column_name} {column_type}")
    return MigrationOutcome.APPLIED
