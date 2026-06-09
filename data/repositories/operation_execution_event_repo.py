from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from core.models.operation_execution_event import (
    OperationExecutionEvent,
    normalize_operation_execution_event_values,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import OperationExecutionScope, validate_current_official_execution_scope
from core.models.operation_execution_state import OperationExecutionState

from .base_repo import BaseRepository
from .operation_execution_state_aggregation import OperationExecutionStateAggregationMixin

_EVENT_COLUMNS = (
    "id",
    "schedule_version",
    "schedule_id",
    "op_id",
    "batch_id",
    "source_table",
    "effective_plan_role",
    "scenario_id",
    "event_type",
    "reported_status",
    "event_time",
    "actual_machine_id",
    "actual_operator_id",
    "quantity_done",
    "quantity_scrapped",
    "reason_code",
    "reason_detail",
    "severity",
    "impact_minutes",
    "affected_machine_id",
    "affected_operator_id",
    "handling_status",
    "suggest_reschedule",
    "remark",
    "created_by",
    "idempotency_key",
    "request_fingerprint",
    "previous_state_revision",
    "created_at",
)

_REQUIRED_TEXT_FIELDS = (
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
)


def _columns_sql() -> str:
    return ", ".join(_EVENT_COLUMNS)


def _positive_ids(values: Iterable[Any]) -> List[int]:
    # _batch_ids_by_op_ids 只做 SQL IN 查询并落 dict，结果顺序无关；保留 repo 本地 helper，避免 data 层依赖 service。
    seen: Set[int] = set()
    out: List[int] = []
    for raw in values or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _unscoped_execution_read_error() -> ValueError:
    return ValueError("现场执行事件必须按完整计划身份读取，不能只按 op_id 聚合。")


def _text_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(payload: Dict[str, Any], field: str) -> str:
    text = _text_or_none(payload.get(field))
    if text is None:
        raise ValueError(f"{field} is required")
    return text


def _required_positive_int(payload: Dict[str, Any], field: str) -> int:
    raw_value = payload.get(field)
    if raw_value is None:
        raise ValueError(f"{field} is required")
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} is required")  # noqa: B904
    if value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


def _optional_int(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        raise ValueError("integer value is required")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        sign = text[0] if text and text[0] in ("+", "-") else ""
        digits = text[1:] if sign else text
        if digits.isdigit():
            return int(text)
        raise ValueError("integer value is required")
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    raise ValueError("integer value is required")


def _event_payload(event_row: Union[OperationExecutionEvent, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(event_row, OperationExecutionEvent):
        return event_row.to_dict()
    return dict(event_row)


def _suggest_reschedule_value(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text in ("", "0", "no", "false"):
        return 0
    if text in ("1", "yes", "true"):
        return 1
    parsed = _optional_int(value)
    if parsed in (0, 1):
        return int(parsed)
    raise ValueError("suggest_reschedule must be 0 or 1")


def _scope_where(scope: OperationExecutionScope) -> Tuple[str, Tuple[Any, ...]]:
    params = (
        int(scope.schedule_version),
        int(scope.schedule_id),
        int(scope.op_id),
        scope.batch_id,
        scope.source_table,
        scope.effective_plan_role,
    )
    sql = (
        "schedule_version = ? AND schedule_id = ? AND op_id = ? AND batch_id = ? "
        "AND source_table = ? AND effective_plan_role = ?"
    )
    if scope.scenario_id is None:
        return f"({sql} AND scenario_id IS NULL)", params
    return f"({sql} AND scenario_id = ?)", params + (scope.scenario_id,)


def _event_scope(event: OperationExecutionEvent) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=event.schedule_version,
        schedule_id=event.schedule_id,
        op_id=event.op_id,
        batch_id=event.batch_id,
        source_table=event.source_table,
        effective_plan_role=event.effective_plan_role,
        scenario_id=event.scenario_id,
    )


def _validate_events_by_scope(events: Sequence[OperationExecutionEvent]) -> None:
    grouped: Dict[OperationExecutionScope, List[OperationExecutionEvent]] = {}
    for event in events:
        grouped.setdefault(_event_scope(event), []).append(event)
    for scoped_events in grouped.values():
        validate_operation_execution_event_sequence(scoped_events)


def _same_event(left: OperationExecutionEvent, right: OperationExecutionEvent) -> bool:
    if left.id is not None and right.id is not None:
        return int(left.id) == int(right.id)
    return bool(left.idempotency_key) and left.idempotency_key == right.idempotency_key


class OperationExecutionEventRepo(OperationExecutionStateAggregationMixin, BaseRepository):
    """现场执行事件仓库。事件只追加，当前状态由事件流聚合。"""

    def get_event_by_id(self, event_id: int) -> Optional[OperationExecutionEvent]:
        row = self.fetchone(
            f"SELECT {_columns_sql()} FROM OperationExecutionEvents WHERE id = ?",
            (int(event_id),),
        )
        return self._validated_event_from_row(row) if row else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[OperationExecutionEvent]:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        row = self.fetchone(
            f"SELECT {_columns_sql()} FROM OperationExecutionEvents WHERE idempotency_key = ?",
            (key,),
        )
        return self._validated_event_from_row(row) if row else None

    def _validated_event_from_row(self, row: Dict[str, Any]) -> OperationExecutionEvent:
        event = OperationExecutionEvent.from_row(row)
        for scoped_event in self.list_events_by_scope(_event_scope(event)):
            if _same_event(scoped_event, event):
                return scoped_event
        raise ValueError("event is missing from validated operation execution sequence")

    def insert_event(self, event_row: Union[OperationExecutionEvent, Dict[str, Any]]) -> OperationExecutionEvent:
        payload = _event_payload(event_row)
        schedule_version = _required_positive_int(payload, "schedule_version")
        schedule_id = _required_positive_int(payload, "schedule_id")
        op_id = _required_positive_int(payload, "op_id")
        required_text = {field: _required_text(payload, field) for field in _REQUIRED_TEXT_FIELDS}
        event_type, reported_status, event_time = normalize_operation_execution_event_values(
            event_type=required_text["event_type"],
            reported_status=required_text["reported_status"],
            event_time=required_text["event_time"],
        )
        scope = OperationExecutionScope.from_values(
            schedule_version=schedule_version,
            schedule_id=schedule_id,
            op_id=op_id,
            batch_id=required_text["batch_id"],
            source_table=required_text["source_table"],
            effective_plan_role=required_text["effective_plan_role"],
            scenario_id=payload.get("scenario_id"),
        )
        source_table, effective_plan_role, scenario_id = validate_current_official_execution_scope(
            source_table=scope.source_table,
            effective_plan_role=scope.effective_plan_role,
            scenario_id=scope.scenario_id,
        )
        self._ensure_schedule_identity_matches(schedule_version, schedule_id, op_id, required_text["batch_id"])
        event_to_insert = OperationExecutionEvent(
            id=None,
            schedule_version=schedule_version,
            schedule_id=schedule_id,
            op_id=op_id,
            batch_id=scope.batch_id,
            source_table=source_table,
            effective_plan_role=effective_plan_role,
            scenario_id=scenario_id,
            event_type=event_type,
            reported_status=reported_status,
            event_time=event_time,
            actual_machine_id=_text_or_none(payload.get("actual_machine_id")),
            actual_operator_id=_text_or_none(payload.get("actual_operator_id")),
            quantity_done=_optional_int(payload.get("quantity_done")),
            quantity_scrapped=_optional_int(payload.get("quantity_scrapped")),
            reason_code=_text_or_none(payload.get("reason_code")),
            reason_detail=_text_or_none(payload.get("reason_detail")),
            severity=_text_or_none(payload.get("severity")),
            impact_minutes=_optional_int(payload.get("impact_minutes")),
            affected_machine_id=_text_or_none(payload.get("affected_machine_id")),
            affected_operator_id=_text_or_none(payload.get("affected_operator_id")),
            handling_status=_text_or_none(payload.get("handling_status")),
            suggest_reschedule=_suggest_reschedule_value(payload.get("suggest_reschedule")),
            remark=_text_or_none(payload.get("remark")),
            created_by=required_text["created_by"],
            idempotency_key=required_text["idempotency_key"],
            request_fingerprint=required_text["request_fingerprint"],
            previous_state_revision=required_text["previous_state_revision"],
        )
        self._validate_event_sequence_for_insert(scope, event_to_insert)
        cur = self.execute(
            """
            INSERT INTO OperationExecutionEvents (
                schedule_version, schedule_id, op_id, batch_id, source_table,
                effective_plan_role, scenario_id, event_type, reported_status,
                event_time, actual_machine_id, actual_operator_id, quantity_done,
                quantity_scrapped, reason_code, reason_detail, severity,
                impact_minutes, affected_machine_id, affected_operator_id,
                handling_status, suggest_reschedule, remark, created_by,
                idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_version,
                schedule_id,
                op_id,
                scope.batch_id,
                source_table,
                effective_plan_role,
                scenario_id,
                event_type,
                reported_status,
                event_time,
                _text_or_none(payload.get("actual_machine_id")),
                _text_or_none(payload.get("actual_operator_id")),
                _optional_int(payload.get("quantity_done")),
                _optional_int(payload.get("quantity_scrapped")),
                _text_or_none(payload.get("reason_code")),
                _text_or_none(payload.get("reason_detail")),
                _text_or_none(payload.get("severity")),
                _optional_int(payload.get("impact_minutes")),
                _text_or_none(payload.get("affected_machine_id")),
                _text_or_none(payload.get("affected_operator_id")),
                _text_or_none(payload.get("handling_status")),
                _suggest_reschedule_value(payload.get("suggest_reschedule")),
                _text_or_none(payload.get("remark")),
                required_text["created_by"],
                required_text["idempotency_key"],
                required_text["request_fingerprint"],
                required_text["previous_state_revision"],
            ),
        )
        event_id = int(cur.lastrowid or 0)
        created = self.get_event_by_id(event_id)
        if created is None:
            raise RuntimeError("现场反馈写入后没有读回事件。")
        return created

    def _ensure_schedule_identity_matches(
        self,
        schedule_version: int,
        schedule_id: int,
        op_id: int,
        batch_id: str,
    ) -> None:
        row = self.fetchone(
            """
            SELECT s.version, s.op_id, bo.batch_id
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE s.id = ?
            """,
            (int(schedule_id),),
        )
        if (
            row is None
            or int(row["version"] or 0) != int(schedule_version)
            or int(row["op_id"] or 0) != int(op_id)
            or str(row["batch_id"] or "") != batch_id
        ):
            raise ValueError("schedule identity does not match event")

    def _validate_event_sequence_for_insert(self, scope: OperationExecutionScope, event: OperationExecutionEvent) -> None:
        validate_operation_execution_event_sequence([*self.list_events_by_scope(scope), event])

    def list_events_by_op_id(self, op_id: int) -> List[OperationExecutionEvent]: raise _unscoped_execution_read_error()

    def list_events_by_op_ids(self, op_ids: Sequence[int]) -> List[OperationExecutionEvent]: raise _unscoped_execution_read_error()

    def list_events_by_scope(self, scope: OperationExecutionScope) -> List[OperationExecutionEvent]:
        where_sql, params = _scope_where(scope)
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql()}
            FROM OperationExecutionEvents
            WHERE {where_sql}
            ORDER BY id ASC
            """,
            params,
        )
        events = [OperationExecutionEvent.from_row(row) for row in rows]
        validate_operation_execution_event_sequence(events)
        return events

    def list_events_by_scopes(self, scopes: Sequence[OperationExecutionScope]) -> List[OperationExecutionEvent]:
        normalized = list(dict.fromkeys(scopes or ()))
        if not normalized:
            return []
        out: List[OperationExecutionEvent] = []
        for i in range(0, len(normalized), 80):
            chunk = normalized[i : i + 80]
            clauses: List[str] = []
            params: List[Any] = []
            for scope in chunk:
                clause, scope_params = _scope_where(scope)
                clauses.append(clause)
                params.extend(scope_params)
            rows = self.fetchall(
                f"""
                SELECT {_columns_sql()}
                FROM OperationExecutionEvents
                WHERE {" OR ".join(clauses)}
                ORDER BY schedule_version ASC, schedule_id ASC, op_id ASC, id ASC
                """,
                tuple(params),
            )
            out.extend(OperationExecutionEvent.from_row(row) for row in rows)
        _validate_events_by_scope(out)
        return out

    def list_latest_events_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionEvent]: raise _unscoped_execution_read_error()

    def list_latest_exception_events_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionEvent]: raise _unscoped_execution_read_error()

    def aggregate_states_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionState]: raise _unscoped_execution_read_error()

    def state_revision_for_op(self, op_id: int) -> str: raise _unscoped_execution_read_error()

    def _batch_ids_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, str]:
        ids = _positive_ids(op_ids)
        if not ids:
            return {}
        out: Dict[int, str] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"SELECT id, batch_id FROM BatchOperations WHERE id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                out[int(row.get("id") or 0)] = str(row.get("batch_id") or "")
        return out

OperationExecutionEventRepository = OperationExecutionEventRepo

__all__ = ["OperationExecutionEventRepo", "OperationExecutionEventRepository"]
