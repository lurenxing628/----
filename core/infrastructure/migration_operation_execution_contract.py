from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional, Tuple

from .migrations.common import table_exists
from .operation_execution_event_data_contract import operation_execution_event_data_issues


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


ForeignKeyGroup = Tuple[Tuple[str, ...], str, Tuple[str, ...], Tuple[str, ...]]


def _foreign_key_groups(conn: sqlite3.Connection, table_name: str) -> List[ForeignKeyGroup]:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    except sqlite3.OperationalError:
        return []
    grouped: Dict[int, List[Tuple[int, str, str, str, str]]] = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            group_id = int(row["id"])
            item = (
                int(row["seq"]),
                str(row["from"]),
                str(row["table"]),
                str(row["to"]),
                str(row["on_delete"] or "").upper(),
            )
        else:
            group_id = int(row[0])
            item = (int(row[1]), str(row[3]), str(row[2]), str(row[4]), str(row[6] or "").upper())
        grouped.setdefault(group_id, []).append(item)
    out: List[ForeignKeyGroup] = []
    for parts in grouped.values():
        ordered = sorted(parts, key=lambda item: item[0])
        out.append(
            (
                tuple(item[1] for item in ordered),
                str(ordered[0][2]),
                tuple(item[3] for item in ordered),
                tuple(item[4] for item in ordered),
            )
        )
    return out


def _foreign_key_pairs(conn: sqlite3.Connection, table_name: str) -> List[tuple]:
    pairs = []
    for child_columns, parent_table, parent_columns, _ in _foreign_key_groups(conn, table_name):
        for child_column, parent_column in zip(child_columns, parent_columns):
            pairs.append((child_column, parent_table, parent_column))
    return pairs


def _foreign_key_delete_actions(conn: sqlite3.Connection, table_name: str) -> dict:
    actions = {}
    for child_columns, parent_table, parent_columns, delete_actions in _foreign_key_groups(conn, table_name):
        for child_column, parent_column, delete_action in zip(child_columns, parent_columns, delete_actions):
            actions[(child_column, parent_table, parent_column)] = delete_action
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


def _column_has_no_default(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    info = _table_columns_info(conn, table_name).get(column_name) or {}
    return info.get("default") is None


def _required_columns_are_not_null(conn: sqlite3.Connection, table_name: str, columns: List[str]) -> bool:
    info = _table_columns_info(conn, table_name)
    for column in columns:
        item = info.get(column)
        if not item or int(item.get("notnull") or 0) != 1:
            return False
    return True


_OPERATION_EXECUTION_REQUIRED_SQL_FRAGMENTS = (
    "event_type in ('start', 'pause', 'resume', 'finish', 'exception')",
    "reported_status in ('processing', 'paused', 'exception', 'completed')",
    "check((event_type in ('start', 'resume') and reported_status = 'processing') or (event_type = 'pause' and reported_status = 'paused') or (event_type = 'exception' and reported_status = 'exception') or (event_type = 'finish' and reported_status = 'completed'))",
    "reason_code is null or reason_code in ('equipment', 'person', 'material', 'quality', 'process', 'external', 'other')",
    "severity is null or severity in ('low', 'medium', 'high', 'critical')",
    "handling_status is null or handling_status in ('new', 'checking', 'waiting', 'handled')",
    "check(suggest_reschedule in (0, 1))",
    "check(event_type not in ('pause', 'exception') or (reason_code is not null and trim(reason_code) <> ''))",
    "check(event_type <> 'exception' or (severity is not null and trim(severity) <> ''))",
    "source_table = 'schedule'",
    "effective_plan_role = 'adopted'",
    "scenario_id is null",
    "unique(schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role, previous_state_revision)",
    "check(schedule_version > 0)",
    "check(schedule_id > 0)",
    "check(op_id > 0)",
    "check(quantity_done is null or quantity_done >= 0)",
    "check(quantity_scrapped is null or quantity_scrapped >= 0)",
    "check(impact_minutes is null or impact_minutes >= 0)",
    "check(trim(batch_id) <> '')",
    "check(trim(event_time) <> '' and datetime(event_time) is not null)",
    "check(trim(created_by) <> '')",
    "check(trim(idempotency_key) <> '')",
    "check(trim(request_fingerprint) <> '')",
    "check(trim(previous_state_revision) <> '')",
)

_OPERATION_EXECUTION_REQUIRED_NOT_NULL_COLUMNS = [
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
]

_OPERATION_EXECUTION_REQUIRED_FOREIGN_PAIRS = {
    ("schedule_id", "Schedule", "id"),
    ("schedule_version", "Schedule", "version"),
    ("op_id", "Schedule", "op_id"),
    ("op_id", "BatchOperations", "id"),
    ("batch_id", "BatchOperations", "batch_id"),
    ("actual_machine_id", "Machines", "machine_id"),
    ("affected_machine_id", "Machines", "machine_id"),
    ("actual_operator_id", "Operators", "operator_id"),
    ("affected_operator_id", "Operators", "operator_id"),
}

_OPERATION_EXECUTION_REQUIRED_FOREIGN_GROUPS = {
    (("schedule_id", "schedule_version", "op_id"), "Schedule", ("id", "version", "op_id")),
    (("op_id", "batch_id"), "BatchOperations", ("id", "batch_id")),
}

_OPERATION_EXECUTION_REQUIRED_INDEXES = {
    "idx_operation_execution_events_op": ["op_id", "event_time"],
    "idx_operation_execution_events_schedule": ["schedule_id"],
    "idx_operation_execution_events_schedule_op": ["schedule_id", "op_id"],
    "idx_operation_execution_events_batch": ["batch_id"],
    "idx_operation_execution_events_op_revision_unique": [
        "schedule_version",
        "schedule_id",
        "op_id",
        "batch_id",
        "source_table",
        "effective_plan_role",
        "previous_state_revision",
    ],
    "idx_operation_execution_events_latest_exception": ["op_id", "event_type", "id"],
}

_OPERATION_EXECUTION_REQUIRED_PARENT_INDEXES = {
    "idx_schedule_identity_unique": ("Schedule", ["id", "version", "op_id"]),
    "idx_batch_operations_identity_unique": ("BatchOperations", ["id", "batch_id"]),
}


def has_operation_execution_event_contract(conn: sqlite3.Connection) -> bool:
    return not operation_execution_event_contract_issues(conn)


def operation_execution_event_contract_issues(conn: sqlite3.Connection) -> List[str]:
    if not table_exists(conn, "OperationExecutionEvents"):
        return ["missing_table: OperationExecutionEvents"]
    normalized_sql = _normalize_sql_contract_text(_table_sql(conn, "OperationExecutionEvents"))
    issues = []
    issues.extend(_operation_execution_sql_contract_issues(normalized_sql))
    issues.extend(_operation_execution_column_contract_issues(conn, normalized_sql))
    issues.extend(_operation_execution_foreign_key_contract_issues(conn))
    issues.extend(_operation_execution_index_contract_issues(conn))
    issues.extend(_operation_execution_probe_issues(conn))
    issues.extend(operation_execution_event_data_issues(conn))
    return issues


def _normalize_sql_contract_text(sql: str) -> str:
    normalized = " ".join(str(sql or "").lower().split())
    replacements = (("( ", "("), (" )", ")"), (" ,", ","))
    for old, new in replacements:
        while old in normalized:
            normalized = normalized.replace(old, new)
    return normalized


def _operation_execution_sql_contract_issues(normalized_sql: str) -> List[str]:
    return [
        f"bad_sql_fragment: OperationExecutionEvents missing {fragment}"
        for fragment in _OPERATION_EXECUTION_REQUIRED_SQL_FRAGMENTS
        if fragment not in normalized_sql
    ]


def _operation_execution_column_contract_issues(conn: sqlite3.Connection, normalized_sql: str) -> List[str]:
    issues = []
    info = _table_columns_info(conn, "OperationExecutionEvents")
    for column in _OPERATION_EXECUTION_REQUIRED_NOT_NULL_COLUMNS:
        item = info.get(column)
        if not item:
            issues.append(f"missing_column: OperationExecutionEvents.{column}")
        elif int(item.get("notnull") or 0) != 1:
            issues.append(f"nullable_column: OperationExecutionEvents.{column}")
    id_info = info.get("id") or {}
    if int(id_info.get("pk") or 0) != 1 or "autoincrement" not in normalized_sql:
        issues.append("bad_column: OperationExecutionEvents.id must be autoincrement primary key")
    for column in ("source_table", "effective_plan_role"):
        if not _column_has_no_default(conn, "OperationExecutionEvents", column):
            issues.append(f"bad_default: OperationExecutionEvents.{column} must not have default")
    for column, expected in (("suggest_reschedule", "0"), ("created_at", "current_timestamp")):
        if not _column_default_is(conn, "OperationExecutionEvents", column, expected):
            issues.append(f"bad_default: OperationExecutionEvents.{column} expected {expected}")
    return issues


def _operation_execution_foreign_key_contract_issues(conn: sqlite3.Connection) -> List[str]:
    issues = []
    groups = {
        (child_columns, parent_table, parent_columns)
        for child_columns, parent_table, parent_columns, _ in _foreign_key_groups(conn, "OperationExecutionEvents")
    }
    for child_columns, parent_table, parent_columns in sorted(_OPERATION_EXECUTION_REQUIRED_FOREIGN_GROUPS):
        if (child_columns, parent_table, parent_columns) not in groups:
            issues.append(
                "bad_fk_group: OperationExecutionEvents."
                f"{child_columns} -> {parent_table}{parent_columns}"
            )
    pairs = set(_foreign_key_pairs(conn, "OperationExecutionEvents"))
    for pair in sorted(_OPERATION_EXECUTION_REQUIRED_FOREIGN_PAIRS):
        if pair not in pairs:
            issues.append(f"bad_fk: OperationExecutionEvents.{pair[0]} -> {pair[1]}.{pair[2]}")
    foreign_delete_actions = _foreign_key_delete_actions(conn, "OperationExecutionEvents")
    for pair in (("schedule_id", "Schedule", "id"), ("op_id", "BatchOperations", "id")):
        if foreign_delete_actions.get(pair) == "CASCADE":
            issues.append(f"bad_fk_delete: OperationExecutionEvents.{pair[0]} must not cascade")
    return issues


def _operation_execution_index_contract_issues(conn: sqlite3.Connection) -> List[str]:
    issues = []
    if not _unique_index_has_columns(conn, "OperationExecutionEvents", ["idempotency_key"]):
        issues.append("bad_index: OperationExecutionEvents.idempotency_key must be unique")
    for name, columns in _OPERATION_EXECUTION_REQUIRED_INDEXES.items():
        actual = _index_columns(conn, name, table_name="OperationExecutionEvents")
        if actual != columns:
            issues.append(f"bad_index: {name} expected {columns} got {actual}")
    if not _index_is_unique(conn, "idx_operation_execution_events_op_revision_unique"):
        issues.append("bad_index: idx_operation_execution_events_op_revision_unique must be unique")
    for name, (table_name, columns) in _OPERATION_EXECUTION_REQUIRED_PARENT_INDEXES.items():
        actual = _index_columns(conn, name, table_name=table_name)
        if actual != columns or not _unique_index_has_columns(conn, table_name, columns):
            issues.append(f"bad_parent_index: {name} expected {table_name}{columns} got {actual}")
    return issues


def _operation_execution_probe_issues(conn: sqlite3.Connection) -> List[str]:
    try:
        conn.execute("SAVEPOINT aps_operation_execution_schema_probe")
        _seed_operation_execution_probe_parents(conn)
        issues = []
        probes = [
            {"event_type": "running", "idempotency_key": "__probe_bad_event_type__", "previous_state_revision": "2147483001:0:bad_event"},
            {"reported_status": "finished", "idempotency_key": "__probe_bad_status__", "previous_state_revision": "2147483001:0:bad_status"},
            {"event_time": "not-a-date", "idempotency_key": "__probe_bad_event_time__", "previous_state_revision": "2147483001:0:bad_event_time"},
            {"event_type": "finish", "reported_status": "processing", "idempotency_key": "__probe_bad_status_pair__", "previous_state_revision": "2147483001:0:bad_status_pair"},
            {"schedule_version": 2147483999, "idempotency_key": "__probe_bad_schedule_identity__", "previous_state_revision": "2147483001:0:bad_schedule_identity"},
            {"schedule_version": 2147483002, "op_id": 2147483001, "idempotency_key": "__probe_bad_schedule_fk_group__", "previous_state_revision": "2147483001:0:bad_schedule_fk_group"},
            {"batch_id": "__probe_bad_batch__", "idempotency_key": "__probe_bad_batch_identity__", "previous_state_revision": "2147483001:0:bad_batch_identity"},
            {"batch_id": "__schema_probe_batch_2__", "idempotency_key": "__probe_bad_batch_fk_group__", "previous_state_revision": "2147483001:0:bad_batch_fk_group"},
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
                issues.append(f"bad_probe: accepted {overrides['idempotency_key']}")
        return issues
    except sqlite3.Error as exc:
        return [f"bad_probe_error: {exc}"]
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
        INSERT OR IGNORE INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("__schema_probe_batch_2__", "__schema_probe_part__", "结构检测批次2", 1, "2099-01-01", "normal", "yes", "scheduled"),
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
        INSERT OR IGNORE INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (2147483002, "__schema_probe_op_2__", "__schema_probe_batch_2__", "__probe_piece_2__", 1, "结构检测工序2", "internal", "scheduled"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)
        """,
        (2147483001, 2147483001, "2099-01-01 08:00:00", "2099-01-01 09:00:00", "unlocked", 2147483001),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)
        """,
        (2147483002, 2147483002, "2099-01-02 08:00:00", "2099-01-02 09:00:00", "unlocked", 2147483002),
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
