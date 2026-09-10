"""Read-only planned batch delivery, designed for the workspace's read transaction.

read_plan_delivery(conn, *, scope, identity, logger=None) -> (public, private_facts)
The caller passes its exact resolved PlanIdentity and PlanReadScope. It owns the
transaction and incorporates private_facts into its unified snapshot fingerprint;
never serialize that second value. No clock, actual completion or shipment is
inferred here. No current-official capability is assigned by this projection.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES, PlanReadScope
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

from .plan_delivery_completeness import completion_evidence
from .plan_delivery_projection import project_delivery_batch, selected_batch_keys, task_intervals
from .plan_delivery_repository import PlanDeliveryRepository
from .plan_point_evidence import annotate_plan_points


def read_plan_delivery(
    conn, *, scope: PlanReadScope, identity: PlanIdentity, logger=None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Select task-overlap batches, calculate completion from their FULL plan rows.

    Every current BatchOperations row must be covered at least once. Segments and
    duplicates count once per operation but all affect the last planned finish.
    This is an operation-coverage check, not a historical frozen route or an
    execution/quantity/actual-delivery certificate. Invalid-time rows participate
    in every range, matching the existing task overlap-or-bad-time convention.
    """
    if not conn.in_transaction:
        raise RuntimeError("Delivery reads require a caller-owned read transaction.")
    repo = PlanDeliveryRepository(conn, logger=logger)
    scenario = repo.validate_identity(scope, identity)
    rows = _delivery_rows(conn, repo.task_rows(identity), identity.source_table)
    intervals = task_intervals(rows)
    keys = selected_batch_keys(rows, intervals, scope)
    batches, operations = repo.batch_facts(keys)
    references = WorkbenchIdentityRepository(conn, logger=logger).active_map("batch", keys)
    if set(references) != set(keys):
        raise WorkbenchCommandRejected("identity_missing", "批次永久身份缺失，交付读取不会补建或替换引用。")
    record = repo.completion_record(identity, scenario)
    items = _delivery_items(rows, operations, batches, intervals, references, record)
    public = {"state": "loaded", "plan_ref": scope.plan_ref, "scope": scope.scope(), "items": items,
              "batch_count": len(items), "items_complete": True, "completeness": _completeness(items),
              "basis": {"kind": "planned_delivery", "time_basis": "factory_local",
                        "batch_selection": "plan_task_batches" if scope.range_start is None else "overlap_or_bad_time_batches",
                        "completion_scope": "full_selected_plan", "operation_scope": "current_batch_operations",
                        "due_boundary": "next_day_exclusive", "actual_completion": "not_evaluated",
                        "actual_delivery": "not_evaluated"}}
    if len(canonical_json(public).encode("utf-8")) > MAX_PLAN_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "交付查询结果超过 8 MiB 上限，未返回截断结果。", 413)
    facts = {"identity": {"version": identity.version, "role": identity.effective_plan_role,
                          "source_table": identity.source_table, "candidate_id": identity.candidate_id,
                          "candidate_key": identity.candidate_key, "scenario_id": identity.scenario_id},
             "scope": scope.scope(), "tasks": rows, "batches": batches, "operations": operations,
             "completion_record": record,
             "batch_identities": [(key, references[key].ref, references[key].revision) for key in keys]}
    return public, facts


def _delivery_rows(conn, rows, source_table):
    try:
        return annotate_plan_points(conn, rows, source_table=source_table)
    except WorkbenchCommandRejected as exc:
        if exc.code != "point_evidence_unproven":
            raise
        # Legacy delivery keeps bad rows visible and marks completion unknown.
        # This is not permission to interpret an unproven equal row as a point.
        return [dict(row, point_evidence_issue=exc.code) if row["start_time"] == row["end_time"] else row for row in rows]


def _delivery_items(rows, operations, batches, intervals, references, record):
    tasks_by_batch, operations_by_batch = defaultdict(list), defaultdict(list)
    finish_by_batch = {}
    for row in rows:
        tasks_by_batch[row["batch_id"]].append(row)
        interval = intervals[row["schedule_id"]]
        if interval is not None:
            finish_by_batch[row["batch_id"]] = max(interval[1], finish_by_batch.get(row["batch_id"], interval[1]))
    incomplete, uncertain = completion_evidence(record, len(rows), finish_by_batch)
    for operation in operations:
        operations_by_batch[operation["batch_id"]].append(operation)
    return [project_delivery_batch(batch, references[batch["batch_id"]].ref, tasks_by_batch[batch["batch_id"]],
                                    operations_by_batch[batch["batch_id"]], intervals,
                                    batch["batch_id"] in incomplete, uncertain) for batch in batches]


def _completeness(items):
    states = {row["completeness"] for row in items}
    if "incomplete" in states:
        return "incomplete"
    return "unknown" if not items or "unknown" in states else "complete"
