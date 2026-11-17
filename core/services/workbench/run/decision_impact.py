"""Permanent-identity batch and operation impacts from one decision source."""

from datetime import timedelta

from core.models.workbench_run_candidate import local_time

BATCH_CHANGES = ("all", "changed", "earlier", "later", "new_overdue", "relieved_overdue", "completion_improved", "completion_worsened", "operation_changed", "unchanged", "unknown")
OPERATION_CHANGES = ("all", "changed", "added", "removed", "moved", "machine_changed", "operator_changed", "supplier_changed", "source_changed", "status_changed", "unchanged", "unknown")
BATCH_SORTS = ("current_priority", "worsened", "improved", "after_delay_hours", "delay_delta_hours", "finish_delta_hours", "batch_id")
OPERATION_SORTS = ("sequence", "start_delta_hours", "end_delta_hours", "batch_id", "change_kind")
DELIVERY_FILTERS = ("all", "attention", "overdue", "deferred", "unplanned", "on_time")


def _resource_delta(before, after, kind):
    for side in (before, after):
        resource = side[kind]
        if resource is not None and resource["ref"] is None or any(gap["field"] in (kind, kind + ".ref") for gap in side["data_gaps"]):
            return None
    return (before[kind] or {}).get("ref") != (after[kind] or {}).get("ref")


def operation_delta(before, after, *, before_status=None, after_status=None,
                     task_intervals, reference_task_intervals):
    status_changed = before_status != after_status if before_status not in (None, "unavailable") and after_status not in (None, "unavailable") else None
    delta = {"start_delta_hours": None, "end_delta_hours": None, "machine_changed": None, "operator_changed": None,
             "supplier_changed": None, "source_changed": None, "status_changed": status_changed}
    fields = ["status"] if status_changed else []
    if before is None or after is None:
        kinds = ["added" if after else "removed" if before else "unknown"]
        if status_changed:
            kinds.append("status_changed")
        side = after if after is not None else before
        if side is not None:
            fields.extend(("start", "end", "source"))
            fields.extend(key for key in ("machine", "operator", "supplier") if side[key] is not None and side[key]["ref"] is not None)
        return {**delta, "change_kinds": kinds, "changed_fields": fields}
    old_interval, new_interval = reference_task_intervals[before["row_ref"]], task_intervals[after["row_ref"]]
    for index, field in enumerate(("start", "end")):
        delta[field + "_delta_hours"] = (new_interval[index] - old_interval[index]).total_seconds() / 3600.0
    for kind in ("machine", "operator", "supplier"):
        delta[kind + "_changed"] = _resource_delta(before, after, kind)
    delta["source_changed"] = before["source"] != after["source"]
    kinds = []
    if any(delta[key] != 0 for key in ("start_delta_hours", "end_delta_hours")):
        kinds.append("moved")
    fields.extend(key for key in ("start", "end") if delta[key + "_delta_hours"] != 0)
    kinds.extend(key for key in ("machine_changed", "operator_changed", "supplier_changed", "source_changed", "status_changed") if delta[key] is True)
    fields.extend(key for key in ("machine", "operator", "supplier", "source") if delta[key + "_changed"] is True)
    if any(value is None for key, value in delta.items() if key != "status_changed"):
        kinds.append("unknown")
    return {**delta, "change_kinds": kinds or ["unchanged"], "changed_fields": fields}


def _task_bounds(tasks, task_intervals):
    intervals = [task_intervals[row["row_ref"]] for row in tasks]
    low, high = min(pair[0] for pair in intervals), max(pair[1] for pair in intervals)
    if any(pair[0] == pair[1] == high for pair in intervals):
        high += timedelta(microseconds=1)
    return low, high


def drill_target(source, *, tasks, batch_ref, operation_ref=None, before=False, window=None,
                 window_bounds=None, task_intervals=None, task_bounds=None):
    if before and source.baseline["state"] != "available":
        return None
    candidate_ref = source.reference_ref if before and source.comparison_mode == "candidates" else source.selected_ref
    scope = source.scope
    if window_bounds is not None:
        start, end = window_bounds
    else:
        low, high = window if window is not None else (scope["range_start"], scope["range_end"])
        start, end = local_time(low), local_time(high)
    if task_bounds is None and tasks:
        if task_intervals is None:
            task_intervals = source.task_intervals("reference" if before else source.selected_ref)
        task_bounds = _task_bounds(tasks, task_intervals)
    if task_bounds is not None:
        start, end = min(start, task_bounds[0]), max(end, task_bounds[1])
    start_iso, end_iso = start.isoformat(), end.isoformat()
    result = {"run_ref": source.run["run_ref"], "candidate_ref": candidate_ref, "comparison_mode": source.comparison_mode,
              "reference_candidate_ref": source.reference_ref, "range_start": start_iso, "range_end": end_iso,
              "batch_ref": batch_ref, "operation_ref": operation_ref,
              "drill_range_adjusted": start_iso != scope["range_start"] or end_iso != scope["range_end"]}
    if before and source.comparison_mode == "admission_official":
        result.update(reference_view=True, plan_ref=source.baseline["plan_ref"])
    return {key: value for key, value in result.items() if value is not None}
