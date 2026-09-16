"""Read-only dashboard comparisons anchored to one immutable run admission."""

from collections import defaultdict

from core.models.schedule_plan_role import SOURCE_SCHEDULE
from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, RunCandidateReadScope, reject

from .dashboard_candidate_metrics import changeovers, resource_comparison, scoped_rows
from .plan_delivery_completeness import completion_evidence
from .plan_delivery_projection import project_delivery_batch, task_intervals
from .run_candidate_baseline import AdmissionBaseline, WorkbenchRunCandidateBaselineQueryService
from .run_candidate_facts import GenerationFacts, _table
from .run_candidate_values import bounded_size, stored_json
from .run_candidates import WorkbenchRunCandidateQueryService


def _common_batches(admission, batch_ref):
    refs = set(admission.settings["batch_refs"])
    if batch_ref is not None:
        if batch_ref not in refs:
            reject("entity_not_found", "所选批次不在本次排产范围。", 404)
        refs = {batch_ref}
    return sorted(refs)


def _baseline_tasks(baseline, admission):
    result = []
    for row in baseline["comparisons"]:
        op = admission.facts.tables["BatchOperations"][admission.facts.operations[row["operation_ref"]]]
        labels = {key: row[key] for key in ("operation_ref", "batch_ref", "process_label", "sequence")}
        for segment in row["baseline_segments"]:
            result.append({**labels, **segment, "source": op.get("source")})
    return result


def _baseline_finish(schedules, intervals):
    finish = {}
    for row in schedules:
        interval = intervals[row["schedule_id"]]
        if interval is not None:
            finish[row["batch_id"]] = max(interval[1], finish.get(row["batch_id"], interval[1]))
    return finish


def _baseline_deliveries(admission, capture, refs):
    facts, schedules, operations = admission.facts, [], defaultdict(list)
    for op in facts.tables["BatchOperations"].values():
        operations[op["batch_id"]].append({**op, "op_id": op["id"]})
    for row in admission.baseline["rows"]:
        op = facts.tables["BatchOperations"][row["op_id"]]
        schedules.append({**row, "schedule_id": row["id"], "batch_id": op["batch_id"]})
    intervals = task_intervals(schedules)
    if admission.baseline["version"] is None:
        incomplete, uncertain = set(), ["no_admission_baseline"]
    else:
        archive = stored_json(capture["facts_text"])
        history = [row for row in _table(archive, "ScheduleHistory") or [] if row["version"] == admission.baseline["version"]]
        if len(history) != 1:
            reject("candidate_baseline_invalid", "排产时的正式计划摘要无效，请刷新重试。", 500)
        finish = _baseline_finish(schedules, intervals)
        incomplete, uncertain = completion_evidence({"source": SOURCE_SCHEDULE, "summary": history[0]["result_summary"],
                                                     "result_status": history[0]["result_status"]}, len(schedules), finish)
    by_batch = defaultdict(list)
    for row in schedules:
        by_batch[row["batch_id"]].append(row)
    keys = {ref: key for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    return [project_delivery_batch(facts.tables["Batches"][keys[ref]], ref, by_batch[keys[ref]], operations[keys[ref]],
                                   intervals, keys[ref] in incomplete, uncertain) for ref in refs]


def _delivery_summary(rows):
    unknown = sum(row["risk"] == "unknown" for row in rows)
    known = sum(row["is_overdue"] is True for row in rows)
    return {"batch_count": len(rows), "overdue_count": None if unknown else known, "known_overdue_count": known,
            "unknown_count": unknown, "total_tardiness_hours": None if unknown else round(sum(row["delay_hours"] for row in rows), 6)}


def _delivery_rows(before, after, refs):
    old, new = ({row["batch_ref"]: row for row in rows} for rows in (before, after))
    if not set(refs) <= set(old) or not set(refs) <= set(new):
        reject("candidate_comparison_incomplete", "缺少排产时的批次数据，暂时无法比较。", 500)
    result = []
    for ref in refs:
        previous, current = old[ref], new[ref]
        if previous["batch_id"] != current["batch_id"] or previous["due_date"] != current["due_date"]:
            reject("candidate_comparison_inconsistent", "候选方案与对比基准的批次资料不一致，请重新排产。", 500)
        first, second = previous["delay_hours"], current["delay_hours"]
        result.append({"batch_ref": ref, "batch_id": current["batch_id"], "part_label": current["part_label"],
                       "before": previous, "after": current,
                       "delay_delta_hours": None if first is None or second is None else round(second - first, 6)})
    return result


def _machine_changes(baseline, refs):
    selected = [row for row in baseline["comparisons"] if row["batch_ref"] in refs]
    changed = [row["operation_ref"] for row in selected if row["delta"]["machine_changed"] is True]
    unknown = sum(row["delta"]["machine_changed"] is None for row in selected)
    return {"count": None if unknown else len(changed), "known_count": len(changed),
            "unknown_count": unknown, "operation_refs": changed, "basis": "matched_operation_permanent_identity"}


def _projection(workspace, baseline, full_workspace, full_baseline, admission, capture, scope):
    refs = _common_batches(admission, scope.batch_ref)
    before_delivery = _baseline_deliveries(admission, capture, refs)
    after_delivery = [row for row in full_workspace["delivery_risks"]["items"] if row["batch_ref"] in refs]
    batches = _delivery_rows(before_delivery, after_delivery, refs)
    before = [row for row in _baseline_tasks(full_baseline, admission) if row["batch_ref"] in refs]
    after = [row for row in full_workspace["tasks"] if row["batch_ref"] in refs]
    start, end = scope.range_start, scope.range_end
    captured = full_baseline["baseline"]["available"]
    old_cost = changeovers(scoped_rows(before, refs, start, end), admission.facts, captured)
    new_cost = changeovers(scoped_rows(after, refs, start, end), admission.facts)
    resources = resource_comparison(before, after, capture, admission.facts, start, end, captured)
    missing_resources = sum(row["source"] not in ("internal", "external") or
                            row["source"] == "internal" and (not row["machine"] or row["machine"]["ref"] is None)
                            for row in before + after)
    return {"candidate": workspace["candidate"], "generation": baseline["generation"], "baseline": baseline["baseline"],
            "time_scope": baseline["time_scope"], "batch_ref": scope.batch_ref, "batch_refs": refs,
            "capture_sha256": capture["facts_hash"], "batches": batches, "resources": resources,
            "summary": {"before": {**_delivery_summary(before_delivery), "changeovers": old_cost},
                        "after": {**_delivery_summary(after_delivery), "changeovers": new_cost},
                        "changeover_delta": None if old_cost["value"] is None or new_cost["value"] is None else new_cost["value"] - old_cost["value"]},
            "machine_changes": _machine_changes(baseline, refs),
            "resource_scope_complete": not bool(missing_resources), "resource_scope_unknown_rows": missing_resources,
            "basis": {"comparison": "candidate_minus_admission_official", "batch_scope": "admission_selected_batches",
                      "delivery": "complete_captured_batch_operations", "resources": "same_range_daily_peak_available_occupancy",
                      "changeovers": "same_range_scheduled_operation_type_changes", "current_entities_consulted": False},
            "capabilities": {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}}


def read_candidate_comparison(conn, scope):
    if scope.range_start is None or scope.range_end is None:
        reject("invalid_input", "请选择共同的比较时间范围。", 400)
    reader = WorkbenchRunCandidateQueryService(conn)
    baseline_reader = WorkbenchRunCandidateBaselineQueryService(conn)
    baseline_scope = RunCandidateBaselineScope(scope.candidate_ref, scope.range_start, scope.range_end,
                                               scope.batch_ref, scope.sort, scope.order)
    with reader.store.snapshot():
        workspace, workspace_state = reader.workspace(scope)
        baseline, baseline_state = baseline_reader.baseline(baseline_scope)
        full_workspace, _ = reader.workspace(RunCandidateReadScope(scope.candidate_ref))
        full_baseline, _ = baseline_reader.baseline(RunCandidateBaselineScope(scope.candidate_ref))
        run_ref = workspace["candidate"]["run_ref"]
        run, _, disposition = reader._load(run_ref)
        capture = reader.store.capture(run_ref)
        facts = GenerationFacts(capture)
        admission = AdmissionBaseline(capture, facts, disposition, run["accepted_at"])
        data = _projection(workspace, baseline, full_workspace, full_baseline, admission, capture, scope)
        state = input_fingerprint({"data": data, "workspace": workspace_state, "baseline": baseline_state})
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, state
