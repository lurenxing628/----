"""Current event DDL and the frozen v39 representation used by the v40 upgrade."""

_LEGACY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS OperationExecutionEvents (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_version         INTEGER NOT NULL,
    schedule_id              INTEGER NOT NULL,
    op_id                    INTEGER NOT NULL,
    batch_id                 TEXT NOT NULL,
    source_table             TEXT NOT NULL CHECK(source_table = 'schedule'),
    effective_plan_role      TEXT NOT NULL CHECK(effective_plan_role = 'adopted'),
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
    suggest_reschedule       INTEGER NOT NULL DEFAULT 0 CHECK(suggest_reschedule IN (0, 1)),
    remark                   TEXT,
    created_by               TEXT NOT NULL,
    idempotency_key          TEXT NOT NULL UNIQUE,
    request_fingerprint      TEXT NOT NULL,
    previous_state_revision  TEXT NOT NULL,
    created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id, schedule_version, op_id) REFERENCES Schedule(id, version, op_id),
    FOREIGN KEY (op_id, batch_id) REFERENCES BatchOperations(id, batch_id),
    FOREIGN KEY (actual_machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (actual_operator_id) REFERENCES Operators(operator_id),
    FOREIGN KEY (affected_machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (affected_operator_id) REFERENCES Operators(operator_id),
    UNIQUE(schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role, previous_state_revision),
    CHECK(schedule_version > 0),
    CHECK(schedule_id > 0),
    CHECK(op_id > 0),
    CHECK(TRIM(batch_id) <> ''),
    CHECK(TRIM(event_time) <> '' AND datetime(event_time) IS NOT NULL),
    CHECK((event_type IN ('start', 'resume') AND reported_status = 'processing') OR (event_type = 'pause' AND reported_status = 'paused') OR (event_type = 'exception' AND reported_status = 'exception') OR (event_type = 'finish' AND reported_status = 'completed')),
    CHECK(event_type NOT IN ('pause', 'exception') OR (reason_code IS NOT NULL AND TRIM(reason_code) <> '')),
    CHECK(event_type <> 'exception' OR (severity IS NOT NULL AND TRIM(severity) <> '')),
    CHECK(TRIM(created_by) <> ''),
    CHECK(TRIM(idempotency_key) <> ''),
    CHECK(TRIM(request_fingerprint) <> ''),
    CHECK(TRIM(previous_state_revision) <> '')
)
"""

_INDEXES = {
    "idx_operation_execution_events_op": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_op ON OperationExecutionEvents(op_id, event_time)",
    "idx_operation_execution_events_schedule": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule ON OperationExecutionEvents(schedule_id)",
    "idx_operation_execution_events_schedule_op": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule_op ON OperationExecutionEvents(schedule_id, op_id)",
    "idx_operation_execution_events_batch": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_batch ON OperationExecutionEvents(batch_id)",
    "idx_operation_execution_events_latest_exception": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_latest_exception ON OperationExecutionEvents(op_id, event_type, id)",
}


def operation_execution_event_objects(*, legacy=False):
    sql = (
        _LEGACY_TABLE_SQL
        if legacy
        else _LEGACY_TABLE_SQL.replace("request_fingerprint      TEXT NOT NULL", "request_fingerprint      TEXT")
    )
    return {"OperationExecutionEvents": sql, **_INDEXES}
