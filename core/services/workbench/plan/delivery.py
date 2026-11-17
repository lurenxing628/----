"""Planned batch delivery: one admission of the batches a plan scope selects, read in the caller's transaction."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.facts.delivery_projection import (
    DeliveryBatch,
    DeliveryTask,
    delivery_summary,
    project_delivery_batch,
)
from core.shared.local_datetime import us_to_datetime
from data.repositories.workbench_plan_delivery_repo import WorkbenchPlanDeliveryRepository

from .read_context import PlanReadContext


@dataclass(frozen=True)
class PlanDeliveryAdmission:
    """The selected batches' delivery input, and what of the selection could not be admitted.

    ``batches`` are the selected batches with a stored row and an active permanent ref, in batch order;
    ``scope_issues`` concern the whole selection (a deferred operation whose batch is unknown). The official plan
    view rejects a selection with anything missing; the dashboard keeps evaluating the admitted batches.
    """

    batches: Tuple[DeliveryBatch, ...]
    deferred_operation_ids: FrozenSet[int]
    scope_issues: Tuple[str, ...]
    missing_batch_ids: Tuple[str, ...]
    missing_identity_ids: Tuple[str, ...]

    def items(self, *, scope_issues: Tuple[str, ...]) -> List[Dict[str, Any]]:
        return [project_delivery_batch(item, deferred_operation_ids=self.deferred_operation_ids,
                                       scope_issues=scope_issues) for item in self.batches]


def plan_delivery_batch(batch, batch_ref, rows, operation_ids) -> DeliveryBatch:
    """One batch's delivery input from its stored plan rows; each row's own ``end_us`` is its finish."""
    return DeliveryBatch(batch, batch_ref, frozenset(operation_ids),
                         tuple(DeliveryTask(row["op_id"], us_to_datetime(row["end_us"])) for row in rows), False, ())


def admit_plan_delivery(context: PlanReadContext, entry, scope: PlanReadScope, *, logger=None) -> PlanDeliveryAdmission:
    """Select the batches with a task in the scope (a whole-plan scope adds the deferred operations' batches),
    then admit each against its stored row and active ref; completion always counts the FULL plan rows."""
    repo = WorkbenchPlanDeliveryRepository(context.conn, logger=logger)
    deferred = context.history_documents(entry.plan_identity.version).deferred_operation_ids
    rows = context.detail_rows(entry)
    keys = {row["batch_id"] for row in context.scoped_rows(entry, scope)}
    scope_issues: Tuple[str, ...] = ()
    if scope.range_start is None and deferred:
        found = repo.list_operation_batch_ids(deferred)
        keys |= {row["batch_id"] for row in found}
        if {row["op_id"] for row in found} != deferred:
            scope_issues = ("deferred_operation_source_missing",)
    selected = sorted(keys)
    batches = {row["batch_id"]: row for row in repo.list_batches_by_ids(selected)}
    present = [key for key in selected if key in batches]
    refs = context.active_map("batch", present)
    admitted = [key for key in present if key in refs]
    tasks, operations = defaultdict(list), defaultdict(list)
    for row in rows:
        tasks[row["batch_id"]].append(row)
    for row in repo.list_batch_operations_by_ids(admitted):
        operations[row["batch_id"]].append(row["op_id"])
    return PlanDeliveryAdmission(
        tuple(plan_delivery_batch(batches[key], refs[key].ref, tasks[key], operations[key]) for key in admitted),
        deferred, scope_issues,
        tuple(key for key in selected if key not in batches), tuple(key for key in present if key not in refs),
    )


def read_plan_delivery(conn, *, scope: PlanReadScope, context: PlanReadContext, logger=None) -> Dict[str, Any]:
    """The official plan's delivery view; every selected batch must be admitted."""
    if not conn.in_transaction:
        raise RuntimeError("Delivery reads require a caller-owned read transaction.")
    with context.read_scope():
        entry, _ = context.selected(scope.plan_ref)
        admission = admit_plan_delivery(context, entry, scope, logger=logger)
    if admission.missing_batch_ids:
        raise WorkbenchCommandRejected("plan_unavailable", "计划涉及的批次已不存在，请到批次管理核对。")
    if admission.missing_identity_ids:
        raise WorkbenchCommandRejected("identity_missing", "批次编号缺失，无法评估交付风险。请到批次管理核对。")
    return plan_delivery_view(scope, admission.items(scope_issues=admission.scope_issues))


def plan_delivery_view(scope: PlanReadScope, items) -> Dict[str, Any]:
    return {
        "state": "loaded",
        "plan_ref": scope.plan_ref,
        "scope": scope.scope(),
        "items": items,
        "batch_count": len(items),
        "items_complete": True,
        "completeness": _completeness(items),
        "summary": delivery_summary(items),
        "basis": {
            "kind": "planned_delivery",
            "time_basis": "factory_local",
            "completion_scope": "full_selected_plan",
            "operation_scope": "current_batch_operations",
            "due_boundary": "next_day_exclusive",
            "actual_completion": "not_evaluated",
            "actual_delivery": "not_evaluated",
        },
    }


def _completeness(items):
    states = {row["completeness"] for row in items}
    if "incomplete" in states:
        return "incomplete"
    return "unknown" if not items or "unknown" in states else "complete"
