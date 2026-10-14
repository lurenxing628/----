"""Read-only dashboard comparisons anchored to one immutable run admission."""

from collections import defaultdict
from types import SimpleNamespace

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import canonical_json
from core.models.workbench_run_analysis import operation_change
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, RunCandidateReadScope, reject
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_values import bounded_size
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.delivery_projection import delivery_batch_delta, delivery_summary

from .candidate_baseline import WorkbenchRunCandidateBaselineQueryService, _rows, _scope_rows
from .candidate_metrics import candidate_resource_cohort, changeovers, resource_comparison
from .candidate_tradeoffs import candidate_tradeoffs
from .candidates import WorkbenchRunCandidateQueryService
from .decision_delivery import project_decision_delivery


def _common_batches(settings, batch_ref):
    refs = set(settings["batch_refs"])
    if batch_ref is not None:
        if batch_ref not in refs:
            reject("entity_not_found", "所选批次不在本次排产范围。", 404)
        refs = {batch_ref}
    return sorted(refs)


def _admission_comparison(conn, source):
    """Adapt the canonical formal source to existing descriptive comparison DTOs."""
    official = read_decision_baseline(source.capture, source.facts, source.disposition, source.run["accepted_at"],
                                      source_resolver=decision_baseline_source_resolver(conn))
    by_operation = defaultdict(list)
    for task in official["tasks"]:
        by_operation[task["operation_ref"]].append(task)
    frame = SimpleNamespace(facts=source.facts, settings=source.capture["input"], selected=set(source.disposition),
                            by_operation=by_operation, segments=lambda ref: by_operation[ref],
                            baseline={"plan_ref": official["identity"]["plan_ref"],
                                      "version": official["identity"]["version"], "rows": official["tasks"]})
    return official, frame, _rows(source.tasks, frame, source.disposition)


def _baseline_deliveries(facts, official, refs):
    return project_decision_delivery(facts, official["tasks"], refs,
                                     deferred_ids=official["deferred_operation_ids"],
                                     available=official["identity"]["state"] == "available")


def _delivery_summary(rows):
    return delivery_summary(rows)


def _delivery_rows(before, after, refs):
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


def _machine_changes(baseline, refs):
    selected = [row for row in baseline["comparisons"] if row["batch_ref"] in refs]
    machines = [(row["operation_ref"], operation_change(row)[1]) for row in selected]
    changed = [ref for ref, changed in machines if changed is True]
    unknown = sum(changed is None for _, changed in machines)
    return {"count": None if unknown else len(changed), "known_count": len(changed),
            "unknown_count": unknown, "operation_refs": changed, "basis": "matched_operation_permanent_identity"}


def _projection(workspace, baseline, full_workspace, full_baseline, official, facts, capture, scope, cohort):
    refs = _common_batches(capture["input"], scope.batch_ref)
    before_delivery = _baseline_deliveries(facts, official, refs)
    after_delivery = [row for row in full_workspace["delivery_risks"]["items"] if row["batch_ref"] in refs]
    batches = _delivery_rows(before_delivery, after_delivery, refs)
    before = [row for row in official["tasks"] if row["batch_ref"] in refs]
    after = [row for row in full_workspace["tasks"] if row["batch_ref"] in refs]
    start, end = scope.range_start, scope.range_end
    captured = full_baseline["baseline"]["available"]
    old_cost = changeovers(official["tasks"], facts, captured, start=start, end=end,
                          next_operation_refs=[row["operation_ref"] for row in before])
    new_cost = changeovers(full_workspace["tasks"], facts, start=start, end=end,
                          next_operation_refs=[row["operation_ref"] for row in after])
    resources, resource_common = resource_comparison(before, after, capture, facts, start, end, captured, cohort)
    resource_common.update(batch_refs=refs, resource_view="selected_batches", run_ref=workspace["generation"]["run_ref"])
    missing_resources = sum(row["source"] not in ("internal", "external") or
                            row["source"] == "internal" and (not row["machine"] or row["machine"]["ref"] is None)
                            for row in before + after)
    result = {"candidate": workspace["candidate"], "generation": baseline["generation"], "baseline": baseline["baseline"],
            "time_scope": baseline["time_scope"], "batch_ref": scope.batch_ref, "batch_refs": refs,
            "batches": batches, "resources": resources, "resource_common": resource_common,
            "summary": {"before": {**_delivery_summary(before_delivery), "changeovers": old_cost},
                        "after": {**_delivery_summary(after_delivery), "changeovers": new_cost},
                        "changeover_delta": None if old_cost["value"] is None or new_cost["value"] is None else new_cost["value"] - old_cost["value"]},
            "machine_changes": _machine_changes(full_baseline, refs),
            "resource_scope_complete": not bool(missing_resources), "resource_scope_unknown_rows": missing_resources,
            "basis": {"comparison": "candidate_minus_admission_official", "batch_scope": "admission_selected_batches",
                      "delivery": "complete_captured_batch_operations", "resources": "same_range_daily_peak_available_occupancy",
                      "changeovers": "same_range_scheduled_operation_type_changes", "current_entities_consulted": False},
            "capabilities": {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}}
    selected_batches = set(refs)
    subject_operation_refs = {ref for ref, key in facts.operations.items()
        if facts.entity_refs.get(("batch", facts.tables["BatchOperations"][key]["batch_id"])) in selected_batches}
    result["tradeoffs"] = candidate_tradeoffs(result, before_delivery, after_delivery, official["tasks"], full_workspace["tasks"],
                                           subject_operation_refs=subject_operation_refs)
    return result


def read_candidate_comparison(conn, scope):
    if scope.range_start is None or scope.range_end is None:
        reject("invalid_input", "请选择共同的比较时间范围。", 400)
    reader = WorkbenchRunCandidateQueryService(conn)
    baseline_scope = RunCandidateBaselineScope(scope.candidate_ref, scope.range_start, scope.range_end,
                                               scope.batch_ref, scope.sort, scope.order)
    with reader.store.snapshot(), read_evidence_scope(conn):
        source = read_candidate_source(reader.store, scope.candidate_ref)
        official, frame, rows = _admission_comparison(conn, source)
        workspace, workspace_state = reader._workspace(source, scope)
        candidate = workspace["candidate"]
        baseline = WorkbenchRunCandidateBaselineQueryService._dto(source.run, candidate, frame, _scope_rows(rows, baseline_scope), len(rows), baseline_scope)
        full_workspace, _ = reader._workspace(source, RunCandidateReadScope(scope.candidate_ref))
        full_baseline = WorkbenchRunCandidateBaselineQueryService._dto(source.run, candidate, frame, rows, len(rows), RunCandidateBaselineScope(scope.candidate_ref))
        data = _projection(workspace, baseline, full_workspace, full_baseline, official, source.facts, source.capture, scope,
                           candidate_resource_cohort(reader.store, source, official["tasks"]))
        state = {**workspace_state, "official_sources": official["source_states"]}
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, state
