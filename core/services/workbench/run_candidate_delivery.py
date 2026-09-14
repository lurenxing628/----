"""Batch delivery from validated candidate rows and immutable admission facts."""

from collections import defaultdict

from .plan_delivery_projection import project_delivery_batch, task_intervals
from .run_candidate_values import corrupt


def _group_tasks(tasks, facts):
    rows, by_batch, uncertain = [], defaultdict(list), set()
    for task in tasks:
        op_id = facts.operations.get(task["operation_ref"])
        operation = facts.tables["BatchOperations"].get(op_id)
        if operation is None:
            uncertain.add("captured_operation_missing")
            continue
        batch = operation["batch_id"]
        by_batch[batch].append(task)
        row = {"schedule_id": task["row_ref"], "op_id": op_id, "batch_id": batch,
               "start_time": task["start"], "end_time": task["end"]}
        if task.get("event_kind") == "point" and task.get("occupies_resources") is False:
            row["_point_work"] = True
        rows.append(row)
    return rows, by_batch, uncertain


def _selected_keys(settings, facts, by_batch, visible, unplanned, scope, uncertain):
    refs = {ref: key for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    if scope.batch_ref:
        requested = [scope.batch_ref]
    elif scope.range_start:
        requested = [row["batch_ref"] for row in visible + (unplanned or [])]
    else:
        requested = settings.get("batch_refs")
        if type(requested) is not list:
            uncertain.add("captured_input_scope_missing")
            requested = []
    keys = set(by_batch) if scope.batch_ref is None and scope.range_start is None else set()
    for ref in requested:
        if ref is not None and type(ref) is not str:
            corrupt()
        if ref not in refs:
            uncertain.add("captured_batch_identity_missing")
        else:
            keys.add(refs[ref])
    return sorted(keys)


def _negative_completion(candidate, disposition):
    uncertain = [] if disposition is not None else ["captured_dispositions_missing"]
    completion = (candidate["artifact"].get("metrics") or {}).get("completion")
    if completion is None:
        return set(), uncertain
    if type(completion) is not dict:
        corrupt()
    ids = completion.get("incomplete_batch_ids", [])
    if type(ids) is not list or any(type(value) is not str or not value for value in ids):
        corrupt()
    return set(ids), uncertain


def _last_operations(item, tasks):
    if not item["schedule_complete"] or item["planned_finish"] is None:
        return []
    fields = ("row_ref", "operation_ref", "sequence", "piece_id", "process_label",
              "start", "end", "machine", "operator")
    finish = max(task["end"] for task in tasks)
    return [{key: task[key] for key in fields} for task in tasks
            if task["end"] == finish]


def _items(keys, facts, rows, tasks, intervals, incomplete, uncertain):
    operations, schedules = defaultdict(list), defaultdict(list)
    for operation in facts.tables["BatchOperations"].values():
        operations[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
    for row in rows:
        schedules[row["batch_id"]].append(row)
    result, missing = [], []
    for key in keys:
        batch, ref = facts.tables["Batches"].get(key), facts.entity_refs.get(("batch", key))
        if batch is None or ref is None:
            missing.append(key)
            continue
        item = project_delivery_batch(batch, ref, schedules[key], operations[key], intervals,
                                      key in incomplete, sorted(uncertain))
        quantity = batch.get("quantity")
        item["quantity"] = quantity if type(quantity) is int and quantity >= 0 else None
        item["last_operations"] = _last_operations(item, tasks[key])
        result.append(item)
    return result, missing


def candidate_delivery_risks(candidate, facts, tasks, disposition, scope, settings, visible, unplanned):
    """Select by display scope, but calculate every selected batch in full."""
    rows, by_batch, uncertain = _group_tasks(tasks, facts)
    keys = _selected_keys(settings, facts, by_batch, visible, unplanned, scope, uncertain)
    incomplete, negative = _negative_completion(candidate, disposition)
    uncertain.update(negative)
    items, missing = _items(keys, facts, rows, by_batch, task_intervals(rows), incomplete, uncertain)
    issues = [{"code": code, "message": "排产时记下的依据不完整，交付结论算不出来；系统没有拿当前资料凑。"}
              for code in sorted(uncertain)]
    if missing:
        issues.append({"code": "captured_batch_missing", "message": "排产时缺少部分批次资料，这些批次的交付情况算不出来。"})
    unknown = sum(item["risk"] == "unknown" for item in items) + len(missing)
    return {"candidate_ref": candidate["candidate_ref"], "scope": scope.scope(),
            "state": "available" if not issues else "partial" if items else "unavailable",
            "items": items, "items_complete": not issues, "batch_count": len(keys), "issues": issues,
            "summary": {"overdue_count": sum(item["risk"] == "overdue" for item in items),
                        "unknown_count": unknown, "batch_count": len(keys),
                        "total_tardiness_hours": None if unknown or issues else sum(item["delay_hours"] for item in items)},
            "basis": {"kind": "planned_delivery", "metadata_basis": "captured_at_run_admission",
                      "operation_scope": "captured_batch_operations", "completion_scope": "full_candidate",
                      "time_basis": "factory_local", "due_boundary": "next_day_exclusive",
                      "current_entities_consulted": False, "actual_completion": "not_evaluated",
                      "actual_delivery": "not_evaluated", "root_causes": "not_evaluated"}}
