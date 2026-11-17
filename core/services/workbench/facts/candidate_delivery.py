"""Batch delivery from validated candidate rows and immutable admission facts."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .delivery_projection import DeliveryBatch, DeliveryTask, delivery_summary, project_delivery_batch
from .preflight_dependencies import material_deferred_ids

if TYPE_CHECKING:
    from .candidate_facts import GenerationFacts


def captured_delivery_groups(tasks, facts: GenerationFacts, intervals):
    """Each saved task under its archived batch, paired with its delivery task."""
    groups = defaultdict(list)
    for task in tasks:
        operation = facts.operation(task["operation_ref"])
        groups[operation["batch_id"]].append((task, DeliveryTask(operation["id"], intervals[task["row_ref"]][1])))
    return groups


def captured_operation_ids(facts: GenerationFacts, batch_id):
    return frozenset(row["op_id"] for row in facts.operations_by_batch.get(batch_id, ()))


def captured_delivery_batch(facts: GenerationFacts, batch, ref, group, *, incomplete) -> DeliveryBatch:
    return DeliveryBatch(batch, ref, captured_operation_ids(facts, batch["batch_id"]),
                         tuple(task for _, task in group), incomplete, ())


def _selected_keys(settings, facts: GenerationFacts, by_batch, visible, unplanned, scope):
    """The archived batches a delivery view covers. Every requested ref is an archived batch's: the admitted input's
    (``AdmissionBaseline``), the scope's (one of the candidate's batches, ``scope_workspace_tasks``), or a task's or
    unplanned operation's, whose labels come from the archive."""
    batch_ref = scope.batch_ref if scope is not None else None
    range_start = scope.range_start if scope is not None else None
    if batch_ref:
        requested = [batch_ref]
    elif range_start:
        requested = [row["batch_ref"] for row in visible + unplanned]
    else:
        requested = settings["batch_refs"]
    keys = set(by_batch) if batch_ref is None and range_start is None else set()
    keys.update(facts.batch_id(ref) for ref in requested)
    return sorted(keys)


def _last_operations(item, tasks):
    if not item["schedule_complete"] or item["planned_finish"] is None:
        return []
    fields = ("row_ref", "operation_ref", "sequence", "piece_id", "process_label",
              "start", "end", "machine", "operator")
    finish = max(task["end"] for task in tasks)
    return [{key: task[key] for key in fields} for task in tasks
            if task["end"] == finish]


def _items(keys, facts: GenerationFacts, groups, incomplete, deferred, *, precomputed):
    result = []
    for key in keys:
        batch, ref = facts.related("Batches", key), facts.entity_ref("batch", key)
        if precomputed is not None and ref in precomputed:
            item = dict(precomputed[ref])
        else:
            item = project_delivery_batch(captured_delivery_batch(facts, batch, ref, groups[key], incomplete=key in incomplete),
                                          deferred_operation_ids=deferred, scope_issues=())
        item["last_operations"] = _last_operations(item, [task for task, _ in groups[key]])
        result.append(item)
    return result


def _project_items(candidate, facts: GenerationFacts, tasks, settings, deferred_ids, *, intervals, scope=None, visible=(), unplanned=None,
                   precomputed=None):
    groups = captured_delivery_groups(tasks, facts, intervals)
    keys = _selected_keys(settings, facts, groups, visible, unplanned, scope)
    incomplete = set(candidate["artifact"]["metrics"]["completion"]["incomplete_batch_ids"])
    return _items(keys, facts, groups, incomplete, deferred_ids, precomputed=precomputed)


def project_delivery_detail(candidate, facts: GenerationFacts, tasks, settings, *, intervals,
                            deferred_ids, precomputed_delivery=None):
    """Keep all whole-candidate batch rows and every tied last operation for saved detail."""
    precomputed = (
        {row["batch_ref"]: row for row in precomputed_delivery}
        if precomputed_delivery is not None
        else None
    )
    return _project_items(candidate, facts, tasks, settings, deferred_ids,
                          intervals=intervals, precomputed=precomputed)


def candidate_delivery_risks(candidate, facts: GenerationFacts, tasks, disposition, scope, settings, visible, unplanned, *, intervals):
    """Select by display scope, but calculate every selected batch in full."""
    items = _project_items(candidate, facts, tasks, settings,
        material_deferred_ids(disposition.values(), settings), intervals=intervals, scope=scope, visible=visible, unplanned=unplanned)
    return {"candidate_ref": candidate["candidate_ref"], "scope": scope.scope(),
            "state": "available", "items": items, "items_complete": True, "batch_count": len(items), "issues": [],
            "summary": delivery_summary(items),
            "basis": {"kind": "planned_delivery", "metadata_basis": "captured_at_run_admission",
                      "operation_scope": "captured_batch_operations", "completion_scope": "full_candidate",
                      "time_basis": "factory_local", "due_boundary": "next_day_exclusive",
                      "actual_completion": "not_evaluated", "actual_delivery": "not_evaluated",
                      "root_causes": "not_evaluated"}}
