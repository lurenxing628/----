from __future__ import annotations

import sqlite3

from .common import MigrationOutcome, add_column_if_missing

_SCENARIO_SNAPSHOT_COLUMNS = (
    ("execution_snapshot_revision", "execution_snapshot_revision TEXT"),
    ("execution_snapshot_op_ids", "execution_snapshot_op_ids TEXT"),
    ("execution_snapshot_op_count", "execution_snapshot_op_count INTEGER NOT NULL DEFAULT 0"),
)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v17 迁移：给甘特图 Scenario 增加现场执行快照字段。
    """
    for column_name, ddl in _SCENARIO_SNAPSHOT_COLUMNS:
        add_column_if_missing(
            conn,
            "ScheduleAdjustmentScenario",
            column_name,
            ddl,
            migration_label="v17",
            logger=logger,
        )
    return MigrationOutcome.APPLIED
