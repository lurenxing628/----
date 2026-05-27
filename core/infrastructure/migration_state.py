from __future__ import annotations

import sqlite3
from typing import List, Optional

from .migrations.common import MigrationOutcome, column_exists, fallback_log, table_exists

CURRENT_SCHEMA_VERSION = 16


class MigrationContractError(RuntimeError):
    """迁移契约不满足：允许补缺失整表，但不允许静默吞掉复杂残缺库。"""


def build_contract_error(
    *,
    missing_tables: Optional[List[str]] = None,
    blocked_version: Optional[int] = None,
    blocked_outcome: Optional[MigrationOutcome] = None,
    bootstrap_error: Optional[Exception] = None,
) -> MigrationContractError:
    parts = ["检测到非空数据库存在不受支持的残缺结构。"]
    if missing_tables:
        parts.append(f"已识别缺失整表：{', '.join(missing_tables)}。")
    parts.append("系统只会自动补齐缺失整表；现有表结构残缺请先人工修复或恢复到完整备份后再重试。")
    if bootstrap_error is not None:
        parts.append(f"缺失整表预补齐失败：{bootstrap_error}")
    elif blocked_version is not None and blocked_outcome is not None:
        parts.append(f"迁移预检在 v{blocked_version} 返回 {blocked_outcome.value}。")
    return MigrationContractError(" ".join(parts))


def build_future_schema_version_error(db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION) -> MigrationContractError:
    current = int(db_version)
    supported = int(supported_version)
    return MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={current} 高于当前程序支持版本 {supported}。",
                "为避免旧程序破坏高版本数据库，已阻断启动/迁移。",
                "不支持数据库降级迁移。",
                "请升级程序或恢复兼容版本备份后再重试。",
            ]
        )
    )


def ensure_schema_version_not_newer(db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION) -> None:
    if int(db_version) > int(supported_version):
        raise build_future_schema_version_error(int(db_version), supported_version=int(supported_version))


def ensure_schema_version(conn: sqlite3.Connection, logger=None) -> None:
    """
    确保 SchemaVersion 表存在，并写入/修正版本号。

    兼容策略：
    - 老库可能没有 SchemaVersion：插入 version=0
    - 新库可能由 schema.sql 初始化为 version=0：若检测到结构已满足当前版本且库中仍无业务数据，则直接将版本提升到 CURRENT_SCHEMA_VERSION
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0)")

    version = get_schema_version(conn)
    if version <= 0 and detect_schema_is_current(conn) and is_truly_empty_db(conn):
        set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        if logger:
            fallback_log(
                logger, "info", f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。"
            )


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if not row:
            return 0
        return int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        # 仅在“表/列不存在”等可预期场景回落 0；其它错误必须可观测（向上抛出）
        if "no such table" in msg or "no such column" in msg:
            return 0
        raise


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (int(version),))


def is_truly_empty_db(conn: sqlite3.Connection) -> bool:
    for name in list_user_tables(conn):
        quoted_name = '"' + str(name).replace('"', '""') + '"'
        row = conn.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1").fetchone()
        if row is not None:
            return False
    return True


def list_user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name <> 'SchemaVersion'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]


def has_no_user_tables(conn: sqlite3.Connection) -> bool:
    return len(list_user_tables(conn)) == 0


def detect_schema_is_current(conn: sqlite3.Connection) -> bool:
    """
    用“结构特征”判断当前 DB 是否已经包含当前 schema.sql 的关键字段，
    用于 brand-new 空库初始化后的版本快进。
    """
    needed = [
        ("ResourceTeams", "team_id"),
        ("Operators", "team_id"),
        ("Machines", "category"),
        ("Machines", "team_id"),
        ("Batches", "ready_date"),
        ("MachineDowntimes", "scope_type"),
        ("MachineDowntimes", "scope_value"),
        ("WorkCalendar", "shift_start"),
        ("WorkCalendar", "shift_end"),
        ("OperatorCalendar", "operator_id"),
        ("OperatorMachine", "skill_level"),
        ("OperatorMachine", "is_primary"),
        ("ScheduleCandidate", "candidate_key"),
        ("ScheduleCandidate", "status"),
        ("ScheduleCandidateRows", "candidate_id"),
        ("ScheduleCandidateSelection", "source_table"),
        ("ScheduleVersionSeq", "version"),
        ("ScheduleAdjustmentDraft", "draft_id"),
        ("ScheduleAdjustmentChange", "draft_id"),
        ("ScheduleAdjustmentScenario", "scenario_id"),
        ("ScheduleAdjustmentScenario", "published_version"),
        ("ScheduleAdjustmentScenario", "published_by"),
        ("ScheduleAdjustmentScenario", "published_reason"),
        ("ScheduleAdjustmentScenario", "published_at"),
        ("ScheduleAdjustmentScenarioRow", "scenario_id"),
        ("OperationExecutionEvents", "id"),
        ("OperationExecutionEvents", "schedule_version"),
        ("OperationExecutionEvents", "schedule_id"),
        ("OperationExecutionEvents", "op_id"),
        ("OperationExecutionEvents", "batch_id"),
        ("OperationExecutionEvents", "source_table"),
        ("OperationExecutionEvents", "effective_plan_role"),
        ("OperationExecutionEvents", "scenario_id"),
        ("OperationExecutionEvents", "event_type"),
        ("OperationExecutionEvents", "reported_status"),
        ("OperationExecutionEvents", "event_time"),
        ("OperationExecutionEvents", "actual_machine_id"),
        ("OperationExecutionEvents", "actual_operator_id"),
        ("OperationExecutionEvents", "quantity_done"),
        ("OperationExecutionEvents", "quantity_scrapped"),
        ("OperationExecutionEvents", "reason_code"),
        ("OperationExecutionEvents", "reason_detail"),
        ("OperationExecutionEvents", "severity"),
        ("OperationExecutionEvents", "impact_minutes"),
        ("OperationExecutionEvents", "affected_machine_id"),
        ("OperationExecutionEvents", "affected_operator_id"),
        ("OperationExecutionEvents", "handling_status"),
        ("OperationExecutionEvents", "suggest_reschedule"),
        ("OperationExecutionEvents", "remark"),
        ("OperationExecutionEvents", "created_by"),
        ("OperationExecutionEvents", "idempotency_key"),
        ("OperationExecutionEvents", "request_fingerprint"),
        ("OperationExecutionEvents", "previous_state_revision"),
        ("OperationExecutionEvents", "created_at"),
    ]
    for table, col in needed:
        if not column_exists(conn, table, col):
            return False
    return (
        _has_system_management_tables(conn)
        and _has_schedule_unique_index(conn)
        and _has_candidate_indexes(conn)
        and _has_adjustment_draft_indexes(conn)
        and _has_adjustment_scenario_indexes(conn)
        and _has_operation_execution_event_contract(conn)
        and _batch_material_ready_default_is_no(conn)
    )


def _batch_material_ready_default_is_no(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("PRAGMA table_info(BatchMaterials)").fetchall()
    except sqlite3.OperationalError:
        return False
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        if name != "ready_status":
            continue
        default_value = row["dflt_value"] if isinstance(row, sqlite3.Row) else row[4]
        normalized = str(default_value or "").strip().strip("'\"").lower()
        return normalized == "no"
    return False


def _has_system_management_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('SystemConfig','SystemJobState')"
    ).fetchall()
    names = {r[0] if not isinstance(r, sqlite3.Row) else r["name"] for r in row}
    return "SystemConfig" in names and "SystemJobState" in names


def _has_schedule_unique_index(conn: sqlite3.Connection) -> bool:
    index_row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='index'
          AND name='idx_schedule_version_op_unique'
          AND tbl_name='Schedule'
        LIMIT 1
        """
    ).fetchone()
    return index_row is not None


def _has_candidate_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_version_time',
                  'idx_schedule_history_version',
                  'idx_schedule_candidate_version',
                  'idx_schedule_candidate_version_kind',
                  'idx_schedule_candidate_rows_version_candidate',
                  'idx_schedule_candidate_rows_version_candidate_time',
                  'idx_schedule_candidate_rows_time',
                  'idx_schedule_candidate_selection_version'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_version_time",
        "idx_schedule_history_version",
        "idx_schedule_candidate_version",
        "idx_schedule_candidate_version_kind",
        "idx_schedule_candidate_rows_version_candidate",
        "idx_schedule_candidate_rows_version_candidate_time",
        "idx_schedule_candidate_rows_time",
        "idx_schedule_candidate_selection_version",
    }


def _has_adjustment_draft_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_adjustment_draft_base',
                  'idx_schedule_adjustment_draft_status',
                  'idx_schedule_adjustment_change_draft_op'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_adjustment_draft_base",
        "idx_schedule_adjustment_draft_status",
        "idx_schedule_adjustment_change_draft_op",
    }


def _has_adjustment_scenario_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_adjustment_scenario_base',
                  'idx_schedule_adjustment_scenario_draft',
                  'idx_schedule_adjustment_scenario_row_op',
                  'idx_schedule_adjustment_scenario_row_time'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_adjustment_scenario_base",
        "idx_schedule_adjustment_scenario_draft",
        "idx_schedule_adjustment_scenario_row_op",
        "idx_schedule_adjustment_scenario_row_time",
    }


def _table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not row:
        return ""
    return str(row["sql"] if isinstance(row, sqlite3.Row) else row[0] or "")


def _index_table(conn: sqlite3.Connection, index_name: str) -> str:
    row = conn.execute(
        "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    ).fetchone()
    if not row:
        return ""
    return str(row["tbl_name"] if isinstance(row, sqlite3.Row) else row[0] or "")


def _index_columns(conn: sqlite3.Connection, index_name: str, *, table_name: Optional[str] = None) -> List[str]:
    if table_name is not None and _index_table(conn, index_name) != table_name:
        return []
    try:
        rows = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
    except sqlite3.OperationalError:
        return []
    return [str(row["name"] if isinstance(row, sqlite3.Row) else row[2]) for row in rows]


def _index_is_unique(conn: sqlite3.Connection, index_name: str) -> bool:
    try:
        rows = conn.execute("PRAGMA index_list(OperationExecutionEvents)").fetchall()
    except sqlite3.OperationalError:
        return False
    for row in rows:
        name = str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
        if name == index_name:
            unique = row["unique"] if isinstance(row, sqlite3.Row) else row[2]
            return int(unique or 0) == 1
    return False


def _unique_index_has_columns(conn: sqlite3.Connection, table_name: str, columns: List[str]) -> bool:
    expected = [str(col) for col in columns]
    try:
        rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
    except sqlite3.OperationalError:
        return False
    for row in rows:
        name = str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
        unique = row["unique"] if isinstance(row, sqlite3.Row) else row[2]
        if int(unique or 0) != 1:
            continue
        if _index_columns(conn, name, table_name=table_name) == expected:
            return True
    return False


def _foreign_key_targets(conn: sqlite3.Connection, table_name: str) -> List[str]:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    except sqlite3.OperationalError:
        return []
    return [str(row["table"] if isinstance(row, sqlite3.Row) else row[2]) for row in rows]


def _foreign_key_pairs(conn: sqlite3.Connection, table_name: str) -> List[tuple]:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    except sqlite3.OperationalError:
        return []
    pairs = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            pairs.append((str(row["from"]), str(row["table"]), str(row["to"])))
        else:
            pairs.append((str(row[3]), str(row[2]), str(row[4])))
    return pairs


def _foreign_key_delete_actions(conn: sqlite3.Connection, table_name: str) -> dict:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    except sqlite3.OperationalError:
        return {}
    actions = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            key = (str(row["from"]), str(row["table"]), str(row["to"]))
            actions[key] = str(row["on_delete"] or "").upper()
        else:
            key = (str(row[3]), str(row[2]), str(row[4]))
            actions[key] = str(row[6] or "").upper()
    return actions


def _table_columns_info(conn: sqlite3.Connection, table_name: str) -> dict:
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.OperationalError:
        return {}
    out = {}
    for row in rows:
        name = str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
        out[name] = {
            "type": str(row["type"] if isinstance(row, sqlite3.Row) else row[2] or ""),
            "notnull": int(row["notnull"] if isinstance(row, sqlite3.Row) else row[3] or 0),
            "default": row["dflt_value"] if isinstance(row, sqlite3.Row) else row[4],
            "pk": int(row["pk"] if isinstance(row, sqlite3.Row) else row[5] or 0),
        }
    return out


def _column_default_is(conn: sqlite3.Connection, table_name: str, column_name: str, expected: str) -> bool:
    info = _table_columns_info(conn, table_name).get(column_name) or {}
    normalized = str(info.get("default") or "").strip().strip("'\"").lower()
    return normalized == str(expected or "").strip().lower()


def _required_columns_are_not_null(conn: sqlite3.Connection, table_name: str, columns: List[str]) -> bool:
    info = _table_columns_info(conn, table_name)
    for column in columns:
        item = info.get(column)
        if not item or int(item.get("notnull") or 0) != 1:
            return False
    return True


def _has_operation_execution_event_contract(conn: sqlite3.Connection) -> bool:
    if not table_exists(conn, "OperationExecutionEvents"):
        return False
    table_sql = _table_sql(conn, "OperationExecutionEvents").lower()
    required_sql_fragments = (
        "event_type in ('start', 'pause', 'resume', 'finish', 'exception')",
        "reported_status in ('processing', 'paused', 'exception', 'completed')",
        "reason_code is null or reason_code in ('equipment', 'person', 'material', 'quality', 'process', 'external', 'other')",
        "severity is null or severity in ('low', 'medium', 'high', 'critical')",
        "handling_status is null or handling_status in ('new', 'checking', 'waiting', 'handled')",
        "check(suggest_reschedule in (0, 1))",
        "check(event_type not in ('pause', 'exception') or (reason_code is not null and trim(reason_code) <> ''))",
        "check(event_type <> 'exception' or (severity is not null and trim(severity) <> ''))",
        "source_table = 'schedule'",
        "effective_plan_role = 'adopted'",
        "scenario_id is null",
        "unique(op_id, previous_state_revision)",
        "check(schedule_version > 0)",
        "check(schedule_id > 0)",
        "check(op_id > 0)",
        "check(quantity_done is null or quantity_done >= 0)",
        "check(quantity_scrapped is null or quantity_scrapped >= 0)",
        "check(impact_minutes is null or impact_minutes >= 0)",
        "check(trim(batch_id) <> '')",
        "check(trim(created_by) <> '')",
        "check(trim(idempotency_key) <> '')",
        "check(trim(request_fingerprint) <> '')",
        "check(trim(previous_state_revision) <> '')",
    )
    normalized_sql = " ".join(table_sql.split())
    for fragment in required_sql_fragments:
        if fragment not in normalized_sql:
            return False
    if not _required_columns_are_not_null(
        conn,
        "OperationExecutionEvents",
        [
            "schedule_version",
            "schedule_id",
            "op_id",
            "batch_id",
            "source_table",
            "effective_plan_role",
            "event_type",
            "reported_status",
            "event_time",
            "created_by",
            "idempotency_key",
            "request_fingerprint",
            "previous_state_revision",
            "suggest_reschedule",
            "created_at",
        ],
    ):
        return False
    id_info = _table_columns_info(conn, "OperationExecutionEvents").get("id") or {}
    if int(id_info.get("pk") or 0) != 1:
        return False
    if "autoincrement" not in normalized_sql:
        return False
    if not _column_default_is(conn, "OperationExecutionEvents", "source_table", "schedule"):
        return False
    if not _column_default_is(conn, "OperationExecutionEvents", "effective_plan_role", "adopted"):
        return False
    if not _column_default_is(conn, "OperationExecutionEvents", "suggest_reschedule", "0"):
        return False
    if not _column_default_is(conn, "OperationExecutionEvents", "created_at", "current_timestamp"):
        return False
    foreign_targets = set(_foreign_key_targets(conn, "OperationExecutionEvents"))
    if not {"Schedule", "BatchOperations"} <= foreign_targets:
        return False
    foreign_pairs = set(_foreign_key_pairs(conn, "OperationExecutionEvents"))
    if not {
        ("schedule_id", "Schedule", "id"),
        ("op_id", "BatchOperations", "id"),
        ("actual_machine_id", "Machines", "machine_id"),
        ("affected_machine_id", "Machines", "machine_id"),
        ("actual_operator_id", "Operators", "operator_id"),
        ("affected_operator_id", "Operators", "operator_id"),
    } <= foreign_pairs:
        return False
    foreign_delete_actions = _foreign_key_delete_actions(conn, "OperationExecutionEvents")
    if foreign_delete_actions.get(("schedule_id", "Schedule", "id")) == "CASCADE":
        return False
    if foreign_delete_actions.get(("op_id", "BatchOperations", "id")) == "CASCADE":
        return False
    if not _unique_index_has_columns(conn, "OperationExecutionEvents", ["idempotency_key"]):
        return False
    required_indexes = {
        "idx_operation_execution_events_op": ["op_id", "event_time"],
        "idx_operation_execution_events_schedule": ["schedule_id"],
        "idx_operation_execution_events_schedule_op": ["schedule_id", "op_id"],
        "idx_operation_execution_events_batch": ["batch_id"],
        "idx_operation_execution_events_op_revision_unique": ["op_id", "previous_state_revision"],
        "idx_operation_execution_events_latest_exception": ["op_id", "event_type", "id"],
    }
    for name, columns in required_indexes.items():
        if _index_columns(conn, name, table_name="OperationExecutionEvents") != columns:
            return False
    if not _index_is_unique(conn, "idx_operation_execution_events_op_revision_unique"):
        return False
    return _operation_execution_rejects_bad_probe_values(conn)


def _operation_execution_rejects_bad_probe_values(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SAVEPOINT aps_operation_execution_schema_probe")
        _seed_operation_execution_probe_parents(conn)
        probes = [
            {"event_type": "running", "idempotency_key": "__probe_bad_event_type__", "previous_state_revision": "2147483001:0:bad_event"},
            {"reported_status": "finished", "idempotency_key": "__probe_bad_status__", "previous_state_revision": "2147483001:0:bad_status"},
            {"source_table": "candidate_rows", "idempotency_key": "__probe_bad_source__", "previous_state_revision": "2147483001:0:bad_source"},
            {"effective_plan_role": "baseline_best", "idempotency_key": "__probe_bad_role__", "previous_state_revision": "2147483001:0:bad_role"},
            {"scenario_id": "__probe_scenario__", "idempotency_key": "__probe_bad_scenario__", "previous_state_revision": "2147483001:0:bad_scenario"},
            {"reason_code": "bad_reason", "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_bad_reason__", "previous_state_revision": "2147483001:0:bad_reason"},
            {"reason_code": None, "event_type": "pause", "reported_status": "paused", "idempotency_key": "__probe_missing_pause_reason__", "previous_state_revision": "2147483001:0:missing_pause_reason"},
            {"reason_code": None, "severity": "high", "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_missing_exception_reason__", "previous_state_revision": "2147483001:0:missing_exception_reason"},
            {"severity": "bad_severity", "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_bad_severity__", "previous_state_revision": "2147483001:0:bad_severity"},
            {"reason_code": "equipment", "severity": None, "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_missing_exception_severity__", "previous_state_revision": "2147483001:0:missing_exception_severity"},
            {"impact_minutes": -1, "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_bad_impact__", "previous_state_revision": "2147483001:0:bad_impact"},
            {"handling_status": "bad_handling", "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_bad_handling__", "previous_state_revision": "2147483001:0:bad_handling"},
            {"suggest_reschedule": 2, "event_type": "exception", "reported_status": "exception", "idempotency_key": "__probe_bad_suggest__", "previous_state_revision": "2147483001:0:bad_suggest"},
        ]
        for overrides in probes:
            if _operation_execution_bad_probe_is_accepted(conn, overrides):
                return False
        return True
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.execute("ROLLBACK TO SAVEPOINT aps_operation_execution_schema_probe")
            conn.execute("RELEASE SAVEPOINT aps_operation_execution_schema_probe")
        except sqlite3.Error:
            pass


def _seed_operation_execution_probe_parents(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO Parts(part_no, part_name) VALUES (?, ?)",
        ("__schema_probe_part__", "结构检测零件"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("__schema_probe_batch__", "__schema_probe_part__", "结构检测批次", 1, "2099-01-01", "normal", "yes", "scheduled"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (2147483001, "__schema_probe_op__", "__schema_probe_batch__", "__probe_piece__", 1, "结构检测工序", "internal", "scheduled"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)
        """,
        (2147483001, 2147483001, "2099-01-01 08:00:00", "2099-01-01 09:00:00", "unlocked", 2147483001),
    )


def _operation_execution_bad_probe_is_accepted(conn: sqlite3.Connection, overrides: dict) -> bool:
    payload = {
        "schedule_version": 2147483001,
        "schedule_id": 2147483001,
        "op_id": 2147483001,
        "batch_id": "__schema_probe_batch__",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
        "event_type": "start",
        "reported_status": "processing",
        "event_time": "2099-01-01 08:05:00",
        "created_by": "__schema_probe_user__",
        "idempotency_key": "__schema_probe_key__",
        "request_fingerprint": "__schema_probe_fingerprint__",
        "previous_state_revision": "2147483001:0:0",
        "reason_code": None,
        "severity": None,
        "impact_minutes": None,
        "handling_status": None,
        "suggest_reschedule": 0,
    }
    payload.update(overrides)
    try:
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                scenario_id, event_type, reported_status, event_time, created_by, idempotency_key,
                request_fingerprint, previous_state_revision, reason_code, severity, impact_minutes,
                handling_status, suggest_reschedule
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["schedule_version"],
                payload["schedule_id"],
                payload["op_id"],
                payload["batch_id"],
                payload["source_table"],
                payload["effective_plan_role"],
                payload["scenario_id"],
                payload["event_type"],
                payload["reported_status"],
                payload["event_time"],
                payload["created_by"],
                payload["idempotency_key"],
                payload["request_fingerprint"],
                payload["previous_state_revision"],
                payload["reason_code"],
                payload["severity"],
                payload["impact_minutes"],
                payload["handling_status"],
                payload["suggest_reschedule"],
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False
