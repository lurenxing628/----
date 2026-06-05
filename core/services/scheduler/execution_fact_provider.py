from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED, OperationExecutionEvent
from core.models.operation_execution_scope import OperationExecutionScope, operation_execution_scope_from_event
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo

from .operation_execution_scope_read import scopes_by_op_id_for_plan_rows


@dataclass(frozen=True)
class ExecutionFact:
    op_id: int
    batch_id: Optional[str]
    actual_status: str
    actual_start_time: Optional[datetime]
    actual_end_time: Optional[datetime]
    actual_machine_id: Optional[str]
    actual_operator_id: Optional[str]
    last_event_schedule_version: Optional[int]
    last_event_schedule_id: Optional[int]
    state_revision: str
    latest_exception_impact_minutes: Optional[int] = None
    latest_exception_handling_status: Optional[str] = None
    latest_exception_suggest_reschedule: bool = False
    schedule_version: Optional[int] = None
    schedule_id: Optional[int] = None
    source_table: Optional[str] = None
    effective_plan_role: Optional[str] = None
    scenario_id: Optional[str] = None


def _state_value(state, attr: str):
    return None if state is None else getattr(state, attr)


def _fact_from_state(
    op_id: int,
    state,
    latest,
    *,
    scope: Optional[OperationExecutionScope] = None,
) -> ExecutionFact:
    status = EXECUTION_STATUS_NOT_STARTED if state is None else str(state.current_status or EXECUTION_STATUS_NOT_STARTED)
    return ExecutionFact(
        op_id=int(op_id),
        batch_id=_state_value(state, "batch_id") or (None if scope is None else scope.batch_id),
        actual_status=status,
        actual_start_time=_parse_execution_time(_state_value(state, "actual_start_time")),
        actual_end_time=_parse_execution_time(_state_value(state, "actual_end_time")),
        actual_machine_id=_state_value(state, "actual_machine_id"),
        actual_operator_id=_state_value(state, "actual_operator_id"),
        last_event_schedule_version=None if latest is None else int(latest.schedule_version),
        last_event_schedule_id=None if latest is None else int(latest.schedule_id),
        state_revision=f"{int(op_id)}:0:0" if state is None else state.state_revision,
        latest_exception_impact_minutes=_state_value(state, "latest_exception_impact_minutes"),
        latest_exception_handling_status=_state_value(state, "latest_exception_handling_status"),
        latest_exception_suggest_reschedule=False if state is None else bool(state.latest_exception_suggest_reschedule),
        schedule_version=None if scope is None else int(scope.schedule_version),
        schedule_id=None if scope is None else int(scope.schedule_id),
        source_table=None if scope is None else scope.source_table,
        effective_plan_role=None if scope is None else scope.effective_plan_role,
        scenario_id=None if scope is None else scope.scenario_id,
    )


def _positive_op_ids(values: Sequence[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for raw in values or []:
        try:
            op_id = int(raw)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    return out


def _parse_execution_time(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


class ExecutionFactProvider:
    """读取现场执行事实。

    具体计划页和重排保护必须按计划身份读取。
    """

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.event_repo = OperationExecutionEventRepo(conn, logger=logger)

    def list_by_op_ids(self, op_ids: Sequence[int]) -> List[ExecutionFact]:
        raise ValueError("现场执行事实必须按完整计划身份读取，不能只按 op_id 聚合。")

    def facts_by_op_id(self, op_ids: Sequence[int]) -> Dict[int, ExecutionFact]:
        raise ValueError("现场执行事实必须按完整计划身份读取，不能只按 op_id 聚合。")

    def facts_by_scope(self, scopes: Sequence[OperationExecutionScope]) -> Dict[OperationExecutionScope, ExecutionFact]:
        normalized = list(dict.fromkeys(scopes or ()))
        states = self.event_repo.aggregate_states_by_scopes(normalized)
        latest_events = self._latest_events_by_scope(normalized)
        return {
            scope: _fact_from_state(
                int(scope.op_id),
                states.get(scope),
                latest_events.get(scope),
                scope=scope,
            )
            for scope in normalized
        }

    def facts_by_op_id_for_scopes(
        self,
        scopes: Sequence[OperationExecutionScope],
        *,
        include_op_ids: Sequence[int] = (),
    ) -> Dict[int, ExecutionFact]:
        facts_by_scope = self.facts_by_scope(scopes)
        out: Dict[int, ExecutionFact] = {}
        scopes_by_op_id: Dict[int, OperationExecutionScope] = {}
        for scope, fact in facts_by_scope.items():
            op_id = int(scope.op_id)
            existing = scopes_by_op_id.get(op_id)
            if existing is not None and existing != scope:
                raise ValueError(f"工序 {op_id} 对应多个现场执行身份，不能按 op_id 合并读取。")
            scopes_by_op_id[op_id] = scope
            out[op_id] = fact
        missing = [op_id for op_id in _positive_op_ids(include_op_ids) if op_id not in out]
        if missing:
            raise ValueError(f"现场执行事实缺少完整计划身份：op_id={missing[0]}")
        return out

    def facts_by_op_id_for_plan_rows(
        self,
        rows: Sequence[Any],
        plan_fields: Mapping[str, Any],
        *,
        include_op_ids: Sequence[int] = (),
    ) -> Dict[int, ExecutionFact]:
        scopes_by_op_id = scopes_by_op_id_for_plan_rows(rows, plan_fields)
        return self.facts_by_op_id_for_scopes(
            list(scopes_by_op_id.values()),
            include_op_ids=include_op_ids,
        )

    def _latest_events_by_scope(
        self,
        scopes: Sequence[OperationExecutionScope],
    ) -> Dict[OperationExecutionScope, OperationExecutionEvent]:
        latest: Dict[OperationExecutionScope, OperationExecutionEvent] = {}
        for event in self.event_repo.list_events_by_scopes(scopes):
            latest[operation_execution_scope_from_event(event)] = event
        return latest


__all__ = ["ExecutionFact", "ExecutionFactProvider"]
