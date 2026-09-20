"""Compare a candidate with its admission baseline, under BL's bounded read snapshot."""

from collections import Counter

from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason, elapsed_hours
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, local_time, reject

from .facts.candidate_baseline import AdmissionBaseline, invalid_baseline
from .facts.candidate_facts import GenerationFacts
from .facts.candidate_projection import candidate_summary
from .facts.candidate_tasks import operation_labels, tasks_projection
from .facts.candidate_values import bounded_size, corrupt
from .run_candidates import WorkbenchRunCandidateQueryService


def _candidate_interval(task):
    fields = ("row_ref", "start", "end", "source", "machine", "operator", "supplier", "locked", "data_gaps")
    result = {**{key: task[key] for key in fields}, "elapsed_hours": elapsed_hours(task["start"], task["end"]),
              "effective_processing_hours": None}
    if task.get("event_kind") == "point":
        result.update(event_kind="point", duration_seconds=0, occupies_resources=False)
    return result


def _check_task_window(tasks, admission, disposition):
    start, end = (local_time(value) for value in preflight_window(admission.settings))
    for task in tasks:
        protected = disposition.get(task["operation_ref"], {}).get("status") == "protected" or task["locked"]
        if not protected and (local_time(task["start"]) < start or local_time(task["end"]) > end):
            invalid_baseline()


def _comparison_labels(facts, ref):
    labels, _ = operation_labels(facts, ref)
    execution = facts.execution[ref]
    labels["execution_at_generation"].update({key: execution[key] for key in (
        "first_actual_start", "confirmed_finish", "unknown_record_count", "records_complete", "quantity_complete", "completion_basis")})
    labels["execution_at_generation"].update(
        report_count=len(execution["reports"]), legacy_fact_count=len(execution["legacy_facts"]),
        legacy_unavailable_field_count=sum(len(row["unavailable_fields"]) for row in execution["legacy_facts"]))
    return labels


def _comparison_row(ref, task, admission, disposition):
    labels = _comparison_labels(admission.facts, ref)
    return RunBaselineComparison(
        ref, task["row_ref"] if task else None, labels, _candidate_interval(task) if task else None,
        admission.segments(ref), ref in admission.selected,
        "scheduled" if task else "skipped" if disposition.get(ref, {}).get("status") == "skipped"
        else "unscheduled" if ref in admission.selected else None,
    ).to_dict()


def _rows(tasks, admission, disposition):
    by_ref = {task["operation_ref"]: task for task in tasks}
    if not set(by_ref) <= admission.selected | set(admission.by_operation):
        invalid_baseline()
    _check_task_window(tasks, admission, disposition)
    return [_comparison_row(ref, by_ref.get(ref), admission, disposition)
            for ref in sorted(admission.selected | set(admission.by_operation) | set(by_ref))]


def _in_time(row, start, end):
    from .facts.zero_duration_evidence import overlaps

    if row["candidate"] is None:
        return True
    intervals = [row["candidate"]] + row["baseline_segments"]
    if any(item["start"] is None or item["end"] is None or
           (item["start"] == item["end"] and item.get("event_kind") != "point") for item in intervals):
        return True
    return any(overlaps(local_time(item["start"]), local_time(item["end"]), start, end) for item in intervals)


def _scope_rows(rows, scope):
    if scope.batch_ref is not None:
        if scope.batch_ref not in {row["batch_ref"] for row in rows}:
            reject("entity_not_found", "该批次不在排产时的对照范围内，请重新选择。", 404)
        rows = [row for row in rows if row["batch_ref"] == scope.batch_ref]
    if scope.range_start is not None:
        start, end = local_time(scope.range_start), local_time(scope.range_end)
        rows = [row for row in rows if _in_time(row, start, end)]

    def key(row):
        if scope.sort == "sequence":
            value = row["sequence"]
            return value is None, int(value) if value is not None else 0, row["operation_ref"]
        intervals = [row["candidate"]] if row["candidate"] else row["baseline_segments"]
        values = [item[scope.sort] for item in intervals if item[scope.sort] is not None]
        return not values, min(values) if values else "", row["operation_ref"]

    return sorted(rows, key=key, reverse=scope.order == "desc")


class WorkbenchRunCandidateBaselineQueryService:
    def __init__(self, conn):
        self.reader = WorkbenchRunCandidateQueryService(conn)

    def baseline(self, scope):
        store = self.reader.store
        with store.snapshot():
            run_ref = store.candidate_run(scope.candidate_ref)
            run, candidates, disposition = self.reader._load(run_ref)
            candidate = next((row for row in candidates if row["candidate_ref"] == scope.candidate_ref), None)
            if candidate is None:
                corrupt()
            summary = candidate_summary(candidate, disposition)
            capture = store.capture(run_ref)
            facts = GenerationFacts(capture)
            admission = AdmissionBaseline(capture, facts, disposition, run["accepted_at"])
            raw = store.tasks(scope.candidate_ref)
            if len(raw) != candidate["task_count"]:
                corrupt()
            # BL allows missing display metadata; comparison requires an exact captured identity.
            for row in raw:
                if facts.operations.get(row["operation_ref"]) != row["payload"].get("op_id"):
                    invalid_baseline()
            tasks = tasks_projection(raw, candidate, facts)
            all_rows = _rows(tasks, admission, disposition)
            rows = _scope_rows(all_rows, scope)
            data = self._dto(run, summary, admission, rows, len(all_rows), scope)
            bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
            return data, input_fingerprint(data)

    @staticmethod
    def _dto(run, candidate, admission, rows, count, scope):
        available = any(row["comparison_available"] for row in rows)
        captured = admission.baseline["version"] is not None
        reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
        return {"candidate": candidate, "generation": {
                    "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
                    "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
                    "current_entities_consulted": False, "formal_version_allocated": False, "input": admission.settings,
                    "source_verification": {"facts_digest_verified": True, "baseline_matches_archived_schedule": True,
                                            "execution_matches_archived_evidence": True, "input_independent_digest_recorded": False}},
                "baseline": {"baseline_ref": admission.baseline["plan_ref"], "kind": "admission_official",
                             "available": captured, "captured_task_count": len(admission.baseline["rows"]),
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
                              "historical_supplier_not_recorded", "not_an_optimization_score", "input_digest_not_recorded")]}
