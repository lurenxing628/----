from __future__ import annotations

import sqlite3

from .common import MigrationOutcome

_ADJUSTMENT_DRAFT_SQL = """
CREATE TABLE IF NOT EXISTS ScheduleAdjustmentDraft (
    draft_id        TEXT PRIMARY KEY,
    base_version    INTEGER NOT NULL,
    base_plan_role  TEXT NOT NULL CHECK(base_plan_role IN ('adopted', 'baseline_best', 'critical_best')),
    status          TEXT NOT NULL DEFAULT 'editing' CHECK(status IN ('editing', 'validated', 'saved_scenario', 'discarded', 'published', 'expired')),
    created_by      TEXT,
    reason          TEXT,
    change_count    INTEGER NOT NULL DEFAULT 0,
    audit_summary   TEXT,
    expires_at      DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ScheduleAdjustmentChange (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id           TEXT NOT NULL,
    schedule_id        INTEGER,
    op_id              INTEGER NOT NULL,
    change_type        TEXT NOT NULL CHECK(change_type IN ('move_time', 'resize_time', 'change_resource')),
    from_start         DATETIME,
    from_end           DATETIME,
    to_start           DATETIME,
    to_end             DATETIME,
    from_machine_id    TEXT,
    to_machine_id      TEXT,
    from_operator_id   TEXT,
    to_operator_id     TEXT,
    validation_status  TEXT NOT NULL DEFAULT 'pending' CHECK(validation_status IN ('pending', 'valid', 'warning', 'blocked')),
    validation_message TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(draft_id) REFERENCES ScheduleAdjustmentDraft(draft_id) ON DELETE CASCADE,
    FOREIGN KEY(op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_draft_base
ON ScheduleAdjustmentDraft(base_version, base_plan_role);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_draft_status
ON ScheduleAdjustmentDraft(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_change_draft_op
ON ScheduleAdjustmentChange(draft_id, op_id);
"""


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v12 迁移：新增甘特图模拟调整 Draft 草稿表。
    """
    conn.executescript(_ADJUSTMENT_DRAFT_SQL)
    return MigrationOutcome.APPLIED
