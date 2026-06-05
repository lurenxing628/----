from __future__ import annotations

import sqlite3
from typing import Any, List, Optional, Tuple

from core.models._helpers import parse_int
from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_PAUSE,
    normalize_operation_event_time,
    normalize_operation_execution_event_values,
    validate_operation_execution_event_sequence,
)


def operation_execution_event_data_issues(conn: sqlite3.Connection, *, limit: int = 8) -> List[str]:
    if not _table_exists(conn, "OperationExecutionEvents"):
        return []
    issues: List[str] = []
    issues.extend(_event_value_issues(conn, limit=limit))
    if len(issues) < limit:
        issues.extend(operation_execution_event_sequence_issues(conn, limit=limit - len(issues)))
    if len(issues) < limit:
        issues.extend(_foreign_key_data_issues(conn, limit=limit - len(issues)))
    return issues[:limit]


def _row_value(row: Any, key: str, index: int) -> Any:
    return row[key] if isinstance(row, sqlite3.Row) else row[index]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()
    return row is not None


def _int_value(value: Any, field_name: str) -> int:
    parsed = parse_int(value, default=None)
    if parsed is None:
        raise ValueError(f"{field_name} must be an integer: {value!r}")
    return parsed


def _positive_int(value: Any, field_name: str) -> None:
    if _int_value(value, field_name) <= 0:
        raise ValueError(f"{field_name} must be greater than 0")


def _optional_non_negative_int(value: Any, field_name: str) -> None:
    if value is None:
        return
    if _int_value(value, field_name) < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")


def _required_text(value: Any, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _optional_value(value: Any, allowed_values: Tuple[str, ...], field_name: str) -> str:
    text = _text(value)
    if not text:
        return ""
    if text not in allowed_values:
        raise ValueError(f"{field_name} must be one of {allowed_values}: {value!r}")
    return text


def _validate_event_contract_row(row: Any) -> None:
    _positive_int(_row_value(row, "schedule_version", 1), "schedule_version")
    _positive_int(_row_value(row, "schedule_id", 2), "schedule_id")
    _positive_int(_row_value(row, "op_id", 3), "op_id")
    _required_text(_row_value(row, "batch_id", 4), "batch_id")
    if _text(_row_value(row, "source_table", 5)) != "schedule":
        raise ValueError("source_table must be 'schedule'")
    if _text(_row_value(row, "effective_plan_role", 6)) != "adopted":
        raise ValueError("effective_plan_role must be 'adopted'")
    if _row_value(row, "scenario_id", 7) is not None:
        raise ValueError("scenario_id must be NULL")
    event_type, _status, _event_time = normalize_operation_execution_event_values(
        event_type=_row_value(row, "event_type", 8),
        reported_status=_row_value(row, "reported_status", 9),
        event_time=_row_value(row, "event_time", 10),
    )
    _optional_non_negative_int(_row_value(row, "quantity_done", 11), "quantity_done")
    _optional_non_negative_int(_row_value(row, "quantity_scrapped", 12), "quantity_scrapped")
    reason_code = _optional_value(
        _row_value(row, "reason_code", 13),
        ("equipment", "person", "material", "quality", "process", "external", "other"),
        "reason_code",
    )
    if event_type in (EXECUTION_EVENT_PAUSE, EXECUTION_EVENT_EXCEPTION) and not reason_code:
        raise ValueError("reason_code is required for pause or exception event")
    severity = _optional_value(
        _row_value(row, "severity", 14),
        ("low", "medium", "high", "critical"),
        "severity",
    )
    if event_type == EXECUTION_EVENT_EXCEPTION and not severity:
        raise ValueError("severity is required for exception event")
    _optional_non_negative_int(_row_value(row, "impact_minutes", 15), "impact_minutes")
    _optional_value(
        _row_value(row, "handling_status", 16),
        ("new", "checking", "waiting", "handled"),
        "handling_status",
    )
    if _int_value(_row_value(row, "suggest_reschedule", 17), "suggest_reschedule") not in (0, 1):
        raise ValueError("suggest_reschedule must be 0 or 1")
    _required_text(_row_value(row, "created_by", 18), "created_by")
    _required_text(_row_value(row, "idempotency_key", 19), "idempotency_key")
    _required_text(_row_value(row, "request_fingerprint", 20), "request_fingerprint")
    _required_text(_row_value(row, "previous_state_revision", 21), "previous_state_revision")
    normalize_operation_event_time(_row_value(row, "created_at", 22))


def _event_value_issues(conn: sqlite3.Connection, *, limit: int) -> List[str]:
    issues: List[str] = []
    try:
        rows = conn.execute(
            """
            SELECT
                id, schedule_version, schedule_id, op_id, batch_id,
                source_table, effective_plan_role, scenario_id,
                event_type, reported_status, event_time,
                quantity_done, quantity_scrapped, reason_code, severity,
                impact_minutes, handling_status, suggest_reschedule,
                created_by, idempotency_key, request_fingerprint,
                previous_state_revision, created_at
            FROM OperationExecutionEvents
            ORDER BY id ASC
            """
        )
        for row in rows:
            event_id = _row_value(row, "id", 0)
            try:
                _validate_event_contract_row(row)
            except ValueError as exc:
                issues.append(f"bad_data: OperationExecutionEvents.id={event_id} {exc}")
                if len(issues) >= limit:
                    break
    except sqlite3.Error as exc:
        issues.append(f"bad_data_check_error: OperationExecutionEvents {exc}")
    return issues


def _sequence_key(row: Any) -> Tuple[str, str, str, str, str, str, str]:
    return (
        _text(_row_value(row, "schedule_version", 1)),
        _text(_row_value(row, "schedule_id", 2)),
        _text(_row_value(row, "op_id", 3)),
        _text(_row_value(row, "batch_id", 4)),
        _text(_row_value(row, "source_table", 5)),
        _text(_row_value(row, "effective_plan_role", 6)),
        _text(_row_value(row, "scenario_id", 7)),
    )


def _sequence_issue(rows: List[Any]) -> str:
    ids = ", ".join(str(_row_value(row, "id", 0)) for row in rows[:8])
    try:
        validate_operation_execution_event_sequence(rows)
    except ValueError as exc:
        return f"bad_sequence: OperationExecutionEvents.ids={ids} {exc}"
    return ""


def operation_execution_event_sequence_issues(conn: sqlite3.Connection, *, limit: int = 8) -> List[str]:
    if not _table_exists(conn, "OperationExecutionEvents"):
        return []
    issues: List[str] = []
    try:
        rows = conn.execute(
            """
            SELECT
                id, schedule_version, schedule_id, op_id, batch_id,
                source_table, effective_plan_role, scenario_id,
                event_type, reported_status, event_time, previous_state_revision
            FROM OperationExecutionEvents
            ORDER BY schedule_version ASC, schedule_id ASC, op_id ASC, batch_id ASC,
                     source_table ASC, effective_plan_role ASC, scenario_id ASC, id ASC
            """
        ).fetchall()
    except sqlite3.Error as exc:
        return [f"bad_sequence_check_error: OperationExecutionEvents {exc}"]

    current_key: Optional[Tuple[str, str, str, str, str, str, str]] = None
    current_rows: List[Any] = []
    for row in rows:
        key = _sequence_key(row)
        if current_key is not None and key != current_key:
            issue = _sequence_issue(current_rows)
            if issue:
                issues.append(issue)
                if len(issues) >= limit:
                    return issues
            current_rows = []
        current_key = key
        current_rows.append(row)
    if current_rows and len(issues) < limit:
        issue = _sequence_issue(current_rows)
        if issue:
            issues.append(issue)
    return issues[:limit]


def _foreign_key_data_issues(conn: sqlite3.Connection, *, limit: int) -> List[str]:
    issues: List[str] = []
    try:
        rows = conn.execute("PRAGMA foreign_key_check(OperationExecutionEvents)").fetchall()
    except sqlite3.Error as exc:
        return [f"bad_fk_check_error: OperationExecutionEvents {exc}"]
    for row in rows:
        table_name = _row_value(row, "table", 0)
        row_id = _row_value(row, "rowid", 1)
        parent = _row_value(row, "parent", 2)
        issues.append(f"bad_fk_data: {table_name}.rowid={row_id} -> {parent}")
        if len(issues) >= limit:
            break
    return issues


__all__ = ["operation_execution_event_data_issues", "operation_execution_event_sequence_issues"]
