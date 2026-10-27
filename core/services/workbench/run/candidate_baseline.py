"""Compare a candidate with its admission baseline, under BL's bounded read snapshot."""

from collections import Counter

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason, elapsed_hours
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
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository


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
    refs = admission.selected | set(admission.by_operation)
    if not set(by_ref) <= refs:
        invalid_baseline()
    _check_task_window(tasks, admission, disposition)
    return [_comparison_row(ref, by_ref.get(ref), admission, disposition)
            for ref in sorted(refs)]


def _in_time(row, start, end):
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


def _baseline_origins(conn, baseline):
    try:
        if baseline["version"] is None:
            return {}, None, None
        history = WorkbenchPlanBaselineRepository(conn).get_history_result_summary(baseline["version"])
        evidence = read_adoption_source(conn, plan_ref=baseline["plan_ref"], version=baseline["version"], history=history)
        return read_adoption_operation_facts(conn, evidence), evidence, None
    except AdoptionBaselineUnavailable as exc:
        return {}, None, {"code": exc.code, "message": REASONS[exc.code]}
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return {}, None, {"code": exc.code, "message": str(exc)}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {}, None, {"code": "adoption_snapshot_invalid", "message": REASONS["adoption_snapshot_invalid"]}


class WorkbenchRunCandidateBaselineQueryService:
    def __init__(self, conn):
        self.store = CandidateStore(conn)

    def baseline(self, scope):
        store = self.store
        with store.snapshot():
            source = read_candidate_source(store, scope.candidate_ref)
            admission, rows, source_state = self._source(source)
            return self._baseline(source, admission, rows, source_state, scope)

    def _source(self, source):
        from core.services.workbench.plan.point_evidence import official_point_work

        conn, baseline = self.store.conn, source.capture["baseline"]
        with read_evidence_scope(conn):
            origins, evidence, origin_issue = _baseline_origins(conn, baseline)
            admission = AdmissionBaseline(source.capture, source.facts, source.disposition,
                point_work=lambda: official_point_work(conn, baseline["version"], evidence=evidence) if evidence is not None else {},
                origins=origins, origin_issue=origin_issue)
            source_state = {"plan_ref": baseline["plan_ref"], "version": baseline["version"],
                            "available": evidence is not None,
                            "issue_code": origin_issue["code"] if origin_issue is not None else None}
            # Workspace allows missing display metadata; comparison requires exact captured identity.
            for row in source.raw_tasks:
                if source.facts.operations.get(row["operation_ref"]) != row["payload"].get("op_id"):
                    invalid_baseline()
            return admission, _rows(source.tasks, admission, source.disposition), source_state

    def _baseline(self, source, admission, all_rows, source_state, scope):
        rows = _scope_rows(all_rows, scope)
        data = self._dto(source.run, candidate_summary(source.candidate, source.disposition,
                                                       scheduled_op_ids=source.scheduled_op_ids),
                         admission, rows, len(all_rows), scope)
        return data, {**source.snapshot_identity, "baseline_source": source_state}

    @staticmethod
    def _dto(run, candidate, admission, rows, count, scope):
        available = any(row["comparison_available"] for row in rows)
        captured = admission.baseline["version"] is not None
        reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
        return {"candidate": candidate, "generation": {
                    "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
                    "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
                    "current_entities_consulted": False, "formal_version_allocated": False, "input": admission.settings},
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
