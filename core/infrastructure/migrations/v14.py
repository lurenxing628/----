from __future__ import annotations

import sqlite3

from ..migration_common import MigrationOutcome, add_column_if_missing, merge_outcomes

_PUBLISH_COLUMNS = (
    ("published_version", "published_version INTEGER"),
    ("published_by", "published_by TEXT"),
    ("published_reason", "published_reason TEXT"),
    ("published_at", "published_at DATETIME"),
)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v14 迁移：给甘特图 Scenario 增加正式采用审计字段。
    """
    return merge_outcomes(
        *(
            add_column_if_missing(
                conn,
                "ScheduleAdjustmentScenario",
                column_name,
                ddl,
                migration_label="v14",
                logger=logger,
            )
            for column_name, ddl in _PUBLISH_COLUMNS
        )
    )
