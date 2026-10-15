"""Batch delivery from validated candidate rows and immutable admission facts."""

from collections import defaultdict

from .candidate_values import corrupt
from .delivery_projection import delivery_summary, project_delivery_batch, task_intervals
from .preflight_dependencies import material_deferred_ids


def prepare_candidate_delivery_groups(tasks, facts):
    """Capture schedule rows, complete batch task groups and unresolved source facts."""
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
    refs = facts.batch_ids_by_ref
    batch_ref = scope.batch_ref if scope is not None else None
    range_start = scope.range_start if scope is not None else None
    if batch_ref:
        requested = [batch_ref]
    elif range_start:
        requested = [row["batch_ref"] for row in visible + (unplanned or [])]
    else:
        requested = settings.get("batch_refs")
        if type(requested) is not list:
            uncertain.add("captured_input_scope_missing")
            requested = []
    keys = set(by_batch) if batch_ref is None and range_start is None else set()
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


def _items(keys, facts, rows, tasks, intervals, incomplete, uncertain, deferred):
    operations, schedules = facts.operations_by_batch, defaultdict(list)
    for row in rows:
        schedules[row["batch_id"]].append(row)
    result, missing = [], []
    for key in keys:
        batch, ref = facts.tables["Batches"].get(key), facts.entity_refs.get(("batch", key))
        if batch is None or ref is None:
            missing.append(key)
            continue
        item = project_delivery_batch(batch, ref, schedules[key], operations.get(key, ()), intervals,
                                      key in incomplete, sorted(uncertain), deferred_operation_ids=deferred)
        item["last_operations"] = _last_operations(item, tasks.get(key, []))
        result.append(item)
    return result, missing


def _project_items(candidate, facts, tasks, disposition, settings, *, scope=None, visible=(), unplanned=None,
                   intervals=None, prepared_groups=None, deferred_ids=None):
    rows, by_batch, original_uncertain = (prepare_candidate_delivery_groups(tasks, facts)
                                          if prepared_groups is None else prepared_groups)
    uncertain = set(original_uncertain)
    keys = _selected_keys(settings, facts, by_batch, visible, unplanned, scope, uncertain)
    incomplete, negative = _negative_completion(candidate, disposition)
    uncertain.update(negative)
    deferred = material_deferred_ids((disposition or {}).values(), settings) if deferred_ids is None else deferred_ids
    items, missing = _items(keys, facts, rows, by_batch, task_intervals(rows) if intervals is None else intervals,
                            incomplete, uncertain, deferred)
    return items, missing, uncertain, len(keys)


def project_legacy_delivery_detail(candidate, facts, tasks, disposition, settings, *, intervals=None, prepared_groups=None, deferred_ids=None):
    """Keep all whole-candidate batch rows and every tied last operation for saved detail."""
    return _project_items(candidate, facts, tasks, disposition, settings,
                          intervals=intervals, prepared_groups=prepared_groups, deferred_ids=deferred_ids)[0]


def candidate_delivery_risks(candidate, facts, tasks, disposition, scope, settings, visible, unplanned, *,
                             intervals=None, prepared_groups=None):
    """Select by display scope, but calculate every selected batch in full."""
    items, missing, uncertain, batch_count = _project_items(candidate, facts, tasks, disposition, settings,
        scope=scope, visible=visible, unplanned=unplanned, intervals=intervals, prepared_groups=prepared_groups)
    issues = [{"code": code, "message": "排产时记下的依据不完整，交付结论算不出来；系统没有拿当前资料凑。"}
              for code in sorted(uncertain)]
    if missing:
        issues.append({"code": "captured_batch_missing", "message": "排产存档中缺少批次资料：" + "、".join(missing)
                       + "。请在排产记录中核对这些批次。"})
    return {"candidate_ref": candidate["candidate_ref"], "scope": scope.scope(),
            "state": "available" if not issues else "partial" if items else "unavailable",
            "items": items, "items_complete": not issues, "batch_count": batch_count, "issues": issues,
            "summary": delivery_summary(items, len(missing)),
            "basis": {"kind": "planned_delivery", "metadata_basis": "captured_at_run_admission",
                      "operation_scope": "captured_batch_operations", "completion_scope": "full_candidate",
                      "time_basis": "factory_local", "due_boundary": "next_day_exclusive",
                      "current_entities_consulted": False, "actual_completion": "not_evaluated",
                      "actual_delivery": "not_evaluated", "root_causes": "not_evaluated"}}
