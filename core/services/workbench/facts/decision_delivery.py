"""Decision views supply frozen rows to the shared whole-batch delivery rule."""

from collections import defaultdict

from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.delivery_projection import project_delivery_batch, task_intervals


def project_decision_delivery(facts, tasks, batch_refs, *, deferred_ids=(), candidate=None, available=True, intervals=None):
    schedules = defaultdict(list)
    for task in tasks:
        key = facts.operations.get(task["operation_ref"])
        operation = facts.tables["BatchOperations"].get(key)
        if operation is None:
            continue
        schedules[operation["batch_id"]].append({"schedule_id": task["row_ref"], "op_id": key,
            "batch_id": operation["batch_id"], "start_time": task["start"], "end_time": task["end"],
            "_point_work": task.get("event_kind") == "point" and task.get("occupies_resources") is False})
    return _delivery_batches(facts, schedules, batch_refs, deferred_ids=deferred_ids, candidate=candidate,
                             available=available, intervals=intervals)


def _delivery_batches(facts, schedules, batch_refs, *, deferred_ids, candidate, available, intervals):
    operations = facts.operations_by_batch
    completion = ((candidate or {}).get("artifact", {}).get("metrics") or {}).get("completion")
    incomplete = set(completion.get("incomplete_batch_ids", [])) if type(completion) is dict else set()
    keys = facts.batch_ids_by_ref
    result = []
    uncertain = [] if available else ["candidate_result_unavailable" if candidate is not None else "no_admission_baseline"]
    for ref in batch_refs:
        key = keys.get(ref)
        batch = facts.tables["Batches"].get(key)
        if batch is None:
            corrupt()
        rows = schedules[key]
        item = project_delivery_batch(batch, ref, rows, operations.get(key, ()), task_intervals(rows) if intervals is None else intervals, key in incomplete,
                                      uncertain, deferred_operation_ids=deferred_ids)
        if not available:
            item.update(completion_state="unknown", completeness="unknown", scheduled_operation_count=None,
                        unscheduled_operation_count=None, deferred_operation_count=None, ordinary_unscheduled_operation_count=None,
                        task_count=None, invalid_task_count=None)
        result.append(item)
    return result
