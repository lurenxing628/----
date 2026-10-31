-- 本文件由 python -m tools.generate_schema_sql --write 生成：手写源是 core/infrastructure 的 DDL 模块，请勿手改。
-- 校验：python -m tools.generate_schema_sql --check。
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS SchemaVersion (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     INTEGER NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);
CREATE TABLE IF NOT EXISTS Operators (
    operator_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
, team_id TEXT);
CREATE TABLE IF NOT EXISTS OpTypes (
    op_type_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'internal',
    default_hours   REAL,
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS Machines (
    machine_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    op_type_id      TEXT,
    category        TEXT,                       -- 设备类别（用于“按类别停机/筛选”等）
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP, team_id TEXT,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id)
);
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
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id) ON DELETE CASCADE
);
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
    UNIQUE (operator_id, machine_id)
);
CREATE TABLE IF NOT EXISTS OperatorSkill (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     TEXT NOT NULL,
    op_type_id      TEXT NOT NULL,
    skill_level     TEXT DEFAULT 'normal',
    is_primary      TEXT DEFAULT 'no',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
    UNIQUE (operator_id, op_type_id)
);
CREATE INDEX IF NOT EXISTS idx_operators_status ON Operators(status);
CREATE INDEX IF NOT EXISTS idx_operator_machine_machine ON OperatorMachine(machine_id);
CREATE TABLE IF NOT EXISTS Suppliers (
    supplier_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    default_days    REAL DEFAULT 1,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS Parts (
    part_no         TEXT PRIMARY KEY,
    part_name       TEXT NOT NULL,
    route_raw       TEXT,
    route_parsed    TEXT DEFAULT 'no',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
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
    UNIQUE (part_no, seq)
);
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
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
);
CREATE INDEX IF NOT EXISTS idx_part_operations_part ON PartOperations(part_no);
CREATE INDEX IF NOT EXISTS idx_part_operations_source ON PartOperations(source);
CREATE INDEX IF NOT EXISTS idx_external_groups_part ON ExternalGroups(part_no);
CREATE INDEX IF NOT EXISTS idx_machines_status ON Machines(status);
CREATE INDEX IF NOT EXISTS idx_machines_op_type ON Machines(op_type_id);
CREATE TABLE IF NOT EXISTS Batches (
    batch_id        TEXT PRIMARY KEY,
    part_no         TEXT NOT NULL,
    part_name       TEXT,
    quantity        INTEGER NOT NULL,
    due_date        DATE,
    priority        TEXT DEFAULT 'normal',
    ready_status    TEXT DEFAULT 'yes',
    ready_date      DATE,                       -- 齐套日期（可选）：最早可开工日期（YYYY-MM-DD）
    status          TEXT DEFAULT 'pending',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (part_no) REFERENCES Parts(part_no)
);
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
CREATE TABLE IF NOT EXISTS ScheduleVersionSeq (
    version         INTEGER PRIMARY KEY AUTOINCREMENT
);
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
, periods_json TEXT);
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
    remark          TEXT, periods_json TEXT,
    PRIMARY KEY (operator_id, date),
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE
);
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
CREATE INDEX IF NOT EXISTS idx_batch_operations_status ON BatchOperations(status);
CREATE INDEX IF NOT EXISTS idx_schedule_op ON Schedule(op_id);
CREATE INDEX IF NOT EXISTS idx_schedule_machine ON Schedule(machine_id);
CREATE INDEX IF NOT EXISTS idx_schedule_operator ON Schedule(operator_id);
CREATE INDEX IF NOT EXISTS idx_schedule_time ON Schedule(start_time, end_time);
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
CREATE TABLE IF NOT EXISTS ResourceTeams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
CREATE INDEX IF NOT EXISTS idx_operators_team_id ON Operators(team_id);
CREATE INDEX IF NOT EXISTS idx_machines_team_id ON Machines(team_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_version_op_unique ON Schedule(version, op_id);
CREATE INDEX IF NOT EXISTS idx_schedule_version_time
ON Schedule(version, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_schedule_history_version
ON ScheduleHistory(version);
CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_operations_identity_unique ON BatchOperations(id, batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_identity_unique ON Schedule(id, version, op_id);
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
        outcome_json TEXT NOT NULL,
        input_json TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS WorkbenchProcessWorkflow (
        part_ref TEXT PRIMARY KEY NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        route_confirmed_at TEXT, route_confirmed_by TEXT, route_content_json TEXT,
        source_confirmed_at TEXT, source_confirmed_by TEXT, source_content_json TEXT,
        hours_confirmed_at TEXT, hours_confirmed_by TEXT, hours_content_json TEXT,
        CHECK((route_confirmed_at IS NULL AND route_confirmed_by IS NULL AND route_content_json IS NULL) OR (typeof(route_content_json) = 'text' AND length(route_content_json) > 0 AND typeof(route_confirmed_at) = 'text' AND length(route_confirmed_at) > 0)), CHECK(route_confirmed_by IS NULL OR (typeof(route_confirmed_by) = 'text' AND length(trim(route_confirmed_by)) > 0)),
        CHECK((source_confirmed_at IS NULL AND source_confirmed_by IS NULL AND source_content_json IS NULL) OR (typeof(source_content_json) = 'text' AND length(source_content_json) > 0 AND typeof(source_confirmed_at) = 'text' AND length(source_confirmed_at) > 0)), CHECK(source_confirmed_by IS NULL OR (typeof(source_confirmed_by) = 'text' AND length(trim(source_confirmed_by)) > 0)),
        CHECK((hours_confirmed_at IS NULL AND hours_confirmed_by IS NULL AND hours_content_json IS NULL) OR (typeof(hours_content_json) = 'text' AND length(hours_content_json) > 0 AND typeof(hours_confirmed_at) = 'text' AND length(hours_confirmed_at) > 0)), CHECK(hours_confirmed_by IS NULL OR (typeof(hours_confirmed_by) = 'text' AND length(trim(hours_confirmed_by)) > 0))
    );
CREATE TABLE IF NOT EXISTS WorkbenchProcessOperationConfirmations (
        part_ref TEXT NOT NULL REFERENCES WorkbenchProcessWorkflow(part_ref),
        operation_ref TEXT NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        stage TEXT NOT NULL CHECK(stage IN ('source', 'hours')),
        confirmed_at TEXT, confirmed_by TEXT, content_json TEXT,
        CHECK(typeof(content_json) = 'text' AND length(content_json) > 0 AND typeof(confirmed_at) = 'text' AND length(confirmed_at) > 0), CHECK(confirmed_by IS NULL OR (typeof(confirmed_by) = 'text' AND length(trim(confirmed_by)) > 0)),
        PRIMARY KEY(part_ref, operation_ref, stage)
    );
CREATE INDEX IF NOT EXISTS idx_wb_process_confirmation_operation ON WorkbenchProcessOperationConfirmations(operation_ref);
CREATE TABLE IF NOT EXISTS WorkbenchPlanSourceRefs (
        ref TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*'), kind TEXT NOT NULL, source_key TEXT NOT NULL,
        alternate_key TEXT, extra_key TEXT, version INTEGER, plan_role TEXT,
        source_table TEXT, owner_key TEXT, operation_id INTEGER,
        operation_ref TEXT,
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
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_insert AFTER INSERT ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND alternate_key = CAST(NEW."op_code" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A');INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref) SELECT lower(hex(randomblob(24))), 'operation', CAST(NEW."id" AS TEXT), CAST(NEW."op_code" AS TEXT), replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, NULL, NULL, NULL WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_update AFTER UPDATE ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND alternate_key = CAST(NEW."op_code" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A') AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (0);UPDATE WorkbenchPlanSourceRefs SET kind = 'operation', source_key = CAST(NEW."id" AS TEXT), alternate_key = CAST(NEW."op_code" AS TEXT), extra_key = replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), version = NULL, plan_role = NULL, source_table = NULL, owner_key = NULL, operation_id = NULL WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref) SELECT lower(hex(randomblob(24))), 'operation', CAST(NEW."id" AS TEXT), CAST(NEW."op_code" AS TEXT), replace(replace(CAST(NEW."batch_id" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."seq" AS TEXT), '%', '%25'), ':', '%3A') || ':' || replace(replace(CAST(NEW."piece_id" AS TEXT), '%', '%25'), ':', '%3A'), NULL, NULL, NULL, NULL, NULL, NULL WHERE 0;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_operation_delete AFTER DELETE ON "BatchOperations" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'operation' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_insert AFTER INSERT ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref) SELECT lower(hex(randomblob(24))), 'schedule_row', CAST(NEW."id" AS TEXT), NULL, NULL, NEW.version, NULL, 'schedule', CAST(NEW.version AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1) WHERE 1;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_update AFTER UPDATE ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(NEW."id" AS TEXT) AND source_key != CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT) AND (OLD.version IS NOT NEW.version OR OLD.op_id IS NOT NEW.op_id);UPDATE WorkbenchPlanSourceRefs SET kind = 'schedule_row', source_key = CAST(NEW."id" AS TEXT), alternate_key = NULL, extra_key = NULL, version = NEW.version, plan_role = NULL, source_table = 'schedule', owner_key = CAST(NEW.version AS TEXT), operation_id = NEW.op_id WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, alternate_key, extra_key, version, plan_role, source_table, owner_key, operation_id, operation_ref) SELECT lower(hex(randomblob(24))), 'schedule_row', CAST(NEW."id" AS TEXT), NULL, NULL, NEW.version, NULL, 'schedule', CAST(NEW.version AS TEXT), NEW.op_id, (SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = 'operation' AND source_key = CAST(NEW.op_id AS TEXT) AND active = 1) WHERE OLD.version IS NOT NEW.version OR OLD.op_id IS NOT NEW.op_id;UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_row_delete AFTER DELETE ON "Schedule" BEGIN UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE kind = 'schedule_row' AND active = 1 AND source_key = CAST(OLD."id" AS TEXT);UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER IF NOT EXISTS wb_plan_task_plan_insert AFTER INSERT ON WorkbenchPlanSourceRefs WHEN NEW.kind = 'official' BEGIN INSERT INTO WorkbenchTaskRefs(ref, plan_ref, row_ref)
        SELECT lower(hex(randomblob(24))), pairs.plan_ref, pairs.row_ref FROM (SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'official' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (p.ref = NEW.ref) AND (1)) pairs
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchTaskRefs t
            WHERE t.plan_ref = pairs.plan_ref AND t.row_ref = pairs.row_ref); END;
CREATE TRIGGER IF NOT EXISTS wb_plan_task_row_insert AFTER INSERT ON WorkbenchPlanSourceRefs WHEN NEW.kind = 'schedule_row' BEGIN INSERT INTO WorkbenchTaskRefs(ref, plan_ref, row_ref)
        SELECT lower(hex(randomblob(24))), pairs.plan_ref, pairs.row_ref FROM (SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p JOIN WorkbenchPlanSourceRefs r ON p.kind = 'official' AND r.kind = 'schedule_row' AND r.version = p.version WHERE p.active = 1 AND r.active = 1 AND (1) AND (r.ref = NEW.ref)) pairs
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchTaskRefs t
            WHERE t.plan_ref = pairs.plan_ref AND t.row_ref = pairs.row_ref); END;
CREATE TRIGGER IF NOT EXISTS wb_plan_source_ref_insert_guard BEFORE INSERT ON WorkbenchPlanSourceRefs
            WHEN EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs WHERE ref = NEW.ref)
            BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: WorkbenchPlanSourceRefs.ref'); END;
CREATE TRIGGER IF NOT EXISTS wb_plan_task_ref_insert_guard BEFORE INSERT ON WorkbenchTaskRefs
            WHEN EXISTS (SELECT 1 FROM WorkbenchTaskRefs WHERE ref = NEW.ref)
            BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: WorkbenchTaskRefs.ref'); END;
CREATE TABLE IF NOT EXISTS WorkbenchExecutionLedgerClock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0),
            next_report_no INTEGER NOT NULL CHECK(typeof(next_report_no) = 'integer' AND next_report_no > 0)
        );
CREATE TABLE IF NOT EXISTS WorkbenchProductionReports (
            report_ref TEXT NOT NULL CHECK(length(report_ref) = 48 AND report_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            report_no TEXT NOT NULL UNIQUE CHECK(length(report_no) BETWEEN 1 AND 64),
            operation_ref TEXT NOT NULL, recorded_against_task_ref TEXT NOT NULL,
            recorded_against_plan_ref TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('manual', 'excel')),
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(recorded_against_task_ref) REFERENCES WorkbenchTaskRefs(ref),
            FOREIGN KEY(recorded_against_plan_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
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
CREATE TABLE IF NOT EXISTS WorkbenchProductionReportVoids (
            void_fact_ref TEXT PRIMARY KEY NOT NULL CHECK(length(void_fact_ref)=48 AND void_fact_ref NOT GLOB '*[^0-9a-f]*'),
            report_ref TEXT NOT NULL UNIQUE,
            original_revision_ref TEXT NOT NULL UNIQUE,
            reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator)) > 0),
            declared_operator TEXT NOT NULL, recorded_at TEXT NOT NULL,
            request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(report_ref) REFERENCES WorkbenchProductionReports(report_ref),
            FOREIGN KEY(original_revision_ref) REFERENCES WorkbenchProductionReportRevisions(revision_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TRIGGER IF NOT EXISTS wb_execution_voids_clock AFTER INSERT ON WorkbenchProductionReportVoids
            BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision=revision+1 WHERE singleton=1; END;
CREATE TRIGGER IF NOT EXISTS wb_execution_voids_current_revision BEFORE INSERT ON WorkbenchProductionReportVoids
            WHEN NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions r
                WHERE r.report_ref=NEW.report_ref AND r.revision_ref=NEW.original_revision_ref
                AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions later
                    WHERE later.report_ref=r.report_ref AND later.sequence>r.sequence))
            BEGIN SELECT RAISE(ABORT, 'report void requires current revision'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_voided_no_revision BEFORE INSERT ON WorkbenchProductionReportRevisions
            WHEN EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids v WHERE v.report_ref=NEW.report_ref)
            BEGIN SELECT RAISE(ABORT, 'voided report cannot be revised'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_voids_no_replace BEFORE INSERT ON WorkbenchProductionReportVoids
            WHEN EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids v WHERE v.void_fact_ref=NEW.void_fact_ref
                OR v.report_ref=NEW.report_ref OR v.original_revision_ref=NEW.original_revision_ref OR v.request_key=NEW.request_key)
            BEGIN SELECT RAISE(ABORT, 'execution void cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_voids_no_update BEFORE UPDATE ON WorkbenchProductionReportVoids BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wb_execution_voids_no_delete BEFORE DELETE ON WorkbenchProductionReportVoids BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS WorkbenchRunJobs (
            run_ref TEXT NOT NULL CHECK(length(run_ref)=48 AND run_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
            input_ref TEXT NOT NULL, normalized_input_json TEXT NOT NULL,
            facts_json TEXT NOT NULL, execution_json TEXT NOT NULL,
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
            status TEXT NOT NULL CHECK(status='completed'),
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
        BEFORE UPDATE ON WorkbenchRunJobs WHEN NEW.run_ref IS NOT OLD.run_ref OR NEW.request_key IS NOT OLD.request_key OR NEW.input_ref IS NOT OLD.input_ref OR NEW.normalized_input_json IS NOT OLD.normalized_input_json OR NEW.facts_json IS NOT OLD.facts_json OR NEW.execution_json IS NOT OLD.execution_json OR NEW.baseline_json IS NOT OLD.baseline_json OR NEW.accepted_at IS NOT OLD.accepted_at
        BEGIN SELECT RAISE(ABORT,'run admission is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_run_state_transition
        BEFORE UPDATE ON WorkbenchRunJobs WHEN
        OLD.state IN ('complete','partial','failed','interrupted') OR
        NOT (NEW.state=OLD.state OR (OLD.state='queued' AND NEW.state IN ('running','interrupted'))
             OR (OLD.state='running' AND NEW.state IN ('complete','partial','failed','interrupted')))
        BEGIN SELECT RAISE(ABORT,'invalid run transition'); END;
CREATE TABLE IF NOT EXISTS WorkbenchRunAdmissionReadModels (
            run_ref TEXT NOT NULL CHECK(length(run_ref)=48 AND run_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            projection_version TEXT NOT NULL, scope_json TEXT NOT NULL, decision_json TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref));
CREATE TABLE IF NOT EXISTS WorkbenchRunDecisionReadModels (
            run_ref TEXT NOT NULL CHECK(length(run_ref)=48 AND run_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, projection_version TEXT NOT NULL,
            header_json TEXT NOT NULL, context_json TEXT NOT NULL, memberships_json TEXT NOT NULL,
            calendar_json TEXT NOT NULL, official_json TEXT NOT NULL, process_json TEXT,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref));
CREATE TABLE IF NOT EXISTS WorkbenchRunCandidateReadModels (
            candidate_ref TEXT NOT NULL CHECK(length(candidate_ref)=48 AND candidate_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, run_ref TEXT NOT NULL,
            projection_version TEXT NOT NULL, summary_json TEXT NOT NULL, preparation_json TEXT NOT NULL,
            completion_json TEXT NOT NULL, delivery_json TEXT NOT NULL, delivery_detail_json TEXT NOT NULL,
            arrangements_json TEXT NOT NULL,
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref));
CREATE INDEX IF NOT EXISTS idx_wb_run_input ON WorkbenchRunJobs(input_ref);
CREATE INDEX IF NOT EXISTS idx_wb_command_action_context_time ON WorkbenchCommandReceipts(action,context_ref,committed_at_utc,request_key);
CREATE INDEX IF NOT EXISTS idx_wb_run_candidate_model_run ON WorkbenchRunCandidateReadModels(run_ref,candidate_ref);
CREATE INDEX IF NOT EXISTS idx_wb_run_accepted ON WorkbenchRunJobs(accepted_at,run_ref);
CREATE INDEX IF NOT EXISTS idx_wb_run_started ON WorkbenchRunJobs(started_at,run_ref);
CREATE INDEX IF NOT EXISTS idx_wb_run_finished ON WorkbenchRunJobs(finished_at,run_ref);
CREATE TRIGGER IF NOT EXISTS wb_runadmissionreadmodels_no_update BEFORE UPDATE ON WorkbenchRunAdmissionReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runadmissionreadmodels_no_delete BEFORE DELETE ON WorkbenchRunAdmissionReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_rundecisionreadmodels_no_update BEFORE UPDATE ON WorkbenchRunDecisionReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_rundecisionreadmodels_no_delete BEFORE DELETE ON WorkbenchRunDecisionReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidatereadmodels_no_update BEFORE UPDATE ON WorkbenchRunCandidateReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_runcandidatereadmodels_no_delete BEFORE DELETE ON WorkbenchRunCandidateReadModels BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END;
CREATE TABLE IF NOT EXISTS WorkbenchTemplateLineageOrigins (
            lineage_ref TEXT NOT NULL CHECK(length(lineage_ref)=48 AND lineage_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            operation_ref TEXT NOT NULL UNIQUE, template_operation_ref TEXT NOT NULL,
            template_revision INTEGER NOT NULL CHECK(typeof(template_revision)='integer' AND template_revision>0),
            source_operation_ref TEXT, source_lineage_ref TEXT, source_event_id INTEGER,
            source_eligible INTEGER NOT NULL CHECK(source_eligible IN (0,1)), birth_event_id INTEGER NOT NULL UNIQUE,
            evidence_version TEXT NOT NULL CHECK(evidence_version='template-copy-v1'),
            template_snapshot TEXT NOT NULL,
            instance_snapshot TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_wb_lineage_operation_id_text ON BatchOperations(CAST(id AS TEXT));
CREATE TABLE IF NOT EXISTS WorkbenchTrialDrafts (
            draft_ref TEXT NOT NULL CHECK(length(draft_ref)=48 AND draft_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, base_kind TEXT NOT NULL CHECK(base_kind IN ('plan_ref','candidate_ref')),
            base_ref TEXT NOT NULL CHECK(length(base_ref)=48 AND base_ref NOT GLOB '*[^0-9a-f]*'), admission_json TEXT NOT NULL,
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
            original_json TEXT NOT NULL, current_json TEXT NOT NULL,
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
            revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
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
CREATE TRIGGER IF NOT EXISTS wb_trialdrafts_identity BEFORE UPDATE ON WorkbenchTrialDrafts WHEN NEW.draft_ref IS NOT OLD.draft_ref OR NEW.base_kind IS NOT OLD.base_kind OR NEW.base_ref IS NOT OLD.base_ref OR NEW.admission_json IS NOT OLD.admission_json OR NEW.row_count IS NOT OLD.row_count OR NEW.created_at IS NOT OLD.created_at OR NEW.local_operator IS NOT OLD.local_operator OR NEW.request_key IS NOT OLD.request_key BEGIN SELECT RAISE(ABORT,'trial baseline is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_trialrows_identity BEFORE UPDATE ON WorkbenchTrialRows WHEN NEW.row_ref IS NOT OLD.row_ref OR NEW.task_ref IS NOT OLD.task_ref OR NEW.draft_ref IS NOT OLD.draft_ref OR NEW.operation_ref IS NOT OLD.operation_ref OR NEW.source_task_ref IS NOT OLD.source_task_ref OR NEW.source_row_ref IS NOT OLD.source_row_ref OR NEW.ordinal IS NOT OLD.ordinal OR NEW.original_json IS NOT OLD.original_json BEGIN SELECT RAISE(ABORT,'trial baseline is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_trial_transition BEFORE UPDATE ON WorkbenchTrialDrafts
        WHEN OLD.status<>'editing' OR NEW.revision<>OLD.revision+1
        BEGIN SELECT RAISE(ABORT,'invalid trial transition'); END;
CREATE TRIGGER IF NOT EXISTS wb_trial_closed_rows BEFORE UPDATE ON WorkbenchTrialRows
        WHEN (SELECT status FROM WorkbenchTrialDrafts WHERE draft_ref=OLD.draft_ref)<>'editing'
        BEGIN SELECT RAISE(ABORT,'closed trial is immutable'); END;
CREATE TABLE IF NOT EXISTS WorkbenchCalibrationAdoptions (
            adoption_ref TEXT NOT NULL CHECK(length(adoption_ref)=48 AND adoption_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            template_operation_ref TEXT NOT NULL REFERENCES WorkbenchEntityRefs(ref),
            request_key TEXT NOT NULL UNIQUE,
            template_revision_before INTEGER NOT NULL CHECK(typeof(template_revision_before)='integer' AND template_revision_before>0),
            template_revision_after INTEGER NOT NULL CHECK(typeof(template_revision_after)='integer' AND template_revision_after>=template_revision_before),
            old_unit_hours,
            new_unit_hours REAL NOT NULL CHECK(new_unit_hours>=0 AND new_unit_hours<=1.7976931348623157e308),
            reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator)) BETWEEN 1 AND 100),
            confirmed INTEGER NOT NULL CHECK(typeof(confirmed)='integer' AND confirmed=1),
            application_operator TEXT NOT NULL CHECK(length(trim(application_operator)) BETWEEN 1 AND 512),
            adopted_at TEXT NOT NULL, generated_at TEXT NOT NULL,
            method_version TEXT NOT NULL,
            sample_count INTEGER NOT NULL CHECK(typeof(sample_count)='integer' AND sample_count BETWEEN 5 AND 20),
            evidence_json TEXT NOT NULL, template_before TEXT NOT NULL, template_after TEXT NOT NULL,
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TRIGGER IF NOT EXISTS wb_calibration_adoption_no_update BEFORE UPDATE ON WorkbenchCalibrationAdoptions BEGIN SELECT RAISE(ABORT,'calibration adoption is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_calibration_adoption_no_delete BEFORE DELETE ON WorkbenchCalibrationAdoptions BEGIN SELECT RAISE(ABORT,'calibration adoption is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wb_calibration_adoption_no_replace BEFORE INSERT ON WorkbenchCalibrationAdoptions WHEN EXISTS (SELECT 1 FROM WorkbenchCalibrationAdoptions WHERE adoption_ref=NEW.adoption_ref OR request_key=NEW.request_key) BEGIN SELECT RAISE(ABORT,'calibration adoption cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS WorkbenchDashboardItems (
            item_ref TEXT NOT NULL CHECK(length(item_ref)=48 AND item_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, category TEXT NOT NULL CHECK(category IN ('delivery','material','actual','downtime')),
            batch_ref TEXT, task_ref TEXT,
            CHECK((category IN ('delivery','material') AND batch_ref IS NOT NULL AND task_ref IS NULL)
               OR (category IN ('actual','downtime') AND task_ref IS NOT NULL AND batch_ref IS NULL)),
            UNIQUE(category,batch_ref), UNIQUE(category,task_ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(task_ref) REFERENCES WorkbenchTaskRefs(ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchDashboardStates (
            item_ref TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0),
            handling_json TEXT NOT NULL, origin_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardItems(item_ref)
        );
CREATE TABLE IF NOT EXISTS WorkbenchDashboardHistory (
            history_ref TEXT NOT NULL CHECK(length(history_ref)=48 AND history_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, item_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0),
            action TEXT NOT NULL CHECK(action IN ('transition','reopen')), before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            source_json TEXT NOT NULL, source_facts_json TEXT NOT NULL,
            reason TEXT, local_operator TEXT NOT NULL, recorded_at TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(item_ref,sequence), FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardStates(item_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        );
CREATE TABLE IF NOT EXISTS WorkbenchDashboardDowntimeRefs (
            ref TEXT NOT NULL CHECK(length(ref)=48 AND ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, source_id INTEGER NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0)
        );
CREATE UNIQUE INDEX IF NOT EXISTS idx_wb_dashboard_downtime_active ON WorkbenchDashboardDowntimeRefs(source_id) WHERE active=1;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_batch_insert AFTER INSERT ON WorkbenchEntityRefs
            WHEN NEW.kind='batch' AND NEW.active=1 BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'delivery',NEW.ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES(lower(hex(randomblob(24))),'material',NEW.ref); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_task_insert AFTER INSERT ON WorkbenchTaskRefs BEGIN
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'actual',NEW.ref);
            INSERT INTO WorkbenchDashboardItems(item_ref,category,task_ref) VALUES(lower(hex(randomblob(24))),'downtime',NEW.ref); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_downtime_insert AFTER INSERT ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET active=0,revision=revision+1 WHERE source_id=NEW.id AND active=1;
            INSERT INTO WorkbenchDashboardDowntimeRefs VALUES(lower(hex(randomblob(24))),NEW.id,1,1); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_downtime_update AFTER UPDATE ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET source_id=NEW.id,revision=revision+1 WHERE source_id=OLD.id AND active=1; END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_downtime_delete AFTER DELETE ON MachineDowntimes BEGIN
            UPDATE WorkbenchDashboardDowntimeRefs SET active=0,revision=revision+1 WHERE source_id=OLD.id AND active=1; END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_state_identity BEFORE UPDATE ON WorkbenchDashboardStates
            WHEN NEW.item_ref IS NOT OLD.item_ref OR NEW.origin_json IS NOT OLD.origin_json OR NEW.revision<>OLD.revision+1
            BEGIN SELECT RAISE(ABORT,'dashboard origin is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_items_no_update BEFORE UPDATE ON WorkbenchDashboardItems BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_items_no_delete BEFORE DELETE ON WorkbenchDashboardItems BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_history_no_update BEFORE UPDATE ON WorkbenchDashboardHistory BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_history_no_delete BEFORE DELETE ON WorkbenchDashboardHistory BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_states_no_delete BEFORE DELETE ON WorkbenchDashboardStates BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_downtimerefs_no_delete BEFORE DELETE ON WorkbenchDashboardDowntimeRefs BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_items_no_replace BEFORE INSERT ON WorkbenchDashboardItems WHEN EXISTS (SELECT 1 FROM WorkbenchDashboardItems WHERE item_ref=NEW.item_ref OR (category=NEW.category AND batch_ref=NEW.batch_ref) OR (category=NEW.category AND task_ref=NEW.task_ref)) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_states_no_replace BEFORE INSERT ON WorkbenchDashboardStates WHEN EXISTS (SELECT 1 FROM WorkbenchDashboardStates WHERE item_ref=NEW.item_ref) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_history_no_replace BEFORE INSERT ON WorkbenchDashboardHistory WHEN EXISTS (SELECT 1 FROM WorkbenchDashboardHistory WHERE history_ref=NEW.history_ref OR request_key=NEW.request_key OR (item_ref=NEW.item_ref AND sequence=NEW.sequence)) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_downtimerefs_no_replace BEFORE INSERT ON WorkbenchDashboardDowntimeRefs WHEN EXISTS (SELECT 1 FROM WorkbenchDashboardDowntimeRefs WHERE ref=NEW.ref OR (active=1 AND NEW.active=1 AND source_id=NEW.source_id)) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS WorkbenchOutsourcingOperationOrigins (
            operation_ref TEXT PRIMARY KEY NOT NULL, batch_ref TEXT,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref));
CREATE TABLE IF NOT EXISTS WorkbenchOutsourcingReceipts (
            outsourcing_ref TEXT NOT NULL CHECK(length(outsourcing_ref)=48 AND outsourcing_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            target_kind TEXT NOT NULL CHECK(target_kind IN ('single','merged')),
            batch_ref TEXT NOT NULL, supplier_ref TEXT NOT NULL,
            origin_json TEXT NOT NULL, identity_json TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(supplier_ref) REFERENCES WorkbenchEntityRefs(ref));
CREATE TABLE IF NOT EXISTS WorkbenchOutsourcingMembers (
            operation_ref TEXT PRIMARY KEY NOT NULL, outsourcing_ref TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchOutsourcingOperationOrigins(operation_ref),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref));
CREATE INDEX IF NOT EXISTS idx_wb_outsourcing_members_receipt ON WorkbenchOutsourcingMembers(outsourcing_ref);
CREATE TABLE IF NOT EXISTS WorkbenchOutsourcingFacts (
            fact_ref TEXT NOT NULL CHECK(length(fact_ref)=48 AND fact_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, outsourcing_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0), previous_fact_ref TEXT,
            sent TEXT NOT NULL, planned TEXT NOT NULL, returned TEXT,
            confirmed_state TEXT NOT NULL CHECK(confirmed_state IN ('in_transit','returned','awaiting_confirmation')),
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator))>0),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator))>0),
            reason TEXT NOT NULL CHECK(length(trim(reason))>0), recorded_at TEXT NOT NULL,
            before_json TEXT NOT NULL, source_facts_json TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(outsourcing_ref,sequence), UNIQUE(previous_fact_ref),
            CHECK(planned>=sent AND (returned IS NULL OR returned>=sent)),
            CHECK(sent<=recorded_at AND (returned IS NULL OR returned<=recorded_at)),
            CHECK((confirmed_state='returned')=(returned IS NOT NULL)),
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref),
            FOREIGN KEY(previous_fact_ref) REFERENCES WorkbenchOutsourcingFacts(fact_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED);
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_operation_born AFTER INSERT ON WorkbenchPlanSourceRefs
            WHEN NEW.kind='operation' AND NEW.active=1 BEGIN
            INSERT INTO WorkbenchOutsourcingOperationOrigins(operation_ref,batch_ref)
            SELECT NEW.ref,(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=o.batch_id)
            FROM BatchOperations o WHERE CAST(o.id AS TEXT)=NEW.source_key; END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_fact_sequence BEFORE INSERT ON WorkbenchOutsourcingFacts BEGIN
            SELECT CASE WHEN NEW.sequence<>COALESCE((SELECT MAX(sequence) FROM WorkbenchOutsourcingFacts
                WHERE outsourcing_ref=NEW.outsourcing_ref),0)+1 OR NEW.previous_fact_ref IS NOT
                (SELECT fact_ref FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=NEW.outsourcing_ref ORDER BY sequence DESC LIMIT 1)
                THEN RAISE(ABORT,'outsourcing fact sequence mismatch') END;
            SELECT CASE WHEN (SELECT COUNT(*) FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=NEW.outsourcing_ref)<
                (SELECT CASE target_kind WHEN 'single' THEN 1 ELSE 2 END FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=NEW.outsourcing_ref)
                THEN RAISE(ABORT,'outsourcing members incomplete') END; END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_members_sealed BEFORE INSERT ON WorkbenchOutsourcingMembers
            WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=NEW.outsourcing_ref)
              OR EXISTS(SELECT 1 FROM WorkbenchOutsourcingReceipts r JOIN WorkbenchOutsourcingMembers m
                  ON m.outsourcing_ref=r.outsourcing_ref WHERE r.outsourcing_ref=NEW.outsourcing_ref AND r.target_kind='single')
            BEGIN SELECT RAISE(ABORT,'outsourcing membership is sealed'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_operationorigins_no_update BEFORE UPDATE ON WorkbenchOutsourcingOperationOrigins BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_operationorigins_no_delete BEFORE DELETE ON WorkbenchOutsourcingOperationOrigins BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_operationorigins_no_replace BEFORE INSERT ON WorkbenchOutsourcingOperationOrigins WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=NEW.operation_ref) BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_receipts_no_update BEFORE UPDATE ON WorkbenchOutsourcingReceipts BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_receipts_no_delete BEFORE DELETE ON WorkbenchOutsourcingReceipts BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_receipts_no_replace BEFORE INSERT ON WorkbenchOutsourcingReceipts WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=NEW.outsourcing_ref) BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_members_no_update BEFORE UPDATE ON WorkbenchOutsourcingMembers BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_members_no_delete BEFORE DELETE ON WorkbenchOutsourcingMembers BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_members_no_replace BEFORE INSERT ON WorkbenchOutsourcingMembers WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingMembers WHERE operation_ref=NEW.operation_ref) BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_facts_no_update BEFORE UPDATE ON WorkbenchOutsourcingFacts BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_facts_no_delete BEFORE DELETE ON WorkbenchOutsourcingFacts BEGIN SELECT RAISE(ABORT,'outsourcing evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_facts_no_replace BEFORE INSERT ON WorkbenchOutsourcingFacts WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingFacts WHERE fact_ref=NEW.fact_ref OR request_key=NEW.request_key OR (outsourcing_ref=NEW.outsourcing_ref AND sequence=NEW.sequence)) BEGIN SELECT RAISE(ABORT,'outsourcing evidence cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS WorkbenchDashboardExternalItems (
            item_ref TEXT NOT NULL CHECK(length(item_ref)=48 AND item_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
            category TEXT NOT NULL DEFAULT 'external' CHECK(category='external'),
            outsourcing_ref TEXT NOT NULL UNIQUE,
            FOREIGN KEY(outsourcing_ref) REFERENCES WorkbenchOutsourcingReceipts(outsourcing_ref));
CREATE TABLE IF NOT EXISTS WorkbenchDashboardExternalStates (
            item_ref TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>0),
            handling_json TEXT NOT NULL, origin_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardExternalItems(item_ref));
CREATE TABLE IF NOT EXISTS WorkbenchDashboardExternalHistory (
            history_ref TEXT NOT NULL CHECK(length(history_ref)=48 AND history_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY, item_ref TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>0),
            action TEXT NOT NULL CHECK(action IN ('transition','reopen')), before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            source_json TEXT NOT NULL, source_facts_json TEXT NOT NULL,
            reason TEXT, local_operator TEXT NOT NULL, recorded_at TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            UNIQUE(item_ref,sequence), FOREIGN KEY(item_ref) REFERENCES WorkbenchDashboardExternalStates(item_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED);
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_receipt_insert
            AFTER INSERT ON WorkbenchOutsourcingReceipts BEGIN
            INSERT INTO WorkbenchDashboardExternalItems(item_ref,outsourcing_ref)
                VALUES(lower(hex(randomblob(24))),NEW.outsourcing_ref); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_state_identity
            BEFORE UPDATE ON WorkbenchDashboardExternalStates
            WHEN NEW.item_ref IS NOT OLD.item_ref OR NEW.origin_json IS NOT OLD.origin_json OR NEW.revision<>OLD.revision+1
            BEGIN SELECT RAISE(ABORT,'dashboard origin is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_items_no_update BEFORE UPDATE ON WorkbenchDashboardExternalItems BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_items_no_delete BEFORE DELETE ON WorkbenchDashboardExternalItems BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_items_no_replace BEFORE INSERT ON WorkbenchDashboardExternalItems WHEN EXISTS(SELECT 1 FROM WorkbenchDashboardExternalItems WHERE item_ref=NEW.item_ref OR outsourcing_ref=NEW.outsourcing_ref) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_states_no_delete BEFORE DELETE ON WorkbenchDashboardExternalStates BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_states_no_replace BEFORE INSERT ON WorkbenchDashboardExternalStates WHEN EXISTS(SELECT 1 FROM WorkbenchDashboardExternalStates WHERE item_ref=NEW.item_ref) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_history_no_update BEFORE UPDATE ON WorkbenchDashboardExternalHistory BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_history_no_delete BEFORE DELETE ON WorkbenchDashboardExternalHistory BEGIN SELECT RAISE(ABORT,'dashboard evidence is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_dashboard_external_history_no_replace BEFORE INSERT ON WorkbenchDashboardExternalHistory WHEN EXISTS(SELECT 1 FROM WorkbenchDashboardExternalHistory WHERE history_ref=NEW.history_ref OR request_key=NEW.request_key OR (item_ref=NEW.item_ref AND sequence=NEW.sequence)) BEGIN SELECT RAISE(ABORT,'dashboard evidence cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS WorkbenchOutsourcingSourceConfirmations (
            operation_ref TEXT PRIMARY KEY NOT NULL, batch_ref TEXT NOT NULL, fact_ref TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchOutsourcingOperationOrigins(operation_ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(fact_ref) REFERENCES WorkbenchOutsourcingFacts(fact_ref));
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_source_confirmation_guard
            BEFORE INSERT ON WorkbenchOutsourcingSourceConfirmations BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM WorkbenchOutsourcingOperationOrigins o
                JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=o.operation_ref
                JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref
                JOIN WorkbenchOutsourcingFacts f ON f.outsourcing_ref=r.outsourcing_ref
                WHERE o.operation_ref=NEW.operation_ref AND o.batch_ref IS NULL
                AND r.batch_ref=NEW.batch_ref AND f.fact_ref=NEW.fact_ref AND f.sequence=1)
                THEN RAISE(ABORT,'outsourcing source confirmation must reference its first registration') END; END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_source_confirmation_no_update BEFORE UPDATE ON WorkbenchOutsourcingSourceConfirmations BEGIN SELECT RAISE(ABORT,'outsourcing source confirmation is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_source_confirmation_no_delete BEFORE DELETE ON WorkbenchOutsourcingSourceConfirmations BEGIN SELECT RAISE(ABORT,'outsourcing source confirmation is permanent'); END;
CREATE TRIGGER IF NOT EXISTS wb_outsourcing_source_confirmation_no_replace BEFORE INSERT ON WorkbenchOutsourcingSourceConfirmations WHEN EXISTS(SELECT 1 FROM WorkbenchOutsourcingSourceConfirmations WHERE operation_ref=NEW.operation_ref) BEGIN SELECT RAISE(ABORT,'outsourcing source confirmation cannot be replaced'); END;
CREATE TABLE IF NOT EXISTS BatchExternalContexts (
            operation_id INTEGER PRIMARY KEY,
            part_no TEXT NOT NULL, sequence INTEGER NOT NULL,
            template_operation_id INTEGER, template_status TEXT,
            group_id TEXT, group_part_no TEXT, start_sequence INTEGER, end_sequence INTEGER,
            merge_mode TEXT, total_days REAL, supplier_id TEXT, group_ref TEXT,
            template_operation_ref TEXT,
            origin TEXT NOT NULL CHECK(origin IN ('creation','template_copy','instance_copy')),
            captured_at TEXT NOT NULL,
            FOREIGN KEY(operation_id) REFERENCES BatchOperations(id) ON DELETE CASCADE);
CREATE TRIGGER IF NOT EXISTS batch_external_context_created
            AFTER INSERT ON BatchOperations WHEN lower(trim(NEW.source))='external' BEGIN INSERT INTO BatchExternalContexts SELECT o.id,b.part_no,o.seq,t.id,t.status,t.ext_group_id,
        g.part_no,g.start_seq,g.end_seq,g.merge_mode,g.total_days,g.supplier_id,r.ref,tr.ref,
        'creation',CURRENT_TIMESTAMP
        FROM (SELECT * FROM BatchOperations WHERE id=NEW.id) o JOIN Batches b ON b.batch_id=o.batch_id
        LEFT JOIN PartOperations t ON t.part_no=b.part_no AND t.seq=o.seq
        LEFT JOIN ExternalGroups g ON g.group_id=t.ext_group_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='template_operation'
            AND tr.entity_key=CAST(t.id AS TEXT) AND tr.active=1
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group'
            AND r.entity_key=g.group_id AND r.active=1
        WHERE lower(trim(o.source))='external'; END;
CREATE TRIGGER IF NOT EXISTS batch_external_context_source_changed
            AFTER UPDATE OF source ON BatchOperations WHEN lower(trim(NEW.source))='external'
                AND lower(trim(OLD.source)) IS NOT lower(trim(NEW.source))
            BEGIN DELETE FROM BatchExternalContexts WHERE operation_id=NEW.id; INSERT INTO BatchExternalContexts SELECT o.id,b.part_no,o.seq,t.id,t.status,t.ext_group_id,
        g.part_no,g.start_seq,g.end_seq,g.merge_mode,g.total_days,g.supplier_id,r.ref,tr.ref,
        'creation',CURRENT_TIMESTAMP
        FROM (SELECT * FROM BatchOperations WHERE id=NEW.id) o JOIN Batches b ON b.batch_id=o.batch_id
        LEFT JOIN PartOperations t ON t.part_no=b.part_no AND t.seq=o.seq
        LEFT JOIN ExternalGroups g ON g.group_id=t.ext_group_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='template_operation'
            AND tr.entity_key=CAST(t.id AS TEXT) AND tr.active=1
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group'
            AND r.entity_key=g.group_id AND r.active=1
        WHERE lower(trim(o.source))='external'; END;
CREATE TABLE IF NOT EXISTS WorkbenchCalendarDefaults (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            state_ref TEXT NOT NULL DEFAULT (lower(hex(randomblob(24)))),
            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), periods_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS WorkbenchShiftDayPeriods (
            profile_id TEXT NOT NULL, day_offset INTEGER NOT NULL, periods_json TEXT NOT NULL,
            PRIMARY KEY(profile_id, day_offset),
            FOREIGN KEY(profile_id, day_offset) REFERENCES WorkbenchShiftPatternDays(profile_id, day_offset)
                ON DELETE CASCADE);
CREATE TRIGGER IF NOT EXISTS wb_shift_periods_insert
            AFTER INSERT ON WorkbenchShiftDayPeriods BEGIN
                UPDATE WorkbenchEntityRefs SET revision=revision+1
                    WHERE kind='shift_profile' AND active=1 AND entity_key=NEW.profile_id;
            END;
CREATE TRIGGER IF NOT EXISTS wb_shift_periods_update
            AFTER UPDATE ON WorkbenchShiftDayPeriods BEGIN
                UPDATE WorkbenchEntityRefs SET revision=revision+1
                    WHERE kind='shift_profile' AND active=1 AND entity_key=NEW.profile_id;
            END;
CREATE TRIGGER IF NOT EXISTS wb_shift_periods_delete
            AFTER DELETE ON WorkbenchShiftDayPeriods BEGIN
                UPDATE WorkbenchEntityRefs SET revision=revision+1
                    WHERE kind='shift_profile' AND active=1 AND entity_key=OLD.profile_id;
            END;
CREATE TABLE IF NOT EXISTS MachineOpTypes (
            machine_id TEXT NOT NULL REFERENCES Machines(machine_id) ON DELETE CASCADE,
            op_type_id TEXT NOT NULL REFERENCES OpTypes(op_type_id),
            PRIMARY KEY(machine_id, op_type_id));
CREATE INDEX IF NOT EXISTS idx_machine_op_types_type ON MachineOpTypes(op_type_id);
CREATE TRIGGER IF NOT EXISTS wb_machine_types_insert AFTER INSERT ON MachineOpTypes BEGIN
            UPDATE WorkbenchEntityRefs SET revision=revision+1 WHERE active=1 AND ((kind='machine' AND entity_key=NEW.machine_id) OR (kind='op_type' AND entity_key=NEW.op_type_id));
        END;
CREATE TRIGGER IF NOT EXISTS wb_machine_types_update AFTER UPDATE ON MachineOpTypes BEGIN
            UPDATE WorkbenchEntityRefs SET revision=revision+1 WHERE active=1 AND ((kind='machine' AND entity_key=OLD.machine_id) OR (kind='machine' AND entity_key=NEW.machine_id) OR (kind='op_type' AND entity_key=OLD.op_type_id) OR (kind='op_type' AND entity_key=NEW.op_type_id));
        END;
CREATE TRIGGER IF NOT EXISTS wb_machine_types_delete AFTER DELETE ON MachineOpTypes BEGIN
            UPDATE WorkbenchEntityRefs SET revision=revision+1 WHERE active=1 AND ((kind='machine' AND entity_key=OLD.machine_id) OR (kind='op_type' AND entity_key=OLD.op_type_id));
        END;
CREATE TABLE IF NOT EXISTS BatchMaterialReviews (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            batch_quantity INTEGER CHECK(batch_quantity >= 0));
CREATE TABLE IF NOT EXISTS BatchMaterialStages (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            operation_id INTEGER NOT NULL REFERENCES BatchOperations(id) ON DELETE RESTRICT);
CREATE TABLE IF NOT EXISTS BatchMaterialArrivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            arrival_date TEXT NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0));
CREATE INDEX IF NOT EXISTS idx_material_arrival_requirement ON BatchMaterialArrivals(requirement_id);
CREATE TABLE IF NOT EXISTS BatchQuantitySplits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_batch_id TEXT NOT NULL REFERENCES Batches(batch_id),
            child_batch_id TEXT NOT NULL UNIQUE REFERENCES Batches(batch_id),
            original_quantity INTEGER NOT NULL,
            split_quantity INTEGER NOT NULL,
            allocation_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TRIGGER IF NOT EXISTS wb_material_quantity_basis
            AFTER UPDATE OF quantity ON Batches
            WHEN NEW.quantity IS NOT OLD.quantity
            BEGIN
                INSERT OR IGNORE INTO BatchMaterialReviews(requirement_id,batch_quantity)
                    SELECT id, CASE WHEN typeof(OLD.quantity) = 'integer' AND OLD.quantity >= 0
                        THEN OLD.quantity ELSE NULL END
                    FROM BatchMaterials WHERE batch_id = NEW.batch_id;
                UPDATE Batches SET ready_status = 'no'
                    WHERE batch_id = NEW.batch_id AND EXISTS (
                        SELECT 1 FROM BatchMaterials m
                        JOIN BatchMaterialReviews r ON r.requirement_id = m.id
                        WHERE m.batch_id = NEW.batch_id
                            AND (r.batch_quantity IS NULL OR r.batch_quantity IS NOT NEW.quantity));
            END;
CREATE TABLE IF NOT EXISTS WorkbenchSourceRevisions (
        source_key TEXT PRIMARY KEY NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision) = 'integer' AND revision >= 1)
    );
CREATE TRIGGER IF NOT EXISTS wb_src_rev_parts_insert AFTER INSERT ON "Parts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'parts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_parts_update AFTER UPDATE ON "Parts" WHEN OLD."part_no" IS NOT NEW."part_no" OR OLD."part_name" IS NOT NEW."part_name" OR OLD."route_raw" IS NOT NEW."route_raw" OR OLD."route_parsed" IS NOT NEW."route_parsed" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'parts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_parts_delete AFTER DELETE ON "Parts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'parts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_partoperations_insert AFTER INSERT ON "PartOperations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'part_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_partoperations_update AFTER UPDATE ON "PartOperations" WHEN OLD."id" IS NOT NEW."id" OR OLD."part_no" IS NOT NEW."part_no" OR OLD."seq" IS NOT NEW."seq" OR OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."op_type_name" IS NOT NEW."op_type_name" OR OLD."source" IS NOT NEW."source" OR OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."ext_days" IS NOT NEW."ext_days" OR OLD."ext_group_id" IS NOT NEW."ext_group_id" OR OLD."setup_hours" IS NOT NEW."setup_hours" OR OLD."unit_hours" IS NOT NEW."unit_hours" OR OLD."status" IS NOT NEW."status" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'part_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_partoperations_delete AFTER DELETE ON "PartOperations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'part_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_externalgroups_insert AFTER INSERT ON "ExternalGroups" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'external_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_externalgroups_update AFTER UPDATE ON "ExternalGroups" WHEN OLD."group_id" IS NOT NEW."group_id" OR OLD."part_no" IS NOT NEW."part_no" OR OLD."start_seq" IS NOT NEW."start_seq" OR OLD."end_seq" IS NOT NEW."end_seq" OR OLD."merge_mode" IS NOT NEW."merge_mode" OR OLD."total_days" IS NOT NEW."total_days" OR OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'external_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_externalgroups_delete AFTER DELETE ON "ExternalGroups" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'external_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_optypes_insert AFTER INSERT ON "OpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_optypes_update AFTER UPDATE ON "OpTypes" WHEN OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."name" IS NOT NEW."name" OR OLD."category" IS NOT NEW."category" OR OLD."default_hours" IS NOT NEW."default_hours" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_optypes_delete AFTER DELETE ON "OpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machines_insert AFTER INSERT ON "Machines" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machines_update AFTER UPDATE ON "Machines" WHEN OLD."machine_id" IS NOT NEW."machine_id" OR OLD."name" IS NOT NEW."name" OR OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."category" IS NOT NEW."category" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" OR OLD."team_id" IS NOT NEW."team_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machines_delete AFTER DELETE ON "Machines" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machineoptypes_insert AFTER INSERT ON "MachineOpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machineoptypes_update AFTER UPDATE ON "MachineOpTypes" WHEN OLD."machine_id" IS NOT NEW."machine_id" OR OLD."op_type_id" IS NOT NEW."op_type_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machineoptypes_delete AFTER DELETE ON "MachineOpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machinedowntimes_insert AFTER INSERT ON "MachineDowntimes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_downtimes'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machinedowntimes_update AFTER UPDATE ON "MachineDowntimes" WHEN OLD."id" IS NOT NEW."id" OR OLD."machine_id" IS NOT NEW."machine_id" OR OLD."scope_type" IS NOT NEW."scope_type" OR OLD."scope_value" IS NOT NEW."scope_value" OR OLD."start_time" IS NOT NEW."start_time" OR OLD."end_time" IS NOT NEW."end_time" OR OLD."reason_code" IS NOT NEW."reason_code" OR OLD."reason_detail" IS NOT NEW."reason_detail" OR OLD."status" IS NOT NEW."status" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_downtimes'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_machinedowntimes_delete AFTER DELETE ON "MachineDowntimes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'machine_downtimes'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operators_insert AFTER INSERT ON "Operators" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operators'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operators_update AFTER UPDATE ON "Operators" WHEN OLD."operator_id" IS NOT NEW."operator_id" OR OLD."name" IS NOT NEW."name" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" OR OLD."team_id" IS NOT NEW."team_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operators'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operators_delete AFTER DELETE ON "Operators" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operators'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorskill_insert AFTER INSERT ON "OperatorSkill" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_skills'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorskill_update AFTER UPDATE ON "OperatorSkill" WHEN OLD."id" IS NOT NEW."id" OR OLD."operator_id" IS NOT NEW."operator_id" OR OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."skill_level" IS NOT NEW."skill_level" OR OLD."is_primary" IS NOT NEW."is_primary" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_skills'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorskill_delete AFTER DELETE ON "OperatorSkill" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_skills'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatormachine_insert AFTER INSERT ON "OperatorMachine" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatormachine_update AFTER UPDATE ON "OperatorMachine" WHEN OLD."id" IS NOT NEW."id" OR OLD."operator_id" IS NOT NEW."operator_id" OR OLD."machine_id" IS NOT NEW."machine_id" OR OLD."skill_level" IS NOT NEW."skill_level" OR OLD."is_primary" IS NOT NEW."is_primary" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatormachine_delete AFTER DELETE ON "OperatorMachine" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_machines'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_materials_insert AFTER INSERT ON "Materials" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_materials_update AFTER UPDATE ON "Materials" WHEN OLD."material_id" IS NOT NEW."material_id" OR OLD."name" IS NOT NEW."name" OR OLD."spec" IS NOT NEW."spec" OR OLD."unit" IS NOT NEW."unit" OR OLD."stock_qty" IS NOT NEW."stock_qty" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_materials_delete AFTER DELETE ON "Materials" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_suppliers_insert AFTER INSERT ON "Suppliers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_suppliers_update AFTER UPDATE ON "Suppliers" WHEN OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."name" IS NOT NEW."name" OR OLD."default_days" IS NOT NEW."default_days" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_suppliers_delete AFTER DELETE ON "Suppliers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workcalendar_insert AFTER INSERT ON "WorkCalendar" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'work_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workcalendar_update AFTER UPDATE ON "WorkCalendar" WHEN OLD."date" IS NOT NEW."date" OR OLD."day_type" IS NOT NEW."day_type" OR OLD."shift_start" IS NOT NEW."shift_start" OR OLD."shift_end" IS NOT NEW."shift_end" OR OLD."shift_hours" IS NOT NEW."shift_hours" OR OLD."efficiency" IS NOT NEW."efficiency" OR OLD."allow_normal" IS NOT NEW."allow_normal" OR OLD."allow_urgent" IS NOT NEW."allow_urgent" OR OLD."remark" IS NOT NEW."remark" OR OLD."periods_json" IS NOT NEW."periods_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'work_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workcalendar_delete AFTER DELETE ON "WorkCalendar" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'work_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorcalendar_insert AFTER INSERT ON "OperatorCalendar" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorcalendar_update AFTER UPDATE ON "OperatorCalendar" WHEN OLD."operator_id" IS NOT NEW."operator_id" OR OLD."date" IS NOT NEW."date" OR OLD."day_type" IS NOT NEW."day_type" OR OLD."shift_start" IS NOT NEW."shift_start" OR OLD."shift_end" IS NOT NEW."shift_end" OR OLD."shift_hours" IS NOT NEW."shift_hours" OR OLD."efficiency" IS NOT NEW."efficiency" OR OLD."allow_normal" IS NOT NEW."allow_normal" OR OLD."allow_urgent" IS NOT NEW."allow_urgent" OR OLD."remark" IS NOT NEW."remark" OR OLD."periods_json" IS NOT NEW."periods_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_operatorcalendar_delete AFTER DELETE ON "OperatorCalendar" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'operator_calendar'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_resourceteams_insert AFTER INSERT ON "ResourceTeams" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'resource_teams'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_resourceteams_update AFTER UPDATE ON "ResourceTeams" WHEN OLD."team_id" IS NOT NEW."team_id" OR OLD."name" IS NOT NEW."name" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'resource_teams'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_resourceteams_delete AFTER DELETE ON "ResourceTeams" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'resource_teams'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoperatorprofiles_insert AFTER INSERT ON "WorkbenchOperatorProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_operator_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoperatorprofiles_update AFTER UPDATE ON "WorkbenchOperatorProfiles" WHEN OLD."operator_id" IS NOT NEW."operator_id" OR OLD."shift_profile_id" IS NOT NEW."shift_profile_id" OR OLD."skills_declared" IS NOT NEW."skills_declared" OR OLD."inactive_reason" IS NOT NEW."inactive_reason" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_operator_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoperatorprofiles_delete AFTER DELETE ON "WorkbenchOperatorProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_operator_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplieroptypes_insert AFTER INSERT ON "WorkbenchSupplierOpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplieroptypes_update AFTER UPDATE ON "WorkbenchSupplierOpTypes" WHEN OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."op_type_id" IS NOT NEW."op_type_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplieroptypes_delete AFTER DELETE ON "WorkbenchSupplierOpTypes" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplierprofiles_insert AFTER INSERT ON "WorkbenchSupplierProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplierprofiles_update AFTER UPDATE ON "WorkbenchSupplierProfiles" WHEN OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."inactive_reason" IS NOT NEW."inactive_reason" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchsupplierprofiles_delete AFTER DELETE ON "WorkbenchSupplierProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_supplier_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroups_insert AFTER INSERT ON "WorkbenchMachineGroups" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroups_update AFTER UPDATE ON "WorkbenchMachineGroups" WHEN OLD."group_id" IS NOT NEW."group_id" OR OLD."name" IS NOT NEW."name" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroups_delete AFTER DELETE ON "WorkbenchMachineGroups" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_groups'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroupmembers_insert AFTER INSERT ON "WorkbenchMachineGroupMembers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_group_members'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroupmembers_update AFTER UPDATE ON "WorkbenchMachineGroupMembers" WHEN OLD."machine_id" IS NOT NEW."machine_id" OR OLD."group_id" IS NOT NEW."group_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_group_members'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchmachinegroupmembers_delete AFTER DELETE ON "WorkbenchMachineGroupMembers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_machine_group_members'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftprofiles_insert AFTER INSERT ON "WorkbenchShiftProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftprofiles_update AFTER UPDATE ON "WorkbenchShiftProfiles" WHEN OLD."profile_id" IS NOT NEW."profile_id" OR OLD."name" IS NOT NEW."name" OR OLD."anchor_date" IS NOT NEW."anchor_date" OR OLD."cycle_days" IS NOT NEW."cycle_days" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftprofiles_delete AFTER DELETE ON "WorkbenchShiftProfiles" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_profiles'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftpatterndays_insert AFTER INSERT ON "WorkbenchShiftPatternDays" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_pattern_days'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftpatterndays_update AFTER UPDATE ON "WorkbenchShiftPatternDays" WHEN OLD."profile_id" IS NOT NEW."profile_id" OR OLD."day_offset" IS NOT NEW."day_offset" OR OLD."is_rest" IS NOT NEW."is_rest" OR OLD."shift_start" IS NOT NEW."shift_start" OR OLD."shift_end" IS NOT NEW."shift_end" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_pattern_days'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftpatterndays_delete AFTER DELETE ON "WorkbenchShiftPatternDays" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_pattern_days'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftdayperiods_insert AFTER INSERT ON "WorkbenchShiftDayPeriods" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_day_periods'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftdayperiods_update AFTER UPDATE ON "WorkbenchShiftDayPeriods" WHEN OLD."profile_id" IS NOT NEW."profile_id" OR OLD."day_offset" IS NOT NEW."day_offset" OR OLD."periods_json" IS NOT NEW."periods_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_day_periods'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchshiftdayperiods_delete AFTER DELETE ON "WorkbenchShiftDayPeriods" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_shift_day_periods'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalendardefaults_insert AFTER INSERT ON "WorkbenchCalendarDefaults" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_calendar_defaults'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalendardefaults_update AFTER UPDATE ON "WorkbenchCalendarDefaults" WHEN OLD."singleton" IS NOT NEW."singleton" OR OLD."state_ref" IS NOT NEW."state_ref" OR OLD."revision" IS NOT NEW."revision" OR OLD."periods_json" IS NOT NEW."periods_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_calendar_defaults'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalendardefaults_delete AFTER DELETE ON "WorkbenchCalendarDefaults" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_calendar_defaults'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoptypepolicies_insert AFTER INSERT ON "WorkbenchOpTypePolicies" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_op_type_policies'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoptypepolicies_update AFTER UPDATE ON "WorkbenchOpTypePolicies" WHEN OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."default_merge_mode" IS NOT NEW."default_merge_mode" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_op_type_policies'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoptypepolicies_delete AFTER DELETE ON "WorkbenchOpTypePolicies" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_op_type_policies'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchentityrefs_insert AFTER INSERT ON "WorkbenchEntityRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_entity_refs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchentityrefs_update AFTER UPDATE ON "WorkbenchEntityRefs" WHEN OLD."ref" IS NOT NEW."ref" OR OLD."kind" IS NOT NEW."kind" OR OLD."entity_key" IS NOT NEW."entity_key" OR OLD."alternate_key" IS NOT NEW."alternate_key" OR OLD."revision" IS NOT NEW."revision" OR OLD."active" IS NOT NEW."active" OR OLD."created_at_utc" IS NOT NEW."created_at_utc" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_entity_refs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchentityrefs_delete AFTER DELETE ON "WorkbenchEntityRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_entity_refs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batches_insert AFTER INSERT ON "Batches" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batches'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batches_update AFTER UPDATE ON "Batches" WHEN OLD."batch_id" IS NOT NEW."batch_id" OR OLD."part_no" IS NOT NEW."part_no" OR OLD."part_name" IS NOT NEW."part_name" OR OLD."quantity" IS NOT NEW."quantity" OR OLD."due_date" IS NOT NEW."due_date" OR OLD."priority" IS NOT NEW."priority" OR OLD."ready_status" IS NOT NEW."ready_status" OR OLD."ready_date" IS NOT NEW."ready_date" OR OLD."status" IS NOT NEW."status" OR OLD."remark" IS NOT NEW."remark" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batches'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batches_delete AFTER DELETE ON "Batches" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batches'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchoperations_insert AFTER INSERT ON "BatchOperations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchoperations_update AFTER UPDATE ON "BatchOperations" WHEN OLD."id" IS NOT NEW."id" OR OLD."op_code" IS NOT NEW."op_code" OR OLD."batch_id" IS NOT NEW."batch_id" OR OLD."piece_id" IS NOT NEW."piece_id" OR OLD."seq" IS NOT NEW."seq" OR OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."op_type_name" IS NOT NEW."op_type_name" OR OLD."source" IS NOT NEW."source" OR OLD."machine_id" IS NOT NEW."machine_id" OR OLD."operator_id" IS NOT NEW."operator_id" OR OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."setup_hours" IS NOT NEW."setup_hours" OR OLD."unit_hours" IS NOT NEW."unit_hours" OR OLD."ext_days" IS NOT NEW."ext_days" OR OLD."status" IS NOT NEW."status" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchoperations_delete AFTER DELETE ON "BatchOperations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_operations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchexternalcontexts_insert AFTER INSERT ON "BatchExternalContexts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_external_contexts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchexternalcontexts_update AFTER UPDATE ON "BatchExternalContexts" WHEN OLD."operation_id" IS NOT NEW."operation_id" OR OLD."part_no" IS NOT NEW."part_no" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."template_operation_id" IS NOT NEW."template_operation_id" OR OLD."template_status" IS NOT NEW."template_status" OR OLD."group_id" IS NOT NEW."group_id" OR OLD."group_part_no" IS NOT NEW."group_part_no" OR OLD."start_sequence" IS NOT NEW."start_sequence" OR OLD."end_sequence" IS NOT NEW."end_sequence" OR OLD."merge_mode" IS NOT NEW."merge_mode" OR OLD."total_days" IS NOT NEW."total_days" OR OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."group_ref" IS NOT NEW."group_ref" OR OLD."template_operation_ref" IS NOT NEW."template_operation_ref" OR OLD."origin" IS NOT NEW."origin" OR OLD."captured_at" IS NOT NEW."captured_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_external_contexts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchexternalcontexts_delete AFTER DELETE ON "BatchExternalContexts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_external_contexts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterials_insert AFTER INSERT ON "BatchMaterials" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterials_update AFTER UPDATE ON "BatchMaterials" WHEN OLD."id" IS NOT NEW."id" OR OLD."batch_id" IS NOT NEW."batch_id" OR OLD."material_id" IS NOT NEW."material_id" OR OLD."required_qty" IS NOT NEW."required_qty" OR OLD."available_qty" IS NOT NEW."available_qty" OR OLD."ready_status" IS NOT NEW."ready_status" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterials_delete AFTER DELETE ON "BatchMaterials" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_materials'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialreviews_insert AFTER INSERT ON "BatchMaterialReviews" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_reviews'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialreviews_update AFTER UPDATE ON "BatchMaterialReviews" WHEN OLD."requirement_id" IS NOT NEW."requirement_id" OR OLD."batch_quantity" IS NOT NEW."batch_quantity" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_reviews'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialreviews_delete AFTER DELETE ON "BatchMaterialReviews" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_reviews'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialstages_insert AFTER INSERT ON "BatchMaterialStages" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_stages'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialstages_update AFTER UPDATE ON "BatchMaterialStages" WHEN OLD."requirement_id" IS NOT NEW."requirement_id" OR OLD."operation_id" IS NOT NEW."operation_id" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_stages'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialstages_delete AFTER DELETE ON "BatchMaterialStages" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_stages'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialarrivals_insert AFTER INSERT ON "BatchMaterialArrivals" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_arrivals'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialarrivals_update AFTER UPDATE ON "BatchMaterialArrivals" WHEN OLD."id" IS NOT NEW."id" OR OLD."requirement_id" IS NOT NEW."requirement_id" OR OLD."arrival_date" IS NOT NEW."arrival_date" OR OLD."quantity" IS NOT NEW."quantity" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_arrivals'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchmaterialarrivals_delete AFTER DELETE ON "BatchMaterialArrivals" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_material_arrivals'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchquantitysplits_insert AFTER INSERT ON "BatchQuantitySplits" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_quantity_splits'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchquantitysplits_update AFTER UPDATE ON "BatchQuantitySplits" WHEN OLD."id" IS NOT NEW."id" OR OLD."source_batch_id" IS NOT NEW."source_batch_id" OR OLD."child_batch_id" IS NOT NEW."child_batch_id" OR OLD."original_quantity" IS NOT NEW."original_quantity" OR OLD."split_quantity" IS NOT NEW."split_quantity" OR OLD."allocation_date" IS NOT NEW."allocation_date" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_quantity_splits'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_batchquantitysplits_delete AFTER DELETE ON "BatchQuantitySplits" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'batch_quantity_splits'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessworkflow_insert AFTER INSERT ON "WorkbenchProcessWorkflow" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_workflow'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessworkflow_update AFTER UPDATE ON "WorkbenchProcessWorkflow" WHEN OLD."part_ref" IS NOT NEW."part_ref" OR OLD."route_confirmed_at" IS NOT NEW."route_confirmed_at" OR OLD."route_confirmed_by" IS NOT NEW."route_confirmed_by" OR OLD."route_content_json" IS NOT NEW."route_content_json" OR OLD."source_confirmed_at" IS NOT NEW."source_confirmed_at" OR OLD."source_confirmed_by" IS NOT NEW."source_confirmed_by" OR OLD."source_content_json" IS NOT NEW."source_content_json" OR OLD."hours_confirmed_at" IS NOT NEW."hours_confirmed_at" OR OLD."hours_confirmed_by" IS NOT NEW."hours_confirmed_by" OR OLD."hours_content_json" IS NOT NEW."hours_content_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_workflow'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessworkflow_delete AFTER DELETE ON "WorkbenchProcessWorkflow" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_workflow'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessoperationconfirmations_insert AFTER INSERT ON "WorkbenchProcessOperationConfirmations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_operation_confirmations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessoperationconfirmations_update AFTER UPDATE ON "WorkbenchProcessOperationConfirmations" WHEN OLD."part_ref" IS NOT NEW."part_ref" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."stage" IS NOT NEW."stage" OR OLD."confirmed_at" IS NOT NEW."confirmed_at" OR OLD."confirmed_by" IS NOT NEW."confirmed_by" OR OLD."content_json" IS NOT NEW."content_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_operation_confirmations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchprocessoperationconfirmations_delete AFTER DELETE ON "WorkbenchProcessOperationConfirmations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_process_operation_confirmations'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageorigins_insert AFTER INSERT ON "WorkbenchTemplateLineageOrigins" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageorigins_update AFTER UPDATE ON "WorkbenchTemplateLineageOrigins" WHEN OLD."lineage_ref" IS NOT NEW."lineage_ref" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."template_operation_ref" IS NOT NEW."template_operation_ref" OR OLD."template_revision" IS NOT NEW."template_revision" OR OLD."source_operation_ref" IS NOT NEW."source_operation_ref" OR OLD."source_lineage_ref" IS NOT NEW."source_lineage_ref" OR OLD."source_event_id" IS NOT NEW."source_event_id" OR OLD."source_eligible" IS NOT NEW."source_eligible" OR OLD."birth_event_id" IS NOT NEW."birth_event_id" OR OLD."evidence_version" IS NOT NEW."evidence_version" OR OLD."template_snapshot" IS NOT NEW."template_snapshot" OR OLD."instance_snapshot" IS NOT NEW."instance_snapshot" OR OLD."recorded_at_utc" IS NOT NEW."recorded_at_utc" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageorigins_delete AFTER DELETE ON "WorkbenchTemplateLineageOrigins" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageevents_insert AFTER INSERT ON "WorkbenchTemplateLineageEvents" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageevents_update AFTER UPDATE ON "WorkbenchTemplateLineageEvents" WHEN OLD."event_id" IS NOT NEW."event_id" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."event_type" IS NOT NEW."event_type" OR OLD."affects_calibration" IS NOT NEW."affects_calibration" OR OLD."reason" IS NOT NEW."reason" OR OLD."recorded_at_utc" IS NOT NEW."recorded_at_utc" OR OLD."id" IS NOT NEW."id" OR OLD."op_code" IS NOT NEW."op_code" OR OLD."batch_id" IS NOT NEW."batch_id" OR OLD."piece_id" IS NOT NEW."piece_id" OR OLD."seq" IS NOT NEW."seq" OR OLD."op_type_id" IS NOT NEW."op_type_id" OR OLD."op_type_name" IS NOT NEW."op_type_name" OR OLD."source" IS NOT NEW."source" OR OLD."machine_id" IS NOT NEW."machine_id" OR OLD."operator_id" IS NOT NEW."operator_id" OR OLD."supplier_id" IS NOT NEW."supplier_id" OR OLD."setup_hours" IS NOT NEW."setup_hours" OR OLD."unit_hours" IS NOT NEW."unit_hours" OR OLD."ext_days" IS NOT NEW."ext_days" OR OLD."status" IS NOT NEW."status" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."batch_ref" IS NOT NEW."batch_ref" OR OLD."part_ref" IS NOT NEW."part_ref" OR OLD."quantity" IS NOT NEW."quantity" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtemplatelineageevents_delete AFTER DELETE ON "WorkbenchTemplateLineageEvents" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_template_lineage'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedulehistory_insert AFTER INSERT ON "ScheduleHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_history'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedulehistory_update AFTER UPDATE ON "ScheduleHistory" WHEN OLD."id" IS NOT NEW."id" OR OLD."schedule_time" IS NOT NEW."schedule_time" OR OLD."version" IS NOT NEW."version" OR OLD."strategy" IS NOT NEW."strategy" OR OLD."batch_count" IS NOT NEW."batch_count" OR OLD."op_count" IS NOT NEW."op_count" OR OLD."result_status" IS NOT NEW."result_status" OR OLD."result_summary" IS NOT NEW."result_summary" OR OLD."created_by" IS NOT NEW."created_by" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_history'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedulehistory_delete AFTER DELETE ON "ScheduleHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_history'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleversionseq_insert AFTER INSERT ON "ScheduleVersionSeq" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_version_seq'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleversionseq_update AFTER UPDATE ON "ScheduleVersionSeq" WHEN OLD."version" IS NOT NEW."version" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_version_seq'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleversionseq_delete AFTER DELETE ON "ScheduleVersionSeq" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_version_seq'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleconfig_insert AFTER INSERT ON "ScheduleConfig" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleconfig_update AFTER UPDATE ON "ScheduleConfig" WHEN OLD."id" IS NOT NEW."id" OR OLD."config_key" IS NOT NEW."config_key" OR OLD."config_value" IS NOT NEW."config_value" OR OLD."description" IS NOT NEW."description" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduleconfig_delete AFTER DELETE ON "ScheduleConfig" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplansourcerefs_insert AFTER INSERT ON "WorkbenchPlanSourceRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplansourcerefs_update AFTER UPDATE ON "WorkbenchPlanSourceRefs" WHEN OLD."ref" IS NOT NEW."ref" OR OLD."kind" IS NOT NEW."kind" OR OLD."source_key" IS NOT NEW."source_key" OR OLD."alternate_key" IS NOT NEW."alternate_key" OR OLD."extra_key" IS NOT NEW."extra_key" OR OLD."version" IS NOT NEW."version" OR OLD."plan_role" IS NOT NEW."plan_role" OR OLD."source_table" IS NOT NEW."source_table" OR OLD."owner_key" IS NOT NEW."owner_key" OR OLD."operation_id" IS NOT NEW."operation_id" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."active" IS NOT NEW."active" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplansourcerefs_delete AFTER DELETE ON "WorkbenchPlanSourceRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtaskrefs_insert AFTER INSERT ON "WorkbenchTaskRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtaskrefs_update AFTER UPDATE ON "WorkbenchTaskRefs" WHEN OLD."ref" IS NOT NEW."ref" OR OLD."plan_ref" IS NOT NEW."plan_ref" OR OLD."row_ref" IS NOT NEW."row_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtaskrefs_delete AFTER DELETE ON "WorkbenchTaskRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplanidentityclock_insert AFTER INSERT ON "WorkbenchPlanIdentityClock" WHEN NEW."singleton" IS NOT 1 OR NEW."revision" IS NOT 1 BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplanidentityclock_update AFTER UPDATE ON "WorkbenchPlanIdentityClock" WHEN OLD."singleton" IS NOT NEW."singleton" OR OLD."revision" IS NOT NEW."revision" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchplanidentityclock_delete AFTER DELETE ON "WorkbenchPlanIdentityClock" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'workbench_plan_identity'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchexecutionledgerclock_insert AFTER INSERT ON "WorkbenchExecutionLedgerClock" WHEN NEW."singleton" IS NOT 1 OR NEW."revision" IS NOT 1 OR NEW."next_report_no" IS NOT 1 BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchexecutionledgerclock_update AFTER UPDATE ON "WorkbenchExecutionLedgerClock" WHEN OLD."singleton" IS NOT NEW."singleton" OR OLD."revision" IS NOT NEW."revision" OR OLD."next_report_no" IS NOT NEW."next_report_no" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchexecutionledgerclock_delete AFTER DELETE ON "WorkbenchExecutionLedgerClock" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreports_insert AFTER INSERT ON "WorkbenchProductionReports" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreports_update AFTER UPDATE ON "WorkbenchProductionReports" WHEN OLD."report_ref" IS NOT NEW."report_ref" OR OLD."report_no" IS NOT NEW."report_no" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."recorded_against_task_ref" IS NOT NEW."recorded_against_task_ref" OR OLD."recorded_against_plan_ref" IS NOT NEW."recorded_against_plan_ref" OR OLD."source" IS NOT NEW."source" OR OLD."recorded_at" IS NOT NEW."recorded_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreports_delete AFTER DELETE ON "WorkbenchProductionReports" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportrevisions_insert AFTER INSERT ON "WorkbenchProductionReportRevisions" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportrevisions_update AFTER UPDATE ON "WorkbenchProductionReportRevisions" WHEN OLD."revision_ref" IS NOT NEW."revision_ref" OR OLD."report_ref" IS NOT NEW."report_ref" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."previous_revision_ref" IS NOT NEW."previous_revision_ref" OR OLD."action" IS NOT NEW."action" OR OLD."values_json" IS NOT NEW."values_json" OR OLD."reason" IS NOT NEW."reason" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."declared_operator" IS NOT NEW."declared_operator" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportrevisions_delete AFTER DELETE ON "WorkbenchProductionReportRevisions" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportvoids_insert AFTER INSERT ON "WorkbenchProductionReportVoids" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportvoids_update AFTER UPDATE ON "WorkbenchProductionReportVoids" WHEN OLD."void_fact_ref" IS NOT NEW."void_fact_ref" OR OLD."report_ref" IS NOT NEW."report_ref" OR OLD."original_revision_ref" IS NOT NEW."original_revision_ref" OR OLD."reason" IS NOT NEW."reason" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."declared_operator" IS NOT NEW."declared_operator" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchproductionreportvoids_delete AFTER DELETE ON "WorkbenchProductionReportVoids" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'execution_ledger'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingoperationorigins_insert AFTER INSERT ON "WorkbenchOutsourcingOperationOrigins" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingoperationorigins_update AFTER UPDATE ON "WorkbenchOutsourcingOperationOrigins" WHEN OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."batch_ref" IS NOT NEW."batch_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingoperationorigins_delete AFTER DELETE ON "WorkbenchOutsourcingOperationOrigins" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingsourceconfirmations_insert AFTER INSERT ON "WorkbenchOutsourcingSourceConfirmations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingsourceconfirmations_update AFTER UPDATE ON "WorkbenchOutsourcingSourceConfirmations" WHEN OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."batch_ref" IS NOT NEW."batch_ref" OR OLD."fact_ref" IS NOT NEW."fact_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingsourceconfirmations_delete AFTER DELETE ON "WorkbenchOutsourcingSourceConfirmations" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingmembers_insert AFTER INSERT ON "WorkbenchOutsourcingMembers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingmembers_update AFTER UPDATE ON "WorkbenchOutsourcingMembers" WHEN OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."outsourcing_ref" IS NOT NEW."outsourcing_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingmembers_delete AFTER DELETE ON "WorkbenchOutsourcingMembers" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingreceipts_insert AFTER INSERT ON "WorkbenchOutsourcingReceipts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingreceipts_update AFTER UPDATE ON "WorkbenchOutsourcingReceipts" WHEN OLD."outsourcing_ref" IS NOT NEW."outsourcing_ref" OR OLD."target_kind" IS NOT NEW."target_kind" OR OLD."batch_ref" IS NOT NEW."batch_ref" OR OLD."supplier_ref" IS NOT NEW."supplier_ref" OR OLD."origin_json" IS NOT NEW."origin_json" OR OLD."identity_json" IS NOT NEW."identity_json" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingreceipts_delete AFTER DELETE ON "WorkbenchOutsourcingReceipts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingfacts_insert AFTER INSERT ON "WorkbenchOutsourcingFacts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingfacts_update AFTER UPDATE ON "WorkbenchOutsourcingFacts" WHEN OLD."fact_ref" IS NOT NEW."fact_ref" OR OLD."outsourcing_ref" IS NOT NEW."outsourcing_ref" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."previous_fact_ref" IS NOT NEW."previous_fact_ref" OR OLD."sent" IS NOT NEW."sent" OR OLD."planned" IS NOT NEW."planned" OR OLD."returned" IS NOT NEW."returned" OR OLD."confirmed_state" IS NOT NEW."confirmed_state" OR OLD."declared_operator" IS NOT NEW."declared_operator" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."reason" IS NOT NEW."reason" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."before_json" IS NOT NEW."before_json" OR OLD."source_facts_json" IS NOT NEW."source_facts_json" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchoutsourcingfacts_delete AFTER DELETE ON "WorkbenchOutsourcingFacts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'outsourcing'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarditems_insert AFTER INSERT ON "WorkbenchDashboardItems" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarditems_update AFTER UPDATE ON "WorkbenchDashboardItems" WHEN OLD."item_ref" IS NOT NEW."item_ref" OR OLD."category" IS NOT NEW."category" OR OLD."batch_ref" IS NOT NEW."batch_ref" OR OLD."task_ref" IS NOT NEW."task_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarditems_delete AFTER DELETE ON "WorkbenchDashboardItems" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarddowntimerefs_insert AFTER INSERT ON "WorkbenchDashboardDowntimeRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarddowntimerefs_update AFTER UPDATE ON "WorkbenchDashboardDowntimeRefs" WHEN OLD."ref" IS NOT NEW."ref" OR OLD."source_id" IS NOT NEW."source_id" OR OLD."active" IS NOT NEW."active" OR OLD."revision" IS NOT NEW."revision" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboarddowntimerefs_delete AFTER DELETE ON "WorkbenchDashboardDowntimeRefs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalitems_insert AFTER INSERT ON "WorkbenchDashboardExternalItems" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalitems_update AFTER UPDATE ON "WorkbenchDashboardExternalItems" WHEN OLD."item_ref" IS NOT NEW."item_ref" OR OLD."category" IS NOT NEW."category" OR OLD."outsourcing_ref" IS NOT NEW."outsourcing_ref" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalitems_delete AFTER DELETE ON "WorkbenchDashboardExternalItems" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_items'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardstates_insert AFTER INSERT ON "WorkbenchDashboardStates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardstates_update AFTER UPDATE ON "WorkbenchDashboardStates" WHEN OLD."item_ref" IS NOT NEW."item_ref" OR OLD."revision" IS NOT NEW."revision" OR OLD."handling_json" IS NOT NEW."handling_json" OR OLD."origin_json" IS NOT NEW."origin_json" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardstates_delete AFTER DELETE ON "WorkbenchDashboardStates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardhistory_insert AFTER INSERT ON "WorkbenchDashboardHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardhistory_update AFTER UPDATE ON "WorkbenchDashboardHistory" WHEN OLD."history_ref" IS NOT NEW."history_ref" OR OLD."item_ref" IS NOT NEW."item_ref" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."action" IS NOT NEW."action" OR OLD."before_json" IS NOT NEW."before_json" OR OLD."after_json" IS NOT NEW."after_json" OR OLD."source_json" IS NOT NEW."source_json" OR OLD."source_facts_json" IS NOT NEW."source_facts_json" OR OLD."reason" IS NOT NEW."reason" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardhistory_delete AFTER DELETE ON "WorkbenchDashboardHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalstates_insert AFTER INSERT ON "WorkbenchDashboardExternalStates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalstates_update AFTER UPDATE ON "WorkbenchDashboardExternalStates" WHEN OLD."item_ref" IS NOT NEW."item_ref" OR OLD."revision" IS NOT NEW."revision" OR OLD."handling_json" IS NOT NEW."handling_json" OR OLD."origin_json" IS NOT NEW."origin_json" OR OLD."updated_at" IS NOT NEW."updated_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalstates_delete AFTER DELETE ON "WorkbenchDashboardExternalStates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalhistory_insert AFTER INSERT ON "WorkbenchDashboardExternalHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalhistory_update AFTER UPDATE ON "WorkbenchDashboardExternalHistory" WHEN OLD."history_ref" IS NOT NEW."history_ref" OR OLD."item_ref" IS NOT NEW."item_ref" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."action" IS NOT NEW."action" OR OLD."before_json" IS NOT NEW."before_json" OR OLD."after_json" IS NOT NEW."after_json" OR OLD."source_json" IS NOT NEW."source_json" OR OLD."source_facts_json" IS NOT NEW."source_facts_json" OR OLD."reason" IS NOT NEW."reason" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchdashboardexternalhistory_delete AFTER DELETE ON "WorkbenchDashboardExternalHistory" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'dashboard_handling'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalibrationadoptions_insert AFTER INSERT ON "WorkbenchCalibrationAdoptions" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'calibration_adoptions'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalibrationadoptions_update AFTER UPDATE ON "WorkbenchCalibrationAdoptions" WHEN OLD."adoption_ref" IS NOT NEW."adoption_ref" OR OLD."template_operation_ref" IS NOT NEW."template_operation_ref" OR OLD."request_key" IS NOT NEW."request_key" OR OLD."template_revision_before" IS NOT NEW."template_revision_before" OR OLD."template_revision_after" IS NOT NEW."template_revision_after" OR OLD."old_unit_hours" IS NOT NEW."old_unit_hours" OR OLD."new_unit_hours" IS NOT NEW."new_unit_hours" OR OLD."reason" IS NOT NEW."reason" OR OLD."declared_operator" IS NOT NEW."declared_operator" OR OLD."confirmed" IS NOT NEW."confirmed" OR OLD."application_operator" IS NOT NEW."application_operator" OR OLD."adopted_at" IS NOT NEW."adopted_at" OR OLD."generated_at" IS NOT NEW."generated_at" OR OLD."method_version" IS NOT NEW."method_version" OR OLD."sample_count" IS NOT NEW."sample_count" OR OLD."evidence_json" IS NOT NEW."evidence_json" OR OLD."template_before" IS NOT NEW."template_before" OR OLD."template_after" IS NOT NEW."template_after" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'calibration_adoptions'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchcalibrationadoptions_delete AFTER DELETE ON "WorkbenchCalibrationAdoptions" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'calibration_adoptions'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunjobs_insert AFTER INSERT ON "WorkbenchRunJobs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunjobs_update AFTER UPDATE ON "WorkbenchRunJobs" WHEN OLD."run_ref" IS NOT NEW."run_ref" OR OLD."request_key" IS NOT NEW."request_key" OR OLD."input_ref" IS NOT NEW."input_ref" OR OLD."normalized_input_json" IS NOT NEW."normalized_input_json" OR OLD."facts_json" IS NOT NEW."facts_json" OR OLD."execution_json" IS NOT NEW."execution_json" OR OLD."baseline_json" IS NOT NEW."baseline_json" OR OLD."accepted_at" IS NOT NEW."accepted_at" OR OLD."state" IS NOT NEW."state" OR OLD."stage" IS NOT NEW."stage" OR OLD."executor_ref" IS NOT NEW."executor_ref" OR OLD."started_at" IS NOT NEW."started_at" OR OLD."finished_at" IS NOT NEW."finished_at" OR OLD."error_json" IS NOT NEW."error_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunjobs_delete AFTER DELETE ON "WorkbenchRunJobs" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunreceipts_insert AFTER INSERT ON "WorkbenchRunReceipts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunreceipts_update AFTER UPDATE ON "WorkbenchRunReceipts" WHEN OLD."receipt_ref" IS NOT NEW."receipt_ref" OR OLD."run_ref" IS NOT NEW."run_ref" OR OLD."state" IS NOT NEW."state" OR OLD."result_json" IS NOT NEW."result_json" OR OLD."recorded_at" IS NOT NEW."recorded_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunreceipts_delete AFTER DELETE ON "WorkbenchRunReceipts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidates_insert AFTER INSERT ON "WorkbenchRunCandidates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidates_update AFTER UPDATE ON "WorkbenchRunCandidates" WHEN OLD."candidate_ref" IS NOT NEW."candidate_ref" OR OLD."run_ref" IS NOT NEW."run_ref" OR OLD."candidate_key" IS NOT NEW."candidate_key" OR OLD."sequence" IS NOT NEW."sequence" OR OLD."status" IS NOT NEW."status" OR OLD."task_count" IS NOT NEW."task_count" OR OLD."artifact_json" IS NOT NEW."artifact_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidates_delete AFTER DELETE ON "WorkbenchRunCandidates" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatetasks_insert AFTER INSERT ON "WorkbenchRunCandidateTasks" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatetasks_update AFTER UPDATE ON "WorkbenchRunCandidateTasks" WHEN OLD."row_ref" IS NOT NEW."row_ref" OR OLD."candidate_ref" IS NOT NEW."candidate_ref" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."ordinal" IS NOT NEW."ordinal" OR OLD."payload_json" IS NOT NEW."payload_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatetasks_delete AFTER DELETE ON "WorkbenchRunCandidateTasks" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunadmissionreadmodels_insert AFTER INSERT ON "WorkbenchRunAdmissionReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunadmissionreadmodels_update AFTER UPDATE ON "WorkbenchRunAdmissionReadModels" WHEN OLD."run_ref" IS NOT NEW."run_ref" OR OLD."projection_version" IS NOT NEW."projection_version" OR OLD."scope_json" IS NOT NEW."scope_json" OR OLD."decision_json" IS NOT NEW."decision_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrunadmissionreadmodels_delete AFTER DELETE ON "WorkbenchRunAdmissionReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrundecisionreadmodels_insert AFTER INSERT ON "WorkbenchRunDecisionReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrundecisionreadmodels_update AFTER UPDATE ON "WorkbenchRunDecisionReadModels" WHEN OLD."run_ref" IS NOT NEW."run_ref" OR OLD."projection_version" IS NOT NEW."projection_version" OR OLD."header_json" IS NOT NEW."header_json" OR OLD."context_json" IS NOT NEW."context_json" OR OLD."memberships_json" IS NOT NEW."memberships_json" OR OLD."calendar_json" IS NOT NEW."calendar_json" OR OLD."official_json" IS NOT NEW."official_json" OR OLD."process_json" IS NOT NEW."process_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchrundecisionreadmodels_delete AFTER DELETE ON "WorkbenchRunDecisionReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatereadmodels_insert AFTER INSERT ON "WorkbenchRunCandidateReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatereadmodels_update AFTER UPDATE ON "WorkbenchRunCandidateReadModels" WHEN OLD."candidate_ref" IS NOT NEW."candidate_ref" OR OLD."run_ref" IS NOT NEW."run_ref" OR OLD."projection_version" IS NOT NEW."projection_version" OR OLD."summary_json" IS NOT NEW."summary_json" OR OLD."preparation_json" IS NOT NEW."preparation_json" OR OLD."completion_json" IS NOT NEW."completion_json" OR OLD."delivery_json" IS NOT NEW."delivery_json" OR OLD."delivery_detail_json" IS NOT NEW."delivery_detail_json" OR OLD."arrangements_json" IS NOT NEW."arrangements_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchruncandidatereadmodels_delete AFTER DELETE ON "WorkbenchRunCandidateReadModels" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'run_jobs'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialdrafts_insert AFTER INSERT ON "WorkbenchTrialDrafts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialdrafts_update AFTER UPDATE ON "WorkbenchTrialDrafts" WHEN OLD."draft_ref" IS NOT NEW."draft_ref" OR OLD."base_kind" IS NOT NEW."base_kind" OR OLD."base_ref" IS NOT NEW."base_ref" OR OLD."admission_json" IS NOT NEW."admission_json" OR OLD."row_count" IS NOT NEW."row_count" OR OLD."revision" IS NOT NEW."revision" OR OLD."status" IS NOT NEW."status" OR OLD."validation_json" IS NOT NEW."validation_json" OR OLD."created_at" IS NOT NEW."created_at" OR OLD."updated_at" IS NOT NEW."updated_at" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialdrafts_delete AFTER DELETE ON "WorkbenchTrialDrafts" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialrows_insert AFTER INSERT ON "WorkbenchTrialRows" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialrows_update AFTER UPDATE ON "WorkbenchTrialRows" WHEN OLD."row_ref" IS NOT NEW."row_ref" OR OLD."task_ref" IS NOT NEW."task_ref" OR OLD."draft_ref" IS NOT NEW."draft_ref" OR OLD."operation_ref" IS NOT NEW."operation_ref" OR OLD."source_task_ref" IS NOT NEW."source_task_ref" OR OLD."source_row_ref" IS NOT NEW."source_row_ref" OR OLD."ordinal" IS NOT NEW."ordinal" OR OLD."original_json" IS NOT NEW."original_json" OR OLD."current_json" IS NOT NEW."current_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialrows_delete AFTER DELETE ON "WorkbenchTrialRows" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialchanges_insert AFTER INSERT ON "WorkbenchTrialChanges" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialchanges_update AFTER UPDATE ON "WorkbenchTrialChanges" WHEN OLD."change_ref" IS NOT NEW."change_ref" OR OLD."draft_ref" IS NOT NEW."draft_ref" OR OLD."task_ref" IS NOT NEW."task_ref" OR OLD."revision" IS NOT NEW."revision" OR OLD."before_json" IS NOT NEW."before_json" OR OLD."after_json" IS NOT NEW."after_json" OR OLD."validation_json" IS NOT NEW."validation_json" OR OLD."recorded_at" IS NOT NEW."recorded_at" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialchanges_delete AFTER DELETE ON "WorkbenchTrialChanges" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenarios_insert AFTER INSERT ON "WorkbenchTrialScenarios" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenarios_update AFTER UPDATE ON "WorkbenchTrialScenarios" WHEN OLD."scenario_ref" IS NOT NEW."scenario_ref" OR OLD."draft_ref" IS NOT NEW."draft_ref" OR OLD."name" IS NOT NEW."name" OR OLD."revision" IS NOT NEW."revision" OR OLD."snapshot_json" IS NOT NEW."snapshot_json" OR OLD."saved_at" IS NOT NEW."saved_at" OR OLD."local_operator" IS NOT NEW."local_operator" OR OLD."request_key" IS NOT NEW."request_key" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenarios_delete AFTER DELETE ON "WorkbenchTrialScenarios" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenariorows_insert AFTER INSERT ON "WorkbenchTrialScenarioRows" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenariorows_update AFTER UPDATE ON "WorkbenchTrialScenarioRows" WHEN OLD."row_ref" IS NOT NEW."row_ref" OR OLD."task_ref" IS NOT NEW."task_ref" OR OLD."scenario_ref" IS NOT NEW."scenario_ref" OR OLD."source_row_ref" IS NOT NEW."source_row_ref" OR OLD."payload_json" IS NOT NEW."payload_json" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_workbenchtrialscenariorows_delete AFTER DELETE ON "WorkbenchTrialScenarioRows" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_records'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_op_types_insert AFTER INSERT ON "WorkbenchEntityRefs" WHEN NEW."kind" = 'op_type' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_op_types_update AFTER UPDATE ON "WorkbenchEntityRefs" WHEN (OLD."kind" = 'op_type' OR NEW."kind" = 'op_type') AND (OLD."ref" IS NOT NEW."ref" OR OLD."kind" IS NOT NEW."kind" OR OLD."entity_key" IS NOT NEW."entity_key" OR OLD."alternate_key" IS NOT NEW."alternate_key" OR OLD."revision" IS NOT NEW."revision" OR OLD."active" IS NOT NEW."active" OR OLD."created_at_utc" IS NOT NEW."created_at_utc") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_op_types_delete AFTER DELETE ON "WorkbenchEntityRefs" WHEN OLD."kind" = 'op_type' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'op_types'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_suppliers_insert AFTER INSERT ON "WorkbenchEntityRefs" WHEN NEW."kind" = 'supplier' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_suppliers_update AFTER UPDATE ON "WorkbenchEntityRefs" WHEN (OLD."kind" = 'supplier' OR NEW."kind" = 'supplier') AND (OLD."ref" IS NOT NEW."ref" OR OLD."kind" IS NOT NEW."kind" OR OLD."entity_key" IS NOT NEW."entity_key" OR OLD."alternate_key" IS NOT NEW."alternate_key" OR OLD."revision" IS NOT NEW."revision" OR OLD."active" IS NOT NEW."active" OR OLD."created_at_utc" IS NOT NEW."created_at_utc") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_entity_refs_suppliers_delete AFTER DELETE ON "WorkbenchEntityRefs" WHEN OLD."kind" = 'supplier' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'suppliers'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_rows_insert AFTER INSERT ON "Schedule" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_rows'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_rows_update AFTER UPDATE ON "Schedule" WHEN OLD."id" IS NOT NEW."id" OR OLD."op_id" IS NOT NEW."op_id" OR OLD."machine_id" IS NOT NEW."machine_id" OR OLD."operator_id" IS NOT NEW."operator_id" OR OLD."start_time" IS NOT NEW."start_time" OR OLD."end_time" IS NOT NEW."end_time" OR OLD."lock_status" IS NOT NEW."lock_status" OR OLD."version" IS NOT NEW."version" OR OLD."created_at" IS NOT NEW."created_at" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_rows'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_rows_delete AFTER DELETE ON "Schedule" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_rows'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_references_insert AFTER INSERT ON "Schedule" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_references'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_references_update AFTER UPDATE ON "Schedule" WHEN OLD."op_id" IS NOT NEW."op_id" OR OLD."version" IS NOT NEW."version" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_references'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_schedule_references_delete AFTER DELETE ON "Schedule" BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'schedule_references'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduling_preferences_insert AFTER INSERT ON "SystemConfig" WHEN NEW."config_key" = 'workbench_scheduling_preferences' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'scheduling_preferences'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduling_preferences_update AFTER UPDATE ON "SystemConfig" WHEN (OLD."config_key" = 'workbench_scheduling_preferences' OR NEW."config_key" = 'workbench_scheduling_preferences') AND (OLD."id" IS NOT NEW."id" OR OLD."config_key" IS NOT NEW."config_key" OR OLD."config_value" IS NOT NEW."config_value" OR OLD."description" IS NOT NEW."description" OR OLD."updated_at" IS NOT NEW."updated_at") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'scheduling_preferences'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_scheduling_preferences_delete AFTER DELETE ON "SystemConfig" WHEN OLD."config_key" = 'workbench_scheduling_preferences' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'scheduling_preferences'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_system_config_insert AFTER INSERT ON "SystemConfig" WHEN NEW."config_key" != 'workbench_scheduling_preferences' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'system_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_system_config_update AFTER UPDATE ON "SystemConfig" WHEN (OLD."config_key" != 'workbench_scheduling_preferences' OR NEW."config_key" != 'workbench_scheduling_preferences') AND (OLD."id" IS NOT NEW."id" OR OLD."config_key" IS NOT NEW."config_key" OR OLD."config_value" IS NOT NEW."config_value" OR OLD."description" IS NOT NEW."description" OR OLD."updated_at" IS NOT NEW."updated_at") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'system_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_system_config_delete AFTER DELETE ON "SystemConfig" WHEN OLD."config_key" != 'workbench_scheduling_preferences' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'system_config'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_trial_adoption_receipts_insert AFTER INSERT ON "WorkbenchCommandReceipts" WHEN NEW."action" = 'trial.scenario.adopt' AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = 'trial_adoption' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_adoption_receipts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_trial_adoption_receipts_update AFTER UPDATE ON "WorkbenchCommandReceipts" WHEN (OLD."action" = 'trial.scenario.adopt' AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = 'trial_adoption' OR NEW."action" = 'trial.scenario.adopt' AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = 'trial_adoption') AND (OLD."request_key" IS NOT NEW."request_key" OR OLD."receipt_ref" IS NOT NEW."receipt_ref" OR OLD."action" IS NOT NEW."action" OR OLD."context_ref" IS NOT NEW."context_ref" OR OLD."outcome_json" IS NOT NEW."outcome_json" OR OLD."input_json" IS NOT NEW."input_json" OR OLD."committed_at_utc" IS NOT NEW."committed_at_utc") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_adoption_receipts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_trial_adoption_receipts_delete AFTER DELETE ON "WorkbenchCommandReceipts" WHEN OLD."action" = 'trial.scenario.adopt' AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = 'trial_adoption' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'trial_adoption_receipts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_production_input_receipts_insert AFTER INSERT ON "WorkbenchCommandReceipts" WHEN NEW."action" IS NOT 'trial.scenario.adopt' AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = 'production_input' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'production_input_receipts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_production_input_receipts_update AFTER UPDATE ON "WorkbenchCommandReceipts" WHEN (OLD."action" IS NOT 'trial.scenario.adopt' AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = 'production_input' OR NEW."action" IS NOT 'trial.scenario.adopt' AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = 'production_input') AND (OLD."request_key" IS NOT NEW."request_key" OR OLD."receipt_ref" IS NOT NEW."receipt_ref" OR OLD."action" IS NOT NEW."action" OR OLD."context_ref" IS NOT NEW."context_ref" OR OLD."outcome_json" IS NOT NEW."outcome_json" OR OLD."input_json" IS NOT NEW."input_json" OR OLD."committed_at_utc" IS NOT NEW."committed_at_utc") BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'production_input_receipts'; END;
CREATE TRIGGER IF NOT EXISTS wb_src_rev_production_input_receipts_delete AFTER DELETE ON "WorkbenchCommandReceipts" WHEN OLD."action" IS NOT 'trial.scenario.adopt' AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = 'production_input' BEGIN UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = 'production_input_receipts'; END;
CREATE INDEX IF NOT EXISTS idx_batch_materials_batch ON BatchMaterials(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_operations_supplier ON BatchOperations(supplier_id);
CREATE INDEX IF NOT EXISTS idx_part_operations_supplier ON PartOperations(supplier_id);
CREATE INDEX IF NOT EXISTS idx_wb_run_accepted_sort ON WorkbenchRunJobs(substr(accepted_at,1,19),substr(accepted_at || '0000000',21,6),run_ref);
CREATE INDEX IF NOT EXISTS idx_wb_run_started_sort ON WorkbenchRunJobs(substr(started_at,1,19),substr(started_at || '0000000',21,6),run_ref);
CREATE INDEX IF NOT EXISTS idx_wb_run_finished_sort ON WorkbenchRunJobs(substr(finished_at,1,19),substr(finished_at || '0000000',21,6),run_ref);
CREATE INDEX IF NOT EXISTS idx_material_stage_operation ON BatchMaterialStages(operation_id);
INSERT INTO WorkbenchPlanIdentityClock(singleton, revision) SELECT 1, CASE WHEN NOT EXISTS (SELECT 1 FROM "WorkbenchPlanSourceRefs" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "WorkbenchTaskRefs" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "ScheduleHistory" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "BatchOperations" LIMIT 1) AND NOT EXISTS (SELECT 1 FROM "Schedule" LIMIT 1) THEN 1 ELSE 0 END WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanIdentityClock);
INSERT INTO WorkbenchExecutionLedgerClock(singleton, revision, next_report_no) SELECT 1, CASE WHEN NOT EXISTS (SELECT 1 FROM WorkbenchProductionReports LIMIT 1) AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions LIMIT 1) AND NOT EXISTS (SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1) THEN 1 ELSE 0 END, 1 WHERE NOT EXISTS (SELECT 1 FROM WorkbenchExecutionLedgerClock);
INSERT INTO WorkbenchSourceRevisions(source_key, revision) VALUES ('parts', 1), ('part_operations', 1), ('external_groups', 1), ('op_types', 1), ('machines', 1), ('machine_op_types', 1), ('machine_downtimes', 1), ('operators', 1), ('operator_skills', 1), ('operator_machines', 1), ('materials', 1), ('suppliers', 1), ('work_calendar', 1), ('operator_calendar', 1), ('resource_teams', 1), ('workbench_operator_profiles', 1), ('workbench_supplier_op_types', 1), ('workbench_supplier_profiles', 1), ('workbench_machine_groups', 1), ('workbench_machine_group_members', 1), ('workbench_shift_profiles', 1), ('workbench_shift_pattern_days', 1), ('workbench_shift_day_periods', 1), ('workbench_calendar_defaults', 1), ('workbench_op_type_policies', 1), ('workbench_entity_refs', 1), ('batches', 1), ('batch_operations', 1), ('batch_external_contexts', 1), ('batch_materials', 1), ('batch_material_reviews', 1), ('batch_material_stages', 1), ('batch_material_arrivals', 1), ('batch_quantity_splits', 1), ('workbench_process_workflow', 1), ('workbench_process_operation_confirmations', 1), ('workbench_template_lineage', 1), ('schedule_history', 1), ('schedule_version_seq', 1), ('schedule_config', 1), ('workbench_plan_identity', 1), ('execution_ledger', 1), ('outsourcing', 1), ('dashboard_items', 1), ('dashboard_handling', 1), ('calibration_adoptions', 1), ('run_jobs', 1), ('trial_records', 1), ('schedule_rows', 1), ('schedule_references', 1), ('scheduling_preferences', 1), ('system_config', 1), ('trial_adoption_receipts', 1), ('production_input_receipts', 1) ON CONFLICT(source_key) DO NOTHING;
