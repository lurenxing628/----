"""Core business tables and indexes owned by the baseline schema."""

from __future__ import annotations

from typing import Dict

_CORE_OBJECTS: Dict[str, str] = {
    'Operators': """CREATE TABLE Operators (
    operator_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
, team_id TEXT)""",
    'OpTypes': """CREATE TABLE OpTypes (
    op_type_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'internal',
    default_hours   REAL,
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'Machines': """CREATE TABLE Machines (
    machine_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    op_type_id      TEXT,
    category        TEXT,                       -- 设备类别（用于“按类别停机/筛选”等）
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP, team_id TEXT,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id)
)""",
    'MachineDowntimes': """CREATE TABLE MachineDowntimes (
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
)""",
    'idx_machine_downtimes_machine': 'CREATE INDEX idx_machine_downtimes_machine ON MachineDowntimes(machine_id)',
    'idx_machine_downtimes_time': 'CREATE INDEX idx_machine_downtimes_time ON MachineDowntimes(start_time, end_time)',
    'OperatorMachine': """CREATE TABLE OperatorMachine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     TEXT NOT NULL,
    machine_id      TEXT NOT NULL,
    skill_level     TEXT DEFAULT 'normal',
    is_primary      TEXT DEFAULT 'no',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id) ON DELETE CASCADE,
    UNIQUE (operator_id, machine_id)
)""",
    'OperatorSkill': """CREATE TABLE OperatorSkill (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     TEXT NOT NULL,
    op_type_id      TEXT NOT NULL,
    skill_level     TEXT DEFAULT 'normal',
    is_primary      TEXT DEFAULT 'no',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES Operators(operator_id) ON DELETE CASCADE,
    FOREIGN KEY (op_type_id) REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
    UNIQUE (operator_id, op_type_id)
)""",
    'idx_operators_status': 'CREATE INDEX idx_operators_status ON Operators(status)',
    'idx_operator_machine_machine': 'CREATE INDEX idx_operator_machine_machine ON OperatorMachine(machine_id)',
    'Suppliers': """CREATE TABLE Suppliers (
    supplier_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    default_days    REAL DEFAULT 1,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'Parts': """CREATE TABLE Parts (
    part_no         TEXT PRIMARY KEY,
    part_name       TEXT NOT NULL,
    route_raw       TEXT,
    route_parsed    TEXT DEFAULT 'no',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'PartOperations': """CREATE TABLE PartOperations (
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
)""",
    'ExternalGroups': """CREATE TABLE ExternalGroups (
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
)""",
    'idx_part_operations_part': 'CREATE INDEX idx_part_operations_part ON PartOperations(part_no)',
    'idx_part_operations_source': 'CREATE INDEX idx_part_operations_source ON PartOperations(source)',
    'idx_external_groups_part': 'CREATE INDEX idx_external_groups_part ON ExternalGroups(part_no)',
    'idx_machines_status': 'CREATE INDEX idx_machines_status ON Machines(status)',
    'idx_machines_op_type': 'CREATE INDEX idx_machines_op_type ON Machines(op_type_id)',
    'Batches': """CREATE TABLE Batches (
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
)""",
    'BatchOperations': """CREATE TABLE BatchOperations (
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
)""",
    'Schedule': """CREATE TABLE Schedule (
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
)""",
    'ScheduleVersionSeq': """CREATE TABLE ScheduleVersionSeq (
    version         INTEGER PRIMARY KEY AUTOINCREMENT
)""",
    'WorkCalendar': """CREATE TABLE WorkCalendar (
    date            DATE PRIMARY KEY,
    day_type        TEXT DEFAULT 'workday',
    shift_start     TEXT,                       -- 班次开始（HH:MM，可选；默认 08:00）
    shift_end       TEXT,                       -- 班次结束（HH:MM，可选；用于推导 shift_hours）
    shift_hours     REAL DEFAULT 8,
    efficiency      REAL DEFAULT 1.0,
    allow_normal    TEXT DEFAULT 'yes',
    allow_urgent    TEXT DEFAULT 'yes',
    remark          TEXT
, periods_json TEXT)""",
    'OperatorCalendar': """CREATE TABLE OperatorCalendar (
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
)""",
    'idx_operator_calendar_date': 'CREATE INDEX idx_operator_calendar_date ON OperatorCalendar(date)',
    'ScheduleConfig': """CREATE TABLE ScheduleConfig (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'SystemConfig': """CREATE TABLE SystemConfig (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'SystemJobState': """CREATE TABLE SystemJobState (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key         TEXT NOT NULL UNIQUE,
    last_run_time   DATETIME,
    last_run_detail TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'idx_system_job_state_time': 'CREATE INDEX idx_system_job_state_time ON SystemJobState(last_run_time)',
    'idx_batches_status': 'CREATE INDEX idx_batches_status ON Batches(status)',
    'idx_batches_priority': 'CREATE INDEX idx_batches_priority ON Batches(priority)',
    'idx_batches_due_date': 'CREATE INDEX idx_batches_due_date ON Batches(due_date)',
    'idx_batch_operations_batch': 'CREATE INDEX idx_batch_operations_batch ON BatchOperations(batch_id)',
    'idx_batch_operations_status': 'CREATE INDEX idx_batch_operations_status ON BatchOperations(status)',
    'idx_schedule_op': 'CREATE INDEX idx_schedule_op ON Schedule(op_id)',
    'idx_schedule_machine': 'CREATE INDEX idx_schedule_machine ON Schedule(machine_id)',
    'idx_schedule_operator': 'CREATE INDEX idx_schedule_operator ON Schedule(operator_id)',
    'idx_schedule_time': 'CREATE INDEX idx_schedule_time ON Schedule(start_time, end_time)',
    'OperationLogs': """CREATE TABLE OperationLogs (
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
)""",
    'ScheduleHistory': """CREATE TABLE ScheduleHistory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
    version         INTEGER NOT NULL,
    strategy        TEXT NOT NULL,
    batch_count     INTEGER,
    op_count        INTEGER,
    result_status   TEXT,
    result_summary  TEXT,
    created_by      TEXT
)""",
    'idx_operation_logs_time': 'CREATE INDEX idx_operation_logs_time ON OperationLogs(log_time)',
    'idx_operation_logs_level': 'CREATE INDEX idx_operation_logs_level ON OperationLogs(log_level)',
    'idx_operation_logs_module': 'CREATE INDEX idx_operation_logs_module ON OperationLogs(module)',
    'idx_schedule_history_time': 'CREATE INDEX idx_schedule_history_time ON ScheduleHistory(schedule_time)',
    'Materials': """CREATE TABLE Materials (
    material_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    spec            TEXT,
    unit            TEXT,
    stock_qty       REAL DEFAULT 0,
    status          TEXT DEFAULT 'active',
    remark          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'BatchMaterials': """CREATE TABLE BatchMaterials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    material_id     TEXT NOT NULL,
    required_qty    REAL NOT NULL,
    available_qty   REAL DEFAULT 0,
    ready_status    TEXT DEFAULT 'no',
    FOREIGN KEY (batch_id) REFERENCES Batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES Materials(material_id)
)""",
    'ResourceTeams': """CREATE TABLE ResourceTeams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
    'idx_operators_team_id': 'CREATE INDEX idx_operators_team_id ON Operators(team_id)',
    'idx_machines_team_id': 'CREATE INDEX idx_machines_team_id ON Machines(team_id)',
    'idx_schedule_version_op_unique': 'CREATE UNIQUE INDEX idx_schedule_version_op_unique ON Schedule(version, op_id)',
    'idx_schedule_version_time': """CREATE INDEX idx_schedule_version_time
ON Schedule(version, start_time, end_time)""",
    'idx_schedule_history_version': """CREATE INDEX idx_schedule_history_version
ON ScheduleHistory(version)""",
    'idx_batch_operations_identity_unique': 'CREATE UNIQUE INDEX idx_batch_operations_identity_unique ON BatchOperations(id, batch_id)',
    'idx_schedule_identity_unique': 'CREATE UNIQUE INDEX idx_schedule_identity_unique ON Schedule(id, version, op_id)',
}


def core_objects() -> Dict[str, str]:
    return _CORE_OBJECTS
