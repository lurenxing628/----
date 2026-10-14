"""All same-run candidates under one admission archive and one viewing reference."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import canonical_json
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import bounded_size, corrupt

from .decision_metrics import (
    candidate_metrics,
    metric_definitions,
    metric_delta,
    operation_changes,
)
from .decision_recommendation import recommendation
from .decision_reference import official_reference_metrics
from .decision_selection import selection_roles
from .decision_source import DecisionSource

CORE_METRIC_KEYS = (
    "expected_operation_count", "scheduled_operation_count", "unplanned_operation_count", "deferred_operation_count",
    "overdue_count", "total_tardiness_hours", "makespan_hours", "weighted_tardiness_hours", "elapsed_seconds",
    "changeover_count", "machine_used_count", "operator_used_count", "machine_busy_hours_total",
    "operator_busy_hours_total", "machine_util_avg", "operator_util_avg",
)
CORE_CANDIDATE_COVERAGE = ("schedulable", "delivery", "search")
CORE_BASELINE_COVERAGE = ("schedulable", "delivery")


def read_run_decision(conn, run_ref, *, comparison_mode="candidates", reference_candidate_ref=None,
                      selected_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches"):
    return _read_projection(conn, run_ref, decision_overview, comparison_mode=comparison_mode,
        reference_candidate_ref=reference_candidate_ref, selected_candidate_ref=selected_candidate_ref,
        range_start=range_start, range_end=range_end, resource_view=resource_view)


def read_run_decision_summary(conn, run_ref, *, comparison_mode="candidates", reference_candidate_ref=None,
                              selected_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches"):
    return _read_projection(conn, run_ref, decision_summary, comparison_mode=comparison_mode,
        reference_candidate_ref=reference_candidate_ref, selected_candidate_ref=selected_candidate_ref,
        range_start=range_start, range_end=range_end, resource_view=resource_view)


def _read_projection(conn, run_ref, projection, **query):
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, **query)
        return projection(source), source.state()


def _core_candidates(source):
    return [_candidate(row, source.core_tasks(row["candidate_ref"]), source.facts, source.capture, source.disposition,
                       source.scope, source.basis, source.rows, source.completion.delivery(row["candidate_ref"]))
            for row in source.rows]


def _enriched_candidates(source, candidates, keys):
    names = {source.computation_key(key) for key in keys}
    source.resources.prepare_keys(keys)
    before_tasks = source.before_tasks
    reference_deferred = {ref for ref in source.scope["operation_refs"]
                          if source.facts.operations[ref] in source.reference_deferred_ids}
    result = {}
    for candidate in candidates:
        key = candidate["candidate_ref"]
        if key not in names:
            continue
        candidate = {**candidate, "metrics": dict(candidate["metrics"]), "coverage": dict(candidate["coverage"])}
        candidate["metrics"].update(source.resources.metrics(key))
        candidate["coverage"]["resources"] = source.resources.overview_coverage(key)
        candidate["metrics"].update(source.preparation.metrics(key))
        candidate["coverage"]["preparation"] = source.preparation.public_coverage(key)
        candidate["metrics"].update(source.changeovers.metrics(key))
        candidate["metrics"].update(operation_changes(source.tasks(key), before_tasks,
            source.scope["operation_refs"], source.baseline["state"] == "available",
            selected_available=candidate["persisted_status"] == "completed", deferred_refs=source.deferred_refs,
            reference_deferred_refs=reference_deferred, reference_groups=source.reference_operation_groups,
            task_intervals=source.task_intervals(key), reference_task_intervals=source.task_intervals("reference")))
        result[key] = candidate
    return result


def _reference_metrics(source, candidates, *, metric_keys=None):
    reference_candidate = next((row for row in candidates if row["candidate_ref"] == source.reference_ref), None)
    if source.comparison_mode == "admission_official":
        return official_reference_metrics(source, metric_keys=metric_keys)
    previous = dict(reference_candidate["metrics"]) if reference_candidate else {}
    before_coverage = dict(reference_candidate["coverage"]) if reference_candidate else {"schedulable": {"state": "unavailable"}}
    return previous, before_coverage


def _enriched_reference(source, previous, before_coverage, candidates):
    reference_candidate = candidates.get(source.computation_key("reference"))
    if reference_candidate is not None:
        return dict(reference_candidate["metrics"]), dict(reference_candidate["coverage"])
    previous, before_coverage = dict(previous), dict(before_coverage)
    previous.update(source.resources.metrics("reference"))
    previous.update(source.preparation.metrics("reference"))
    previous.update(source.changeovers.metrics("reference"))
    before_coverage["resources"] = source.resources.overview_coverage("reference")
    before_coverage["preparation"] = source.preparation.public_coverage("reference")
    return previous, before_coverage


def _reference_operation_refs(source):
    tasks = source.before_tasks if source.comparison_mode == "admission_official" else (
        source.core_tasks(source.reference_ref) if source.reference_ref else [])
    return {task["operation_ref"] for task in tasks}


def _set_deltas(source, candidates, previous, definitions):
    before_refs = _reference_operation_refs(source)
    for candidate in candidates:
        same_work = {task["operation_ref"] for task in source.core_tasks(candidate["candidate_ref"])} == before_refs
        candidate["deltas"] = {definition["key"]: metric_delta(definition, candidate["metrics"][definition["key"]],
            previous.get(definition["key"], {}), work_scope_comparable=same_work)
            for definition in definitions if definition["key"] in candidate["metrics"]}
        if candidate["persisted_status"] != "completed":
            candidate["deltas"] = {key: {**delta, "value": None, "state": "unavailable", "direction": "neutral"}
                                   for key, delta in candidate["deltas"].items()}


def _public_metrics(values):
    return {key: {field: value for field, value in item.items() if field != "covered_operation_refs"}
            for key, item in values.items()}


def _overview_data(source, candidates, previous, before_coverage, definitions, recommendation_candidates):
    selected = next((row for row in candidates if row["candidate_ref"] == source.selected_ref), None)
    for candidate in candidates:
        candidate["metrics"] = _public_metrics(candidate["metrics"])
    return {"run": source.run, "scope": source.scope, "capture_ref": source.run["run_ref"],
            "catalog_complete": source.run["state"] not in ("queued", "running"), "metric_definitions": definitions,
            "candidates": candidates, "selection_basis": source.basis,
            "recommendation": recommendation(source, recommendation_candidates, definitions),
            "difference_summary": _difference_summary(selected, previous, definitions),
            "baseline": {**source.baseline, "metrics": _public_metrics(previous), "coverage": before_coverage},
            "resource_cohort": source.resource_cohort}


def _bounded_overview(data):
    bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
    return data


def decision_overview(source):
    definitions = metric_definitions()
    core = _core_candidates(source)
    enriched = _enriched_candidates(source, core, ["reference"] + [row["candidate_ref"] for row in core])
    candidates = [enriched[row["candidate_ref"]] for row in core]
    previous, before_coverage = _reference_metrics(source, candidates)
    previous, before_coverage = _enriched_reference(source, previous, before_coverage, enriched)
    _set_deltas(source, candidates, previous, definitions)
    data = _overview_data(source, candidates, previous, before_coverage, definitions, candidates)
    data["completion_groups"] = [{"group_index": index + 1, "source_available": group["source_available"],
        "candidate_refs": group["candidate_refs"], "complete_batch_count": len(group["complete_batch_refs"]),
        "sample_complete_batch_refs": group["complete_batch_refs"][:3]}
        for index, group in enumerate(source.completion.groups(candidates))]
    return _bounded_overview(data)


def decision_summary(source):
    definitions = metric_definitions()
    candidates = _core_candidates(source)
    selected = next((row for row in candidates if row["candidate_ref"] == source.basis["selected_candidate_ref"]), None)
    previous, before_coverage = _reference_metrics(source, candidates,
        metric_keys=None if selected is not None else CORE_METRIC_KEYS)
    core_previous = {key: value for key, value in previous.items() if key in CORE_METRIC_KEYS}
    core_coverage = {key: value for key, value in before_coverage.items() if key in CORE_BASELINE_COVERAGE}
    _set_deltas(source, candidates, core_previous, definitions)
    recommendation_candidates = []
    if selected is not None:
        enriched = _enriched_candidates(source, candidates, [selected["candidate_ref"], "reference"])
        full_previous, _ = _enriched_reference(source, previous, before_coverage, enriched)
        recommended = enriched[selected["candidate_ref"]]
        _set_deltas(source, [recommended], full_previous, definitions)
        recommended["metrics"] = _public_metrics(recommended["metrics"])
        recommendation_candidates = [recommended]
    return _bounded_overview(_overview_data(source, candidates, core_previous, core_coverage,
                                            definitions, recommendation_candidates))


def _difference_summary(selected, previous, definitions):
    coverage_fields = ("state", "scope", "known_subtotal", "known_count", "unknown_count", "total_count")
    definitions = {row["key"]: row for row in definitions}
    items = []
    for key in ("overdue_count", "total_tardiness_hours", "makespan_hours"):
        definition = definitions[key]
        before, after = previous.get(key, {}), selected["metrics"][key] if selected else {}
        delta = selected["deltas"][key] if selected else {
            "value": None, "state": "unavailable", "direction": "neutral", "reference_value": before.get("value"), "selected_value": None}
        items.append({**{field: definition[field] for field in ("key", "label", "unit", "precision", "scope")}, **delta,
                      "reference_coverage": {field: before.get(field) for field in coverage_fields},
                      "selected_coverage": {field: after.get(field) for field in coverage_fields}})
    return {"scope": "full_admission", "items": items}


def _candidate(row, tasks, facts, capture, disposition, scope, basis, rows, delivery_items):
    artifact = row["artifact"]
    if artifact.get("status") != row["status"] or artifact.get("sequence") != row["sequence"]:
        corrupt()
    coverage, values = candidate_metrics(row, tasks, facts, capture["input"], disposition, scope["batch_refs"], delivery_items=delivery_items)
    completed = sum(candidate["status"] == "completed" for candidate in rows)
    coverage["search"] = {"state": "complete" if completed == len(rows) else "partial", "completed_count": completed,
                          "failed_count": sum(candidate["status"] == "failed" for candidate in rows),
                          "skipped_count": sum(candidate["status"] == "skipped" for candidate in rows), "total_count": len(rows)}
    state = coverage["schedulable"]["state"]
    completeness = "no_result" if row["status"] != "completed" else "unknown" if state == "unavailable" else state
    reused = artifact.get("reused_from_candidate_key")
    return {"candidate_ref": row["candidate_ref"], "label": artifact.get("label"), "kind": artifact.get("kind"),
            "status": "partial" if completeness == "partial" else row["status"], "persisted_status": row["status"],
            "task_count": row["task_count"], "completeness": completeness, "coverage": coverage, "metrics": values,
            "capabilities": {"view": True, "compare": row["status"] == "completed", "gantt": row["status"] == "completed",
                             "adoption_preview": row["status"] == "completed", "adopt": False},
            "selection_role": selection_roles(row, basis),
            "equivalent_source_ref": next((item["candidate_ref"] for item in rows if item["artifact"].get("candidate_key") == reused), None),
            "source": {**{key: artifact.get(key) for key in ("algo_mode", "used_strategy", "dispatch_mode", "dispatch_rule", "failure_reason")},
                       "reason": _candidate_reason(row)}}


def _candidate_reason(row):
    if row["status"] == "completed":
        return None
    reason = row["artifact"].get("failure_reason")
    if reason == "candidate_time_budget_reached":
        return {"code": reason, "message": "本次计算时间预算已用完，该候选已跳过。"}
    if type(reason) is str and reason.strip():
        return {"code": "candidate_" + row["status"], "message": reason}
    return {"code": "candidate_reason_missing", "message": "排产存档缺少该候选的" + ("失败" if row["status"] == "failed" else "跳过") + "原因，请到排产记录核对。"}
