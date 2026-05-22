from __future__ import annotations

import sqlite3

from .common import MigrationOutcome

_ADJUSTMENT_SCENARIO_SQL = """
CREATE TABLE IF NOT EXISTS ScheduleAdjustmentScenario (
    scenario_id        TEXT PRIMARY KEY,
    source_draft_id    TEXT NOT NULL UNIQUE,
    base_version       INTEGER NOT NULL,
    base_plan_role     TEXT NOT NULL CHECK(base_plan_role IN ('adopted', 'baseline_best', 'critical_best')),
    base_source_table  TEXT NOT NULL,
    base_candidate_id  INTEGER,
    base_candidate_key TEXT,
    scenario_name      TEXT,
    status             TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'discarded', 'published', 'expired')),
    validation_status  TEXT NOT NULL CHECK(validation_status IN ('valid', 'warning')),
    issue_count        INTEGER NOT NULL DEFAULT 0,
    issues_json        TEXT,
    row_count          INTEGER NOT NULL DEFAULT 0,
    created_by         TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ScheduleAdjustmentScenarioRow (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id         TEXT NOT NULL,
    source_table        TEXT NOT NULL,
    source_row_id       INTEGER,
    op_id               INTEGER NOT NULL,
    machine_id          TEXT,
    operator_id         TEXT,
    start_time          DATETIME NOT NULL,
    end_time            DATETIME NOT NULL,
    lock_status         TEXT,
    is_changed          TEXT NOT NULL DEFAULT 'no' CHECK(is_changed IN ('yes', 'no')),
    change_summary_json TEXT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scenario_id) REFERENCES ScheduleAdjustmentScenario(scenario_id) ON DELETE CASCADE,
    FOREIGN KEY(op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_base
ON ScheduleAdjustmentScenario(base_version, base_plan_role, status);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_draft
ON ScheduleAdjustmentScenario(source_draft_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_row_op
ON ScheduleAdjustmentScenarioRow(scenario_id, op_id);

CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_row_time
ON ScheduleAdjustmentScenarioRow(scenario_id, start_time, end_time);
"""


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v13 迁移：新增甘特图 Scenario 模拟方案表。
    """
    conn.executescript(_ADJUSTMENT_SCENARIO_SQL)
    return MigrationOutcome.APPLIED
