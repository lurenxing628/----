"""In-memory candidate computation. No worker admission, version allocation or publish."""

from functools import partial

from core.infrastructure.connection_guards import is_query_only
from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_compute import CandidateRunComputation
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_orchestrator import orchestrate_schedule_run
from core.services.scheduler.summary.schedule_summary import build_result_summary
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.run_input_rows import fail
from core.services.workbench.facts.zero_duration import candidate_point_validator

from .compute_graph import piece_graph_preparer
from .compute_validation import prepare_candidate_validation_context, validate_candidate
from .input import prepare_candidate_run_input
from .piece_adoption import prepare_piece_validation_context, validate_piece_candidate
from .preflight_facts import PreflightFacts


def compute_candidate_run(conn, normalized_input, execution_projections, *, version_override=None,
                          capture=None,
                          validated_projections=None) -> CandidateRunComputation:
    """Compute actual candidate rows under one read snapshot; worker owns run lock."""
    with candidate_read_snapshot(conn):
        return _prepare_and_compute_in_snapshot(
            conn, normalized_input, execution_projections, version_override, capture,
            validated_projections=validated_projections)


def _prepare_and_compute_in_snapshot(
    conn, normalized_input, execution_projections, version_override,
    capture, validated_projections,
):
    # The private continuation consumes this preparation in the same read snapshot.
    facts = None
    if capture is not None:
        facts = PreflightFacts(conn, capture=capture)
        facts.bind_capture(capture)
    prepared = prepare_candidate_run_input(
        conn, normalized_input, execution_projections, capture_fingerprint=False, facts=facts,
        validated_projections=validated_projections)
    version = _prepared_version(prepared, version_override)
    return _compute_in_read_snapshot(conn, prepared, version)


def _prepared_version(schedule_input, version_override):
    version = schedule_input.prev_version if version_override is None else version_override
    if type(version) is not int or version < 0:
        fail("invalid_version_context", "Version context must be an explicit non-negative integer.")
    return version


def _candidate_payloads(conn, schedule_input, comparison, *, selected_payload):
    payloads = {}
    with read_evidence_scope(conn):
        validation_context = prepare_candidate_validation_context(schedule_input)
        piece_context = (prepare_piece_validation_context(conn, schedule_input)
                         if any(op.piece_id is not None for op in schedule_input.operations) else None)
        for candidate in comparison.candidates:
            if candidate.status == "completed":
                payloads[candidate.candidate_key] = validate_candidate(
                    schedule_input, candidate.results, list(candidate.summary.errors),
                    prepared_payload=(selected_payload if candidate.candidate_key == comparison.selection.selected_candidate_key else None),
                    context=validation_context,
                )
                if piece_context is not None:
                    validate_piece_candidate(
                        conn, prepared=schedule_input,
                        payload=payloads[candidate.candidate_key], context=piece_context,
                        candidate_validated=True,
                    )
    return payloads


def _computation_state(schedule_input, comparison, payloads):
    selected = comparison.selection.selected_plan
    selected_ids = payloads[selected.candidate_key].scheduled_op_ids
    is_partial = (selected_ids != schedule_input.schedule_output_allowed_op_ids
               or any(row["status"] == "skipped" for row in schedule_input.dispositions)
               or comparison.failed_count > 0 or comparison.skipped_count > 0)
    return "partial" if is_partial else "complete"


def _compute_in_read_snapshot(conn, schedule_input, version):
    """Private continuation after preparation in the current snapshot."""
    if not conn.in_transaction or not is_query_only(conn):
        fail("candidate_read_snapshot_lost", "Candidate computation requires its active read-only snapshot.")
    compare = run_candidate_comparison
    if any(op.piece_id is not None for op in schedule_input.operations):
        compare = partial(compare, prepare_graph_fn=piece_graph_preparer(schedule_input))
    orchestration = orchestrate_schedule_run(
        schedule_input=schedule_input, version=version, strict_mode=True,
        build_result_summary_fn=build_result_summary,
        point_validator=candidate_point_validator(schedule_input),
        candidate_comparison_fn=compare,
    )
    comparison = orchestration.candidate_comparison
    payloads = _candidate_payloads(conn, schedule_input, comparison,
                                   selected_payload=orchestration.validated_schedule_payload)
    state = _computation_state(schedule_input, comparison, payloads)
    return CandidateRunComputation(schedule_input, orchestration, payloads,
                                   schedule_input.dispositions, state)
