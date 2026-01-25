-- ============================================================
-- 回转壳体单元智能排产系统（V1） - SQLite Schema
-- 说明：
--   - 所有“布尔概念”统一为字符串枚举，便于 Excel 导入导出与未来扩展
--   - V1 明确不实现并发/资源锁：不包含 ResourceLocks 表
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- Schema Version（用于轻量迁移/回滚）
-- 约定：
--   - version 从 0 开始递增
--   - 应用启动时会根据 version 执行必要迁移，并在迁移前自动备份（若提供 backup_dir）
-- ============================================================

CREATE TABLE IF NOT EXISTS SchemaVersion (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    version         INTEGER NOT NULL,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);

-- ============================================================
-- Personnel Module
-- ============================================================

CREATE TABLE IF NOT EXISTS Operators (
    operator_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Process Module
-- ============================================================

CREATE TABLE IF NOT EXISTS OpTypes (
    op_type_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'internal',
    default_hours   REAL,
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Equipment Module（依赖 OpTypes）
CREATE TABLE IF NOT EXISTS Machines (
    machine_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    op_type_id      TEXT,
    category        TEXT,                       -- 设备类别（用于“按类别停机/筛选”等）
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id)
);

-- 设备停机时间段（预留停机原因；用于“设备资源不可用区间”）
-- 说明：
-- - 与 Machines.status（长期状态）并存：status=active 表示该时间段有效；cancelled 表示已取消
-- - start_time/end_time 建议使用 ISO 格式：YYYY-MM-DD HH:MM:SS（便于排序/比较）
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

-- 人员-设备关联（与设备模块共享）
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

-- 人员-工种能力（预留）
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
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id)
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

-- ============================================================
-- Scheduler Module
-- ============================================================

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

CREATE TABLE IF NOT EXISTS ScheduleConfig (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- System Settings / Jobs（系统管理：自动备份/自动清理等）
-- ============================================================

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

-- ============================================================
-- Logging Module
-- ============================================================

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

-- ============================================================
-- Material Module（预留）
-- ============================================================

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

