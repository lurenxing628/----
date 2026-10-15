"""Decision views supply frozen rows to the shared whole-batch delivery rule."""

from collections import defaultdict

from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.delivery_projection import delivery_summary, project_delivery_batch, task_intervals


def project_decision_delivery(facts, tasks, batch_refs, *, deferred_ids=(), candidate=None, available=True, issues=(), intervals=None):
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
                             available=available, issues=issues, intervals=intervals)


def project_saved_decision_delivery(facts, tasks, batch_refs, *, intervals, deferred_ids=(), candidate=None, available=True, issues=()):
    schedules = defaultdict(list)
    for task in tasks:
        key = facts.operations.get(task["operation_ref"])
        operation = facts.tables["BatchOperations"].get(key)
        if operation is None:
            continue
        payload, interval = task["payload"], intervals[task["row_ref"]]
        schedules[operation["batch_id"]].append({"schedule_id": task["row_ref"], "op_id": key,
            "batch_id": operation["batch_id"], "start_time": payload["start_time"], "end_time": payload["end_time"],
            "_point_work": interval[0] == interval[1]})
    return _delivery_batches(facts, schedules, batch_refs, deferred_ids=deferred_ids, candidate=candidate,
                             available=available, issues=issues, intervals=intervals)


def _delivery_batches(facts, schedules, batch_refs, *, deferred_ids, candidate, available, issues, intervals):
    operations = defaultdict(list)
    for operation in facts.tables["BatchOperations"].values():
        operations[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
    completion = ((candidate or {}).get("artifact", {}).get("metrics") or {}).get("completion")
    incomplete = set(completion.get("incomplete_batch_ids", [])) if type(completion) is dict else set()
    keys = {ref: key for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    result = []
    for ref in batch_refs:
        key = keys.get(ref)
        batch = facts.tables["Batches"].get(key)
        if batch is None:
            corrupt()
        rows = schedules[key]
        uncertain = list(issues) + ([] if available else ["candidate_result_unavailable" if candidate is not None else "no_admission_baseline"])
        item = project_delivery_batch(batch, ref, rows, operations[key], task_intervals(rows) if intervals is None else intervals, key in incomplete,
                                      uncertain, deferred_operation_ids=deferred_ids)
        if not available:
            item.update(completion_state="unknown", completeness="unknown", scheduled_operation_count=None,
                        unscheduled_operation_count=None, deferred_operation_count=None, ordinary_unscheduled_operation_count=None,
                        task_count=None, invalid_task_count=None)
        result.append(item)
    return result


def decision_delivery_summary(items):
    summary = delivery_summary(items)
    return {**summary, "state": "complete" if summary["complete_batch_count"] == summary["batch_count"] else "partial",
            "delivery_state": summary["state"]}


def common_delivery(before, after):
    return common_completed_delivery(before, after)
