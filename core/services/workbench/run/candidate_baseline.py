"""Compare a candidate with its admission baseline directly from self-contained Schedule rows."""

from collections import Counter

from core.models.workbench_preflight import run_dates
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason
from core.models.workbench_run_candidate import local_time, reject
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline, invalid_baseline
from core.services.workbench.facts.candidate_projection import baseline_capture, candidate_summary
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import operation_labels, operation_sequence_order
from core.services.workbench.facts.zero_duration import overlaps


def _candidate_interval(task, interval):
    fields = ("row_ref", "start", "end", "source", "machine", "operator", "supplier", "locked", "data_gaps")
    hours = (interval[1] - interval[0]).total_seconds() / 3600
    result = {
        **{key: task[key] for key in fields},
        "elapsed_hours": hours,
        "effective_processing_hours": None,
    }
    if task.get("event_kind") == "point":
        result.update(event_kind="point", duration_seconds=0, occupies_resources=False)
    return result


def _check_raw_task_window(raw_tasks, admission, disposition, *, task_intervals):
    dates = run_dates(admission.settings)
    start, end = dates.start, dates.end_exclusive
    for row in raw_tasks:
        protected = disposition[row["operation_ref"]]["status"] == "protected" or row["locked"]
        if not protected:
            task_start, task_end = task_intervals[row["row_ref"]]
            if task_start < start or task_end > end:
                invalid_baseline()


def _pair_in_time(row_ref, segment, start, end, *, task_intervals, baseline_intervals):
    cand_start, cand_end = task_intervals[row_ref]
    if overlaps(cand_start, cand_end, start, end):
        return True
    if segment is None:
        return False
    first, last = baseline_intervals[segment["row_ref"]]
    return overlaps(first, last, start, end)


def comparison_row_in_time(row, start, end, *, task_intervals, baseline_intervals):
    cand = row["candidate"]
    if cand is None:
        return True
    return _pair_in_time(
        cand["row_ref"],
        row["baseline_segment"],
        start,
        end,
        task_intervals=task_intervals,
        baseline_intervals=baseline_intervals,
    )


def _raw_in_time(raw_task, segment, start, end, *, task_intervals, baseline_intervals):
    if raw_task is None:
        return True
    return _pair_in_time(
        raw_task["row_ref"],
        segment,
        start,
        end,
        task_intervals=task_intervals,
        baseline_intervals=baseline_intervals,
    )


def _comparison_labels(facts, ref):
    labels, _ = operation_labels(facts, ref)
    execution = facts.execution[ref]
    labels["execution_at_generation"].update(
        {
            key: execution[key]
            for key in (
                "first_actual_start",
                "confirmed_finish",
                "unknown_record_count",
                "records_complete",
                "quantity_complete",
                "completion_basis",
            )
        }
    )
    labels["execution_at_generation"]["report_count"] = len(execution["reports"])
    return labels


def _comparison_row(ref, task, segment, admission, disposition, *, task_intervals):
    labels = _comparison_labels(admission.facts, ref)
    cand_span = task_intervals[task["row_ref"]] if task is not None else None
    base_span = admission.segment_intervals[segment["row_ref"]] if segment is not None else None
    if task:
        status = "scheduled"
    elif ref not in admission.selected:
        # An official-plan operation outside the admitted batches has no disposition.
        status = None
    else:
        status = "skipped" if disposition[ref]["status"] == "skipped" else "unscheduled"
    return RunBaselineComparison(
        ref,
        task["row_ref"] if task else None,
        labels,
        _candidate_interval(task, cand_span) if task else None,
        segment,
        ref in admission.selected,
        status,
        candidate_interval=cand_span,
        baseline_interval=base_span,
    ).to_dict()


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

    @staticmethod
    def _source(source):
        admission = AdmissionBaseline(source.capture, source.facts, source.disposition)
        baseline = admission.baseline
        source_state = {
            "plan_ref": baseline["plan_ref"],
            "version": baseline["version"],
            "available": baseline["version"] is not None,
            "issue_code": None,
        }
        for row in source.raw_tasks:
            if source.facts.operations.get(row["operation_ref"]) != row["op_id"]:
                invalid_baseline()
        raw_by_ref = {row["operation_ref"]: row for row in source.raw_tasks}
        refs = sorted(admission.selected | set(admission.by_operation))
        if not set(raw_by_ref) <= admission.selected:
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
        segment_by_ref = {ref: admission.operation_segment(ref) for ref in target_refs}
        if scope.range_start is not None:
            start, end = local_time(scope.range_start), local_time(scope.range_end)
            target_refs = [
                ref
                for ref in target_refs
                if _raw_in_time(
                    raw_by_ref.get(ref),
                    segment_by_ref[ref],
                    start,
                    end,
                    task_intervals=source.task_intervals,
                    baseline_intervals=admission.segment_intervals,
                )
            ]
        target_raw_tasks = [raw_by_ref[ref] for ref in target_refs if ref in raw_by_ref]
        task_by_ref = {task["operation_ref"]: task for task in source.project_tasks(target_raw_tasks)}
        rows = [
            _comparison_row(
                ref,
                task_by_ref.get(ref),
                segment_by_ref[ref],
                admission,
                source.disposition,
                task_intervals=source.task_intervals,
            )
            for ref in target_refs
        ]

        def key(row):
            if scope.sort == "sequence":
                return operation_sequence_order(row)
            side = row["candidate"] or row["baseline_segment"]
            return side is None, side[scope.sort] if side is not None else "", row["operation_ref"]

        rows = sorted(rows, key=key, reverse=scope.order == "desc")
        return self._dto(
            source.run,
            candidate_summary(source.candidate, source.disposition, scheduled_op_ids=source.scheduled_op_ids),
            admission,
            rows,
            len(refs),
            scope,
        )

    @staticmethod
    def _dto(run, candidate, admission, rows, count, scope):
        available = any(row["comparison_available"] for row in rows)
        captured = admission.baseline["version"] is not None
        reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
        return {
            "candidate": candidate,
            "generation": {
                "run_ref": run["run_ref"],
                "accepted_at": run["accepted_at"],
                "finished_at": run["finished_at"],
                "metadata_basis": "captured_at_run_admission",
                "execution_basis": "captured_at_run_admission",
                "input": admission.settings,
            },
            "baseline": {
                **baseline_capture(admission.baseline, run["accepted_at"]),
                "available": captured,
                "comparison_available": available,
                "reason": reason,
            },
            "comparisons": rows,
            "operation_count": len(rows),
            "full_operation_count": count,
            "counts": dict(Counter(row["status"] for row in rows)),
            "execution_affected_count": sum(row["execution_affected"] for row in rows),
            "time_scope": {
                "range_start": scope.range_start,
                "range_end": scope.range_end,
                "interval": "half_open_overlap",
                "membership": "either_side_overlap",
                "counterpart_policy": "retain_complete_counterpart",
                "time_basis": "factory_local",
                "unplanned_policy": "included_without_time_interval",
                "unknown_or_zero_interval_policy": "included_without_time_interval",
            },
            "batch_ref": scope.batch_ref,
            "delta_basis": "candidate_minus_admission_baseline",
            "duration_basis": "elapsed_wall_clock_hours_not_effective_processing",
            "improvement_assessment": None,
            "capabilities": {
                "view": True,
                "adopt": False,
                "edit_draft": False,
                "report_actual": False,
                "export": False,
            },
            "data_gaps": [
                baseline_reason(code)
                for code in ("effective_hours_not_recorded", "not_an_optimization_score")
            ],
        }
