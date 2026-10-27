"""Read-only planned batch delivery, designed for the workspace's read transaction.

read_plan_delivery(conn, *, scope, identity, context, logger=None) -> (public, private_facts)
The caller passes its exact resolved PlanIdentity, PlanReadScope and PlanReadContext. It owns the
transaction and incorporates private_facts into its unified snapshot fingerprint;
never serialize that second value. No clock, actual completion or shipment is
inferred here. No current-official capability is assigned by this projection.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.facts.delivery_completeness import completion_evidence
from core.services.workbench.facts.delivery_projection import (
    delivery_summary,
    project_delivery_batch,
    selected_batch_keys,
    task_intervals,
)
from core.services.workbench.facts.material_deferral_evidence import archived_deferred_operation_evidence
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

from .delivery_repository import PlanDeliveryRepository
from .read_context import PlanReadContext


def read_plan_delivery(
    conn, *, scope: PlanReadScope, identity: PlanIdentity, context: PlanReadContext, logger=None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Select task-overlap batches, calculate completion from their FULL plan rows.

    Every current BatchOperations row must be covered at least once. Segments and
    duplicates count once per operation but all affect the last planned finish.
    This is an operation-coverage check, not a historical frozen route or an
    execution/quantity/actual-delivery certificate. Rows with invalid times never
    reach here: plan admission (``context.selected``) rejects such a plan.
    """
    if not conn.in_transaction:
        raise RuntimeError("Delivery reads require a caller-owned read transaction.")
    with context.read_scope():
        return _read_plan_delivery(conn, scope=scope, identity=identity, logger=logger, context=context)


def _read_plan_delivery(conn, *, scope, identity, logger, context):
    repo = PlanDeliveryRepository(conn, logger=logger)
    repo.validate_identity(scope, identity, context=context)
    _, entry, _ = context.selected(scope.plan_ref)
    rows = repo.task_rows(context=context, entry=entry)
    intervals = task_intervals(rows)
    keys = selected_batch_keys(rows, intervals, scope)
    record = repo.completion_record(identity, context=context)
    deferred, deferred_issues = archived_deferred_operation_evidence(record)
    if scope.range_start is None and deferred:
        pending_keys, pending_issues = repo.deferred_batch_keys(deferred)
        keys = sorted(set(keys) | pending_keys)
        deferred_issues.extend(pending_issues)
    batches, operations = repo.batch_facts(keys)
    references = context.active_map("batch", keys)
    if set(references) != set(keys):
        raise WorkbenchCommandRejected("identity_missing", "批次编号缺失，无法评估交付风险。请到批次管理核对。")
    items = _delivery_items(rows, operations, batches, intervals, references, record, deferred, deferred_issues)
    public = {"state": "loaded", "plan_ref": scope.plan_ref, "scope": scope.scope(), "items": items,
              "batch_count": len(items), "items_complete": True, "completeness": _completeness(items),
              "summary": delivery_summary(items),
              "basis": {"kind": "planned_delivery", "time_basis": "factory_local",
                        "batch_selection": "plan_task_and_deferred_batches" if scope.range_start is None else "overlap_or_bad_time_batches",
                        "completion_scope": "full_selected_plan", "operation_scope": "current_batch_operations",
                        "due_boundary": "next_day_exclusive", "actual_completion": "not_evaluated",
                        "actual_delivery": "not_evaluated"}}
    facts = {"identity": {"version": identity.version, "role": identity.effective_plan_role,
                          "source_table": identity.source_table},
             "scope": scope.scope(), "tasks": rows, "batches": batches, "operations": operations,
             "completion_record": record,
             "batch_identities": [(key, references[key].ref, references[key].revision) for key in keys]}
    return public, facts


def _delivery_items(rows, operations, batches, intervals, references, record, deferred, deferred_issues):
    tasks_by_batch, operations_by_batch = defaultdict(list), defaultdict(list)
    finish_by_batch = {}
    for row in rows:
        tasks_by_batch[row["batch_id"]].append(row)
        interval = intervals[row["schedule_id"]]
        if interval is not None:
            finish_by_batch[row["batch_id"]] = max(interval[1], finish_by_batch.get(row["batch_id"], interval[1]))
    incomplete, uncertain = completion_evidence(record, finish_by_batch)
    uncertain.extend(deferred_issues)
    for operation in operations:
        operations_by_batch[operation["batch_id"]].append(operation)
    return [project_delivery_batch(batch, references[batch["batch_id"]].ref, tasks_by_batch[batch["batch_id"]],
                                    operations_by_batch[batch["batch_id"]], intervals,
                                    batch["batch_id"] in incomplete, uncertain,
                                    deferred_operation_ids=deferred) for batch in batches]


def _completeness(items):
    states = {row["completeness"] for row in items}
    if "incomplete" in states:
        return "incomplete"
    return "unknown" if not items or "unknown" in states else "complete"
