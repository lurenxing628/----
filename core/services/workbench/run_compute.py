"""In-memory candidate computation. No worker admission, version allocation or publish."""

from functools import partial

from core.models.workbench_run_compute import CandidateRunComputation
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_optimizer import optimize_schedule
from core.services.scheduler.run.schedule_orchestrator import orchestrate_schedule_run
from core.services.scheduler.schedule_service import ScheduleService
from core.services.scheduler.summary.schedule_summary import build_result_summary
from core.services.workbench.preflight_facts import full_facts_fingerprint

from .piece_adoption import validate_piece_adoption
from .run_compute_graph import piece_graph_preparer
from .run_compute_validation import validate_candidate
from .run_input import CandidateRunInput, prepare_candidate_run_input
from .run_input_readonly import candidate_read_snapshot
from .run_input_rows import fail
from .zero_duration import PointEventError, candidate_point_validator


def compute_candidate_run(conn, normalized_input, execution_projections, *, version_override=None,
                          on_progress=None) -> CandidateRunComputation:
    """Compute actual candidate rows under one read snapshot; worker owns run lock.

    ``on_progress(done, total)`` is only a progress sink for the worker's status ledger; it never
    receives prepared input or results and cannot influence the computation.
    """
    with candidate_read_snapshot(conn):
        return _prepare_and_compute_in_snapshot(conn, normalized_input, execution_projections, version_override, on_progress)


def _prepare_and_compute_in_snapshot(conn, normalized_input, execution_projections, version_override, on_progress=None):
    # No prepared-input handoff or caller callback occurs here. Preparation's
    # complete fingerprint and computation share the enclosing read transaction.
    prepared = prepare_candidate_run_input(conn, normalized_input, execution_projections)
    version = _prepared_version(conn, prepared, version_override)
    return _compute_in_read_snapshot(conn, prepared, version, on_progress)


def _prepared_version(conn, schedule_input, version_override):
    if not isinstance(schedule_input, CandidateRunInput):
        raise TypeError("schedule_input must come from prepare_candidate_run_input")
    if schedule_input.cal_svc.conn is not conn:
        fail("candidate_connection_mismatch", "Prepared calendar and worker must use the same SQLite connection.")
    version = schedule_input.prev_version if version_override is None else version_override
    if type(version) is not int or version < 0:
        fail("invalid_version_context", "Version context must be an explicit non-negative integer.")
    if version == 0 and schedule_input.prev_version != 0:
        fail("version_context_unrepresentable", "The existing orchestrator cannot retain explicit zero beside a previous version.")
    return version


def _candidate_payloads(conn, schedule_input, comparison):
    payloads = {}
    for candidate in comparison.candidates:
        if candidate.status == "completed":
            payloads[candidate.candidate_key] = validate_candidate(
                schedule_input, candidate.results, list(candidate.summary.errors),
            )
            if any(op.piece_id is not None for op in schedule_input.operations):
                validate_piece_adoption(conn, prepared=schedule_input, payload=payloads[candidate.candidate_key])
    return payloads


def _computation_state(schedule_input, comparison, payloads):
    selected = comparison.selection.selected_plan
    selected_ids = payloads[selected.candidate_key].scheduled_op_ids
    is_partial = (selected_ids != schedule_input.schedule_output_allowed_op_ids
               or any(row["status"] == "skipped" for row in schedule_input.dispositions)
               or comparison.failed_count > 0 or comparison.skipped_count > 0)
    return "partial" if is_partial else "complete"


def compute_prepared_candidate_run(conn, schedule_input: CandidateRunInput, *, version_override=None) -> CandidateRunComputation:
    """Reject a stale prepared input; return internal artifacts, not a public RunResult.

    version_override is output context only. It never allocates a version.
    Caller must not mutate prepared artifacts or use a connection from another DB.
    """
    version = _prepared_version(conn, schedule_input, version_override)
    with candidate_read_snapshot(conn):
        if full_facts_fingerprint(conn) != schedule_input.facts_fingerprint:
            fail("candidate_input_stale", "排产资料在这中间变了，这次排产没有开始。请重新做一次排产检查。")
        return _compute_in_read_snapshot(conn, schedule_input, version)


def _compute_in_read_snapshot(conn, schedule_input, version, on_progress=None):
    """Private continuation after preparation or full freshness validation."""
    if not conn.in_transaction or conn.execute("PRAGMA query_only").fetchone()[0] != 1:
        fail("candidate_read_snapshot_lost", "Candidate computation requires its active read-only snapshot.")
    svc = ScheduleService(conn)
    compare = run_candidate_comparison
    if callable(on_progress):
        compare = partial(compare, on_progress=on_progress)
    if any(op.piece_id is not None for op in schedule_input.operations):
        compare = partial(compare, prepare_graph_fn=piece_graph_preparer(schedule_input))
    orchestration = orchestrate_schedule_run(
        svc, schedule_input=schedule_input, simulate=True, strict_mode=True,
        optimize_schedule_fn=partial(_optimize_representable_candidate, schedule_input),
        build_result_summary_fn=build_result_summary,
        allocate_version=False, version_override=version, persist_schedule_fn=None,
        point_validator=candidate_point_validator(schedule_input),
        candidate_comparison_fn=compare,
    )
    comparison = orchestration.candidate_comparison
    if comparison is None:
        fail("candidate_comparison_missing", "这次排产没有算出可比较的方案，排产没有完成。请刷新重试；仍不行请联系维护人员。")
    payloads = _candidate_payloads(conn, schedule_input, comparison)
    state = _computation_state(schedule_input, comparison, payloads)
    return CandidateRunComputation(schedule_input, orchestration, payloads,
                                   schedule_input.dispositions, state)


def _optimize_representable_candidate(schedule_input, **kwargs):
    outcome = optimize_schedule(**kwargs)
    validate_point = candidate_point_validator(schedule_input)
    try:
        for row in outcome.results:
            if row.start_time == row.end_time:
                validate_point(row)
    except PointEventError as exc:
        fail(exc.code, str(exc))
    return outcome
