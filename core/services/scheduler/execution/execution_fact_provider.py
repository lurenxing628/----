from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.models.operation_execution_event import (
    EXECUTION_STATUS_NOT_STARTED,
    OperationExecutionEvent,
    parse_operation_event_time,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.workbench_execution import ExecutionProjection
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from data.repositories.operation_execution_state_builder import build_operation_execution_state

from .execution_ledger_adapter import adapt_ledger_facts, ledger_read_snapshot
from .operation_execution_scope_read import scopes_by_op_id_for_plan_rows


def positive_op_ids(values: Sequence[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for raw in values or ():
        try:
            op_id = int(raw)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    # 固定工序集合顺序，使相同来源的快照内容不受调用方排列顺序影响。
    return sorted(out)


@dataclass(frozen=True)
class ExecutionFact:
    op_id: int
    batch_id: Optional[str]
    actual_status: str
    actual_start_time: Optional[datetime]
    actual_end_time: Optional[datetime]
    actual_machine_id: Optional[str]
    actual_operator_id: Optional[str]
    state_revision: str
    latest_exception_impact_minutes: Optional[int] = None
    latest_exception_handling_status: Optional[str] = None
    latest_exception_suggest_reschedule: bool = False
    schedule_version: Optional[int] = None
    schedule_id: Optional[int] = None
    source_table: Optional[str] = None
    effective_plan_role: Optional[str] = None
    scenario_id: Optional[str] = None
    ledger_operation_ref: Optional[str] = None
    ledger_execution_state: Optional[str] = None
    remaining_quantity: Optional[int] = None
    target_quantity: Optional[int] = None
    quantity_basis: Optional[str] = None
    execution_effective_intervals: Tuple[Tuple[datetime, datetime], ...] = ()
    execution_protection_reasons: Tuple[str, ...] = ()
    execution_protection_content: Optional[Dict[str, Any]] = None


def _state_value(state, attr: str):
    return None if state is None else getattr(state, attr)


def _fact_from_state(
    op_id: int,
    state,
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


def _parse_execution_time(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return parse_operation_event_time(value)


class ExecutionFactProvider:
    """读取现场执行事实。

    具体计划页和重排保护必须按计划身份读取。
    """

    def __init__(self, conn, logger=None, *, capture=None, ledger=None):
        self.conn = conn
        self.logger = logger
        self.event_repo = OperationExecutionEventRepo(conn, logger=logger)
        self.capture: Any = capture
        self.ledger = ledger

    def facts_by_scope(
        self, scopes: Sequence[OperationExecutionScope], *,
        execution_projections: Optional[Sequence[ExecutionProjection]] = None,
    ) -> Dict[OperationExecutionScope, ExecutionFact]:
        normalized = list(dict.fromkeys(scopes or ()))
        # The injectable legacy repository also supports connection-free unit tests.
        if self.conn is None:
            if execution_projections is not None:
                raise ValueError("执行投影适配需要真实连接核对永久计划身份。")
            return self._legacy_facts(normalized)
        with ledger_read_snapshot(self.conn, ledger=self.ledger) as ledger:
            facts = self._legacy_facts(normalized)
            if ledger is None:
                if execution_projections:
                    raise ValueError("旧版本数据库不能接收执行台账投影。")
                return facts
            return adapt_ledger_facts(ledger, facts, execution_projections=execution_projections)

    def _legacy_facts(self, normalized: Sequence[OperationExecutionScope]) -> Dict[OperationExecutionScope, ExecutionFact]:
        if self.capture is None:
            states = self.event_repo.aggregate_states_by_scopes(normalized)
        else:
            states = self._captured_states(normalized)
        return {
            scope: _fact_from_state(
                int(scope.op_id),
                states.get(scope),
                scope=scope,
            )
            for scope in normalized
        }

    def _captured_states(self, scopes):
        capture = self.capture
        scope_fields = ("schedule_version", "schedule_id", "op_id", "batch_id", "source_table", "effective_plan_role", "scenario_id")
        if not hasattr(capture, "execution_event_rows"):
            capture.execution_event_rows, capture.execution_states = {}, {}
            for row in capture.table("OperationExecutionEvents"):
                key = tuple(row[field] for field in scope_fields)
                capture.execution_event_rows.setdefault(key, []).append(row)
            from core.models.resource_identity import build_resource_identity

            capture.execution_machine_identities = {
                row["machine_id"]: build_resource_identity(resource_id=row["machine_id"], resource_name=row["name"])
                for row in capture.table("Machines")}
            capture.execution_operator_identities = {
                row["operator_id"]: build_resource_identity(resource_id=row["operator_id"], resource_name=row["name"])
                for row in capture.table("Operators")}
        for scope in scopes:
            if scope in capture.execution_states:
                continue
            key = tuple(getattr(scope, field) for field in scope_fields)
            events = [OperationExecutionEvent.from_row(row) for row in capture.execution_event_rows.get(key, ())]
            validate_operation_execution_event_sequence(events)
            capture.execution_states[scope] = build_operation_execution_state(
                op_id=scope.op_id, batch_id=scope.batch_id, events=events,
                machine_resources=capture.execution_machine_identities,
                operator_resources=capture.execution_operator_identities)
        return {scope: capture.execution_states[scope] for scope in scopes}

    def facts_by_op_id_for_scopes(
        self,
        scopes: Sequence[OperationExecutionScope],
        *,
        include_op_ids: Sequence[int] = (),
        execution_projections: Optional[Sequence[ExecutionProjection]] = None,
    ) -> Dict[int, ExecutionFact]:
        facts_by_scope = self.facts_by_scope(scopes, execution_projections=execution_projections)
        out: Dict[int, ExecutionFact] = {}
        scopes_by_op_id: Dict[int, OperationExecutionScope] = {}
        for scope, fact in facts_by_scope.items():
            op_id = int(scope.op_id)
            existing = scopes_by_op_id.get(op_id)
            if existing is not None and existing != scope:
                raise ValueError(f"工序 {op_id} 对应多个现场执行身份，不能按 op_id 合并读取。")
            scopes_by_op_id[op_id] = scope
            out[op_id] = fact
        missing = [op_id for op_id in positive_op_ids(include_op_ids) if op_id not in out]
        if missing:
            raise ValueError(f"现场执行事实缺少完整计划身份：op_id={missing[0]}")
        return out

    def facts_by_op_id_for_plan_rows(
        self,
        rows: Sequence[Any],
        plan_fields: Mapping[str, Any],
        *,
        include_op_ids: Sequence[int] = (),
        execution_projections: Optional[Sequence[ExecutionProjection]] = None,
    ) -> Dict[int, ExecutionFact]:
        scopes_by_op_id = scopes_by_op_id_for_plan_rows(rows, plan_fields)
        facts_by_scope = self.facts_by_scope(
            list(scopes_by_op_id.values()),
            execution_projections=execution_projections,
        )
        out = {op_id: facts_by_scope[scope] for op_id, scope in scopes_by_op_id.items()}
        missing = [op_id for op_id in positive_op_ids(include_op_ids) if op_id not in out]
        if missing:
            raise ValueError(f"现场执行事实缺少完整计划身份：op_id={missing[0]}")
        return out


__all__ = ["ExecutionFact", "ExecutionFactProvider"]
