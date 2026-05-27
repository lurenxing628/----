from __future__ import annotations

import sqlite3

from .common import MigrationOutcome

_EVENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS OperationExecutionEvents (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_version         INTEGER NOT NULL,
    schedule_id              INTEGER NOT NULL,
    op_id                    INTEGER NOT NULL,
    batch_id                 TEXT NOT NULL,
    source_table             TEXT NOT NULL DEFAULT 'schedule' CHECK(source_table = 'schedule'),
    effective_plan_role      TEXT NOT NULL DEFAULT 'adopted' CHECK(effective_plan_role = 'adopted'),
    scenario_id              TEXT CHECK(scenario_id IS NULL),
    event_type               TEXT NOT NULL CHECK(event_type IN ('start', 'pause', 'resume', 'finish', 'exception')),
    reported_status          TEXT NOT NULL CHECK(reported_status IN ('processing', 'paused', 'exception', 'completed')),
    event_time               DATETIME NOT NULL,
    actual_machine_id        TEXT,
    actual_operator_id       TEXT,
    quantity_done            INTEGER CHECK(quantity_done IS NULL OR quantity_done >= 0),
    quantity_scrapped        INTEGER CHECK(quantity_scrapped IS NULL OR quantity_scrapped >= 0),
    reason_code              TEXT CHECK(reason_code IS NULL OR reason_code IN ('equipment', 'person', 'material', 'quality', 'process', 'external', 'other')),
    reason_detail            TEXT,
    severity                 TEXT CHECK(severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')),
    impact_minutes           INTEGER CHECK(impact_minutes IS NULL OR impact_minutes >= 0),
    affected_machine_id      TEXT,
    affected_operator_id     TEXT,
    handling_status          TEXT CHECK(handling_status IS NULL OR handling_status IN ('new', 'checking', 'waiting', 'handled')),
    suggest_reschedule       TEXT CHECK(suggest_reschedule IS NULL OR suggest_reschedule IN ('yes', 'no')),
    remark                   TEXT,
    created_by               TEXT NOT NULL,
    idempotency_key          TEXT NOT NULL UNIQUE,
    request_fingerprint      TEXT NOT NULL,
    previous_state_revision  TEXT NOT NULL,
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES Schedule(id) ON DELETE CASCADE,
    FOREIGN KEY (op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE,
    FOREIGN KEY (actual_machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (actual_operator_id) REFERENCES Operators(operator_id),
    FOREIGN KEY (affected_machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (affected_operator_id) REFERENCES Operators(operator_id),
    UNIQUE(op_id, previous_state_revision),
    CHECK(schedule_version > 0),
    CHECK(schedule_id > 0),
    CHECK(op_id > 0),
    CHECK(TRIM(batch_id) <> ''),
    CHECK(TRIM(created_by) <> ''),
    CHECK(TRIM(idempotency_key) <> ''),
    CHECK(TRIM(request_fingerprint) <> ''),
    CHECK(TRIM(previous_state_revision) <> '')
)
"""

_EVENT_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_op ON OperationExecutionEvents(op_id, event_time)",
    "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule ON OperationExecutionEvents(schedule_id)",
    "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule_op ON OperationExecutionEvents(schedule_id, op_id)",
    "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_batch ON OperationExecutionEvents(batch_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_execution_events_op_revision_unique ON OperationExecutionEvents(op_id, previous_state_revision)",
    "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_latest_exception ON OperationExecutionEvents(op_id, event_type, id)",
)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v15 迁移：新增现场执行事件表。
    """
    conn.execute(_EVENT_TABLE_SQL)
    for sql in _EVENT_INDEX_SQL:
        conn.execute(sql)
    return MigrationOutcome.APPLIED
