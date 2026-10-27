from __future__ import annotations

import sqlite3
from itertools import groupby, islice
from typing import Any, Iterable, List, Tuple

from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_PAUSE,
    OPERATION_EXECUTION_EVENT_COLUMNS,
    OPERATION_EXECUTION_EVENT_SEQUENCE_COLUMNS,
    OperationExecutionEvent,
    OperationExecutionEventSequenceEntry,
    normalize_operation_event_time,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import required_execution_text

_EVENT_ORDER_SQL = """
    ORDER BY schedule_version ASC, schedule_id ASC, op_id ASC, batch_id ASC,
             source_table ASC, effective_plan_role ASC, scenario_id ASC, id ASC
"""
_EVENT_VALUE_SQL = (
    "SELECT " + ", ".join(OPERATION_EXECUTION_EVENT_COLUMNS) + " FROM OperationExecutionEvents" + _EVENT_ORDER_SQL
)
# 迁移 v16/v18/v19 在旧表结构上也跑顺序校验，只读顺序校验需要的列。
_EVENT_SEQUENCE_SQL = (
    "SELECT " + ", ".join(OPERATION_EXECUTION_EVENT_SEQUENCE_COLUMNS) + " FROM OperationExecutionEvents" + _EVENT_ORDER_SQL
)

_SEQUENCE_SCOPE_COLUMNS = ("schedule_version", "schedule_id", "op_id", "batch_id", "source_table",
                           "effective_plan_role", "scenario_id")
_DATA_ISSUE_LIMIT = 8
_SEQUENCE_ISSUE_LIMIT = 4


def operation_execution_event_data_issues(conn: sqlite3.Connection) -> List[str]:
    issues: List[str] = []
    issues.extend(_event_value_issues(conn, limit=_DATA_ISSUE_LIMIT))
    if len(issues) < _DATA_ISSUE_LIMIT:
        issues.extend(_foreign_key_data_issues(conn, limit=_DATA_ISSUE_LIMIT - len(issues)))
    return issues[:_DATA_ISSUE_LIMIT]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_value(value: Any, allowed_values: Tuple[str, ...], field_name: str) -> str:
    text = _text(value)
    if not text:
        return ""
    if text not in allowed_values:
        raise ValueError(f"{field_name} must be one of {allowed_values}: {value!r}")
    return text


def _validate_event_contract_row(row: Any) -> OperationExecutionEvent:
    # from_row 已校验计划身份（含 scenario_id 只许 NULL）与事件类型、状态、时间。
    event = OperationExecutionEvent.from_row(row)
    event_type = event.event_type
    reason_code = _optional_value(
        row["reason_code"],
        ("equipment", "person", "material", "quality", "process", "external", "other"),
        "reason_code",
    )
    if event_type in (EXECUTION_EVENT_PAUSE, EXECUTION_EVENT_EXCEPTION) and not reason_code:
        raise ValueError("reason_code is required for pause or exception event")
    severity = _optional_value(
        row["severity"],
        ("low", "medium", "high", "critical"),
        "severity",
    )
    if event_type == EXECUTION_EVENT_EXCEPTION and not severity:
        raise ValueError("severity is required for exception event")
    _optional_value(
        row["handling_status"],
        ("new", "checking", "waiting", "handled"),
        "handling_status",
    )
    required_execution_text(row["created_by"], "created_by")
    required_execution_text(row["idempotency_key"], "idempotency_key")
    fingerprint = row["request_fingerprint"]
    if fingerprint is not None:
        required_execution_text(fingerprint, "request_fingerprint")
    normalize_operation_event_time(row["created_at"])
    return event


def _collect_scoped_event_issues(
    conn: sqlite3.Connection,
    *,
    sql: str,
    error_prefix: str,
    limit: int,
    validate_row: bool,
) -> List[str]:
    issues: List[str] = []
    try:
        rows = conn.execute(sql)
        for _, group in groupby(rows, key=_sequence_key):
            if not validate_row:
                scoped_rows = list(group)
                issue = _sequence_issue(
                    (OperationExecutionEventSequenceEntry.from_row(item) for item in scoped_rows),
                    event_ids=(item["id"] for item in scoped_rows),
                )
            else:
                events: List[OperationExecutionEvent] = []
                for row in group:
                    try:
                        events.append(_validate_event_contract_row(row))
                    except ValueError as exc:
                        issues.append(f"bad_data: OperationExecutionEvents.id={row['id']} {exc}")
                        if len(issues) >= limit:
                            return issues[:limit]
                issue = _sequence_issue(events, event_ids=(event.id for event in events)) if events else ""
            if issue:
                issues.append(issue)
                if len(issues) >= limit:
                    return issues[:limit]
    except sqlite3.Error as exc:
        issues.append(f"{error_prefix}: OperationExecutionEvents {exc}")
    return issues[:limit]


def _event_value_issues(conn: sqlite3.Connection, *, limit: int) -> List[str]:
    return _collect_scoped_event_issues(
        conn,
        sql=_EVENT_VALUE_SQL,
        error_prefix="bad_data_check_error",
        limit=limit,
        validate_row=True,
    )


def _sequence_key(row: Any) -> Tuple[str, ...]:
    return tuple(_text(row[name]) for name in _SEQUENCE_SCOPE_COLUMNS)


def _sequence_issue(events: Iterable[OperationExecutionEventSequenceEntry], *, event_ids: Iterable[object]) -> str:
    try:
        validate_operation_execution_event_sequence(events)
    except ValueError as exc:
        ids = ", ".join(str(event_id) for event_id in islice(event_ids, 8))
        return f"bad_sequence: OperationExecutionEvents.ids={ids} {exc}"
    return ""


def operation_execution_event_sequence_issues(conn: sqlite3.Connection) -> List[str]:
    return _collect_scoped_event_issues(
        conn,
        sql=_EVENT_SEQUENCE_SQL,
        error_prefix="bad_sequence_check_error",
        limit=_SEQUENCE_ISSUE_LIMIT,
        validate_row=False,
    )


def _foreign_key_data_issues(conn: sqlite3.Connection, *, limit: int) -> List[str]:
    issues: List[str] = []
    try:
        rows = conn.execute("PRAGMA foreign_key_check(OperationExecutionEvents)").fetchall()
    except sqlite3.Error as exc:
        return [f"bad_fk_check_error: OperationExecutionEvents {exc}"]
    for row in rows:
        issues.append(f"bad_fk_data: {row[0]}.rowid={row[1]} -> {row[2]}")
        if len(issues) >= limit:
            break
    return issues


__all__ = ["operation_execution_event_data_issues", "operation_execution_event_sequence_issues"]
