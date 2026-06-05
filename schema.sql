PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS SchemaVersion (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);
CREATE TABLE IF NOT EXISTS ResourceTeams (
    team_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS Operators (
    operator_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    team_id         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS OpTypes (
    op_type_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'internal',
    default_hours   REAL,
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS Machines (
    machine_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    op_type_id      TEXT,
    category        TEXT,                       -- 设备类别（用于“按类别停机/筛选”等）
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    team_id         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id));
CREATE TABLE IF NOT EXISTS MachineDowntimes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id      TEXT NOT NULL,
    scope_type      TEXT DEFAULT 'machine',      -- machine/category/all（V1.1 预留；当前实现会展开为“按设备逐条写入”）
    scope_value     TEXT,                        -- scope 的取值：machine_id / category / '*'（可空）
    start_time      DATETIME NOT NULL,
    end_time        DATETIME NOT NULL,
    reason_code     TEXT,                       -- 预留：maintenance/breakdown/power/tooling/other
    reason_detail   TEXT,                       -- 预留：原因备注
    status          TEXT DEFAULT 'active',       -- active/cancelled
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_machine_downtimes_machine ON MachineDowntimes(machine_id);
CREATE INDEX IF NOT EXISTS idx_machine_downtimes_time ON MachineDowntimes(start_time, end_time);
CREATE TABLE IF NOT EXISTS OperatorMachine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     TEXT NOT NULL,
    machine_id      TEXT NOT NULL,
    skill_level     TEXT DEFAULT 'normal',
    is_primary      TEXT DEFAULT 'no',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id) ON DELETE CASCADE,
    UNIQUE (operator_id, machine_id));
CREATE TABLE IF NOT EXISTS OperatorSkill (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     TEXT NOT NULL,
    op_type_id      TEXT NOT NULL,
    skill_level     TEXT DEFAULT 'normal',
    is_primary      TEXT DEFAULT 'no',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
    UNIQUE (operator_id, op_type_id));
CREATE INDEX IF NOT EXISTS idx_operators_status ON Operators(status);
CREATE INDEX IF NOT EXISTS idx_operators_team_id ON Operators(team_id);
CREATE INDEX IF NOT EXISTS idx_operator_machine_operator ON OperatorMachine(operator_id);
CREATE INDEX IF NOT EXISTS idx_operator_machine_machine ON OperatorMachine(machine_id);
CREATE TABLE IF NOT EXISTS Suppliers (
    supplier_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    op_type_id      TEXT,
    default_days    REAL DEFAULT 1,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id));
CREATE TABLE IF NOT EXISTS Parts (
    part_no         TEXT PRIMARY KEY,
    part_name       TEXT NOT NULL,
    route_raw       TEXT,
    route_parsed    TEXT DEFAULT 'no',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS PartOperations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no         TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    op_type_id      TEXT,
    op_type_name    TEXT NOT NULL,
    source          TEXT DEFAULT 'internal',
    supplier_id     TEXT,
    ext_days        REAL,
    ext_group_id    TEXT,
    setup_hours     REAL DEFAULT 0,
    unit_hours      REAL DEFAULT 0,
    status          TEXT DEFAULT 'active',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (part_no) REFERENCES Parts(part_no) ON DELETE CASCADE,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id),
    UNIQUE (part_no, seq));
CREATE TABLE IF NOT EXISTS ExternalGroups (
    group_id        TEXT PRIMARY KEY,
    part_no         TEXT NOT NULL,
    start_seq       INTEGER NOT NULL,
    end_seq         INTEGER NOT NULL,
    merge_mode      TEXT DEFAULT 'separate',
    total_days      REAL,
    supplier_id     TEXT,
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (part_no) REFERENCES Parts(part_no) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id));
CREATE INDEX IF NOT EXISTS idx_part_operations_part ON PartOperations(part_no);
CREATE INDEX IF NOT EXISTS idx_part_operations_source ON PartOperations(source);
CREATE INDEX IF NOT EXISTS idx_external_groups_part ON ExternalGroups(part_no);
CREATE INDEX IF NOT EXISTS idx_machines_status ON Machines(status);
CREATE INDEX IF NOT EXISTS idx_machines_op_type ON Machines(op_type_id);
CREATE INDEX IF NOT EXISTS idx_machines_team_id ON Machines(team_id);
CREATE TABLE IF NOT EXISTS Batches (
    batch_id        TEXT PRIMARY KEY,
    part_no         TEXT NOT NULL,
    part_name       TEXT,
    quantity        INTEGER NOT NULL,
    due_date        DATE,
    priority        TEXT DEFAULT 'normal',
    ready_status    TEXT DEFAULT 'yes',
    ready_date      DATE,
    status          TEXT DEFAULT 'pending',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (part_no) REFERENCES Parts(part_no));
CREATE TABLE IF NOT EXISTS BatchOperations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    op_code         TEXT NOT NULL UNIQUE,
    batch_id        TEXT NOT NULL,
    piece_id        TEXT,
    seq             INTEGER NOT NULL,
    op_type_id      TEXT,
    op_type_name    TEXT NOT NULL,
    source          TEXT DEFAULT 'internal',
    machine_id      TEXT,
    operator_id     TEXT,
    supplier_id     TEXT,
    setup_hours     REAL DEFAULT 0,
    unit_hours      REAL DEFAULT 0,
    ext_days        REAL,
    status          TEXT DEFAULT 'pending',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES Batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id),
    UNIQUE (batch_id, seq, piece_id)
);
CREATE TABLE IF NOT EXISTS Schedule (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    op_id           INTEGER NOT NULL,
    machine_id      TEXT,
    operator_id     TEXT,
    start_time      DATETIME NOT NULL,
    end_time        DATETIME NOT NULL,
    lock_status     TEXT DEFAULT 'unlocked',
    version         INTEGER DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (op_id) REFERENCES BatchOperations(id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id),
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id)
);
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
);
CREATE TABLE IF NOT EXISTS ScheduleCandidate (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    version               INTEGER NOT NULL,
    candidate_key         TEXT NOT NULL,
    candidate_label       TEXT NOT NULL,
    candidate_kind        TEXT NOT NULL CHECK(candidate_kind IN ('baseline', 'critical_chain')),
    status                TEXT NOT NULL CHECK(status IN ('completed', 'failed', 'skipped', 'not_run')),
    graph_enabled         TEXT NOT NULL DEFAULT 'no' CHECK(graph_enabled IN ('yes', 'no')),
    weight_level          INTEGER,
    weight_count          INTEGER,
    critical_weight       INTEGER,
    impact_weight         INTEGER,
    downstream_weight     INTEGER,
    sort_strategy         TEXT,
    dispatch_mode         TEXT,
    dispatch_rule         TEXT,
    objective             TEXT,
    score_json            TEXT,
    metrics_json          TEXT,
    health_json           TEXT,
    summary_json          TEXT,
    selection_reason      TEXT,
    failure_reason        TEXT,
    detail_saved          TEXT NOT NULL DEFAULT 'no' CHECK(detail_saved IN ('yes', 'no')),
    elapsed_ms            INTEGER,
    started_at            DATETIME,
    finished_at           DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version, candidate_key),
    UNIQUE(id, version)
);
CREATE TABLE IF NOT EXISTS ScheduleCandidateRows (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    version          INTEGER NOT NULL,
    candidate_id     INTEGER NOT NULL,
    op_id            INTEGER NOT NULL,
    machine_id       TEXT,
    operator_id      TEXT,
    start_time       DATETIME NOT NULL,
    end_time         DATETIME NOT NULL,
    lock_status      TEXT DEFAULT 'unlocked',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id, version) REFERENCES ScheduleCandidate(id, version) ON DELETE CASCADE,
    UNIQUE(candidate_id, op_id)
);
CREATE TABLE IF NOT EXISTS ScheduleCandidateSelection (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version         INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('adopted', 'baseline_best', 'critical_best')),
    candidate_id    INTEGER NOT NULL,
    source_table    TEXT NOT NULL CHECK(source_table IN ('schedule', 'candidate_rows')),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id, version) REFERENCES ScheduleCandidate(id, version) ON DELETE CASCADE,
    UNIQUE(version, role)
);
CREATE TABLE IF NOT EXISTS ScheduleVersionSeq (version INTEGER PRIMARY KEY AUTOINCREMENT);
CREATE TABLE IF NOT EXISTS WorkCalendar (
    date            DATE PRIMARY KEY,
    day_type        TEXT DEFAULT 'workday',
    shift_start     TEXT,                       -- 班次开始（HH:MM，可选；默认 08:00）
    shift_end       TEXT,                       -- 班次结束（HH:MM，可选；用于推导 shift_hours）
    shift_hours     REAL DEFAULT 8,
    efficiency      REAL DEFAULT 1.0,
    allow_normal    TEXT DEFAULT 'yes',
    allow_urgent    TEXT DEFAULT 'yes',
    remark          TEXT
);
CREATE TABLE IF NOT EXISTS OperatorCalendar (
    operator_id     TEXT NOT NULL,
    date            DATE NOT NULL,
    day_type        TEXT DEFAULT 'workday',
    shift_start     TEXT,                       -- 班次开始（HH:MM，可选；默认 08:00）
    shift_end       TEXT,                       -- 班次结束（HH:MM，可选；用于推导 shift_hours）
    shift_hours     REAL DEFAULT 8,
    efficiency      REAL DEFAULT 1.0,
    allow_normal    TEXT DEFAULT 'yes',
    allow_urgent    TEXT DEFAULT 'yes',
    remark          TEXT,
    PRIMARY KEY (operator_id, date),
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_operator_calendar_operator_date ON OperatorCalendar(operator_id, date);
CREATE INDEX IF NOT EXISTS idx_operator_calendar_date ON OperatorCalendar(date);
CREATE TABLE IF NOT EXISTS ScheduleConfig (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS SystemConfig (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS SystemJobState (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key         TEXT NOT NULL UNIQUE,
    last_run_time   DATETIME,
    last_run_detail TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_system_job_state_time ON SystemJobState(last_run_time);
CREATE INDEX IF NOT EXISTS idx_batches_status ON Batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_priority ON Batches(priority);
CREATE INDEX IF NOT EXISTS idx_batches_due_date ON Batches(due_date);
CREATE INDEX IF NOT EXISTS idx_batch_operations_batch ON BatchOperations(batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_operations_identity_unique ON BatchOperations(id, batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_operations_status ON BatchOperations(status);
CREATE INDEX IF NOT EXISTS idx_schedule_op ON Schedule(op_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_version_op_unique ON Schedule(version, op_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_identity_unique ON Schedule(id, version, op_id);
CREATE INDEX IF NOT EXISTS idx_schedule_machine ON Schedule(machine_id);
CREATE INDEX IF NOT EXISTS idx_schedule_operator ON Schedule(operator_id);
CREATE INDEX IF NOT EXISTS idx_schedule_time ON Schedule(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_schedule_version_time ON Schedule(version, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_operation_execution_events_op ON OperationExecutionEvents(op_id, event_time);
CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule ON OperationExecutionEvents(schedule_id);
CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule_op ON OperationExecutionEvents(schedule_id, op_id);
CREATE INDEX IF NOT EXISTS idx_operation_execution_events_batch ON OperationExecutionEvents(batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_execution_events_op_revision_unique
ON OperationExecutionEvents(schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role, previous_state_revision);
CREATE INDEX IF NOT EXISTS idx_operation_execution_events_latest_exception ON OperationExecutionEvents(op_id, event_type, id);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_version ON ScheduleCandidate(version);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_version_kind ON ScheduleCandidate(version, candidate_kind);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_version_candidate ON ScheduleCandidateRows(version, candidate_id);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_version_candidate_time ON ScheduleCandidateRows(version, candidate_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_time ON ScheduleCandidateRows(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_selection_version ON ScheduleCandidateSelection(version);
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
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_draft_base ON ScheduleAdjustmentDraft(base_version, base_plan_role);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_draft_status ON ScheduleAdjustmentDraft(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_change_draft_op ON ScheduleAdjustmentChange(draft_id, op_id);
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
    execution_snapshot_revision TEXT,
    execution_snapshot_op_ids   TEXT,
    execution_snapshot_op_count INTEGER NOT NULL DEFAULT 0,
    created_by         TEXT,
    published_version  INTEGER,
    published_by       TEXT,
    published_reason   TEXT,
    published_at       DATETIME,
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
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_base ON ScheduleAdjustmentScenario(base_version, base_plan_role, status);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_draft ON ScheduleAdjustmentScenario(source_draft_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_row_op ON ScheduleAdjustmentScenarioRow(scenario_id, op_id);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustment_scenario_row_time ON ScheduleAdjustmentScenarioRow(scenario_id, start_time, end_time);
CREATE TABLE IF NOT EXISTS OperationLogs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    log_time        DATETIME DEFAULT CURRENT_TIMESTAMP,
    log_level       TEXT NOT NULL,
    module          TEXT NOT NULL,
    action          TEXT NOT NULL,
    target_type     TEXT,
    target_id       TEXT,
    operator        TEXT,
    detail          TEXT,
    error_code      TEXT,
    error_message   TEXT
);
CREATE TABLE IF NOT EXISTS ScheduleHistory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
    version         INTEGER NOT NULL,
    strategy        TEXT NOT NULL,
    batch_count     INTEGER,
    op_count        INTEGER,
    result_status   TEXT,
    result_summary  TEXT,
    created_by      TEXT
);
CREATE INDEX IF NOT EXISTS idx_operation_logs_time ON OperationLogs(log_time);
CREATE INDEX IF NOT EXISTS idx_operation_logs_level ON OperationLogs(log_level);
CREATE INDEX IF NOT EXISTS idx_operation_logs_module ON OperationLogs(module);
CREATE INDEX IF NOT EXISTS idx_schedule_history_time ON ScheduleHistory(schedule_time);
CREATE INDEX IF NOT EXISTS idx_schedule_history_version ON ScheduleHistory(version);
CREATE TABLE IF NOT EXISTS Materials (
    material_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    spec            TEXT,
    unit            TEXT,
    stock_qty       REAL DEFAULT 0,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS BatchMaterials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    material_id     TEXT NOT NULL,
    required_qty    REAL NOT NULL,
    available_qty   REAL DEFAULT 0,
    ready_status    TEXT DEFAULT 'no',
    FOREIGN KEY (batch_id) REFERENCES Batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES Materials(material_id)
);
