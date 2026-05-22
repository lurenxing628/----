from __future__ import annotations

import sqlite3

from .common import MigrationOutcome

_PERFORMANCE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_schedule_version_time
ON Schedule(version, start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_version_candidate_time
ON ScheduleCandidateRows(version, candidate_id, start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_schedule_history_version
ON ScheduleHistory(version);
"""


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v11 迁移：补排产方案查询索引，避免代表方案查询和候选孤儿清理随着明细增多明显变慢。
    """
    conn.executescript(_PERFORMANCE_INDEXES_SQL)
    return MigrationOutcome.APPLIED
