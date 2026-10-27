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


def compute_candidate_run(conn, normalized_input, execution_projections, *, capture, dispositions) -> CandidateRunComputation:
    """Compute actual candidate rows under one read snapshot; worker owns run lock.

    capture is the worker's production facts capture; execution_projections and
    dispositions are the already validated projections and the classification
    archived by that run's admission.
    """
    with candidate_read_snapshot(conn):
        # The private continuation consumes this preparation in the same read snapshot.
        facts = PreflightFacts(conn, capture=capture)
        facts.bind_capture(capture)
        prepared = prepare_candidate_run_input(conn, normalized_input, execution_projections, facts=facts,
                                               admitted_dispositions=dispositions)
        return _compute_in_read_snapshot(conn, prepared, _prepared_version(prepared))


def _prepared_version(schedule_input):
    # prev_version is read straight from the captured ScheduleHistory rows; this is its only check.
    version = schedule_input.prev_version
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
            payloads[candidate.candidate_key] = validate_candidate(
                schedule_input, candidate.results, list(candidate.summary.errors),
                prepared_payload=(selected_payload if candidate.candidate_key == comparison.selection.selected_candidate_key else None),
                context=validation_context,
            )
            if piece_context is not None:
                validate_piece_candidate(
                    conn, prepared=schedule_input,
                    payload=payloads[candidate.candidate_key], context=piece_context,
                )
    return payloads


def _computation_state(schedule_input, comparison, payloads):
    selected = comparison.selection.selected_plan
    selected_ids = payloads[selected.candidate_key].scheduled_op_ids
    # The unified search returns only completed candidates; partial means the selected plan's scope.
    is_partial = (selected_ids != schedule_input.schedule_output_allowed_op_ids
                  or any(row["status"] == "skipped" for row in schedule_input.dispositions))
    return "partial" if is_partial else "complete"


def _compute_in_read_snapshot(conn, schedule_input, version):
    """Private continuation after preparation in the current snapshot."""
    if not conn.in_transaction or not is_query_only(conn):
        fail("candidate_read_snapshot_lost", "Candidate computation requires its active read-only snapshot.")
    compare = run_candidate_comparison
    if any(op.piece_id is not None for op in schedule_input.operations):
        compare = partial(compare, prepare_graph_fn=piece_graph_preparer(schedule_input))
    orchestration = orchestrate_schedule_run(
        schedule_input=schedule_input, version=version,
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
