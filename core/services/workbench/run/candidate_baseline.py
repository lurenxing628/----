"""Compare a candidate with its admission baseline, under BL's bounded read snapshot."""

from collections import Counter

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason
from core.models.workbench_run_candidate import local_time, reject
from core.services.workbench.facts.adoption_baseline_sources import read_adoption_operation_facts
from core.services.workbench.facts.adoption_baseline_values import REASONS, AdoptionBaselineUnavailable
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline, invalid_baseline
from core.services.workbench.facts.candidate_projection import baseline_capture, candidate_summary
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import operation_labels
from core.services.workbench.facts.zero_duration_evidence import overlaps
from core.services.workbench.plan.adoption_baseline import read_adoption_source
from core.shared.strict_json import clone_json
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository

_ORIGIN_NOT_RECORDED = {"code": "adoption_not_recorded", "message": "此正式版本未保存可核对的采用来源。"}


def _candidate_interval(task, interval):
    fields = ("row_ref", "start", "end", "source", "machine", "operator", "supplier", "locked", "data_gaps")
    hours = (interval[1] - interval[0]).total_seconds() / 3600
    result = {**{key: task[key] for key in fields}, "elapsed_hours": hours,
              "effective_processing_hours": None}
    if task.get("event_kind") == "point":
        result.update(event_kind="point", duration_seconds=0, occupies_resources=False)
    return result


def _check_raw_task_window(raw_tasks, admission, disposition, *, task_intervals):
    start, end = (local_time(value) for value in preflight_window(admission.settings))
    for row in raw_tasks:
        protected = disposition.get(row["operation_ref"], {}).get("status") == "protected" or row["payload"]["locked"]
        if not protected:
            task_start, task_end = task_intervals[row["row_ref"]]
            if task_start < start or task_end > end:
                invalid_baseline()


def _pair_in_time(row_ref, segments, start, end, *, task_intervals, baseline_intervals):
    """Either side overlapping [start, end) keeps the pair; an unknown or zero-length non-point
    baseline segment keeps it without a time test."""
    if any(item["start"] is None or item["end"] is None or
           (item["start"] == item["end"] and item.get("event_kind") != "point") for item in segments):
        return True
    cand_start, cand_end = task_intervals[row_ref]
    if overlaps(cand_start, cand_end, start, end):
        return True
    for item in segments:
        first, last = baseline_intervals[item["row_ref"]]
        if overlaps(first, last, start, end):
            return True
    return False


def _in_time(row, start, end, *, task_intervals, baseline_intervals):
    cand = row["candidate"]
    if cand is None or cand["start"] == cand["end"] and cand.get("event_kind") != "point":
        return True
    return _pair_in_time(cand["row_ref"], row["baseline_segments"], start, end,
                         task_intervals=task_intervals, baseline_intervals=baseline_intervals)


def _raw_in_time(raw_task, segments, start, end, *, task_intervals, baseline_intervals):
    if raw_task is None:
        return True
    return _pair_in_time(raw_task["row_ref"], segments, start, end,
                         task_intervals=task_intervals, baseline_intervals=baseline_intervals)


def _comparison_labels(facts, ref):
    labels, _ = operation_labels(facts, ref)
    execution = facts.execution[ref]
    labels["execution_at_generation"].update({key: execution[key] for key in (
        "first_actual_start", "confirmed_finish", "unknown_record_count", "records_complete", "quantity_complete", "completion_basis")})
    labels["execution_at_generation"]["report_count"] = len(execution["reports"])
    return labels


def _comparison_row(ref, task, segments, admission, disposition, *, task_intervals):
    labels = _comparison_labels(admission.facts, ref)
    cand_span = task_intervals[task["row_ref"]] if task is not None else None
    base_spans = [admission.segment_intervals[seg["row_ref"]] for seg in segments]
    return RunBaselineComparison(
        ref, task["row_ref"] if task else None, labels,
        _candidate_interval(task, cand_span) if task else None,
        segments, ref in admission.selected,
        "scheduled" if task else "skipped" if disposition.get(ref, {}).get("status") == "skipped"
        else "unscheduled" if ref in admission.selected else None,
        candidate_interval=cand_span,
        baseline_intervals=base_spans,
    ).to_dict()


def _baseline_origins(conn, baseline):
    if baseline["version"] is None:
        return {}, None, None
    history = WorkbenchPlanBaselineRepository(conn).get_history_result_summary(baseline["version"])
    try:
        evidence = read_adoption_source(conn, plan_ref=baseline["plan_ref"], version=baseline["version"], history=history)
        return read_adoption_operation_facts(conn, evidence), evidence, None
    except AdoptionBaselineUnavailable as exc:
        return {}, None, {"code": exc.code, "message": REASONS[exc.code]}


class WorkbenchRunCandidateBaselineQueryService:
    def __init__(self, conn):
        self.store = CandidateStore(conn)

    def baseline(self, scope, *, bind_snapshot):
        store = self.store
        with store.snapshot():
            source = read_candidate_source(store, scope.candidate_ref)
            admission, refs, raw_by_ref, source_state = self._source(source)
            snapshot = bind_snapshot(scope.scope(), {**source.snapshot_identity, "baseline_source": source_state})
            return self._baseline(source, admission, refs, raw_by_ref, scope), snapshot

    def _source(self, source):
        from core.services.workbench.plan.point_evidence import official_point_work

        conn = self.store.conn
        with read_evidence_scope(conn):
            admission = AdmissionBaseline(source.capture, source.facts, source.disposition)
            baseline = admission.baseline
            origins, evidence, origin_issue = _baseline_origins(conn, baseline)
            point_work = (lambda: official_point_work(conn, baseline["version"], evidence=evidence)) if evidence is not None else None
            admission.bind_origin(origins, _ORIGIN_NOT_RECORDED if origin_issue is None else origin_issue, point_work)
            source_state = {"plan_ref": baseline["plan_ref"], "version": baseline["version"],
                            "available": evidence is not None,
                            "issue_code": origin_issue["code"] if origin_issue is not None else None}
            # Workspace allows missing display metadata; comparison requires exact captured identity.
            for row in source.raw_tasks:
                if source.facts.operations.get(row["operation_ref"]) != row["payload"]["op_id"]:
                    invalid_baseline()
            raw_by_ref = {row["operation_ref"]: row for row in source.raw_tasks}
            refs = sorted(admission.selected | set(admission.by_operation))
            if not set(raw_by_ref) <= set(refs):
                invalid_baseline()
            _check_raw_task_window(source.raw_tasks, admission, source.disposition, task_intervals=source.task_intervals)
            return admission, refs, raw_by_ref, source_state

    def _baseline(self, source, admission, refs, raw_by_ref, scope):
        target_refs = refs
        if scope.batch_ref is not None:
            known_batches = {admission.facts.operation_batch_ref(ref) for ref in refs}
            if scope.batch_ref not in known_batches:
                reject("entity_not_found", "该批次不在排产时的对照范围内，请重新选择。", 404)
            target_refs = [ref for ref in target_refs if admission.facts.operation_batch_ref(ref) == scope.batch_ref]
        # Each segment read also records its interval in admission.segment_intervals.
        segments_by_ref = {ref: admission.segments(ref) for ref in target_refs}
        if scope.range_start is not None:
            start, end = local_time(scope.range_start), local_time(scope.range_end)
            target_refs = [
                ref
                for ref in target_refs
                if _raw_in_time(
                    raw_by_ref.get(ref),
                    segments_by_ref[ref],
                    start,
                    end,
                    task_intervals=source.task_intervals,
                    baseline_intervals=admission.segment_intervals,
                )
            ]
        target_raw_tasks = [raw_by_ref[ref] for ref in target_refs if ref in raw_by_ref]
        projected_tasks = (
            source.tasks
            if len(target_raw_tasks) == len(source.raw_tasks) and "tasks" in source.__dict__
            else source.project_tasks(target_raw_tasks)
        )
        task_by_ref = {task["operation_ref"]: task for task in projected_tasks}
        rows = [
            _comparison_row(ref, task_by_ref.get(ref), segments_by_ref[ref], admission, source.disposition,
                            task_intervals=source.task_intervals)
            for ref in target_refs
        ]

        def key(row):
            if scope.sort == "sequence":
                value = row["sequence"]
                return value is None, int(value) if value is not None else 0, row["operation_ref"]
            intervals = [row["candidate"]] if row["candidate"] else row["baseline_segments"]
            values = [item[scope.sort] for item in intervals if item[scope.sort] is not None]
            return not values, min(values) if values else "", row["operation_ref"]

        rows = sorted(rows, key=key, reverse=scope.order == "desc")
        data = self._dto(source.run, candidate_summary(source.candidate, source.disposition,
                                                       scheduled_op_ids=source.scheduled_op_ids),
                         admission, rows, len(refs), scope)
        return data

    @staticmethod
    def _dto(run, candidate, admission, rows, count, scope):
        available = any(row["comparison_available"] for row in rows)
        captured = admission.baseline["version"] is not None
        reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
        return {"candidate": candidate, "generation": {
                    "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
                    "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
                    "current_entities_consulted": False, "formal_version_allocated": False, "input": clone_json(admission.settings)},
                "baseline": {**baseline_capture(admission.baseline, run["accepted_at"]), "available": captured,
                             "comparison_available": available, "reason": reason},
                "comparisons": rows, "operation_count": len(rows), "full_operation_count": count, "rows_complete": True,
                "counts": dict(Counter(row["status"] for row in rows)),
                "execution_affected_count": sum(row["execution_affected"] for row in rows),
                "time_scope": {"range_start": scope.range_start, "range_end": scope.range_end,
                               "interval": "half_open_overlap", "membership": "either_side_overlap",
                               "counterpart_policy": "retain_complete_counterpart", "time_basis": "factory_local",
                               "unplanned_policy": "included_without_time_interval",
                               "unknown_or_zero_interval_policy": "included_without_time_interval"},
                "batch_ref": scope.batch_ref, "delta_basis": "candidate_minus_admission_baseline",
                "duration_basis": "elapsed_wall_clock_hours_not_effective_processing",
                "improvement_assessment": None, "capabilities": {"view": True, "adopt": False, "edit_draft": False,
                                                                       "report_actual": False, "export": False},
                "data_gaps": [baseline_reason(code) for code in ("effective_hours_not_recorded",
                              "not_an_optimization_score")]}
