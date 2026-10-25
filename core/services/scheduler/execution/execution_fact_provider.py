from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from core.models.operation_execution_event import (
    OperationExecutionEvent,
    parse_operation_event_time,
    validate_operation_execution_event_sequence,
)
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.workbench_execution import ExecutionProjection
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from data.repositories.operation_execution_state_builder import fold_operation_execution_events

from .execution_ledger_adapter import adapt_ledger_facts, ledger_read_snapshot
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


def _fact_from_events(scope: OperationExecutionScope, events: Sequence[OperationExecutionEvent]) -> ExecutionFact:
    folded = fold_operation_execution_events(op_id=scope.op_id, batch_id=scope.batch_id, events=events)
    exception = folded.latest_exception
    return ExecutionFact(
        op_id=scope.op_id, batch_id=folded.batch_id, actual_status=folded.current_status,
        actual_start_time=None if folded.actual_start_time is None else parse_operation_event_time(folded.actual_start_time),
        actual_end_time=None if folded.actual_end_time is None else parse_operation_event_time(folded.actual_end_time),
        actual_machine_id=folded.actual_machine_id, actual_operator_id=folded.actual_operator_id,
        state_revision=folded.state_revision,
        latest_exception_impact_minutes=None if exception is None else exception.impact_minutes,
        latest_exception_handling_status=None if exception is None else exception.handling_status,
        latest_exception_suggest_reschedule=False if exception is None else bool(exception.suggest_reschedule),
        schedule_version=scope.schedule_version, schedule_id=scope.schedule_id,
        source_table=scope.source_table, effective_plan_role=scope.effective_plan_role, scenario_id=scope.scenario_id,
    )


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
        with ledger_read_snapshot(self.conn, ledger=self.ledger) as ledger:
            facts = self._legacy_facts(normalized)
            if ledger is None:
                if execution_projections:
                    raise ValueError("旧版本数据库不能接收执行台账投影。")
                return facts
            return adapt_ledger_facts(ledger, facts, execution_projections=execution_projections)

    def _legacy_facts(self, normalized: Sequence[OperationExecutionScope]) -> Dict[OperationExecutionScope, ExecutionFact]:
        if self.capture is not None:
            return self._captured_facts(normalized)
        events_by_scope = self.event_repo.list_events_by_scopes(normalized)
        return {scope: _fact_from_events(scope, events_by_scope.get(scope, ())) for scope in normalized}

    def _captured_facts(self, scopes):
        capture = self.capture
        if capture.execution_event_rows is None:
            capture.execution_event_rows = {}
            for row in capture.table("OperationExecutionEvents"):
                scope = OperationExecutionScope(
                    schedule_version=row["schedule_version"], schedule_id=row["schedule_id"], op_id=row["op_id"],
                    batch_id=row["batch_id"], source_table=row["source_table"],
                    effective_plan_role=row["effective_plan_role"], scenario_id=row["scenario_id"],
                )
                capture.execution_event_rows.setdefault(scope, []).append(row)
        for scope in scopes:
            if scope in capture.execution_facts:
                continue
            events = [OperationExecutionEvent.from_row(row) for row in capture.execution_event_rows.get(scope, ())]
            validate_operation_execution_event_sequence(events)
            capture.execution_facts[scope] = _fact_from_events(scope, events)
        return {scope: capture.execution_facts[scope] for scope in scopes}

    def facts_by_op_id_for_plan_rows(
        self,
        rows: Sequence[Mapping[str, Any]],
        plan_fields: Mapping[str, Any],
        *,
        execution_projections: Optional[Sequence[ExecutionProjection]] = None,
    ) -> Dict[int, ExecutionFact]:
        scopes_by_op_id = scopes_by_op_id_for_plan_rows(rows, plan_fields)
        facts_by_scope = self.facts_by_scope(
            list(scopes_by_op_id.values()),
            execution_projections=execution_projections,
        )
        return {op_id: facts_by_scope[scope] for op_id, scope in scopes_by_op_id.items()}


__all__ = ["ExecutionFact", "ExecutionFactProvider"]
