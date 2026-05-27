from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Union

from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_NOT_STARTED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
    OperationExecutionEvent,
)
from core.models.operation_execution_labels import (
    event_type_to_action,
    exception_reason_label,
    execution_action_label,
    execution_status_label,
    handling_status_label,
    severity_label,
    suggest_reschedule_label,
)
from core.models.operation_execution_state import OperationExecutionState

from .base_repo import BaseRepository

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
    "event_type",
    "reported_status",
    "event_time",
    "created_by",
    "idempotency_key",
    "request_fingerprint",
    "previous_state_revision",
)

_REPORTED_STATUS_BY_EVENT_TYPE = {
    EXECUTION_EVENT_START: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_RESUME: EXECUTION_STATUS_PROCESSING,
    EXECUTION_EVENT_PAUSE: EXECUTION_STATUS_PAUSED,
    EXECUTION_EVENT_EXCEPTION: EXECUTION_STATUS_EXCEPTION,
    EXECUTION_EVENT_FINISH: EXECUTION_STATUS_COMPLETED,
}


def _columns_sql() -> str:
    return ", ".join(_EVENT_COLUMNS)


def _positive_ids(values: Iterable[Any]) -> List[int]:
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
    try:
        value = int(payload.get(field))
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


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _duration_minutes(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return None
    return round((end_dt - start_dt).total_seconds() / 60.0, 6)


def _impact_minutes_label(value: Optional[int]) -> str:
    if value is None:
        return "暂时不知道影响多久"
    return f"预计影响 {int(value)} 分钟"


def _suggest_reschedule_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "yes", "true")


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


class OperationExecutionEventRepo(BaseRepository):
    """现场执行事件仓库。事件只追加，当前状态由事件流聚合。"""

    def get_event_by_id(self, event_id: int) -> Optional[OperationExecutionEvent]:
        row = self.fetchone(
            f"SELECT {_columns_sql()} FROM OperationExecutionEvents WHERE id = ?",
            (int(event_id),),
        )
        return OperationExecutionEvent.from_row(row) if row else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[OperationExecutionEvent]:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        row = self.fetchone(
            f"SELECT {_columns_sql()} FROM OperationExecutionEvents WHERE idempotency_key = ?",
            (key,),
        )
        return OperationExecutionEvent.from_row(row) if row else None

    def insert_event(self, event_row: Union[OperationExecutionEvent, Dict[str, Any]]) -> OperationExecutionEvent:
        payload = _event_payload(event_row)
        schedule_version = _required_positive_int(payload, "schedule_version")
        schedule_id = _required_positive_int(payload, "schedule_id")
        op_id = _required_positive_int(payload, "op_id")
        required_text = {field: _required_text(payload, field) for field in _REQUIRED_TEXT_FIELDS}
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
                required_text["batch_id"],
                str(payload.get("source_table") or "schedule"),
                str(payload.get("effective_plan_role") or "adopted"),
                payload.get("scenario_id"),
                required_text["event_type"],
                required_text["reported_status"],
                required_text["event_time"],
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

    def list_events_by_op_id(self, op_id: int) -> List[OperationExecutionEvent]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql()}
            FROM OperationExecutionEvents
            WHERE op_id = ?
            ORDER BY id ASC
            """,
            (int(op_id),),
        )
        return [OperationExecutionEvent.from_row(row) for row in rows]

    def list_events_by_op_ids(self, op_ids: Sequence[int]) -> List[OperationExecutionEvent]:
        ids = _positive_ids(op_ids)
        if not ids:
            return []
        out: List[OperationExecutionEvent] = []
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"""
                SELECT {_columns_sql()}
                FROM OperationExecutionEvents
                WHERE op_id IN ({placeholders})
                ORDER BY op_id ASC, id ASC
                """,
                tuple(chunk),
            )
            out.extend(OperationExecutionEvent.from_row(row) for row in rows)
        return out

    def list_latest_events_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionEvent]:
        latest: Dict[int, OperationExecutionEvent] = {}
        for event in self.list_events_by_op_ids(op_ids):
            latest[int(event.op_id)] = event
        return latest

    def list_latest_exception_events_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionEvent]:
        latest: Dict[int, OperationExecutionEvent] = {}
        for event in self.list_events_by_op_ids(op_ids):
            if event.event_type == EXECUTION_EVENT_EXCEPTION:
                latest[int(event.op_id)] = event
        return latest

    def aggregate_states_by_op_ids(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionState]:
        ids = _positive_ids(op_ids)
        batch_ids = self._batch_ids_by_op_ids(ids)
        events_by_op: Dict[int, List[OperationExecutionEvent]] = {op_id: [] for op_id in ids}
        for event in self.list_events_by_op_ids(ids):
            events_by_op.setdefault(int(event.op_id), []).append(event)

        machine_labels = self._machine_labels(self._machine_ids(events_by_op))
        operator_labels = self._operator_labels(self._operator_ids(events_by_op))
        states: Dict[int, OperationExecutionState] = {}
        for op_id in ids:
            states[op_id] = self._aggregate_single_state(
                op_id=op_id,
                batch_id=batch_ids.get(op_id),
                events=events_by_op.get(op_id) or [],
                machine_labels=machine_labels,
                operator_labels=operator_labels,
            )
        return states

    def state_revision_for_op(self, op_id: int) -> str:
        state = self.aggregate_states_by_op_ids([int(op_id)]).get(int(op_id))
        return state.state_revision if state is not None else f"{int(op_id)}:0:0"

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

    def _machine_labels(self, machine_ids: Sequence[str]) -> Dict[str, str]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in machine_ids) if item]
        if not ids:
            return {}
        out: Dict[str, str] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"SELECT machine_id, name FROM Machines WHERE machine_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                machine_id = str(row.get("machine_id") or "")
                out[machine_id] = str(row.get("name") or machine_id)
        return out

    def _operator_labels(self, operator_ids: Sequence[str]) -> Dict[str, str]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in operator_ids) if item]
        if not ids:
            return {}
        out: Dict[str, str] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"SELECT operator_id, name FROM Operators WHERE operator_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                operator_id = str(row.get("operator_id") or "")
                out[operator_id] = str(row.get("name") or operator_id)
        return out

    @staticmethod
    def _machine_ids(events_by_op: Dict[int, List[OperationExecutionEvent]]) -> List[str]:
        out: List[str] = []
        for events in events_by_op.values():
            for event in events:
                for value in (event.actual_machine_id, event.affected_machine_id):
                    if value:
                        out.append(str(value))
        return out

    @staticmethod
    def _operator_ids(events_by_op: Dict[int, List[OperationExecutionEvent]]) -> List[str]:
        out: List[str] = []
        for events in events_by_op.values():
            for event in events:
                for value in (event.actual_operator_id, event.affected_operator_id):
                    if value:
                        out.append(str(value))
        return out

    def _aggregate_single_state(
        self,
        *,
        op_id: int,
        batch_id: Optional[str],
        events: List[OperationExecutionEvent],
        machine_labels: Dict[str, str],
        operator_labels: Dict[str, str],
    ) -> OperationExecutionState:
        if not events:
            return OperationExecutionState(
                op_id=int(op_id),
                batch_id=batch_id,
                state_revision=f"{int(op_id)}:0:0",
            )

        last_event = events[-1]
        latest_exception = self._latest_exception(events)
        actual_start_time = self._first_event_time(events, EXECUTION_EVENT_START)
        actual_end_time = self._last_event_time(events, EXECUTION_EVENT_FINISH)
        actual_machine_id = self._last_text(events, "actual_machine_id")
        actual_operator_id = self._last_text(events, "actual_operator_id")
        current_status = last_event.reported_status or _REPORTED_STATUS_BY_EVENT_TYPE.get(
            last_event.event_type, EXECUTION_STATUS_NOT_STARTED
        )
        return OperationExecutionState(
            op_id=int(op_id),
            batch_id=last_event.batch_id or batch_id,
            current_status=current_status,
            current_status_label=execution_status_label(current_status),
            actual_start_time=actual_start_time,
            actual_end_time=actual_end_time,
            actual_duration_minutes=_duration_minutes(actual_start_time, actual_end_time),
            pause_duration_minutes=self._pause_duration_minutes(events),
            actual_machine_id=actual_machine_id,
            actual_machine_label=machine_labels.get(actual_machine_id or "") if actual_machine_id else None,
            actual_operator_id=actual_operator_id,
            actual_operator_label=operator_labels.get(actual_operator_id or "") if actual_operator_id else None,
            last_event_id=last_event.id,
            last_event_type=last_event.event_type,
            last_event_time=last_event.event_time,
            last_event_action_label=execution_action_label(event_type_to_action(last_event.event_type)),
            last_event_remark=self._event_remark(last_event),
            latest_exception_event_id=None if latest_exception is None else latest_exception.id,
            latest_exception_time=None if latest_exception is None else latest_exception.event_time,
            latest_exception_reason_code=None if latest_exception is None else latest_exception.reason_code,
            latest_exception_reason_label=None
            if latest_exception is None
            else exception_reason_label(latest_exception.reason_code),
            latest_exception_severity=None if latest_exception is None else latest_exception.severity,
            latest_exception_severity_label=None
            if latest_exception is None
            else severity_label(latest_exception.severity),
            latest_exception_impact_minutes=None if latest_exception is None else latest_exception.impact_minutes,
            latest_exception_impact_minutes_label=None
            if latest_exception is None
            else _impact_minutes_label(latest_exception.impact_minutes),
            latest_exception_affected_machine_id=None
            if latest_exception is None
            else latest_exception.affected_machine_id,
            latest_exception_affected_machine_label=self._label(
                machine_labels,
                None if latest_exception is None else latest_exception.affected_machine_id,
            ),
            latest_exception_affected_operator_id=None
            if latest_exception is None
            else latest_exception.affected_operator_id,
            latest_exception_affected_operator_label=self._label(
                operator_labels,
                None if latest_exception is None else latest_exception.affected_operator_id,
            ),
            latest_exception_handling_status=None if latest_exception is None else latest_exception.handling_status,
            latest_exception_handling_status_label=None
            if latest_exception is None
            else handling_status_label(latest_exception.handling_status),
            latest_exception_suggest_reschedule=False
            if latest_exception is None
            else _suggest_reschedule_bool(latest_exception.suggest_reschedule),
            latest_exception_suggest_reschedule_label=None
            if latest_exception is None
            else suggest_reschedule_label(latest_exception.suggest_reschedule),
            latest_exception_remark=None if latest_exception is None else self._event_remark(latest_exception),
            state_revision=f"{int(op_id)}:{len(events)}:{int(last_event.id or 0)}",
            updated_at=last_event.event_time,
        )

    @staticmethod
    def _event_remark(event: OperationExecutionEvent) -> Optional[str]:
        return event.remark or event.reason_detail

    @staticmethod
    def _latest_exception(events: Sequence[OperationExecutionEvent]) -> Optional[OperationExecutionEvent]:
        for event in reversed(events):
            if event.event_type == EXECUTION_EVENT_EXCEPTION:
                return event
        return None

    @staticmethod
    def _first_event_time(events: Sequence[OperationExecutionEvent], event_type: str) -> Optional[str]:
        for event in events:
            if event.event_type == event_type:
                return event.event_time
        return None

    @staticmethod
    def _last_event_time(events: Sequence[OperationExecutionEvent], event_type: str) -> Optional[str]:
        for event in reversed(events):
            if event.event_type == event_type:
                return event.event_time
        return None

    @staticmethod
    def _last_text(events: Sequence[OperationExecutionEvent], field: str) -> Optional[str]:
        for event in reversed(events):
            value = getattr(event, field)
            if value:
                return str(value)
        return None

    @staticmethod
    def _pause_duration_minutes(events: Sequence[OperationExecutionEvent]) -> float:
        total = 0.0
        pause_started_at: Optional[str] = None
        for event in events:
            if event.event_type == EXECUTION_EVENT_PAUSE:
                pause_started_at = event.event_time
                continue
            if pause_started_at and event.event_type in (
                EXECUTION_EVENT_RESUME,
                EXECUTION_EVENT_FINISH,
                EXECUTION_EVENT_EXCEPTION,
            ):
                minutes = _duration_minutes(pause_started_at, event.event_time)
                if minutes is not None:
                    total += float(minutes)
                pause_started_at = None
        return total

    @staticmethod
    def _label(labels: Dict[str, str], value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return labels.get(str(value), str(value))


OperationExecutionEventRepository = OperationExecutionEventRepo

__all__ = ["OperationExecutionEventRepo", "OperationExecutionEventRepository"]
