"""Permanent-identity batch and operation impacts from one decision source."""

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.candidate_tasks import operation_labels, unplanned_projection
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.decision_metrics import operation_change_metrics
from core.services.workbench.facts.delivery_projection import delivery_batch_delta, delivery_summary
from core.services.workbench.facts.operation_effort_evidence import archived_standard_effort

BATCH_CHANGES = ("all", "changed", "earlier", "later", "new_overdue", "relieved_overdue", "completion_improved", "completion_worsened", "operation_changed", "unchanged", "unknown")
OPERATION_CHANGES = ("all", "changed", "added", "removed", "moved", "machine_changed", "operator_changed", "supplier_changed", "source_changed", "status_changed", "unchanged", "unknown")
BATCH_SORTS = ("current_priority", "worsened", "improved", "after_delay_hours", "delay_delta_hours", "finish_delta_hours", "batch_id")
OPERATION_SORTS = ("sequence", "start_delta_hours", "end_delta_hours", "batch_id", "change_kind")
DELIVERY_FILTERS = ("all", "attention", "overdue", "deferred", "unplanned", "on_time")


def batch_impact_summary(source, *, before=None, after=None):
    if before is None:
        before = source.completion.delivery("reference")
    if after is None:
        after = source.completion.delivery(source.selected_ref)
    changes = operation_change_metrics(source.operation_comparisons.values(), source.scope["operation_refs"],
        source.baseline["state"] == "available", selected_available=source.result_available(source.selected_ref))
    return {"before": delivery_summary(before), "after": delivery_summary(after), **common_completed_delivery(before, after),
            "operation_changes": changes}


def batch_impacts(source):
    before = source.completion.delivery("reference")
    tasks = source.analysis_tasks(source.selected_ref)
    after = source.completion.delivery(source.selected_ref)
    old, new = ({row["batch_ref"]: row for row in rows} for rows in (before, after))
    reference_tasks = [row for row in source.analysis_tasks("reference") if row["operation_ref"] in source.operation_refs]
    selected_by_batch, reference_by_batch = (_by_batch(rows) for rows in (tasks, reference_tasks))
    operation_rows = defaultdict(list)
    expected_by_batch = defaultdict(set)
    for op_ref, row in source.operation_comparisons.items():
        batch_ref = source.operation_batch_ref(op_ref)
        operation_rows[batch_ref].append(row)
        expected_by_batch[batch_ref].add(op_ref)
    result = []
    available = source.result_available(source.selected_ref)
    window_bounds = (local_time(source.scope["range_start"]), local_time(source.scope["range_end"]))
    selected_intervals = source.task_intervals(source.selected_ref) if available else {}
    reference_intervals = source.task_intervals("reference")
    selected_batch_bounds = {
        ref: _task_bounds(rows, selected_intervals)
        for ref, rows in selected_by_batch.items()
    }
    reference_batch_bounds = {
        ref: _task_bounds(rows, reference_intervals)
        for ref, rows in reference_by_batch.items()
    }
    for ref in source.scope["batch_refs"]:
        previous, current = old[ref], new[ref]
        labels = {key: current[key] for key in ("batch_ref", "batch_id", "part_no", "part_label", "priority", "quantity", "due_date", "due_state", "due_issue")}
        delta = delivery_batch_delta(previous, current) if source.baseline["state"] == "available" and available else {
            "finish_delta_hours": None, "delay_delta_hours": None, "change_kinds": ["unknown"]}
        changes = operation_rows[ref]
        changed = sum(bool(row["changed_fields"]) for row in changes)
        unknown = sum(not row["changed_fields"] and "unknown" in row["change_kinds"] for row in changes)
        if changed:
            delta["change_kinds"] = [kind for kind in delta["change_kinds"] if kind != "unchanged"] + ["operation_changed"]
        attention = _attention_kinds(current)
        scheduled = {task["operation_ref"] for task in selected_by_batch[ref]}
        expected = expected_by_batch[ref]
        result.append({**labels, "before": previous, "after": current, **delta,
                       "attention_kinds": attention, "operation_change_count": changed,
                       "operation_unknown_count": unknown,
                       "operation_changes_state": "unavailable" if not changes or unknown == len(changes) else "partial" if unknown else "complete",
                       "unplanned_operation_refs": sorted(expected - scheduled - source.deferred_refs) if available else None,
                       "deferred_operation_refs": sorted(expected & source.deferred_refs) if available else None,
                       "drill": {"selected": drill_target(source, tasks=selected_by_batch[ref], batch_ref=ref,
                                                          window_bounds=window_bounds, task_bounds=selected_batch_bounds.get(ref)) if available else None,
                                 "reference": drill_target(source, tasks=reference_by_batch[ref], batch_ref=ref, before=True,
                                                           window_bounds=window_bounds, task_bounds=reference_batch_bounds.get(ref))}})
    return result, batch_impact_summary(source, before=before, after=after)


def _attention_kinds(delivery):
    return (["overdue"] if delivery["is_overdue"] is True else []) + (
        ["deferred"] if (delivery["deferred_operation_count"] or 0) > 0 else []) + (
        ["unplanned"] if (delivery["ordinary_unscheduled_operation_count"] or 0) > 0 else [])


def _by_batch(tasks):
    result = defaultdict(list)
    for task in tasks:
        result[task["batch_ref"]].append(task)
    return result


def by_operation(tasks):
    result = defaultdict(list)
    for task in tasks:
        result[task["operation_ref"]].append(task)
    return result


def arrangement_view(rows, *, display=True):
    if not rows:
        return None
    if not display and len(rows) == 1:
        return rows[0]
    if display:
        fields = ("row_ref", "start", "end", "machine", "operator", "supplier", "source", "locked", "data_gaps", "interval_comparable")
        segments = [{**{key: row[key] for key in fields}, **{key: row[key] for key in ("event_kind", "occupies_resources") if key in row}} for row in rows]
        if len(segments) == 1:
            return segments[0]
    result: Dict[str, Any] = {"row_ref": None, "start": None, "end": None, "machine": None, "operator": None, "supplier": None, "source": None, "locked": None}
    if display:
        result["segments"] = segments
    result["data_gaps"] = [{"field": "arrangement", "code": "multiple_segments",
        "message": "这道工序在正式基准中有多段安排，逐段事实已保留。"}]
    return result


def _resource_delta(before, after, kind):
    for side in (before, after):
        resource = side.get(kind)
        if resource is not None and resource["ref"] is None or any(gap.get("field") in (kind, kind + ".ref", "arrangement") for gap in side["data_gaps"]):
            return None
    return (before.get(kind) or {}).get("ref") != (after.get(kind) or {}).get("ref")


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
            fields.extend(key for key in ("start", "end", "source") if side.get(key) is not None)
            fields.extend(key for key in ("machine", "operator", "supplier") if (side.get(key) or {}).get("ref") is not None)
        return {**delta, "change_kinds": kinds, "changed_fields": fields}
    old_interval = reference_task_intervals[before["row_ref"]] if before["row_ref"] is not None else None
    new_interval = task_intervals[after["row_ref"]] if after["row_ref"] is not None else None
    for index, field in enumerate(("start", "end")):
        if before[field] is not None and after[field] is not None and before["interval_comparable"] and after["interval_comparable"]:
            old_time = old_interval[index] if old_interval is not None else None
            new_time = new_interval[index] if new_interval is not None else None
            if old_time is not None and new_time is not None:
                delta[field + "_delta_hours"] = (new_time - old_time).total_seconds() / 3600.0
    for kind in ("machine", "operator", "supplier"):
        delta[kind + "_changed"] = _resource_delta(before, after, kind)
    if before["source"] is not None and after["source"] is not None:
        delta["source_changed"] = before["source"] != after["source"]
    kinds = []
    if any(delta[key] is not None and delta[key] != 0 for key in ("start_delta_hours", "end_delta_hours")):
        kinds.append("moved")
    fields.extend(key for key in ("start", "end") if delta[key + "_delta_hours"] is not None and delta[key + "_delta_hours"] != 0)
    kinds.extend(key for key in ("machine_changed", "operator_changed", "supplier_changed", "source_changed", "status_changed") if delta[key] is True)
    fields.extend(key for key in ("machine", "operator", "supplier", "source") if delta[key + "_changed"] is True)
    if any(value is None for key, value in delta.items() if key != "status_changed"):
        kinds.append("unknown")
    return {**delta, "change_kinds": kinds or ["unchanged"], "changed_fields": fields}


def _operation_state(arrangement, *, available, deferred):
    if not available:
        return {"status": "unavailable", "reason": {"code": "arrangement_source_unavailable", "message": "该来源没有产出可查看的任务安排。"}}
    if arrangement is not None:
        return {"status": "arranged", "reason": None}
    return {"status": "deferred" if deferred else "missing",
            "reason": {"code": "material_deferred" if deferred else "operation_unscheduled",
                       "message": "排产时因缺料保留为待料未排。" if deferred else "这份归档没有给该工序安排时间。"}}


def operation_changes(operation_refs, reference_available, *, selected_available,
                      deferred_refs, reference_deferred_refs, reference_groups, selected_groups,
                      task_intervals, reference_task_intervals):
    comparisons = (row for _ref, row in iter_operation_comparisons(operation_refs, reference_available,
        selected_available=selected_available, deferred_refs=deferred_refs, reference_deferred_refs=reference_deferred_refs,
        reference_groups=reference_groups, selected_groups=selected_groups, task_intervals=task_intervals,
        reference_task_intervals=reference_task_intervals))
    return operation_change_metrics(comparisons, operation_refs, reference_available, selected_available=selected_available)


def operation_comparisons(operation_refs, reference_available, *, selected_available,
                          deferred_refs, reference_deferred_refs, reference_groups, selected_groups,
                          task_intervals, reference_task_intervals):
    return dict(iter_operation_comparisons(operation_refs, reference_available,
        selected_available=selected_available, deferred_refs=deferred_refs, reference_deferred_refs=reference_deferred_refs,
        reference_groups=reference_groups, selected_groups=selected_groups, task_intervals=task_intervals,
        reference_task_intervals=reference_task_intervals, display=True))


def iter_operation_comparisons(operation_refs, reference_available, *, selected_available,
                              deferred_refs, reference_deferred_refs, reference_groups, selected_groups,
                              task_intervals, reference_task_intervals, display=False):
    for ref in operation_refs:
        before = arrangement_view(reference_groups.get(ref, ()), display=display)
        after = arrangement_view(selected_groups.get(ref, ()), display=display)
        previous = _operation_state(before, available=reference_available, deferred=ref in reference_deferred_refs)
        current = _operation_state(after, available=selected_available, deferred=ref in deferred_refs)
        delta = operation_delta(before, after, before_status=previous["status"], after_status=current["status"],
                                 task_intervals=task_intervals, reference_task_intervals=reference_task_intervals)
        if not reference_available or not selected_available:
            delta = {**{key: None for key in ("start_delta_hours", "end_delta_hours", "machine_changed", "operator_changed",
                                             "supplier_changed", "source_changed", "status_changed")},
                     "change_kinds": ["unknown"], "changed_fields": []}
        yield ref, {"before": before, "after": after, "before_state": previous, "after_state": current, **delta}


def operation_impacts(source, operation_refs=None):
    refs = source.scope["operation_refs"] if operation_refs is None else list(operation_refs)
    if not refs:
        return []
    old, new = source.analysis_groups("reference"), source.analysis_groups(source.selected_ref)
    comparisons = source.operation_comparisons
    need_after_reasons = any(comparisons[ref]["after_state"]["status"] in ("deferred", "missing") for ref in refs)
    need_before_reasons = source.comparison_mode == "candidates" and any(
        comparisons[ref]["before_state"]["status"] in ("deferred", "missing") for ref in refs
    )
    reasons = (
        {row["operation_ref"]: row["reason"] for row in unplanned_projection(source.disposition, source.analysis_tasks(source.selected_ref), source.facts)}
        if need_after_reasons else {}
    )
    reference_reasons = (
        {row["operation_ref"]: row["reason"] for row in unplanned_projection(source.disposition, source.analysis_tasks("reference"), source.facts)}
        if need_before_reasons else {}
    )
    result = []
    available = source.result_available(source.selected_ref)
    window_bounds = (local_time(source.scope["range_start"]), local_time(source.scope["range_end"]))
    selected_intervals = source.task_intervals(source.selected_ref) if available else {}
    reference_intervals = source.task_intervals("reference")
    for ref in refs:
        labels, operation = operation_labels(source.facts, ref)
        delta = dict(
            comparisons[ref],
            before_state=dict(comparisons[ref]["before_state"]),
            after_state=dict(comparisons[ref]["after_state"]),
        )
        for side, saved in (("after", reasons), ("before", reference_reasons)):
            if delta[side + "_state"]["status"] in ("deferred", "missing") and ref in saved:
                delta[side + "_state"]["reason"] = saved[ref]
        before, after = delta["before"], delta["after"]
        execution = source.facts.execution[ref]
        disposition = source.disposition[ref]
        constraints = {"protected_at_admission": disposition["status"] == "protected",
                       "selected_locked": after["locked"] if after else None, "reference_locked": before["locked"] if before else None,
                       "lock_basis": "saved_arrangement_marker", "protection_basis": "admission_execution_and_dispositions",
                       **{key: execution.get(key) for key in ("execution_state", "known_completed_quantity", "remaining_quantity",
                           "data_quality", "first_actual_start", "confirmed_finish")}, "reasons": [dict(item) for item in disposition["issues"]]}
        result.append({**{key: labels[key] for key in ("operation_ref", "batch_ref", "batch_label", "part_label", "sequence", "process_label", "piece_id", "quantity")},
                       "batch_id": labels["batch_label"], **delta,
                       "effort": archived_standard_effort(operation, execution),
                       "runtime_effort": {"before": source.preparation.compact("reference", ref), "after": source.preparation.compact(source.selected_ref, ref)},
                       "constraints": constraints, "data_gaps": labels["data_gaps"],
                       "drill": {"selected": drill_target(source, tasks=new[ref], batch_ref=labels["batch_ref"], operation_ref=ref,
                                                          window_bounds=window_bounds, task_intervals=selected_intervals) if available else None,
                                 "reference": drill_target(source, tasks=old[ref], batch_ref=labels["batch_ref"], operation_ref=ref, before=True,
                                                           window_bounds=window_bounds, task_intervals=reference_intervals)}})
    return result


def _task_bounds(tasks, task_intervals):
    intervals = []
    for row in tasks:
        if row["start"] is None or row["end"] is None:
            continue
        span = task_intervals.get(row["row_ref"]) if task_intervals is not None else None
        intervals.append(span if span is not None else (local_time(row["start"]), local_time(row["end"])))
    if not intervals:
        return None
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


def option_resources(source, *, view="selected_batches", kinds=("machine", "operator")):
    resources = {}
    operation_refs = set(source.scope["operation_refs"])
    batch_refs = set(source.scope["batch_refs"])
    active_refs = {
        ref for ref in (source.selected_ref, source.reference_ref if source.comparison_mode == "candidates" else None)
        if ref is not None
    }
    task_sources = ["reference"] if source.comparison_mode == "admission_official" else []
    for candidate in source.rows:
        candidate_ref = candidate["candidate_ref"]
        if candidate_ref in active_refs or candidate_ref in source._analysis:
            task_sources.append(candidate_ref)
        else:
            view_data = source._candidate_models[candidate_ref]["summary"]["resource_views"][view]
            for row in view_data["arranged_resources"]:
                if row["kind"] in kinds and row["ref"] is not None:
                    resources[row["ref"]] = {"ref": row["ref"], "label": row["label"], "kind": row["kind"]}
    for key in task_sources:
        for task in source.analysis_tasks(key):
            if view == "selected_batches" and (task["batch_ref"] not in batch_refs or task["operation_ref"] not in operation_refs):
                continue
            for kind in kinds:
                value = task[kind]
                if value is not None and value["ref"] is not None:
                    resources[value["ref"]] = {"ref": value["ref"], "label": value["label"], "kind": kind}
    return resources


def filter_options(source, section):
    delivery_rows = {row["batch_ref"]: row["batch_id"] for row in source.completion.delivery(source.selected_ref)}
    batches = [{"ref": ref, "label": delivery_rows[ref]} for ref in source.scope["batch_refs"]]
    resources = option_resources(source, view="selected_batches", kinds=("machine", "operator")) if section == "operations" else {}
    return {"batches": batches, "resources": sorted(resources.values(), key=lambda item: (item["kind"], item["label"] or "", item["ref"]))}
