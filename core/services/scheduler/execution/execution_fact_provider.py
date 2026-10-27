from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from core.models.operation_execution_scope import EXECUTION_STATUS_NOT_STARTED, OperationExecutionScope
from core.models.workbench_execution import ExecutionProjection

from .execution_ledger_adapter import adapt_ledger_facts, ledger_read_snapshot
from .operation_execution_scope_read import scopes_by_op_id_for_plan_rows


@dataclass(frozen=True)
class ExecutionFact:
    op_id: int
    batch_id: Optional[str]
    actual_status: str = EXECUTION_STATUS_NOT_STARTED
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    actual_machine_id: Optional[str] = None
    actual_operator_id: Optional[str] = None
    state_revision: str = ""
    schedule_version: Optional[int] = None
    schedule_id: Optional[int] = None
    source_table: Optional[str] = None
    effective_plan_role: Optional[str] = None
    ledger_operation_ref: Optional[str] = None
    ledger_execution_state: Optional[str] = None
    remaining_quantity: Optional[int] = None
    target_quantity: Optional[int] = None
    quantity_basis: Optional[str] = None
    execution_effective_intervals: Tuple[Tuple[datetime, datetime], ...] = ()
    execution_protection_reasons: Tuple[str, ...] = ()
    execution_protection_content: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.state_revision:
            object.__setattr__(self, "state_revision", f"{self.op_id}:0:0")


def _initial_fact(scope: OperationExecutionScope) -> ExecutionFact:
    return ExecutionFact(
        op_id=scope.op_id,
        batch_id=scope.batch_id,
        schedule_version=scope.schedule_version,
        schedule_id=scope.schedule_id,
        source_table=scope.source_table,
        effective_plan_role=scope.effective_plan_role,
    )


class ExecutionFactProvider:
    """读取现场执行事实。

    具体计划页和重排保护必须按计划身份读取。
    """

    def __init__(self, conn, *, ledger=None):
        self.conn = conn
        self.ledger = ledger

    def facts_by_scope(
        self, scopes: Sequence[OperationExecutionScope], *,
        execution_projections: Sequence[ExecutionProjection],
    ) -> Dict[OperationExecutionScope, ExecutionFact]:
        normalized = list(dict.fromkeys(scopes))
        with ledger_read_snapshot(self.conn, ledger=self.ledger) as ledger:
            facts = {scope: _initial_fact(scope) for scope in normalized}
            return adapt_ledger_facts(ledger, facts, execution_projections=execution_projections)

    def facts_by_op_id_for_plan_rows(
        self,
        rows: Sequence[Mapping[str, Any]],
        plan_fields: Mapping[str, Any],
        *,
        execution_projections: Sequence[ExecutionProjection],
    ) -> Dict[int, ExecutionFact]:
        scopes_by_op_id = scopes_by_op_id_for_plan_rows(rows, plan_fields)
        facts_by_scope = self.facts_by_scope(
            list(scopes_by_op_id.values()),
            execution_projections=execution_projections,
        )
        return {op_id: facts_by_scope[scope] for op_id, scope in scopes_by_op_id.items()}


__all__ = ["ExecutionFact", "ExecutionFactProvider"]
