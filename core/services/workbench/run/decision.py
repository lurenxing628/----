"""All same-run candidates under one admission archive and one viewing reference."""

from core.services.workbench.facts.decision_metrics import (
    COVERAGE_MEMBER_FIELDS,
    metric_definitions,
    metric_delta,
    metric_value,
    unavailable_operation_change_metrics,
)

from .decision_recommendation import recommendation
from .decision_session import decision_read, decision_snapshot_scope

CORE_METRIC_KEYS = (
    "expected_operation_count", "scheduled_operation_count", "unplanned_operation_count", "deferred_operation_count",
    "overdue_count", "total_tardiness_hours", "makespan_hours", "weighted_tardiness_hours", "elapsed_seconds",
    "changeover_count", "machine_used_count", "operator_used_count", "machine_busy_hours_total",
    "operator_busy_hours_total", "machine_util_avg", "operator_util_avg",
)
# The coverage the summary keeps for its candidates and its baseline.
CORE_COVERAGE = ("schedulable", "delivery")


def operation_change_metrics_from_sql(source, candidate_ref):
    if source.baseline["state"] != "available":
        return unavailable_operation_change_metrics(source.admitted_operation_refs)
    counts = source.repo.operation_change_counts(source.run["run_ref"], source.side_key("reference"), candidate_ref)
    total = counts["total"]
    changed, unknown = counts["changed"], counts["unknown"]
    machines, machine_unknown = counts["machines"], counts["machine_unknown"]
    reason = {
        "code": "arrangement_comparison_incomplete",
        "message": "部分工序缺少设备人员编号，或双方都没有安排，已列出可确认的调整数量。",
    }
    return {
        "changed_operation_count": metric_value(
            None if unknown else changed, total=total, unknown=unknown, subtotal=changed,
            reason=reason if unknown else None, member_unit="operation",
        ),
        "machine_change_count": metric_value(
            None if machine_unknown else machines, total=total, unknown=machine_unknown, subtotal=machines,
            reason=reason if machine_unknown else None, member_unit="operation",
        ),
    }


def read_run_decision(conn, run_ref, *, bind_snapshot, **query):
    return _read_projection(conn, run_ref, decision_overview, bind_snapshot, query)


def read_run_decision_summary(conn, run_ref, *, bind_snapshot, **query):
    return _read_projection(conn, run_ref, decision_summary, bind_snapshot, query)


def _read_projection(conn, run_ref, projection, bind_snapshot, query):
    with decision_read(conn, run_ref, **query) as source:
        snapshot = bind_snapshot(decision_snapshot_scope(source), source.state())
        return projection(source), snapshot


def _core_candidates(source, *, include_evaluations: bool = True):
    return [
        source.saved_candidate(row["candidate_ref"], include_evaluations=include_evaluations)
        for row in source.rows
    ]


def _enriched_candidates(source, candidates, keys, *, metric_keys=None):
    names = {source.computation_key(key) for key in keys}
    wanted = None if metric_keys is None else set(metric_keys)
    definitions = {row["key"]: row for row in metric_definitions()} if wanted is not None else {}
    need_resources = wanted is None or any(
        definitions[key]["source"] == "archived_resource_calendar" for key in wanted if key in definitions
    )
    need_preparation = wanted is None or any(
        definitions[key]["source"] == "runtime_operation_effort" for key in wanted if key in definitions
    )
    need_changeovers = wanted is None or bool({"type_changeover_count", "changed_machine_count"} & wanted)
    need_changes = wanted is None or bool({"changed_operation_count", "machine_change_count"} & wanted)
    if need_resources:
        source.resources.prepare_keys(keys)
    result = {}
    for candidate in candidates:
        key = candidate["candidate_ref"]
        if key not in names:
            continue
        candidate = {**candidate, "metrics": dict(candidate["metrics"]), "coverage": dict(candidate["coverage"])}
        if need_resources:
            candidate["metrics"].update(source.resources.metrics(key))
            candidate["coverage"]["resources"] = (
                source.resources.overview_coverage(key)
                if wanted is None
                else {kind: source.resources.summary(key, kind) for kind in ("machine", "operator")}
            )
        if need_preparation:
            candidate["metrics"].update(source.preparation.metrics(key))
            if wanted is None:
                candidate["coverage"]["preparation"] = source.preparation.public_coverage(key)
        if need_changeovers:
            candidate["metrics"].update(source.changeovers.metrics(key))
        if need_changes:
            candidate["metrics"].update(operation_change_metrics_from_sql(source, key))
        result[key] = candidate
    return result


def _reference_metrics(source, candidates, *, metric_keys=None):
    reference_candidate = next((row for row in candidates if row["candidate_ref"] == source.reference_ref), None)
    if source.comparison_mode == "admission_official":
        saved = source.official["core_metrics"]
        raw_metrics = saved if metric_keys is None else {key: value for key, value in saved.items() if key in metric_keys}
        return source.memberships.expand(raw_metrics), source.memberships.expand(source.official["coverage"])
    previous = reference_candidate["metrics"] if reference_candidate else {}
    before_coverage = reference_candidate["coverage"] if reference_candidate else {"schedulable": {"state": "unavailable"}}
    return previous, before_coverage


def _enriched_reference(source, previous, before_coverage, candidates):
    reference_candidate = candidates.get(source.computation_key("reference"))
    if reference_candidate is not None:
        return reference_candidate["metrics"], reference_candidate["coverage"]
    previous, before_coverage = dict(previous), dict(before_coverage)
    previous.update(source.resources.metrics("reference"))
    previous.update(source.preparation.metrics("reference"))
    previous.update(source.changeovers.metrics("reference"))
    before_coverage["resources"] = source.resources.overview_coverage("reference")
    before_coverage["preparation"] = source.preparation.public_coverage("reference")
    return previous, before_coverage


def _reference_operation_refs(source):
    return source.scheduled_refs("reference") if source.comparison_mode == "admission_official" or source.reference_ref else set()


def _set_deltas(source, candidates, previous, definitions):
    before_refs = _reference_operation_refs(source)
    for candidate in candidates:
        same_work = source.scheduled_refs(candidate["candidate_ref"]) == before_refs
        candidate["deltas"] = {definition["key"]: metric_delta(definition, candidate["metrics"][definition["key"]],
            previous[definition["key"]], work_scope_comparable=same_work)
            for definition in definitions if definition["key"] in candidate["metrics"]}


def _public_metrics(values):
    return {
        key: {field: value for field, value in item.items() if field not in COVERAGE_MEMBER_FIELDS}
        for key, item in values.items()
    }


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


def decision_overview(source):
    definitions = metric_definitions()
    core = _core_candidates(source)
    enriched = _enriched_candidates(source, core, ["reference"] + [row["candidate_ref"] for row in core])
    candidates = [enriched[row["candidate_ref"]] for row in core]
    previous, before_coverage = _reference_metrics(source, candidates)
    previous, before_coverage = _enriched_reference(source, previous, before_coverage, enriched)
    _set_deltas(source, candidates, previous, definitions)
    return _overview_data(source, candidates, previous, before_coverage, definitions, candidates)


def decision_history_candidate(source, *, metric_keys=None):
    """Project one history event against the same all-candidate resource cohort."""
    candidate = source.saved_candidate(source.selected_ref, include_evaluations=False, metric_keys=metric_keys)
    candidates = _enriched_candidates(source, [candidate], [source.selected_ref], metric_keys=metric_keys)
    selected = candidates[source.selected_ref]
    return {"candidates": [selected], "resource_cohort": source.resource_cohort}


def decision_summary(source):
    definitions = metric_definitions()
    candidates = _core_candidates(source, include_evaluations=False)
    selected = next((row for row in candidates if row["candidate_ref"] == source.basis["selected_candidate_ref"]), None)
    previous, before_coverage = _reference_metrics(source, candidates,
        metric_keys=None if selected is not None else CORE_METRIC_KEYS)
    core_previous = {key: value for key, value in previous.items() if key in CORE_METRIC_KEYS}
    core_coverage = {key: before_coverage[key] for key in CORE_COVERAGE if key in before_coverage}
    _set_deltas(source, candidates, core_previous, definitions)
    recommendation_candidates = []
    if selected is not None:
        enriched = _enriched_candidates(source, candidates, [selected["candidate_ref"], "reference"])
        full_previous, _ = _enriched_reference(source, previous, before_coverage, enriched)
        recommended = enriched[selected["candidate_ref"]]
        _set_deltas(source, [recommended], full_previous, definitions)
        recommended["metrics"] = _public_metrics(recommended["metrics"])
        recommendation_candidates = [recommended]
    return _overview_data(source, candidates, core_previous, core_coverage,
                          definitions, recommendation_candidates)


_DIFFERENCE_COVERAGE_FIELDS = ("state", "scope", "known_subtotal", "known_count", "unknown_count", "total_count")


def _difference_coverage(item):
    """One side's coverage of a metric; a side with no value of it (no reference, no selected candidate) covers nothing."""
    return {field: None if item is None else item[field] for field in _DIFFERENCE_COVERAGE_FIELDS}


def _difference_summary(selected, previous, definitions):
    """``previous`` holds these metrics unless there is no reference to view: a candidate comparison of a run
    without candidates."""
    definitions = {row["key"]: row for row in definitions}
    items = []
    for key in ("overdue_count", "total_tardiness_hours", "makespan_hours"):
        definition = definitions[key]
        before, after = previous.get(key), selected["metrics"][key] if selected else None
        delta = selected["deltas"][key] if selected else {
            "value": None, "state": "unavailable", "direction": "neutral",
            "reference_value": None if before is None else before["value"], "selected_value": None}
        items.append({**{field: definition[field] for field in ("key", "label", "unit", "precision", "scope")}, **delta,
                      "reference_coverage": _difference_coverage(before),
                      "selected_coverage": _difference_coverage(after)})
    return {"scope": "full_admission", "items": items}
