"""Shared archive input builders for scheduling and saved-process tests."""

from datetime import datetime, timedelta

from core.algorithm_contracts.resource_occupancy import project_internal_occupancies
from core.algorithm_contracts.resource_pool import DISABLED_RESOURCE_POOL
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import objective_score
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.enums import SortStrategy
from core.models.objective import target_objectives_for
from core.services.scheduler.run.optimizer.multi_start import _evaluate_multi_start_candidate
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.shared_archive import CandidateArchiveRef, SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_decode import decode_and_metrics
from core.services.scheduler.run.schedule_shared_search import open_shared_search
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.optimizer_graph_ready_benchmark import ContinuousCalendar
from tests._support.schedule_decode import NO_END_DATE, config_snapshot, prepared_metrics, required_hours_by_op_id

START = datetime(2026, 10, 13, 20)
OPERATIONS = tuple(make_algo_op(id=index, batch_id=f"B{index}") for index in (1, 2, 3))
BATCHES = {
    f"B{index}": make_batch(batch_id=f"B{index}", due_date="2026-10-13", priority=priority)
    for index, priority in ((1, "critical"), (2, "normal"), (3, "urgent"))
}
# A trial decode resumes from a checkpoint; the arranged decoder below has none to read.
RESUMED_TRIAL = object()


def _result(op_id, start_hour, *, machine="M1", seed_source=None):
    start = START + timedelta(hours=start_hour)
    type_id = "T2" if op_id == 2 else "T1"
    return ScheduleResult(
        op_id=op_id, op_code=f"OP{op_id}", batch_id=f"B{op_id}", seq=1,
        machine_id=machine, operator_id=f"O{op_id}", start_time=start,
        end_time=start + timedelta(hours=1), source="internal", op_type_name=type_id,
        op_type_id=type_id, seed_source=seed_source, state_revision="r1",
    )


def _candidate(results, *, objective="min_tardiness", failures=(), fixed_seed=()):
    rows = list(results)
    seeds = tuple(fixed_seed)
    fixed_ids = {row.op_id for row in seeds}
    metrics = prepared_metrics(
        rows, BATCHES, expected_operations=[op for op in OPERATIONS if op.id not in fixed_ids],
        seed_results=seeds,
        seed_occupancies_by_op_id={row.op_id: project_internal_occupancies(row) for row in seeds},
        failure_details=failures,
    )
    missing = 3 - len({row.op_id for row in rows} & {1, 2, 3})
    summary = ScheduleSummary(
        success=missing == 0, total_ops=3, scheduled_ops=len(rows), failed_ops=missing,
        warnings=["original warning"], errors=[], duration_seconds=0.0,
        failure_details=list(failures),
    )
    return {
        "results": rows, "summary": summary, "metrics": metrics,
        "score": (float(missing),) + objective_score(objective, metrics),
        "objective": objective, "order": ["B1", "B2", "B3"],
        "params": None, "graph_ready_profile": None, "repair_decision": None, "algo_stats": {"visited": [1]},
        "dispatch_mode": "sgs", "dispatch_rule": "cr", "strategy": SortStrategy.PRIORITY_FIRST,
    }


def _archive(primary="min_tardiness", *, limit=64):
    return SharedScheduleArchive(
        primary, target_objectives_for(primary), {1, 2, 3}, set(BATCHES), retention_limit=limit,
    )


def _register_decode(archive, candidate, *, verified=True, elapsed_ms=0):
    observed = archive.register_decode(candidate, verified=verified, elapsed_ms=elapsed_ms)
    candidate["archive_ref"] = CandidateArchiveRef(observed.entry_id, observed)
    return candidate


def _failure(op_id):
    return {"code": "schedule_window_exceeded", "op_id": op_id, "batch_id": f"B{op_id}"}


class ArrangementScheduler(GreedyScheduler):
    """Stands in for the native decoder alone: decoding batch order ``order`` returns the rows a test arranged
    for that order. The shared search, decode session, receipts, events, metrics and archive around it are the
    production ones (``open_shared_search``)."""

    def __init__(self):
        super().__init__(calendar_service=ContinuousCalendar(), config_service=config_snapshot())
        self.arranged = {}

    def schedule_prepared(self, prepared_inputs, *, batch_order, **_changes):
        rows, failures = self.arranged[tuple(sorted(batch_order, key=batch_order.__getitem__))]
        missing = len(prepared_inputs.operations) - len({row.op_id for row in rows})
        return rows, ScheduleSummary(
            success=missing == 0, total_ops=len(prepared_inputs.operations), scheduled_ops=len(rows),
            failed_ops=missing, warnings=[], errors=[], duration_seconds=0.0, failure_details=list(failures))


def arrangement_search(primary="min_tardiness", *, batches=BATCHES, clock=lambda: 0.0, deadline=1.0):
    """The shared search over OPERATIONS and ``batches``, decoding arranged rows (``observe_arrangement``)."""
    return open_shared_search(
        objective_name=primary, scheduler=ArrangementScheduler(), operations=list(OPERATIONS), batches=batches,
        required_hours_by_op_id=required_hours_by_op_id(OPERATIONS, batches), seed_results=[], downtime_map={},
        resource_pool=DISABLED_RESOURCE_POOL, graph_ready_context=None, start_dt=START, end_date=NO_END_DATE,
        readiness_gate_enabled=False, clock=clock, started_at=0.0, deadline=deadline, configured_seconds=deadline)


def observe_arrangement(search, objective, rows, *, order, origin, elapsed_ms, failures=(), trial=False):
    """Decode ``rows`` as batch order ``order`` in the search's decode session and report the candidate.

    A construction decode builds its candidate as multi-start does; a trial resumes and stays unverified.
    Decoding an order again is the session's reuse of that decision.
    """
    session = search.decode_session
    session.scheduler.arranged.setdefault(tuple(order), (list(rows), list(failures)))
    if trial:
        decoded = decode_and_metrics(
            decode_session=session, objective_name=objective, strategy=SortStrategy.PRIORITY_FIRST,
            strategy_params=None, batch_order_override=list(order),
            dispatch_mode="batch_order", dispatch_rule="slack", graph_enabled=False, graph_score_enabled=False,
            graph_priority_key_by_op_id=None, resource_pair_rank={}, decode_resume=RESUMED_TRIAL)
        candidate = {"results": decoded.results, "summary": decoded.summary, "metrics": decoded.metrics,
                     "strategy": decoded.used_strategy, "dispatch_mode": "batch_order", "dispatch_rule": "slack",
                     "repair_decision": None, "archive_ref": decoded.archive_ref(), "decode_receipt": decoded.receipt}
    else:
        candidate = _evaluate_multi_start_candidate(
            strategy=SortStrategy.PRIORITY_FIRST, params=None, order=list(order), dispatch_mode="batch_order",
            dispatch_rule="slack", objective_name=objective, graph_ready_context=None, decode_session=session)
    search.observe(objective, candidate=candidate, origin=origin, verified=not trial, elapsed_ms=elapsed_ms)
    return candidate


def observation_events(search):
    """The search's archive observations, apart from the decode events its session reports."""
    return [event for event in search.events if event["event_type"] == "archive_observation"]


def detached_report(objective, *, clock=lambda: 0.0, candidate_observer=lambda **_: None):
    """A target report outside any shared search, for tests of the report alone: its evaluations go to
    ``candidate_observer``; acceptances and reference captures go nowhere."""
    return OptimizationSearchReportState(
        objective_name=objective, started_at=0.0, candidate_clock=clock, candidate_observer=candidate_observer,
        candidate_acceptance_observer=lambda **_: None, reference_capture_observer=lambda **_: None)
