"""One candidate's full immutable admission comparison, independent of viewport."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_analysis import delivery_deltas, delivery_metrics, operation_metrics
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.delivery_projection import delivery_summary

from .candidate_comparison import (
    _analysis_source,
    _analysis_state,
    _comparison_metadata,
    _comparison_rows,
    _delivery_rows,
)


def read_candidate_analysis(conn, candidate_ref):
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = _analysis_source(store, candidate_ref)
        refs = sorted(source.input["batch_refs"])
        before = source.delivery("reference")
        after = [row for row in source.legacy_delivery(candidate_ref) if row["batch_ref"] in refs]
        batches = _delivery_rows(before, after, refs)
        old_metrics = delivery_metrics(before, delivery_summary(before))
        metrics = delivery_metrics(after, delivery_summary(after))
        rows = _comparison_rows(source)
        changes, operations = operation_metrics({"comparisons": rows, "rows_complete": True,
            "operation_count": len(rows), "full_operation_count": len(rows)}, refs)
        _, baseline = _comparison_metadata(source, rows)
        data = {"candidate_ref": candidate_ref, "run_ref": source.run["run_ref"],
                "baseline": baseline, "batch_refs": refs, "batches": batches,
                "metrics": {**metrics, **changes}, "before_metrics": old_metrics,
                "delivery_deltas": delivery_deltas(old_metrics, metrics), "operations": operations,
                "basis": {"scope": "full_candidate_and_full_admission_baseline", "batch_scope": "admission_selected_batches",
                          "operation_identity": "permanent_operation_reference", "comparison": "candidate_minus_admission_official",
                          "current_entities_consulted": False, "recommendation": None},
                "capabilities": {"view": True, "adopt": False, "edit_draft": False, "report_actual": False}}
        return data, _analysis_state(source)
