from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Union

from core.models.operation_execution_event import (
    EXECUTION_EVENT_EXCEPTION,
    OperationExecutionEvent,
)
from core.models.operation_execution_state import OperationExecutionState
from core.models.resource_identity import ResourceIdentity, build_resource_identity

from .base_repo import BaseRepository
from .operation_execution_state_builder import build_operation_execution_state

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


def _resource_identity(resource_id: Any, resource_name: Any) -> ResourceIdentity:
    return build_resource_identity(resource_id=resource_id, resource_name=resource_name)


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

        machine_resources = self._machine_resources(self._machine_ids(events_by_op))
        operator_resources = self._operator_resources(self._operator_ids(events_by_op))
        states: Dict[int, OperationExecutionState] = {}
        for op_id in ids:
            states[op_id] = self._aggregate_single_state(
                op_id=op_id,
                batch_id=batch_ids.get(op_id),
                events=events_by_op.get(op_id) or [],
                machine_resources=machine_resources,
                operator_resources=operator_resources,
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

    def _machine_resources(self, machine_ids: Sequence[str]) -> Dict[str, ResourceIdentity]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in machine_ids) if item]
        if not ids:
            return {}
        out: Dict[str, ResourceIdentity] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"SELECT machine_id, name FROM Machines WHERE machine_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                machine_id = str(row.get("machine_id") or "")
                out[machine_id] = _resource_identity(machine_id, row.get("name"))
        return out

    def _operator_resources(self, operator_ids: Sequence[str]) -> Dict[str, ResourceIdentity]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in operator_ids) if item]
        if not ids:
            return {}
        out: Dict[str, ResourceIdentity] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.fetchall(
                f"SELECT operator_id, name FROM Operators WHERE operator_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                operator_id = str(row.get("operator_id") or "")
                out[operator_id] = _resource_identity(operator_id, row.get("name"))
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
        machine_resources: Dict[str, ResourceIdentity],
        operator_resources: Dict[str, ResourceIdentity],
    ) -> OperationExecutionState:
        return build_operation_execution_state(
            op_id=op_id,
            batch_id=batch_id,
            events=events,
            machine_resources=machine_resources,
            operator_resources=operator_resources,
        )



OperationExecutionEventRepository = OperationExecutionEventRepo

__all__ = ["OperationExecutionEventRepo", "OperationExecutionEventRepository"]
