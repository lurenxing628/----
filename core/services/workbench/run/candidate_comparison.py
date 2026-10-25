"""Read-only dashboard comparisons from one immutable decision source."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_analysis import operation_change
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason, elapsed_hours
from core.models.workbench_run_candidate import local_time, reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.delivery_projection import delivery_batch_delta, delivery_summary

from .candidate_baseline import _in_time
from .candidate_metrics import changeovers, resource_comparison
from .candidate_tradeoffs import candidate_tradeoffs
from .decision_source import DecisionSource


def _common_batches(settings, batch_ref):
    refs = set(settings["batch_refs"])
    if batch_ref is not None:
        if batch_ref not in refs:
            reject("entity_not_found", "所选批次不在本次排产范围。", 404)
        refs = {batch_ref}
    return sorted(refs)


def analysis_source(store, candidate_ref, *, range_start=None, range_end=None):
    return DecisionSource(store, store.candidate_run(candidate_ref), comparison_mode="admission_official",
                          selected_candidate_ref=candidate_ref, range_start=range_start, range_end=range_end,
                          resource_view="full_candidate")


def _comparison_interval(task):
    fields = ("row_ref", "start", "end", "source", "machine", "operator", "supplier", "locked", "data_gaps")
    start, end = task["start"], task["end"]
    result = {**{key: task[key] for key in fields},
              "elapsed_hours": elapsed_hours(start, end) if start is not None and end is not None else None,
              "effective_processing_hours": None,
              "interval_comparable": task.get("interval_comparable", True)}
    if task.get("event_kind") == "point":
        result.update(event_kind="point", duration_seconds=0, occupies_resources=False)
    return result


def comparison_rows(source):
    """Use the legacy comparison rule on compact permanent-identity rows."""
    old = source.analysis_groups("reference")
    new = {row["operation_ref"]: row for row in source.analysis_tasks(source.selected_ref)}
    selected = source.operation_refs
    result = []
    for ref in sorted(selected | set(old) | set(new)):
        task = new.get(ref)
        # Execution annotations are not consumed by the arrangement metrics.
        labels = {"batch_ref": source.operation_batch_ref(ref), "execution_at_generation": None}
        result.append(RunBaselineComparison(
            ref, task["row_ref"] if task else None, labels, _comparison_interval(task) if task else None,
            [_comparison_interval(row) for row in old.get(ref, ())], ref in selected,
            "scheduled" if task else "skipped" if ref in source.deferred_refs else "unscheduled" if ref in selected else None,
        ).to_dict())
    return result


def comparison_metadata(source, rows, scope=None):
    captured = source.baseline["version"] is not None
    visible = rows
    if scope is not None:
        if scope.batch_ref is not None:
            visible = [row for row in visible if row["batch_ref"] == scope.batch_ref]
        start, end = (local_time(source.scope[key]) for key in ("range_start", "range_end"))
        visible = [row for row in visible if _in_time(row, start, end)]
    available = any(row["comparison_available"] for row in visible)
    reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
    run = source.run
    generation = {"run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
                  "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
                  "current_entities_consulted": False, "formal_version_allocated": False, "input": source.input,
                  "source_verification": {"facts_content_verified": True, "baseline_matches_archived_schedule": True,
                                          "execution_verified_at": "run_admission", "input_source_verified": True,
                                          "candidate_content_verified": True}}
    baseline = {"baseline_ref": source.baseline["plan_ref"], "version": source.baseline["version"],
                "kind": "admission_official", "captured_at": run["accepted_at"],
                "captured_task_count": len(source.analysis_tasks("reference")), "available": captured,
                "comparison_available": available, "reason": reason}
    return generation, baseline


def analysis_state(source):
    return {"read_contract_version": 1, "run_ref": source.run["run_ref"],
            "candidate_ref": source.selected_ref, "official_sources": source.official["source_states"]}


def delivery_rows(before, after, refs):
    old, new = ({row["batch_ref"]: row for row in rows} for rows in (before, after))
    if not set(refs) <= set(old) or not set(refs) <= set(new):
        reject("candidate_comparison_incomplete", "缺少排产时的批次数据，暂时无法比较。", 500)
    result = []
    for ref in refs:
        previous, current = old[ref], new[ref]
        if previous["batch_id"] != current["batch_id"] or previous["due_date"] != current["due_date"]:
            reject("candidate_comparison_inconsistent", "候选方案与对比基准的批次资料不一致，请重新排产。", 500)
        result.append({"batch_ref": ref, "batch_id": current["batch_id"], "part_label": current["part_label"],
                       "before": previous, "after": current,
                       **delivery_batch_delta(previous, current)})
    return result


def _machine_changes(rows, refs):
    machines = [(row["operation_ref"], operation_change(row)[1]) for row in rows if row["batch_ref"] in refs]
    changed = [ref for ref, changed in machines if changed is True]
    unknown = sum(changed is None for _, changed in machines)
    return {"count": None if unknown else len(changed), "known_count": len(changed),
            "unknown_count": unknown, "operation_refs": changed, "basis": "matched_operation_permanent_identity"}


def _projection(source, scope):
    refs = _common_batches(source.input, scope.batch_ref)
    before_delivery = [row for row in source.delivery("reference") if row["batch_ref"] in refs]
    after_delivery = [row for row in source.legacy_delivery(source.selected_ref) if row["batch_ref"] in refs]
    batches = delivery_rows(before_delivery, after_delivery, refs)
    before_tasks, after_tasks = source.analysis_tasks("reference"), source.analysis_tasks(source.selected_ref)
    before, after = ([row for row in tasks if row["batch_ref"] in refs] for tasks in (before_tasks, after_tasks))
    rows = comparison_rows(source)
    generation, baseline = comparison_metadata(source, rows, scope)
    start, end = scope.range_start, scope.range_end
    old_intervals, new_intervals = source.task_intervals("reference"), source.task_intervals(source.selected_ref)
    old_cost = changeovers(before_tasks, baseline["available"], start=start, end=end,
                          next_operation_refs=[row["operation_ref"] for row in before], task_intervals=old_intervals)
    new_cost = changeovers(after_tasks, start=start, end=end,
                          next_operation_refs=[row["operation_ref"] for row in after], task_intervals=new_intervals)
    resources, resource_common = resource_comparison(before, after, start, end, baseline["available"],
        source.resource_cohort["resources"], calendar_archive=source.calendar_archive,
        task_intervals=new_intervals, reference_task_intervals=old_intervals)
    resource_common.update(batch_refs=refs, resource_view="selected_batches", run_ref=source.run["run_ref"])
    missing_resources = sum(row["source"] not in ("internal", "external") or
                            row["source"] == "internal" and (not row["machine"] or row["machine"]["ref"] is None)
                            for row in before + after)
    time_scope = {"range_start": start, "range_end": end, "interval": "half_open_overlap",
                  "membership": "either_side_overlap", "counterpart_policy": "retain_complete_counterpart",
                  "time_basis": "factory_local", "unplanned_policy": "included_without_time_interval",
                  "unknown_or_zero_interval_policy": "included_without_time_interval"}
    result = {"candidate": source.saved_candidate_catalog(source.selected_ref), "generation": generation,
            "baseline": baseline, "time_scope": time_scope, "batch_ref": scope.batch_ref, "batch_refs": refs,
            "batches": batches, "resources": resources, "resource_common": resource_common,
            "summary": {"before": {**delivery_summary(before_delivery), "changeovers": old_cost},
                        "after": {**delivery_summary(after_delivery), "changeovers": new_cost},
                        "changeover_delta": None if old_cost["value"] is None or new_cost["value"] is None else new_cost["value"] - old_cost["value"]},
            "machine_changes": _machine_changes(rows, refs),
            "resource_scope_complete": not bool(missing_resources), "resource_scope_unknown_rows": missing_resources,
            "basis": {"comparison": "candidate_minus_admission_official", "batch_scope": "admission_selected_batches",
                      "delivery": "complete_captured_batch_operations", "resources": "same_range_daily_peak_available_occupancy",
                      "changeovers": "same_range_scheduled_operation_type_changes", "current_entities_consulted": False},
            "capabilities": {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}}
    result["tradeoffs"] = candidate_tradeoffs(result, before_delivery, after_delivery, before_tasks, after_tasks,
        subject_operation_refs={row["operation_ref"] for row in before + after},
        before_intervals=old_intervals, after_intervals=new_intervals)
    return result


def read_candidate_comparison(conn, scope):
    if scope.range_start is None or scope.range_end is None:
        reject("invalid_input", "请选择共同的比较时间范围。", 400)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = analysis_source(store, scope.candidate_ref, range_start=scope.range_start, range_end=scope.range_end)
        data = _projection(source, scope)
        return data, analysis_state(source)
