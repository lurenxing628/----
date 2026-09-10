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

-- Workbench metadata. Generated from workbench_metadata_schema.metadata_objects; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchEntityRefs (
        ref TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*'),
        kind TEXT NOT NULL,
        entity_key TEXT NOT NULL,
        alternate_key TEXT,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision) = 'integer' AND revision > 0),
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
        created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
CREATE TABLE IF NOT EXISTS WorkbenchCommandReceipts (
        request_key TEXT PRIMARY KEY NOT NULL CHECK(length(request_key) BETWEEN 16 AND 128),
        receipt_ref TEXT NOT NULL UNIQUE CHECK(length(receipt_ref) = 32 AND receipt_ref NOT GLOB '*[^0-9a-f]*'),
        action TEXT NOT NULL,
        context_ref TEXT NOT NULL,
        input_hash TEXT NOT NULL CHECK(length(input_hash) = 64 AND input_hash NOT GLOB '*[^0-9a-f]*'),
        outcome_json TEXT NOT NULL,
        committed_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
CREATE UNIQUE INDEX IF NOT EXISTS idx_workbench_refs_active_key ON WorkbenchEntityRefs(kind, entity_key) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_workbench_refs_kind ON WorkbenchEntityRefs(kind, active);
CREATE INDEX IF NOT EXISTS idx_workbench_refs_alternate ON WorkbenchEntityRefs(kind, alternate_key) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_workbench_batch_materials_material ON BatchMaterials(material_id);
CREATE TRIGGER IF NOT EXISTS wb_ref_part_insert AFTER INSERT ON "Parts" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'part' AND active = 1 AND (entity_key = CAST(NEW."part_no" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'part', CAST(NEW."part_no" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_part_update AFTER UPDATE ON "Parts" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'part' AND active = 1 AND entity_key != CAST(OLD."part_no" AS TEXT) AND (entity_key = CAST(NEW."part_no" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."part_no" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'part' AND entity_key = CAST(OLD."part_no" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_part_delete AFTER DELETE ON "Parts" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'part' AND entity_key = CAST(OLD."part_no" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_op_type_insert AFTER INSERT ON "OpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'op_type' AND active = 1 AND (entity_key = CAST(NEW."op_type_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'op_type', CAST(NEW."op_type_id" AS TEXT), CAST(NEW."name" AS TEXT));
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_op_type_update AFTER UPDATE ON "OpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'op_type' AND active = 1 AND entity_key != CAST(OLD."op_type_id" AS TEXT) AND (entity_key = CAST(NEW."op_type_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."op_type_id" AS TEXT), alternate_key = CAST(NEW."name" AS TEXT), revision = revision + 1
                WHERE kind = 'op_type' AND entity_key = CAST(OLD."op_type_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_op_type_delete AFTER DELETE ON "OpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'op_type' AND entity_key = CAST(OLD."op_type_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_insert AFTER INSERT ON "Machines" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine' AND active = 1 AND (entity_key = CAST(NEW."machine_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'machine', CAST(NEW."machine_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_update AFTER UPDATE ON "Machines" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine' AND active = 1 AND entity_key != CAST(OLD."machine_id" AS TEXT) AND (entity_key = CAST(NEW."machine_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."machine_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'machine' AND entity_key = CAST(OLD."machine_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_delete AFTER DELETE ON "Machines" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine' AND entity_key = CAST(OLD."machine_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_insert AFTER INSERT ON "Operators" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator' AND active = 1 AND (entity_key = CAST(NEW."operator_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'operator', CAST(NEW."operator_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_update AFTER UPDATE ON "Operators" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator' AND active = 1 AND entity_key != CAST(OLD."operator_id" AS TEXT) AND (entity_key = CAST(NEW."operator_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."operator_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'operator' AND entity_key = CAST(OLD."operator_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_delete AFTER DELETE ON "Operators" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator' AND entity_key = CAST(OLD."operator_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_supplier_insert AFTER INSERT ON "Suppliers" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'supplier' AND active = 1 AND (entity_key = CAST(NEW."supplier_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'supplier', CAST(NEW."supplier_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_supplier_update AFTER UPDATE ON "Suppliers" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'supplier' AND active = 1 AND entity_key != CAST(OLD."supplier_id" AS TEXT) AND (entity_key = CAST(NEW."supplier_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."supplier_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'supplier' AND entity_key = CAST(OLD."supplier_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_supplier_delete AFTER DELETE ON "Suppliers" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'supplier' AND entity_key = CAST(OLD."supplier_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_material_insert AFTER INSERT ON "Materials" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'material' AND active = 1 AND (entity_key = CAST(NEW."material_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'material', CAST(NEW."material_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_material_update AFTER UPDATE ON "Materials" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'material' AND active = 1 AND entity_key != CAST(OLD."material_id" AS TEXT) AND (entity_key = CAST(NEW."material_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."material_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'material' AND entity_key = CAST(OLD."material_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_material_delete AFTER DELETE ON "Materials" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'material' AND entity_key = CAST(OLD."material_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_calendar_insert AFTER INSERT ON "WorkCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'calendar' AND active = 1 AND (entity_key = CAST(NEW."date" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'calendar', CAST(NEW."date" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_calendar_update AFTER UPDATE ON "WorkCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'calendar' AND active = 1 AND entity_key != CAST(OLD."date" AS TEXT) AND (entity_key = CAST(NEW."date" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."date" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'calendar' AND entity_key = CAST(OLD."date" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_calendar_delete AFTER DELETE ON "WorkCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'calendar' AND entity_key = CAST(OLD."date" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_calendar_insert AFTER INSERT ON "OperatorCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator_calendar' AND active = 1 AND (entity_key = replace(replace(CAST(NEW."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."date" AS TEXT), '%', '%25'), ':', '%3A'));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'operator_calendar', replace(replace(CAST(NEW."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."date" AS TEXT), '%', '%25'), ':', '%3A'), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_calendar_update AFTER UPDATE ON "OperatorCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator_calendar' AND active = 1 AND entity_key != replace(replace(CAST(OLD."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(OLD."date" AS TEXT), '%', '%25'), ':', '%3A') AND (entity_key = replace(replace(CAST(NEW."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."date" AS TEXT), '%', '%25'), ':', '%3A'));
            UPDATE WorkbenchEntityRefs SET entity_key = replace(replace(CAST(NEW."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."date" AS TEXT), '%', '%25'), ':', '%3A'), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'operator_calendar' AND entity_key = replace(replace(CAST(OLD."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(OLD."date" AS TEXT), '%', '%25'), ':', '%3A') AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_operator_calendar_delete AFTER DELETE ON "OperatorCalendar" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'operator_calendar' AND entity_key = replace(replace(CAST(OLD."operator_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(OLD."date" AS TEXT), '%', '%25'), ':', '%3A') AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_batch_insert AFTER INSERT ON "Batches" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'batch' AND active = 1 AND (entity_key = CAST(NEW."batch_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'batch', CAST(NEW."batch_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_batch_update AFTER UPDATE ON "Batches" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'batch' AND active = 1 AND entity_key != CAST(OLD."batch_id" AS TEXT) AND (entity_key = CAST(NEW."batch_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."batch_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'batch' AND entity_key = CAST(OLD."batch_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_batch_delete AFTER DELETE ON "Batches" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'batch' AND entity_key = CAST(OLD."batch_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_resource_team_insert AFTER INSERT ON "ResourceTeams" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'resource_team' AND active = 1 AND (entity_key = CAST(NEW."team_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'resource_team', CAST(NEW."team_id" AS TEXT), CAST(NEW."name" AS TEXT));
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_resource_team_update AFTER UPDATE ON "ResourceTeams" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'resource_team' AND active = 1 AND entity_key != CAST(OLD."team_id" AS TEXT) AND (entity_key = CAST(NEW."team_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."team_id" AS TEXT), alternate_key = CAST(NEW."name" AS TEXT), revision = revision + 1
                WHERE kind = 'resource_team' AND entity_key = CAST(OLD."team_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_resource_team_delete AFTER DELETE ON "ResourceTeams" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'resource_team' AND entity_key = CAST(OLD."team_id" AS TEXT) AND active = 1;
        END;

-- Workbench explicit resources. Generated from workbench_resource_schema.resource_objects; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchMachineGroups (
        group_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS WorkbenchMachineGroupMembers (
        machine_id TEXT PRIMARY KEY NOT NULL REFERENCES Machines(machine_id) ON DELETE CASCADE,
        group_id TEXT NOT NULL REFERENCES WorkbenchMachineGroups(group_id)
    );
CREATE TABLE IF NOT EXISTS WorkbenchShiftProfiles (
        profile_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        anchor_date TEXT NOT NULL, cycle_days INTEGER NOT NULL CHECK(typeof(cycle_days) = 'integer' AND cycle_days BETWEEN 1 AND 366),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS WorkbenchShiftPatternDays (
        profile_id TEXT NOT NULL REFERENCES WorkbenchShiftProfiles(profile_id) ON DELETE CASCADE,
        day_offset INTEGER NOT NULL CHECK(typeof(day_offset) = 'integer' AND day_offset BETWEEN 0 AND 365),
        is_rest INTEGER NOT NULL CHECK(is_rest IN (0, 1)),
        shift_start TEXT NOT NULL, shift_end TEXT NOT NULL,
        PRIMARY KEY(profile_id, day_offset)
    );
CREATE TABLE IF NOT EXISTS WorkbenchOperatorProfiles (
        operator_id TEXT PRIMARY KEY NOT NULL REFERENCES Operators(operator_id) ON DELETE CASCADE,
        shift_profile_id TEXT REFERENCES WorkbenchShiftProfiles(profile_id),
        skills_declared INTEGER NOT NULL DEFAULT 0 CHECK(skills_declared IN (0, 1)),
        inactive_reason TEXT CHECK(inactive_reason IS NULL OR inactive_reason IN ('leave', 'disabled'))
    );
CREATE TABLE IF NOT EXISTS WorkbenchSupplierOpTypes (
        supplier_id TEXT NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        op_type_id TEXT NOT NULL REFERENCES OpTypes(op_type_id),
        PRIMARY KEY(supplier_id, op_type_id)
    );
CREATE TABLE IF NOT EXISTS WorkbenchSupplierProfiles (
        supplier_id TEXT PRIMARY KEY NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        inactive_reason TEXT CHECK(inactive_reason IS NULL OR inactive_reason IN ('pending_review', 'disabled'))
    );
CREATE TABLE IF NOT EXISTS WorkbenchOpTypePolicies (
        op_type_id TEXT PRIMARY KEY NOT NULL REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
        default_merge_mode TEXT NOT NULL CHECK(default_merge_mode IN ('separate', 'merged'))
    );
CREATE INDEX IF NOT EXISTS idx_wb_machine_members_group ON WorkbenchMachineGroupMembers(group_id);
CREATE INDEX IF NOT EXISTS idx_wb_operator_profiles_shift ON WorkbenchOperatorProfiles(shift_profile_id);
CREATE INDEX IF NOT EXISTS idx_wb_supplier_op_types_op ON WorkbenchSupplierOpTypes(op_type_id);
CREATE INDEX IF NOT EXISTS idx_wb_operator_skill_op ON OperatorSkill(op_type_id);
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_group_insert AFTER INSERT ON "WorkbenchMachineGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine_group' AND active = 1 AND (entity_key = CAST(NEW."group_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'machine_group', CAST(NEW."group_id" AS TEXT), CAST(NEW."name" AS TEXT));
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_group_update AFTER UPDATE ON "WorkbenchMachineGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine_group' AND active = 1 AND entity_key != CAST(OLD."group_id" AS TEXT) AND (entity_key = CAST(NEW."group_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."group_id" AS TEXT), alternate_key = CAST(NEW."name" AS TEXT), revision = revision + 1
                WHERE kind = 'machine_group' AND entity_key = CAST(OLD."group_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_machine_group_delete AFTER DELETE ON "WorkbenchMachineGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'machine_group' AND entity_key = CAST(OLD."group_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_shift_profile_insert AFTER INSERT ON "WorkbenchShiftProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'shift_profile' AND active = 1 AND (entity_key = CAST(NEW."profile_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'shift_profile', CAST(NEW."profile_id" AS TEXT), CAST(NEW."name" AS TEXT));
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_shift_profile_update AFTER UPDATE ON "WorkbenchShiftProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'shift_profile' AND active = 1 AND entity_key != CAST(OLD."profile_id" AS TEXT) AND (entity_key = CAST(NEW."profile_id" AS TEXT) OR alternate_key = CAST(NEW."name" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."profile_id" AS TEXT), alternate_key = CAST(NEW."name" AS TEXT), revision = revision + 1
                WHERE kind = 'shift_profile' AND entity_key = CAST(OLD."profile_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_shift_profile_delete AFTER DELETE ON "WorkbenchShiftProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'shift_profile' AND entity_key = CAST(OLD."profile_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchmachinegroupmembers_insert AFTER INSERT ON "WorkbenchMachineGroupMembers" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'machine' AND entity_key IN (NEW."machine_id")) OR (kind = 'machine_group' AND entity_key IN (NEW."group_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchmachinegroupmembers_update AFTER UPDATE ON "WorkbenchMachineGroupMembers" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'machine' AND entity_key IN (OLD."machine_id", NEW."machine_id")) OR (kind = 'machine_group' AND entity_key IN (OLD."group_id", NEW."group_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchmachinegroupmembers_delete AFTER DELETE ON "WorkbenchMachineGroupMembers" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'machine' AND entity_key IN (OLD."machine_id")) OR (kind = 'machine_group' AND entity_key IN (OLD."group_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchshiftpatterndays_insert AFTER INSERT ON "WorkbenchShiftPatternDays" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'shift_profile' AND entity_key IN (NEW."profile_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchshiftpatterndays_update AFTER UPDATE ON "WorkbenchShiftPatternDays" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'shift_profile' AND entity_key IN (OLD."profile_id", NEW."profile_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchshiftpatterndays_delete AFTER DELETE ON "WorkbenchShiftPatternDays" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'shift_profile' AND entity_key IN (OLD."profile_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoperatorprofiles_insert AFTER INSERT ON "WorkbenchOperatorProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (NEW."operator_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoperatorprofiles_update AFTER UPDATE ON "WorkbenchOperatorProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id", NEW."operator_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoperatorprofiles_delete AFTER DELETE ON "WorkbenchOperatorProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplieroptypes_insert AFTER INSERT ON "WorkbenchSupplierOpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (NEW."supplier_id")) OR (kind = 'op_type' AND entity_key IN (NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplieroptypes_update AFTER UPDATE ON "WorkbenchSupplierOpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (OLD."supplier_id", NEW."supplier_id")) OR (kind = 'op_type' AND entity_key IN (OLD."op_type_id", NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplieroptypes_delete AFTER DELETE ON "WorkbenchSupplierOpTypes" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (OLD."supplier_id")) OR (kind = 'op_type' AND entity_key IN (OLD."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplierprofiles_insert AFTER INSERT ON "WorkbenchSupplierProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (NEW."supplier_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplierprofiles_update AFTER UPDATE ON "WorkbenchSupplierProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (OLD."supplier_id", NEW."supplier_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchsupplierprofiles_delete AFTER DELETE ON "WorkbenchSupplierProfiles" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'supplier' AND entity_key IN (OLD."supplier_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoptypepolicies_insert AFTER INSERT ON "WorkbenchOpTypePolicies" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'op_type' AND entity_key IN (NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoptypepolicies_update AFTER UPDATE ON "WorkbenchOpTypePolicies" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'op_type' AND entity_key IN (OLD."op_type_id", NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_workbenchoptypepolicies_delete AFTER DELETE ON "WorkbenchOpTypePolicies" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'op_type' AND entity_key IN (OLD."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatorskill_insert AFTER INSERT ON "OperatorSkill" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (NEW."operator_id")) OR (kind = 'op_type' AND entity_key IN (NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatorskill_update AFTER UPDATE ON "OperatorSkill" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id", NEW."operator_id")) OR (kind = 'op_type' AND entity_key IN (OLD."op_type_id", NEW."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatorskill_delete AFTER DELETE ON "OperatorSkill" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id")) OR (kind = 'op_type' AND entity_key IN (OLD."op_type_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatormachine_insert AFTER INSERT ON "OperatorMachine" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (NEW."operator_id")) OR (kind = 'machine' AND entity_key IN (NEW."machine_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatormachine_update AFTER UPDATE ON "OperatorMachine" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id", NEW."operator_id")) OR (kind = 'machine' AND entity_key IN (OLD."machine_id", NEW."machine_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_touch_operatormachine_delete AFTER DELETE ON "OperatorMachine" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ((kind = 'operator' AND entity_key IN (OLD."operator_id")) OR (kind = 'machine' AND entity_key IN (OLD."machine_id")));
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_shift_members_insert AFTER INSERT ON WorkbenchOperatorProfiles BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND kind = 'shift_profile' AND entity_key IN (NEW.shift_profile_id);
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_shift_members_update AFTER UPDATE ON WorkbenchOperatorProfiles WHEN OLD.shift_profile_id IS NOT NEW.shift_profile_id OR OLD.operator_id IS NOT NEW.operator_id BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND kind = 'shift_profile' AND entity_key IN (OLD.shift_profile_id, NEW.shift_profile_id);
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_shift_members_delete AFTER DELETE ON WorkbenchOperatorProfiles BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND kind = 'shift_profile' AND entity_key IN (OLD.shift_profile_id);
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_operator_status_reason AFTER UPDATE OF status ON Operators BEGIN
            UPDATE WorkbenchOperatorProfiles SET inactive_reason = NULL WHERE operator_id = NEW.operator_id AND inactive_reason IS NOT NULL;
        END;
CREATE TRIGGER IF NOT EXISTS wb_resource_supplier_status_reason AFTER UPDATE OF status ON Suppliers BEGIN
            UPDATE WorkbenchSupplierProfiles SET inactive_reason = NULL WHERE supplier_id = NEW.supplier_id AND inactive_reason IS NOT NULL;
        END;

-- Template identities. Generated from workbench_process_schema.process_objects; tested for parity.
CREATE TRIGGER IF NOT EXISTS wb_ref_template_operation_insert AFTER INSERT ON "PartOperations" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_operation' AND active = 1 AND entity_key = CAST(NEW."id" AS TEXT);
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_operation' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."part_no" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A');
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'template_operation', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."part_no" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A'));
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_template_operation_update AFTER UPDATE ON "PartOperations" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_operation' AND active = 1 AND entity_key != CAST(OLD."id" AS TEXT) AND entity_key = CAST(NEW."id" AS TEXT);
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_operation' AND active = 1 AND entity_key != CAST(OLD."id" AS TEXT) AND alternate_key = replace(replace(CAST(NEW."part_no" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A');
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."id" AS TEXT), alternate_key = replace(replace(CAST(NEW."part_no" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A'), revision = revision + 1
                WHERE kind = 'template_operation' AND entity_key = CAST(OLD."id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_template_operation_delete AFTER DELETE ON "PartOperations" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_operation' AND entity_key = CAST(OLD."id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_template_external_group_insert AFTER INSERT ON "ExternalGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_external_group' AND active = 1 AND (entity_key = CAST(NEW."group_id" AS TEXT));
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), 'template_external_group', CAST(NEW."group_id" AS TEXT), NULL);
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_template_external_group_update AFTER UPDATE ON "ExternalGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_external_group' AND active = 1 AND entity_key != CAST(OLD."group_id" AS TEXT) AND (entity_key = CAST(NEW."group_id" AS TEXT));
            UPDATE WorkbenchEntityRefs SET entity_key = CAST(NEW."group_id" AS TEXT), alternate_key = NULL, revision = revision + 1
                WHERE kind = 'template_external_group' AND entity_key = CAST(OLD."group_id" AS TEXT) AND active = 1;
        END;
CREATE TRIGGER IF NOT EXISTS wb_ref_template_external_group_delete AFTER DELETE ON "ExternalGroups" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = 'template_external_group' AND entity_key = CAST(OLD."group_id" AS TEXT) AND active = 1;
        END;

-- Explicit process workflow. Generated from workbench_process_workflow_schema.workflow_objects; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchProcessWorkflow (
        part_ref TEXT PRIMARY KEY NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        route_signature TEXT, route_confirmed_at TEXT, route_confirmed_by TEXT,
        source_signature TEXT, source_confirmed_at TEXT, source_confirmed_by TEXT,
        hours_signature TEXT, hours_confirmed_at TEXT, hours_confirmed_by TEXT,
        CHECK((route_signature IS NULL AND route_confirmed_at IS NULL AND route_confirmed_by IS NULL) OR (typeof(route_signature) = 'text' AND length(route_signature) = 64 AND route_signature NOT GLOB '*[^0-9a-f]*' AND typeof(route_confirmed_at) = 'text' AND length(route_confirmed_at) > 0)), CHECK(route_confirmed_by IS NULL OR (typeof(route_confirmed_by) = 'text' AND length(trim(route_confirmed_by)) > 0)),
        CHECK((source_signature IS NULL AND source_confirmed_at IS NULL AND source_confirmed_by IS NULL) OR (typeof(source_signature) = 'text' AND length(source_signature) = 64 AND source_signature NOT GLOB '*[^0-9a-f]*' AND typeof(source_confirmed_at) = 'text' AND length(source_confirmed_at) > 0)), CHECK(source_confirmed_by IS NULL OR (typeof(source_confirmed_by) = 'text' AND length(trim(source_confirmed_by)) > 0)),
        CHECK((hours_signature IS NULL AND hours_confirmed_at IS NULL AND hours_confirmed_by IS NULL) OR (typeof(hours_signature) = 'text' AND length(hours_signature) = 64 AND hours_signature NOT GLOB '*[^0-9a-f]*' AND typeof(hours_confirmed_at) = 'text' AND length(hours_confirmed_at) > 0)), CHECK(hours_confirmed_by IS NULL OR (typeof(hours_confirmed_by) = 'text' AND length(trim(hours_confirmed_by)) > 0))
    );
CREATE TABLE IF NOT EXISTS WorkbenchProcessOperationConfirmations (
        part_ref TEXT NOT NULL REFERENCES WorkbenchProcessWorkflow(part_ref),
        operation_ref TEXT NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        stage TEXT NOT NULL CHECK(stage IN ('source', 'hours')),
        signature TEXT, confirmed_at TEXT, confirmed_by TEXT,
        CHECK(typeof(signature) = 'text' AND length(signature) = 64 AND signature NOT GLOB '*[^0-9a-f]*' AND typeof(confirmed_at) = 'text' AND length(confirmed_at) > 0), CHECK(confirmed_by IS NULL OR (typeof(confirmed_by) = 'text' AND length(trim(confirmed_by)) > 0)),
        PRIMARY KEY(part_ref, operation_ref, stage)
    );
CREATE INDEX IF NOT EXISTS idx_wb_process_confirmation_operation ON WorkbenchProcessOperationConfirmations(operation_ref);

-- Permanent plan and task identities. Generated from workbench_plan_identity_schema; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchPlanSourceRefs (
        ref TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*'), kind TEXT NOT NULL, source_key TEXT NOT NULL,
        alternate_key TEXT, extra_key TEXT, version INTEGER, plan_role TEXT,
        source_table TEXT, owner_key TEXT, operation_id INTEGER,
        operation_ref TEXT, parent_ref TEXT,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
    );
CREATE TABLE IF NOT EXISTS WorkbenchTaskRefs (
        ref TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*'), plan_ref TEXT NOT NULL, row_ref TEXT NOT NULL,
        UNIQUE(plan_ref, row_ref)
    );
CREATE TABLE IF NOT EXISTS WorkbenchPlanIdentityClock (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0)
    );
CREATE UNIQUE INDEX IF NOT EXISTS idx_wb_plan_source_key ON WorkbenchPlanSourceRefs(kind, source_key) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_wb_plan_source_alternate ON WorkbenchPlanSourceRefs(kind, alternate_key) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_wb_plan_source_extra ON WorkbenchPlanSourceRefs(kind, extra_key) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_wb_plan_source_version ON WorkbenchPlanSourceRefs(kind, version, plan_role) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_wb_plan_source_parent ON WorkbenchPlanSourceRefs(kind, parent_ref) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_wb_plan_task_row ON WorkbenchTaskRefs(row_ref);
CREATE INDEX IF NOT EXISTS idx_wb_plan_history_head ON ScheduleHistory(version, schedule_time DESC, id DESC);
CREATE TRIGGER IF NOT EXISTS wb_plan_history_insert AFTER INSERT ON ScheduleHistory BEGIN INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, version, plan_role, source_table)
        SELECT lower(hex(randomblob(24))), 'official', CAST(NEW.version AS TEXT), NEW.version, 'adopted', 'schedule'
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs WHERE kind = 'official'
            AND source_key = CAST(NEW.version AS TEXT) AND active = 1);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_history_update AFTER UPDATE ON ScheduleHistory BEGIN INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, version, plan_role, source_table)
        SELECT lower(hex(randomblob(24))), 'official', CAST(NEW.version AS TEXT), NEW.version, 'adopted', 'schedule'
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs WHERE kind = 'official'
            AND source_key = CAST(NEW.version AS TEXT) AND active = 1);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_history_delete AFTER DELETE ON ScheduleHistory BEGIN UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_insert AFTER INSERT ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND alternate_key = CAST(NEW."op_code" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'operation', CAST(NEW."id" AS TEXT), CAST(NEW."op_code" AS TEXT), replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, NULL, NULL, NULL, NULL WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_update AFTER UPDATE ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND alternate_key = CAST(NEW."op_code" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (0);UPDATE WorkbenchPlanSourceRefs SET kind = 'operation', source_key = CAST(NEW."id" AS TEXT), alternate_key = CAST(NEW."op_code" AS TEXT), extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), version = NULL, plan_role = NULL, source_table = NULL, owner_key = NULL, operation_id = NULL WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'operation', CAST(NEW."id" AS TEXT), CAST(NEW."op_code" AS TEXT), replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, NULL, NULL, NULL, NULL WHERE 0;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_delete AFTER DELETE ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_insert AFTER INSERT ON "ScheduleCandidate" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."candidate_key" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'candidate', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."candidate_key" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NULL, NULL, NULL, NULL, NULL, NULL WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_update AFTER UPDATE ON "ScheduleCandidate" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."candidate_key" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.id IS NOT NEW.id OR OLD.version IS NOT NEW.version OR OLD.candidate_key IS NOT NEW.candidate_key);UPDATE WorkbenchPlanSourceRefs SET kind = 'candidate', source_key = CAST(NEW."id" AS TEXT), alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."candidate_key" AS TEXT), '%', '%25'), ':', '%3A'), extra_key = NULL, version = NEW.version, plan_role = NULL, source_table = NULL, owner_key = NULL, operation_id = NULL WHERE kind = 'candidate' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'candidate', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."candidate_key" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NULL, NULL, NULL, NULL, NULL, NULL WHERE OLD.id IS NOT NEW.id OR OLD.version IS NOT NEW.version OR OLD.candidate_key IS NOT NEW.candidate_key;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_delete AFTER DELETE ON "ScheduleCandidate" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_selection_insert AFTER INSERT ON "ScheduleCandidateSelection" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."role" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'selection', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."role" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NEW.role, NEW.source_table, CAST(NEW.candidate_id AS TEXT), NULL, NULL, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'candidate' AND source_key = CAST(NEW.candidate_id AS TEXT) AND active = 1) WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_selection_update AFTER UPDATE ON "ScheduleCandidateSelection" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."role" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.id IS NOT NEW.id OR OLD.version IS NOT NEW.version OR OLD.role IS NOT NEW.role OR OLD.candidate_id IS NOT NEW.candidate_id OR OLD.source_table IS NOT NEW.source_table);UPDATE WorkbenchPlanSourceRefs SET kind = 'selection', source_key = CAST(NEW."id" AS TEXT), alternate_key = replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."role" AS TEXT), '%', '%25'), ':', '%3A'), extra_key = NULL, version = NEW.version, plan_role = NEW.role, source_table = NEW.source_table, owner_key = CAST(NEW.candidate_id AS TEXT), operation_id = NULL WHERE kind = 'selection' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'selection', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."version" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."role" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NEW.role, NEW.source_table, CAST(NEW.candidate_id AS TEXT), NULL, NULL, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'candidate' AND source_key = CAST(NEW.candidate_id AS TEXT) AND active = 1) WHERE OLD.id IS NOT NEW.id OR OLD.version IS NOT NEW.version OR OLD.role IS NOT NEW.role OR OLD.candidate_id IS NOT NEW.candidate_id OR OLD.source_table IS NOT NEW.source_table;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_selection_delete AFTER DELETE ON "ScheduleCandidateSelection" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'selection' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_insert AFTER INSERT ON "ScheduleAdjustmentScenario" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND source_key = CAST(NEW."scenario_id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND alternate_key = CAST(NEW."source_draft_id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'scenario', CAST(NEW."scenario_id" AS TEXT), CAST(NEW."source_draft_id" AS TEXT), NULL, NEW.base_version, NEW.base_plan_role, 'adjustment_scenario_rows', NULL, NULL, NULL, CASE WHEN NEW.base_plan_role = 'adopted'
        THEN (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'official' AND source_key = CAST(NEW.base_version AS TEXT) AND active = 1)
        ELSE (SELECT ref FROM WorkbenchPlanSourceRefs WHERE active = 1 AND kind = 'selection'
            AND version = NEW.base_version AND plan_role = NEW.base_plan_role) END WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_update AFTER UPDATE ON "ScheduleAdjustmentScenario" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND source_key = CAST(NEW."scenario_id" AS TEXT) AND source_key != CAST(OLD."scenario_id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND alternate_key = CAST(NEW."source_draft_id" AS TEXT) AND source_key != CAST(OLD."scenario_id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND source_key = CAST(OLD."scenario_id" AS TEXT) AND (OLD.scenario_id IS NOT NEW.scenario_id OR OLD.source_draft_id IS NOT NEW.source_draft_id OR OLD.base_version IS NOT NEW.base_version OR OLD.base_plan_role IS NOT NEW.base_plan_role OR OLD.base_source_table IS NOT NEW.base_source_table OR OLD.base_candidate_id IS NOT NEW.base_candidate_id OR OLD.base_candidate_key IS NOT NEW.base_candidate_key);UPDATE WorkbenchPlanSourceRefs SET kind = 'scenario', source_key = CAST(NEW."scenario_id" AS TEXT), alternate_key = CAST(NEW."source_draft_id" AS TEXT), extra_key = NULL, version = NEW.base_version, plan_role = NEW.base_plan_role, source_table = 'adjustment_scenario_rows', owner_key = NULL, operation_id = NULL WHERE kind = 'scenario' AND active = 1 AND source_key = CAST(OLD."scenario_id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'scenario', CAST(NEW."scenario_id" AS TEXT), CAST(NEW."source_draft_id" AS TEXT), NULL, NEW.base_version, NEW.base_plan_role, 'adjustment_scenario_rows', NULL, NULL, NULL, CASE WHEN NEW.base_plan_role = 'adopted'
        THEN (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'official' AND source_key = CAST(NEW.base_version AS TEXT) AND active = 1)
        ELSE (SELECT ref FROM WorkbenchPlanSourceRefs WHERE active = 1 AND kind = 'selection'
            AND version = NEW.base_version AND plan_role = NEW.base_plan_role) END WHERE OLD.scenario_id IS NOT NEW.scenario_id OR OLD.source_draft_id IS NOT NEW.source_draft_id OR OLD.base_version IS NOT NEW.base_version OR OLD.base_plan_role IS NOT NEW.base_plan_role OR OLD.base_source_table IS NOT NEW.base_source_table OR OLD.base_candidate_id IS NOT NEW.base_candidate_id OR OLD.base_candidate_key IS NOT NEW.base_candidate_key;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_delete AFTER DELETE ON "ScheduleAdjustmentScenario" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario' AND active = 1 AND source_key = CAST(OLD."scenario_id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_insert AFTER INSERT ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'schedule_row', CAST(NEW."id" AS TEXT), NULL, NULL, NEW.version, NULL, 'schedule', CAST(NEW.version AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), NULL WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_update AFTER UPDATE ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.version IS NOT NEW.version OR OLD.op_id IS NOT NEW.op_id);UPDATE WorkbenchPlanSourceRefs SET kind = 'schedule_row', source_key = CAST(NEW."id" AS TEXT), alternate_key = NULL, extra_key = NULL, version = NEW.version, plan_role = NULL, source_table = 'schedule', owner_key = CAST(NEW.version AS TEXT), operation_id = NEW.op_id WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'schedule_row', CAST(NEW."id" AS TEXT), NULL, NULL, NEW.version, NULL, 'schedule', CAST(NEW.version AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), NULL WHERE OLD.version IS NOT NEW.version OR OLD.op_id IS NOT NEW.op_id;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_delete AFTER DELETE ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_row_insert AFTER INSERT ON "ScheduleCandidateRows" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."candidate_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'candidate_row', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."candidate_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NULL, 'candidate_rows', CAST(NEW.candidate_id AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'candidate' AND source_key = CAST(NEW.candidate_id AS TEXT) AND active = 1) WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_row_update AFTER UPDATE ON "ScheduleCandidateRows" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."candidate_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.version IS NOT NEW.version OR OLD.candidate_id IS NOT NEW.candidate_id OR OLD.op_id IS NOT NEW.op_id);UPDATE WorkbenchPlanSourceRefs SET kind = 'candidate_row', source_key = CAST(NEW."id" AS TEXT), alternate_key = replace(replace(CAST(NEW."candidate_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), extra_key = NULL, version = NEW.version, plan_role = NULL, source_table = 'candidate_rows', owner_key = CAST(NEW.candidate_id AS TEXT), operation_id = NEW.op_id WHERE kind = 'candidate_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'candidate_row', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."candidate_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NEW.version, NULL, 'candidate_rows', CAST(NEW.candidate_id AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'candidate' AND source_key = CAST(NEW.candidate_id AS TEXT) AND active = 1) WHERE OLD.version IS NOT NEW.version OR OLD.candidate_id IS NOT NEW.candidate_id OR OLD.op_id IS NOT NEW.op_id;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_candidate_row_delete AFTER DELETE ON "ScheduleCandidateRows" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'candidate_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_row_insert AFTER INSERT ON "ScheduleAdjustmentScenarioRow" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."scenario_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'scenario_row', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."scenario_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, 'adjustment_scenario_rows', CAST(NEW.scenario_id AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'scenario' AND source_key = CAST(NEW.scenario_id AS TEXT) AND active = 1) WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_row_update AFTER UPDATE ON "ScheduleAdjustmentScenarioRow" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND alternate_key = replace(replace(CAST(NEW."scenario_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.scenario_id IS NOT NEW.scenario_id OR OLD.op_id IS NOT NEW.op_id);UPDATE WorkbenchPlanSourceRefs SET kind = 'scenario_row', source_key = CAST(NEW."id" AS TEXT), alternate_key = replace(replace(CAST(NEW."scenario_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), extra_key = NULL, version = NULL, plan_role = NULL, source_table = 'adjustment_scenario_rows', owner_key = CAST(NEW.scenario_id AS TEXT), operation_id = NEW.op_id WHERE kind = 'scenario_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref, parent_ref) SELECT lower(hex(randomblob(24))), 'scenario_row', CAST(NEW."id" AS TEXT), replace(replace(CAST(NEW."scenario_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."op_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, 'adjustment_scenario_rows', CAST(NEW.scenario_id AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1), (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'scenario' AND source_key = CAST(NEW.scenario_id AS TEXT) AND active = 1) WHERE OLD.scenario_id IS NOT NEW.scenario_id OR OLD.op_id IS NOT NEW.op_id;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_scenario_row_delete AFTER DELETE ON "ScheduleAdjustmentScenarioRow" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'scenario_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_task_plan_insert AFTER INSERT ON WorkbenchPlanSourceRefs WHEN NEW.kind IN ('official', 'selection', 'scenario') BEGIN INSERT INTO WorkbenchTaskRefs(ref, plan_ref, row_ref)
        SELECT lower(hex(randomblob(24))), pairs.plan_ref, pairs.row_ref FROM (SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'official' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (p.ref = NEW.ref) AND (1) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'schedule' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (p.ref = NEW.ref) AND (1) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'candidate_rows' AND r.kind = 'candidate_row' AND r.version = p.version AND r.parent_ref = p.parent_ref WHERE p.active = 1 AND r.active = 1 AND (p.ref = NEW.ref) AND (1) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'scenario' AND r.kind = 'scenario_row' AND r.parent_ref = p.ref WHERE p.active = 1 AND r.active = 1 AND (p.ref = NEW.ref) AND (1)) pairs
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchTaskRefs t
            WHERE t.plan_ref = pairs.plan_ref AND t.row_ref = pairs.row_ref); END;
CREATE TRIGGER IF NOT EXISTS wb_plan_task_row_insert AFTER INSERT ON WorkbenchPlanSourceRefs WHEN NEW.kind IN ('schedule_row', 'candidate_row', 'scenario_row') BEGIN INSERT INTO WorkbenchTaskRefs(ref, plan_ref, row_ref)
        SELECT lower(hex(randomblob(24))), pairs.plan_ref, pairs.row_ref FROM (SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'official' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (1) AND (r.ref = NEW.ref) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'schedule' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (1) AND (r.ref = NEW.ref) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'candidate_rows' AND r.kind = 'candidate_row' AND r.version = p.version AND r.parent_ref = p.parent_ref WHERE p.active = 1 AND r.active = 1 AND (1) AND (r.ref = NEW.ref) UNION ALL SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'scenario' AND r.kind = 'scenario_row' AND r.parent_ref = p.ref WHERE p.active = 1 AND r.active = 1 AND (1) AND (r.ref = NEW.ref)) pairs
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchTaskRefs t
            WHERE t.plan_ref = pairs.plan_ref AND t.row_ref = pairs.row_ref); END;
INSERT INTO WorkbenchPlanIdentityClock(singleton, revision) SELECT 1, CASE WHEN NOT EXISTS (SELECT 1 FROM "WorkbenchPlanSourceRefs" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "WorkbenchTaskRefs" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleHistory" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "BatchOperations" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleCandidate" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleCandidateSelection" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleAdjustmentScenario" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "Schedule" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleCandidateRows" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleAdjustmentScenarioRow" LIMIT 1) THEN 1 ELSE 0 END WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanIdentityClock);

-- Immutable execution ledger. Generated from execution_ledger_objects; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchExecutionLedgerClock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0),
            next_report_no INTEGER NOT NULL CHECK(typeof(next_report_no) = 'integer' AND next_report_no > 0)
        );
CREATE TABLE IF NOT EXISTS WorkbenchExecutionLegacyFacts (
            legacy_fact_ref TEXT NOT NULL CHECK(length(legacy_fact_ref) = 48 AND legacy_fact_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            operation_ref TEXT, recorded_against_task_ref TEXT, recorded_against_plan_ref TEXT,
            actual_machine_ref TEXT, actual_operator_ref TEXT,
            id,
schedule_version,
schedule_id,
op_id,
batch_id,
source_table,
effective_plan_role,
scenario_id,
event_type,
reported_status,
event_time,
actual_machine_id,
actual_operator_id,
quantity_done,
quantity_scrapped,
reason_code,
reason_detail,
severity,
impact_minutes,
affected_machine_id,
affected_operator_id,
handling_status,
suggest_reschedule,
remark,
created_by,
idempotency_key,
request_fingerprint,
previous_state_revision,
created_at, UNIQUE(id)
        );
CREATE TABLE IF NOT EXISTS WorkbenchProductionReports (
            report_ref TEXT NOT NULL CHECK(length(report_ref) = 48 AND report_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            report_no TEXT NOT NULL UNIQUE CHECK(length(report_no) BETWEEN 1 AND 64),
            operation_ref TEXT NOT NULL, recorded_against_task_ref TEXT NOT NULL,
            recorded_against_plan_ref TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('manual', 'excel')),
            legacy_fact_ref TEXT UNIQUE, recorded_at TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(recorded_against_task_ref) REFERENCES WorkbenchTaskRefs(ref),
            FOREIGN KEY(recorded_against_plan_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(legacy_fact_ref) REFERENCES WorkbenchExecutionLegacyFacts(legacy_fact_ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchProductionReportRevisions (
            revision_ref TEXT NOT NULL CHECK(length(revision_ref) = 48 AND revision_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            report_ref TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0),
            previous_revision_ref TEXT, action TEXT NOT NULL CHECK(action IN ('create', 'supplement', 'correct')),
            values_json TEXT NOT NULL, reason TEXT NOT NULL,
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator)) > 0),
            declared_operator TEXT NOT NULL, recorded_at TEXT NOT NULL,
            request_key TEXT NOT NULL,
            UNIQUE(report_ref, sequence), UNIQUE(previous_revision_ref),
            FOREIGN KEY(report_ref) REFERENCES WorkbenchProductionReports(report_ref),
            FOREIGN KEY(previous_revision_ref) REFERENCES WorkbenchProductionReportRevisions(revision_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE INDEX IF NOT EXISTS idx_wb_execution_reports_operation ON WorkbenchProductionReports(operation_ref, recorded_at, report_ref);
CREATE INDEX IF NOT EXISTS idx_wb_execution_reports_task ON WorkbenchProductionReports(recorded_against_task_ref);
CREATE INDEX IF NOT EXISTS idx_wb_execution_legacy_operation ON WorkbenchExecutionLegacyFacts(operation_ref, id);
CREATE INDEX IF NOT EXISTS idx_wb_execution_legacy_unbound ON WorkbenchExecutionLegacyFacts(op_id) WHERE operation_ref IS NULL OR recorded_against_task_ref IS NULL;
CREATE INDEX IF NOT EXISTS idx_wb_execution_revisions_request ON WorkbenchProductionReportRevisions(request_key);
CREATE INDEX IF NOT EXISTS idx_wb_execution_task_operation ON WorkbenchPlanSourceRefs(operation_ref, kind, version);
CREATE INDEX IF NOT EXISTS idx_wb_execution_source_row_history ON WorkbenchPlanSourceRefs(kind, source_key, version, operation_id);
CREATE INDEX IF NOT EXISTS idx_wb_execution_resource_history ON WorkbenchEntityRefs(kind, entity_key);
CREATE TRIGGER IF NOT EXISTS wb_execution_reports_no_update BEFORE UPDATE ON WorkbenchProductionReports BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_reports_no_delete BEFORE DELETE ON WorkbenchProductionReports BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_reports_clock AFTER INSERT ON WorkbenchProductionReports BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_execution_revisions_no_update BEFORE UPDATE ON WorkbenchProductionReportRevisions BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_revisions_no_delete BEFORE DELETE ON WorkbenchProductionReportRevisions BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_revisions_clock AFTER INSERT ON WorkbenchProductionReportRevisions BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_execution_legacy_no_update BEFORE UPDATE ON WorkbenchExecutionLegacyFacts BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_legacy_no_delete BEFORE DELETE ON WorkbenchExecutionLegacyFacts BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_legacy_clock AFTER INSERT ON WorkbenchExecutionLegacyFacts BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_execution_capture_legacy AFTER INSERT ON OperationExecutionEvents BEGIN INSERT INTO WorkbenchExecutionLegacyFacts
        (legacy_fact_ref, operation_ref, recorded_against_task_ref, recorded_against_plan_ref,
         actual_machine_ref, actual_operator_ref, id, schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role, scenario_id, event_type, reported_status, event_time, actual_machine_id, actual_operator_id, quantity_done, quantity_scrapped, reason_code, reason_detail, severity, impact_minutes, affected_machine_id, affected_operator_id, handling_status, suggest_reschedule, remark, created_by, idempotency_key, request_fingerprint, previous_state_revision, created_at)
        SELECT lower(hex(randomblob(24))), r.operation_ref, t.ref, t.plan_ref,
            (SELECT CASE WHEN count(*)=1 THEN min(ref) END FROM WorkbenchEntityRefs
                WHERE kind='machine' AND entity_key=e.actual_machine_id),
            (SELECT CASE WHEN count(*)=1 THEN min(ref) END FROM WorkbenchEntityRefs
                WHERE kind='operator' AND entity_key=e.actual_operator_id), e.id, e.schedule_version, e.schedule_id, e.op_id, e.batch_id, e.source_table, e.effective_plan_role, e.scenario_id, e.event_type, e.reported_status, e.event_time, e.actual_machine_id, e.actual_operator_id, e.quantity_done, e.quantity_scrapped, e.reason_code, e.reason_detail, e.severity, e.impact_minutes, e.affected_machine_id, e.affected_operator_id, e.handling_status, e.suggest_reschedule, e.remark, e.created_by, e.idempotency_key, e.request_fingerprint, e.previous_state_revision, e.created_at
        FROM OperationExecutionEvents e
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.ref = (
            SELECT min(x.ref) FROM WorkbenchPlanSourceRefs x WHERE x.kind = 'schedule_row'
            AND x.source_table = 'schedule' AND e.source_table = 'schedule'
            AND e.effective_plan_role = 'adopted' AND e.scenario_id IS NULL
            AND x.source_key = CAST(e.schedule_id AS TEXT) AND x.version = e.schedule_version
            AND x.operation_id = e.op_id
            AND EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs owner JOIN BatchOperations bo
                ON bo.id = CAST(owner.source_key AS INTEGER) AND CAST(bo.id AS TEXT) = owner.source_key
                WHERE owner.ref = x.operation_ref AND owner.kind = 'operation' AND owner.active = 1
                AND bo.batch_id = e.batch_id)
            GROUP BY x.kind, x.source_key, x.version, x.operation_id HAVING count(*) = 1)
        LEFT JOIN WorkbenchPlanSourceRefs p ON p.kind = 'official' AND p.active = 1
            AND p.version = e.schedule_version
        LEFT JOIN WorkbenchTaskRefs t ON t.row_ref = r.ref AND t.plan_ref = p.ref
        WHERE e.id = NEW.id; END;
INSERT INTO WorkbenchExecutionLedgerClock(singleton, revision, next_report_no) SELECT 1, CASE WHEN NOT EXISTS (SELECT 1 FROM WorkbenchExecutionLegacyFacts LIMIT 1) AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReports LIMIT 1) AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions LIMIT 1) AND NOT EXISTS (SELECT 1 FROM OperationExecutionEvents LIMIT 1) AND NOT EXISTS (SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1) THEN 1 ELSE 0 END, 1 WHERE NOT EXISTS (SELECT 1 FROM WorkbenchExecutionLedgerClock);

-- Permanent candidate runs. Generated from workbench_run_objects; tested for parity.
CREATE TABLE IF NOT EXISTS WorkbenchRunJobs (
            run_ref TEXT NOT NULL CHECK(length(run_ref)=48 AND run_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
            input_ref TEXT NOT NULL, normalized_input_json TEXT NOT NULL,
            facts_hash TEXT NOT NULL, facts_json TEXT NOT NULL, execution_json TEXT NOT NULL,
            baseline_json TEXT NOT NULL, accepted_at TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('queued','running','complete','partial','failed','interrupted')),
            stage TEXT NOT NULL CHECK(stage IN ('queued','computing','finished','awaiting_reconciliation')),
            executor_ref TEXT, started_at TEXT, finished_at TEXT, error_json TEXT,
            CHECK((state='queued' AND stage IN ('queued','awaiting_reconciliation') AND executor_ref IS NULL
                   AND started_at IS NULL AND finished_at IS NULL)
               OR (state='running' AND stage IN ('computing','awaiting_reconciliation') AND executor_ref IS NOT NULL
                   AND started_at IS NOT NULL AND finished_at IS NULL)
               OR (state IN ('complete','partial','failed','interrupted') AND stage='finished' AND finished_at IS NOT NULL)),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TABLE IF NOT EXISTS WorkbenchRunReceipts (
            receipt_ref TEXT NOT NULL CHECK(length(receipt_ref)=48 AND receipt_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, run_ref TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK(state IN ('complete','partial','failed','interrupted')),
            result_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchRunCandidates (
            candidate_ref TEXT NOT NULL CHECK(length(candidate_ref)=48 AND candidate_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, run_ref TEXT NOT NULL, candidate_key TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>=0),
            status TEXT NOT NULL CHECK(status IN ('completed','failed','skipped')),
            task_count INTEGER NOT NULL CHECK(typeof(task_count)='integer' AND task_count>=0),
            artifact_json TEXT NOT NULL, UNIQUE(run_ref,candidate_key), UNIQUE(run_ref,sequence),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchRunCandidateTasks (
            row_ref TEXT NOT NULL CHECK(length(row_ref)=48 AND row_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, candidate_ref TEXT NOT NULL, operation_ref TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0),
            payload_json TEXT NOT NULL, UNIQUE(candidate_ref,operation_ref), UNIQUE(candidate_ref,ordinal),
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        );
CREATE INDEX IF NOT EXISTS idx_wb_run_state ON WorkbenchRunJobs(state,accepted_at,run_ref);
CREATE TRIGGER IF NOT EXISTS wb_runjobs_no_delete BEFORE DELETE ON WorkbenchRunJobs BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runreceipts_no_update BEFORE UPDATE ON WorkbenchRunReceipts BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runreceipts_no_delete BEFORE DELETE ON WorkbenchRunReceipts BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidates_no_update BEFORE UPDATE ON WorkbenchRunCandidates BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidates_no_delete BEFORE DELETE ON WorkbenchRunCandidates BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidatetasks_no_update BEFORE UPDATE ON WorkbenchRunCandidateTasks BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidatetasks_no_delete BEFORE DELETE ON WorkbenchRunCandidateTasks BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_run_admission_immutable
        BEFORE UPDATE ON WorkbenchRunJobs WHEN NEW.run_ref IS NOT OLD.run_ref OR NEW.request_key IS NOT OLD.request_key OR NEW.input_ref IS NOT OLD.input_ref OR NEW.normalized_input_json IS NOT OLD.normalized_input_json OR NEW.facts_hash IS NOT OLD.facts_hash OR NEW.facts_json IS NOT OLD.facts_json OR NEW.execution_json IS NOT OLD.execution_json OR NEW.baseline_json IS NOT OLD.baseline_json OR NEW.accepted_at IS NOT OLD.accepted_at
        BEGIN SELECT RAISE(ABORT,'run admission is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_run_state_transition
        BEFORE UPDATE ON WorkbenchRunJobs WHEN
        OLD.state IN ('complete','partial','failed','interrupted') OR
        NOT (NEW.state=OLD.state OR (OLD.state='queued' AND NEW.state IN ('running','interrupted'))
             OR (OLD.state='running' AND NEW.state IN ('complete','partial','failed','interrupted')))
        BEGIN SELECT RAISE(ABORT,'invalid run transition'); END;

CREATE TABLE IF NOT EXISTS WorkbenchTemplateLineageOrigins (
            lineage_ref TEXT NOT NULL CHECK(length(lineage_ref)=48 AND lineage_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            operation_ref TEXT NOT NULL UNIQUE, template_operation_ref TEXT NOT NULL,
            template_revision INTEGER NOT NULL CHECK(typeof(template_revision)='integer' AND template_revision>0),
            source_operation_ref TEXT, source_lineage_ref TEXT, source_event_id INTEGER,
            source_eligible INTEGER NOT NULL CHECK(source_eligible IN (0,1)), birth_event_id INTEGER NOT NULL UNIQUE,
            evidence_version TEXT NOT NULL CHECK(evidence_version='template-copy-v1'),
            template_snapshot TEXT NOT NULL, template_fingerprint TEXT NOT NULL,
            instance_snapshot TEXT NOT NULL, instance_fingerprint TEXT NOT NULL,
            recorded_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(template_operation_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(source_operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(source_lineage_ref) REFERENCES WorkbenchTemplateLineageOrigins(lineage_ref),
            FOREIGN KEY(birth_event_id) REFERENCES WorkbenchTemplateLineageEvents(event_id),
            CHECK((source_operation_ref IS NULL)=(source_lineage_ref IS NULL)),
            CHECK((source_operation_ref IS NULL)=(source_event_id IS NULL)),
            CHECK(source_operation_ref IS NOT NULL OR source_eligible=1)
        );
CREATE TABLE IF NOT EXISTS WorkbenchTemplateLineageEvents (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_ref TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN ('created','updated','retired','batch_changed','withdrawn')),
            affects_calibration INTEGER NOT NULL CHECK(affects_calibration IN (0,1)),
            reason TEXT, recorded_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity, FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref));
CREATE INDEX IF NOT EXISTS idx_wb_lineage_events_operation ON WorkbenchTemplateLineageEvents(operation_ref,event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wb_lineage_birth ON WorkbenchTemplateLineageEvents(operation_ref) WHERE event_type='created';
CREATE INDEX IF NOT EXISTS idx_wb_lineage_template_revision ON WorkbenchTemplateLineageOrigins(template_operation_ref,template_revision);
CREATE TRIGGER IF NOT EXISTS wb_lineage_operation_born AFTER INSERT ON WorkbenchPlanSourceRefs WHEN NEW.kind='operation' AND NEW.active=1 BEGIN INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity) SELECT NEW.ref,'created',0,o.id,o.op_code,o.batch_id,o.piece_id,o.seq,o.op_type_id,o.op_type_name,o.source,o.machine_id,o.operator_id,o.supplier_id,o.setup_hours,o.unit_hours,o.ext_days,o.status,o.created_at,(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=b.batch_id),(SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND active=1 AND entity_key=b.part_no),b.quantity FROM BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id WHERE CAST(o.id AS TEXT)=NEW.source_key; END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_operation_update BEFORE UPDATE ON BatchOperations WHEN OLD.id IS NOT NEW.id OR OLD.op_code IS NOT NEW.op_code OR OLD.batch_id IS NOT NEW.batch_id OR OLD.piece_id IS NOT NEW.piece_id OR OLD.seq IS NOT NEW.seq OR OLD.op_type_id IS NOT NEW.op_type_id OR OLD.op_type_name IS NOT NEW.op_type_name OR OLD.source IS NOT NEW.source OR OLD.machine_id IS NOT NEW.machine_id OR OLD.operator_id IS NOT NEW.operator_id OR OLD.supplier_id IS NOT NEW.supplier_id OR OLD.setup_hours IS NOT NEW.setup_hours OR OLD.unit_hours IS NOT NEW.unit_hours OR OLD.ext_days IS NOT NEW.ext_days OR OLD.status IS NOT NEW.status OR OLD.created_at IS NOT NEW.created_at BEGIN INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity) SELECT (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND source_key=CAST(OLD.id AS TEXT)),'updated',(OLD.piece_id IS NOT NEW.piece_id OR OLD.seq IS NOT NEW.seq OR OLD.op_type_id IS NOT NEW.op_type_id OR OLD.op_type_name IS NOT NEW.op_type_name OR OLD.source IS NOT NEW.source OR OLD.supplier_id IS NOT NEW.supplier_id OR OLD.setup_hours IS NOT NEW.setup_hours OR OLD.unit_hours IS NOT NEW.unit_hours OR OLD.ext_days IS NOT NEW.ext_days OR OLD.batch_id IS NOT NEW.batch_id),NEW.id,NEW.op_code,NEW.batch_id,NEW.piece_id,NEW.seq,NEW.op_type_id,NEW.op_type_name,NEW.source,NEW.machine_id,NEW.operator_id,NEW.supplier_id,NEW.setup_hours,NEW.unit_hours,NEW.ext_days,NEW.status,NEW.created_at,(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=b.batch_id),(SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND active=1 AND entity_key=b.part_no),b.quantity FROM Batches b WHERE b.batch_id=NEW.batch_id AND (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND source_key=CAST(OLD.id AS TEXT)) IS NOT NULL; END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_operation_retire AFTER UPDATE ON WorkbenchPlanSourceRefs WHEN OLD.kind='operation' AND OLD.active=1 AND NEW.active=0 BEGIN INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity) SELECT OLD.ref,'retired',1,id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity FROM WorkbenchTemplateLineageEvents WHERE operation_ref=OLD.ref ORDER BY event_id DESC LIMIT 1; END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_batch_change AFTER UPDATE ON Batches WHEN OLD.part_no IS NOT NEW.part_no OR OLD.quantity IS NOT NEW.quantity BEGIN INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,id,op_code,batch_id,piece_id,seq,op_type_id,op_type_name,source,machine_id,operator_id,supplier_id,setup_hours,unit_hours,ext_days,status,created_at,batch_ref,part_ref,quantity) SELECT r.ref,'batch_changed',1,o.id,o.op_code,o.batch_id,o.piece_id,o.seq,o.op_type_id,o.op_type_name,o.source,o.machine_id,o.operator_id,o.supplier_id,o.setup_hours,o.unit_hours,o.ext_days,o.status,o.created_at,(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=b.batch_id),(SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND active=1 AND entity_key=b.part_no),b.quantity FROM BatchOperations o JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT) JOIN Batches b ON b.batch_id=o.batch_id WHERE o.batch_id=NEW.batch_id; END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_origin_no_update BEFORE UPDATE ON WorkbenchTemplateLineageOrigins BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_origin_no_delete BEFORE DELETE ON WorkbenchTemplateLineageOrigins BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_event_no_update BEFORE UPDATE ON WorkbenchTemplateLineageEvents BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_event_no_delete BEFORE DELETE ON WorkbenchTemplateLineageEvents BEGIN SELECT RAISE(ABORT,'template lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_origin_birth BEFORE INSERT ON WorkbenchTemplateLineageOrigins BEGIN
        SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM WorkbenchTemplateLineageEvents e
            JOIN WorkbenchPlanSourceRefs r ON r.ref=e.operation_ref AND r.kind='operation' AND r.active=1
            WHERE e.event_id=NEW.birth_event_id AND e.operation_ref=NEW.operation_ref AND e.event_type='created')
            THEN RAISE(ABORT,'template lineage requires a new instance birth') END;
        SELECT CASE WHEN EXISTS (SELECT 1 FROM WorkbenchTemplateLineageOrigins WHERE operation_ref=NEW.operation_ref OR lineage_ref=NEW.lineage_ref)
            THEN RAISE(ABORT,'template lineage cannot be rebound') END;
    END;
CREATE TRIGGER IF NOT EXISTS wb_lineage_event_no_replace BEFORE INSERT ON WorkbenchTemplateLineageEvents
        WHEN EXISTS (SELECT 1 FROM WorkbenchTemplateLineageEvents WHERE event_id=NEW.event_id)
        BEGIN SELECT RAISE(ABORT,'template lineage events cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS WorkbenchTrialDrafts (
            draft_ref TEXT NOT NULL CHECK(length(draft_ref)=48 AND draft_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, base_kind TEXT NOT NULL CHECK(base_kind IN ('plan_ref','candidate_ref')),
            base_ref TEXT NOT NULL CHECK(length(base_ref)=48 AND base_ref NOT GLOB '*[^0-9a-f]*'), admission_json TEXT NOT NULL, admission_hash TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK(typeof(row_count)='integer' AND row_count>0),
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=1),
            status TEXT NOT NULL CHECK(status IN ('editing','saved','discarded')),
            validation_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            local_operator TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TABLE IF NOT EXISTS WorkbenchTrialRows (
            row_ref TEXT NOT NULL CHECK(length(row_ref)=48 AND row_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, task_ref TEXT NOT NULL CHECK(length(task_ref)=48 AND task_ref NOT GLOB '*[^0-9a-f]*') UNIQUE, draft_ref TEXT NOT NULL,
            operation_ref TEXT NOT NULL, source_task_ref TEXT, source_row_ref TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0),
            original_json TEXT NOT NULL, original_hash TEXT NOT NULL, current_json TEXT NOT NULL,
            UNIQUE(draft_ref,operation_ref), UNIQUE(draft_ref,ordinal),
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchTrialChanges (
            change_ref TEXT NOT NULL CHECK(length(change_ref)=48 AND change_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, draft_ref TEXT NOT NULL, task_ref TEXT NOT NULL,
            revision INTEGER NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            validation_json TEXT NOT NULL, recorded_at TEXT NOT NULL, local_operator TEXT NOT NULL,
            request_key TEXT NOT NULL UNIQUE, UNIQUE(draft_ref,revision),
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(task_ref) REFERENCES WorkbenchTrialRows(task_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TABLE IF NOT EXISTS WorkbenchTrialScenarios (
            scenario_ref TEXT NOT NULL CHECK(length(scenario_ref)=48 AND scenario_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, draft_ref TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
            saved_at TEXT NOT NULL, local_operator TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TABLE IF NOT EXISTS WorkbenchTrialScenarioRows (
            row_ref TEXT NOT NULL CHECK(length(row_ref)=48 AND row_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, task_ref TEXT NOT NULL CHECK(length(task_ref)=48 AND task_ref NOT GLOB '*[^0-9a-f]*') UNIQUE, scenario_ref TEXT NOT NULL,
            source_row_ref TEXT NOT NULL, payload_json TEXT NOT NULL,
            UNIQUE(scenario_ref,source_row_ref),
            FOREIGN KEY(scenario_ref) REFERENCES WorkbenchTrialScenarios(scenario_ref),
            FOREIGN KEY(source_row_ref) REFERENCES WorkbenchTrialRows(row_ref)
        );
CREATE INDEX IF NOT EXISTS idx_wb_trial_status ON WorkbenchTrialDrafts(status,updated_at,draft_ref);
CREATE TRIGGER IF NOT EXISTS wb_trialdrafts_no_delete BEFORE DELETE ON WorkbenchTrialDrafts BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialrows_no_delete BEFORE DELETE ON WorkbenchTrialRows BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialchanges_no_update BEFORE UPDATE ON WorkbenchTrialChanges BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialchanges_no_delete BEFORE DELETE ON WorkbenchTrialChanges BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialscenarios_no_update BEFORE UPDATE ON WorkbenchTrialScenarios BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialscenarios_no_delete BEFORE DELETE ON WorkbenchTrialScenarios BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialscenariorows_no_update BEFORE UPDATE ON WorkbenchTrialScenarioRows BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialscenariorows_no_delete BEFORE DELETE ON WorkbenchTrialScenarioRows BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialdrafts_identity BEFORE UPDATE ON WorkbenchTrialDrafts WHEN NEW.draft_ref IS NOT OLD.draft_ref OR NEW.base_kind IS NOT OLD.base_kind OR NEW.base_ref IS NOT OLD.base_ref OR NEW.admission_json IS NOT OLD.admission_json OR NEW.admission_hash IS NOT OLD.admission_hash OR NEW.row_count IS NOT OLD.row_count OR NEW.created_at IS NOT OLD.created_at OR NEW.local_operator IS NOT OLD.local_operator OR NEW.request_key IS NOT OLD.request_key BEGIN SELECT RAISE(ABORT,'trial baseline is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialrows_identity BEFORE UPDATE ON WorkbenchTrialRows WHEN NEW.row_ref IS NOT OLD.row_ref OR NEW.task_ref IS NOT OLD.task_ref OR NEW.draft_ref IS NOT OLD.draft_ref OR NEW.operation_ref IS NOT OLD.operation_ref OR NEW.source_task_ref IS NOT OLD.source_task_ref OR NEW.source_row_ref IS NOT OLD.source_row_ref OR NEW.ordinal IS NOT OLD.ordinal OR NEW.original_json IS NOT OLD.original_json OR NEW.original_hash IS NOT OLD.original_hash BEGIN SELECT RAISE(ABORT,'trial baseline is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_trial_transition BEFORE UPDATE ON WorkbenchTrialDrafts
        WHEN OLD.status<>'editing' OR NEW.revision<>OLD.revision+1
        BEGIN SELECT RAISE(ABORT,'invalid trial transition'); END;
CREATE TRIGGER IF NOT EXISTS wb_trial_closed_rows BEFORE UPDATE ON WorkbenchTrialRows
        WHEN (SELECT status FROM WorkbenchTrialDrafts WHERE draft_ref=OLD.draft_ref)<>'editing'
        BEGIN SELECT RAISE(ABORT,'closed trial is immutable'); END;
