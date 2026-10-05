"""One candidate's full immutable admission comparison, independent of viewport."""

from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_run_analysis import delivery_deltas, delivery_metrics, operation_metrics
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, RunCandidateReadScope
from core.services.workbench.facts.candidate_values import bounded_size

from .candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from .candidate_comparison import _baseline_deliveries, _delivery_rows, _delivery_summary
from .candidates import WorkbenchRunCandidateQueryService


def read_candidate_analysis(conn, candidate_ref):
    reader = WorkbenchRunCandidateQueryService(conn)
    with reader.store.snapshot():
        source = reader._source(candidate_ref)
        baseline_reader = WorkbenchRunCandidateBaselineQueryService(conn)
        admission, rows = baseline_reader._source(source)
        workspace, _ = reader._workspace(source, RunCandidateReadScope(candidate_ref))
        baseline, _ = baseline_reader._baseline(source, admission, rows, RunCandidateBaselineScope(candidate_ref))
        run_ref, capture = source.run["run_ref"], source.capture
        refs = sorted(admission.settings["batch_refs"])
        before = _baseline_deliveries(admission, capture, refs)
        after = [row for row in workspace["delivery_risks"]["items"] if row["batch_ref"] in refs]
        batches = _delivery_rows(before, after, refs)
        old_metrics = delivery_metrics(before, _delivery_summary(before))
        metrics = delivery_metrics(after, _delivery_summary(after))
        changes, operations = operation_metrics(baseline, refs)
        data = {"candidate_ref": candidate_ref, "run_ref": run_ref, "capture_sha256": capture["facts_hash"],
                "baseline": baseline["baseline"], "batch_refs": refs, "batches": batches,
                "metrics": {**metrics, **changes}, "before_metrics": old_metrics,
                "delivery_deltas": delivery_deltas(old_metrics, metrics), "operations": operations,
                "basis": {"scope": "full_candidate_and_full_admission_baseline", "batch_scope": "admission_selected_batches",
                          "operation_identity": "permanent_operation_reference", "comparison": "candidate_minus_admission_official",
                          "current_entities_consulted": False, "recommendation": None},
                "capabilities": {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}}
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, input_fingerprint(data)
