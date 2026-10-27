"""Solver process evidence retains late work and separates adoption from improvement."""

from copy import deepcopy
from dataclasses import replace
from functools import partial
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError
from core.errors import ValidationError
from core.models.objective import target_objectives_for
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.run import schedule_optimizer_steps, schedule_shared_optimizer
from core.services.scheduler.run.optimizer.candidate_fingerprint import CandidateFingerprint
from core.services.scheduler.run.optimizer.graph.candidates import (
    PreparedDecisionFeatures,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy import _IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import (
    IteratedGreedyLimits,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
from core.services.scheduler.run.optimizer.graph.repair_decisions import prepare_repair_parent
from core.services.scheduler.run.optimizer.graph.reporting import append_graph_trace
from core.services.scheduler.run.optimizer.graph.stages import _candidate_should_replace_best
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph.v2_ranks import build_v2_common_rank_cache
from core.services.scheduler.run.optimizer.graph_ready_profiles import resolve_v2_profiles
from core.services.scheduler.run.optimizer.grasp_ig_candidates import _append_trace
from core.services.scheduler.run.optimizer.local_search_round import _record_improvement
from core.services.scheduler.run.optimizer.neighborhood_moves import NeighborhoodMove
from core.services.scheduler.run.optimizer.process_evidence import sample_elapsed_points
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.search_state import OptimizerSearchState
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession
from core.services.scheduler.run.optimizer.shared_process import build_shared_process
from core.services.scheduler.run.optimizer.step_report_hooks import _append_multi_start_trace, _append_ortools_trace
from core.services.scheduler.run.schedule_shared_search import GoalView, SharedSearch
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    BenchmarkClock,
    ContinuousCalendar,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests._support.shared_schedule_archive import _observe_decoded, _register_decode


def _candidate(primary, *, complete=True, objective="min_tardiness"):
    completion = BatchCompletion(
        expected_operation_count=3,
        missing_operation_count=0 if complete else 1,
        unexpected_result_count=0,
        complete_batch_count=2 if complete else 1,
        incomplete_batch_ids=() if complete else ("B1",),
        partial_batch_ids=() if complete else ("B1",),
        failure_detail_count=0 if complete else 1,
        failure_batch_ids=() if complete else ("B1",),
        explained=not complete,
    )
    metrics = ScheduleMetrics(
        overdue_count=int(primary > 0),
        total_tardiness_hours=float(primary),
        weighted_tardiness_hours=float(primary),
        makespan_hours=10.0,
        changeover_count=0,
        completion=completion,
    )
    failed = 0 if complete else 1
    candidate = {"results": [], "summary": ScheduleSummary(failed_ops=failed, success=complete, total_ops=3,
                                                      scheduled_ops=3 - failed, warnings=[], errors=[], duration_seconds=0.0),
            "score": (float(failed),) + objective_score(objective, metrics), "metrics": metrics,
            "strategy": SortStrategy.PRIORITY_FIRST, "params": {}, "algo_stats": {},
            "dispatch_mode": "sgs", "dispatch_rule": "cr", "order": ["B1", "B2"]}
    archive = SharedScheduleArchive(objective, target_objectives_for(objective), (1, 2, 3), ("B1", "B2"))
    return _register_decode(archive, candidate)


def test_warmstart_keeps_optional_solver_failure_but_propagates_real_candidate_observer(monkeypatch):
    values = default_snapshot_values()
    values.update(sort_strategy="fifo", dispatch_mode="batch_order", ortools_enabled="yes", auto_assign_enabled="no")
    cfg = snapshot_from_values(values)
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=cfg)
    clock = BenchmarkClock()
    started_at = clock()
    deadline = started_at + 10.0
    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, (op.id for op in operations), batches)
    budget = SharedSearchBudget(clock=clock, started_at=started_at, deadline=deadline,
                                target_objectives=targets, configured_seconds=10)
    shared = SharedSearch(archive=archive, clock=clock, started_at=started_at, budget=budget)
    seed_results, downtime_map = [], {}
    session = SharedDecodeSession(
        archive=archive, budget=budget, scheduler=scheduler, operations=operations, batches=batches,
        seed_results=seed_results, downtime_map=downtime_map, resource_pool=None,
        clock=clock, started_at=started_at, deadline=deadline, event_sink=shared.record_event,
    )
    shared.decode_session = session
    optimizer_stats = {}
    best = schedule_optimizer_steps._evaluate_ortools_candidate(
        start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=optimizer_stats,
        readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
        strategy=SortStrategy.FIFO, params={}, ort_order=list(batches),
    )
    shared.observe("min_overdue", candidate=best, origin="initial", verified=True, elapsed_ms=0)
    assert best["summary"].success and scheduler._decode_invocations == 1
    assert best["decode_receipt"]["execution_kind"] == "new_decision"
    assert best["runtime_ms"] == int(best["decode_receipt"]["original_decode_ms"])
    solver_failure = OrtoolsWarmstartError("optional order unavailable")
    observer_failure = RuntimeError("archive observer failed")
    solver_results = [solver_failure, list(reversed(batches))]
    solver_calls = []
    solver_finished_at = None

    def solve_order(**kwargs):
        solver_calls.append(kwargs)
        result = solver_results.pop(0)
        if isinstance(result, Exception):
            raise result
        if solver_finished_at is not None:
            clock.now = solver_finished_at
        return result

    monkeypatch.setattr(schedule_optimizer_steps, "_solve_ortools_order", solve_order)
    optional_report = OptimizationSearchReportState(
        objective_name="min_overdue", started_at=0.0,
    )
    optional_attempts = []
    assert schedule_optimizer_steps.run_ortools_warmstart(
        start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=optimizer_stats,
        readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
        algo_ops_to_schedule=operations, batches=batches,
        algo_mode="improve", cfg=cfg, strategy_enum=SortStrategy.FIFO,
        deadline=deadline, best=best, t_begin=started_at, clock=clock,
        attempts=optional_attempts, improvement_trace=[], search_report_state=optional_report,
    ) is best
    assert scheduler._decode_invocations == 1
    assert optional_attempts[0]["origin"]["message"] == str(solver_failure)

    observed = []

    def observe(candidate, **kwargs):
        assert candidate["summary"].success and candidate["summary"].failed_ops == 0
        assert {row.op_id for row in candidate["results"]} == {op.id for op in operations}
        observed.append(candidate)
        raise observer_failure

    report = OptimizationSearchReportState(
        objective_name="min_overdue", started_at=0.0,
        candidate_observer=observe, candidate_clock=lambda: 0.0,
    )
    attempts = []
    with pytest.raises(RuntimeError) as raised:
        schedule_optimizer_steps.run_ortools_warmstart(
            start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order",
            dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=optimizer_stats,
            readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
            algo_ops_to_schedule=operations, batches=batches,
            algo_mode="improve", cfg=cfg, strategy_enum=SortStrategy.FIFO,
            deadline=deadline, best=best, t_begin=started_at, clock=clock,
            attempts=attempts, improvement_trace=[], search_report_state=report,
        )
    assert raised.value is observer_failure
    assert scheduler._decode_invocations == 2 and len(observed) == 1
    assert attempts == []
    shared.observe("min_overdue", candidate=observed[0], origin="validated_warmstart", verified=True, elapsed_ms=0)

    # Shared ordering admission records one real action, before a decode request exists.
    shared_best = schedule_optimizer_steps._evaluate_ortools_candidate(
        start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=optimizer_stats,
        readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
        strategy=SortStrategy.FIFO, params={}, ort_order=list(batches),
    )
    assert shared_best["decode_receipt"]["execution_kind"] == "decision_reused"
    assert shared_best["runtime_ms"] == shared_best["decode_receipt"]["source_runtime_ms"] == best["runtime_ms"]
    assert session.actual_decoder_calls == scheduler._decode_invocations == 2
    original_best = (tuple(shared_best["results"]), shared_best["summary"], tuple(shared_best["score"]))
    shared_report = OptimizationSearchReportState(
        objective_name="min_overdue", started_at=started_at, candidate_clock=clock,
    )
    view = GoalView("min_overdue", OptimizerSearchState(), shared_report)
    shared.views[view.objective] = view
    for remaining, reason, solver_finishes in ((1.03, "estimated_decode_cost", False),
                                               (0.5, "time_budget", False), (5.0, "time_budget", True)):
        shared_attempts = []
        before_budget = budget.summary()
        before_session = session.stats()
        before_events, before_solver, before_scheduler = len(shared.events), len(solver_calls), scheduler._decode_invocations
        if solver_finishes:
            solver_results.append(list(batches))
            solver_finished_at = deadline
        clock.now = deadline - remaining

        def run_shared_warmstart() -> None:
            schedule_optimizer_steps.run_ortools_warmstart(
                start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order",
                dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=optimizer_stats,
                readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
                algo_ops_to_schedule=operations, batches=batches,
                algo_mode="improve", cfg=cfg, strategy_enum=SortStrategy.FIFO,
                deadline=deadline, best=shared_best, t_begin=started_at, clock=clock,
                attempts=shared_attempts, improvement_trace=[], search_report_state=shared_report,
            )

        stage = schedule_shared_optimizer._WarmStartStage(run=run_shared_warmstart, clock=clock, deadline=deadline)
        shared.run_action(view, stage)
        assert len(solver_calls) == before_solver + int(solver_finishes)
        assert scheduler._decode_invocations == before_scheduler
        assert (tuple(shared_best["results"]), shared_best["summary"], tuple(shared_best["score"])) == original_best
        assert session.stats() == before_session and len(shared.events) == before_events
        assert len(shared_attempts) == 1 and shared_attempts[0]["reason"] == reason
        assert shared_attempts[0]["request_id"] is None and shared_attempts[0]["decode_receipt"] is None
        action = shared.actions[-1]
        assert action["skip_reason"] == reason and action["new_decisions"] == action["reused_decisions"] == 0
        assert action["evaluation_count"] == action["verified_evaluation_count"] == 0
        after_budget = budget.summary()
        assert after_budget["admission_skips"] == dict(
            before_budget["admission_skips"], **{reason: before_budget["admission_skips"].get(reason, 0) + 1})
        assert after_budget["actual_decoder_count"] == before_budget["actual_decoder_count"]


def test_all_trace_producers_preserve_improvement_after_two_hundred_points():
    candidate = _candidate(0.0)
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced")
    move = NeighborhoodMove(neighborhood_name="tardy_window", batch_order=("B1", "B2"))
    report = OptimizationSearchReportState(objective_name="min_tardiness", started_at=0.0)
    def clock():
        return 5.0
    writers = (
        lambda trace: _append_ortools_trace(improvement_trace=trace, candidate=candidate, now=clock, t_begin=0.0),
        lambda trace: _append_multi_start_trace(improvement_trace=trace, candidate=candidate, strategy_key="priority_first",
                                               now=clock, t_begin=0.0),
        lambda trace: append_graph_trace(improvement_trace=trace, candidate=candidate, profile=profile, clock=clock,
                                        t_begin=0.0),
        lambda trace: _record_improvement(candidate=candidate, move=move, attempts=[], improvement_trace=trace,
                                          clock=clock, t_begin=0.0, reference=candidate,
                                          search_report_state=report),
        lambda trace: _append_trace(improvement_trace=trace, candidate=candidate, origin="grasp", index=210,
                                    now=clock, t_begin=0.0),
    )
    for write in writers:
        trace = [{"elapsed_ms": index, "score": [0.0, 100.0]} for index in range(201)]
        write(trace)
        assert len(trace) == 202
        assert trace[-1]["elapsed_ms"] == 5000
        assert trace[-1]["score"] == list(candidate["score"])
        assert trace[-1]["metrics"]["total_tardiness_hours"] == 0.0


class _Clock:
    def __init__(self):
        self.value, self.reads = 0.0, 0

    def __call__(self):
        self.reads += 1
        return self.value


def _identity(name):
    return CandidateFingerprint(
        output_key=(name,),
        same_as_parent=False,
        same_as_seen=False,
        fingerprint_changed=True,
    )


def test_candidate_contents_define_duplicates_and_diagnostic_sequences_preserve_legacy_reports():
    report = OptimizationSearchReportState(objective_name="min_tardiness", started_at=0.0)
    baseline = _candidate(20.0)
    first = report.mark_candidate_evaluated(baseline, origin="baseline")
    report.mark_candidate_accepted(baseline, origin="baseline", fingerprint=first)
    duplicate = _candidate(20.0)
    duplicate.update(strategy=SortStrategy.DUE_DATE_FIRST, order=["B2", "B1"], params={"different": True})
    repeated = report.mark_candidate_evaluated(duplicate, origin="multi_start")
    assert repeated.same_as_seen and repeated.same_as_parent and not repeated.fingerprint_changed
    assert len(report.candidate_fingerprints) == 1
    # The saved content remains immutable when the mutable source metrics change.
    baseline["metrics"].total_tardiness_hours = 999.0
    changed = report.mark_candidate_evaluated(_candidate(8.0), origin="local_search")
    assert changed.output_key != first.output_key and not changed.same_as_seen
    report.mark_candidate_accepted(_candidate(8.0), origin="local_search", fingerprint=changed)
    assert report.best_fingerprint_changed()
    assert report.initial_fingerprint == first.output_key
    assert report.best_fingerprint == changed.output_key
    legacy = {"schema_version": 1, "best_fingerprint_changed": True, "initial_fingerprint": "saved-before-P8",
              "fingerprint_events": [{"output_fingerprint": "saved-before-P8"}]}
    old_public, old_diagnostics = project_search_report(legacy)
    assert old_public["best_fingerprint_changed"] is True
    assert old_diagnostics["initial_fingerprint"] == "saved-before-P8"
    assert old_diagnostics["fingerprint_events"] == legacy["fingerprint_events"]
    invalid = _candidate(1.0)
    invalid["score"] = (False, 1.0)
    with pytest.raises(ValidationError):
        report.mark_candidate_evaluated(invalid, origin="local_search")


def test_equal_elapsed_buckets_retain_late_best_and_all_three_milestones():
    # Explicit progress events exercise the production sampler, independently of a writer.
    raw_points, raw_times = [], []
    for index in range(321):
        candidate = _candidate(400 - index, complete=index >= 210)
        flags = ["first_valid"] if index == 0 else ["first_expected_complete"] if index == 210 else ["strict_improvement"]
        raw_points.append({
            "event_index": index + 1, "elapsed_ms": (index + 1) * 1000,
            "score": list(candidate["score"]), "primary_value": float(400 - index), "flags": flags,
            "completion": {"missing_operation_count": 0 if index >= 210 else 1}, "segment": int(index >= 210),
        })
        raw_times.append((index + 1, (index + 1) * 1000))
    raw_points.append({**deepcopy(raw_points[-1]), "event_index": 322, "elapsed_ms": 400000, "flags": ["final"]})
    original = deepcopy(raw_points)
    points, sampling = sample_elapsed_points(raw_points, elapsed_ms=400000)
    assert sampling["event_total_count"] == 322
    assert sampling["retained_point_count"] == len(points) <= 200
    assert sampling["policy"] == "elapsed_equal_width_bucket_end_best_v1"
    milestones = {flag: point for point in points for flag in point["flags"]
                  if flag in ("first_valid", "first_expected_complete", "final")}
    assert milestones["first_valid"]["event_index"] == 1
    assert milestones["first_valid"]["completion"]["missing_operation_count"] == 1
    assert milestones["first_expected_complete"]["event_index"] == 211
    assert milestones["first_expected_complete"]["completion"]["missing_operation_count"] == 0
    assert milestones["first_valid"]["segment"] != milestones["first_expected_complete"]["segment"]
    assert milestones["final"]["event_index"] == 322
    assert milestones["final"]["elapsed_ms"] == 400000
    assert milestones["final"]["score"] == list(candidate["score"])
    assert milestones["final"]["primary_value"] == 80.0
    assert any(point["event_index"] == 321 and point["primary_value"] == 80.0 for point in points)

    # Independent bucket oracle: each slot retains the last actual incumbent event.
    slots = 197
    bucket_ends = {}
    for event_index, elapsed in raw_times + [(322, 400000)]:
        bucket_ends[min(elapsed * slots // 400000, slots - 1)] = event_index
    assert {point["event_index"] for point in points} == {1, 211, 322} | set(bucket_ends.values())
    assert [point["elapsed_ms"] for point in points] == sorted(point["elapsed_ms"] for point in points)
    assert raw_points == original

    immediate = [{"elapsed_ms": 0, "flags": ["first_valid", "first_expected_complete", "final"]}]
    merged, zero_sampling = sample_elapsed_points(immediate, elapsed_ms=0)
    assert len(merged) == 1
    assert merged[0]["elapsed_ms"] == 0
    assert {"first_valid", "first_expected_complete", "final"} <= set(merged[0]["flags"])
    assert zero_sampling["bucket_width_ms"] == 0.0


def test_adoption_is_separate_from_strict_improvement_and_revisited_stages_do_not_connect():
    # Use the actual GraphReady decision recorder: accepting a tie keeps a zero change,
    # and an incumbent snapshot stays intact after its original metrics change.
    recorded_clock = _Clock()
    reporter = OptimizationSearchReportState(
        objective_name="min_tardiness", started_at=0.0, candidate_clock=recorded_clock)
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced")
    attempts = []
    incumbent = _candidate(20.0)
    incumbent["runtime_ms"] = 20
    recorded_clock.value = 0.125
    identity = _identity("first")
    assert _candidate_should_replace_best(incumbent, profile=profile, best=None, attempts=attempts,
        search_report_state=reporter, fingerprint=identity, clock=recorded_clock, t_begin=0.0)
    reporter.mark_candidate_accepted(incumbent, origin=profile.candidate_origin, fingerprint=identity)
    assert attempts[0]["elapsed_ms"] == 125 and attempts[0]["event_index"] is None
    assert attempts[0]["accepted"] is True and attempts[0]["strict_improved"] is None
    assert attempts[0]["comparison"]["state"] == "no_reference"
    assert attempts[0]["comparison"]["metric_deltas"] is None
    tied = _candidate(20.0)
    tied["runtime_ms"] = 10
    recorded_clock.value = 0.25
    assert _candidate_should_replace_best(tied, profile=profile, best=incumbent, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("tie"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["accepted"] is True and attempts[-1]["strict_improved"] is False
    assert attempts[-1]["elapsed_ms"] == 250 and attempts[-1]["event_index"] is None
    assert attempts[-1]["comparison"]["reference_score"] == list(incumbent["score"])
    assert attempts[-1]["comparison"]["metric_deltas"]["total_tardiness_hours"] == 0.0
    assert recorded_clock.reads == 2  # Each actual attempt reads its explicit clock once.
    incumbent["metrics"].total_tardiness_hours = 999.0
    assert attempts[-1]["comparison"]["reference_metrics"]["total_tardiness_hours"] == 20.0
    partial_reference, partial_candidate = _candidate(20.0, complete=False), _candidate(10.0, complete=False)
    partial_candidate["metrics"].completion = replace(partial_candidate["metrics"].completion,
        incomplete_batch_ids=("B2",), partial_batch_ids=("B2",), failure_batch_ids=("B2",))
    recorded_clock.value = 0.5
    assert _candidate_should_replace_best(partial_candidate, profile=profile, best=partial_reference, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("partial"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["elapsed_ms"] == 500 and attempts[-1]["event_index"] is None
    assert attempts[-1]["comparison"]["state"] == "different_coverage"
    assert attempts[-1]["strict_improved"] is None and attempts[-1]["comparison"]["metric_deltas"] is None


def test_unknown_and_unverified_results_do_not_claim_valid_or_complete_milestones():
    from tests._support.shared_schedule_archive import _archive, _result
    from tests._support.shared_schedule_archive import _candidate as archive_candidate

    clock = _Clock()
    archive = _archive()
    budget = SharedSearchBudget(clock=clock, started_at=0.0, deadline=2.0,
                                target_objectives=archive.target_objectives, configured_seconds=2)
    search = SharedSearch(archive=archive, clock=clock, started_at=0.0, budget=budget)
    search.phase = "graph_ig"
    unknown = archive_candidate([_result(1, 0), _result(2, 2)])
    clock.value = 0.1
    _observe_decoded(search, "min_tardiness", candidate=unknown, origin="graph_ig", verified=True, elapsed_ms=100)
    trial = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    clock.value = 0.2
    _observe_decoded(search, "min_tardiness", candidate=trial, origin="graph_ig", verified=False, elapsed_ms=200)
    assert trial["archive_ref"].entry_id not in archive
    before_verified = build_shared_process(search, runtime_ms=200, stop_reason="completed", decode_stats={},
                                           budget_stats=budget.summary(finished_at=0.2))
    pending_points = before_verified["targets"]["min_tardiness"]["points"]
    assert all(not {"first_valid", "first_expected_complete"} & set(point["flags"]) for point in pending_points)
    assert all(not scope["components_known"] and not scope["is_complete"]
               for scope in before_verified["scopes"].values())
    verified = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    clock.value = 0.3
    _observe_decoded(search, "min_tardiness", candidate=verified, origin="graph_ig", verified=True, elapsed_ms=300)
    evidence = build_shared_process(search, runtime_ms=400, stop_reason="completed", decode_stats={},
                                     budget_stats=budget.summary(finished_at=0.4))
    assert len(evidence["events"]) == 3 and sum(event["verified"] is False for event in evidence["events"]) == 1
    points = evidence["targets"]["min_tardiness"]["points"]
    first = points[0]
    first_scope = evidence["scopes"][first["scope_ref"]]
    assert first_scope["objective_scope"] == "unknown" and first["score"][1] is None
    assert first_scope["components_known"] is False and first_scope["is_complete"] is False
    assert first["score"] == [1.0, None, None, None, None, None]
    assert "first_valid" not in first["flags"] and "first_expected_complete" not in first["flags"]
    assert evidence["events"][1]["entry_id"] == trial["archive_ref"].entry_id
    assert evidence["events"][1]["verified"] is False
    assert all(point.get("source_event_id") != 2 for point in points)
    milestones = [point for point in points if "first_valid" in point["flags"]]
    assert len(milestones) == 1 and milestones[0]["source_event_id"] == 3
    milestone_event = evidence["events"][milestones[0]["source_event_id"] - 1]
    assert milestone_event["verified"] is True and "first_expected_complete" in milestones[0]["flags"]
    complete_scope = evidence["scopes"][milestones[0]["scope_ref"]]
    assert complete_scope["components_known"] is True and complete_scope["is_complete"] is True
    assert complete_scope["scheduled_operation_ids"] == [1, 2, 3]
    assert complete_scope["complete_batch_ids"] == ["B1", "B2", "B3"]
    assert points[-1]["flags"] == ["final"]

    # Reference re-capture and a subsequent full decode use the actual IG return points.
    identity_by_id = {}
    def fingerprint(candidate, parent=None):
        identity = identity_by_id[id(candidate)]
        return identity.with_context(parent_fingerprint=parent, seen_output_fingerprints=())
    pool = SimpleNamespace(fingerprint=fingerprint, seen_outputs=set())
    recorder = OptimizationSearchReportState(
        objective_name="min_tardiness", started_at=0.0, candidate_clock=clock)
    limits = IteratedGreedyLimits()
    report = new_iterated_greedy_report(limits, objective_name="min_tardiness")
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced")
    cfg_values = default_snapshot_values()
    cfg_values.update(auto_assign_enabled="no")
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=snapshot_from_values(cfg_values))
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    fixture_archive = SharedScheduleArchive("min_tardiness", target_objectives_for("min_tardiness"),
                                            (op.id for op in operations), batches)
    fixture_budget = SharedSearchBudget(clock=clock, started_at=0.0, deadline=2.0,
                                        target_objectives=fixture_archive.target_objectives, configured_seconds=2)
    session = SharedDecodeSession(archive=fixture_archive, budget=fixture_budget, scheduler=scheduler,
        operations=operations, batches=batches, seed_results=[], downtime_map={}, resource_pool=None,
        graph_ready_context=context, clock=clock, started_at=0.0, deadline=2.0)
    baseline = schedule_optimizer_steps._evaluate_ortools_candidate(
        strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START_DT, end_date=None,
        ort_order=list(batches), dispatch_mode_cfg="sgs", dispatch_rule_cfg="slack", resource_pool=None,
        objective_name="min_tardiness", optimizer_algo_stats={}, readiness_gate_enabled=False,
        graph_ready_context=None, decode_session=session)
    parent = _parent_from_candidate(baseline, graph_context=context,
                                    prepared=prepare_repair_parent(
                                        baseline, operations, context,
                                        resource_pairs_for=session.native_preparation.qualified_resource_pairs))
    assert parent is not None
    graph_metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                                  batches=batches, start_dt=START_DT, graph_ready_context=context,
                                                  calendar_service=scheduler.calendar, downtime_map={}, seed_results=[])
    decision_features = PreparedDecisionFeatures(graph_metrics, build_v2_common_rank_cache(graph_metrics))
    evaluate = partial(evaluate_graph_ready_candidate,
        prepared_decision_features=decision_features,
        strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START_DT, end_date=None, dispatch_rule="slack",
        resource_pool=None, objective_name="min_tardiness", optimizer_algo_stats=None,
        readiness_gate_enabled=False, version=0, clock=clock)
    search = _IteratedGreedySearch(limits=limits, parent=parent, profile=profile, pool=pool, evaluate=evaluate,
        metrics_by_op_id=context["node_metrics_by_op_id"], start_dt=START_DT, seed=0, deadline=2.0, clock=clock,
        t_begin=0.0, attempts=[], improvement_trace=[], report_state=recorder, report=report,
        decode_session=session, operations=operations, graph_context=context)
    tracker = search.incumbent
    original, capture, improved = _candidate(20.0), _candidate(20.0), _candidate(8.0)
    identity_by_id.update({id(original): _identity("original"), id(capture): _identity("original"),
                          id(improved): _identity("improved")})
    tracker.adopt_best(original)
    clock.value = 0.5
    search._consider_for_incumbent(capture, capture_of=original)
    assert report["reference_captures"] == 1 and tracker.best is original
    row = search.attempts[-1]
    assert row["comparison"]["kind"] == "reference_capture" and row["accepted"] is False
    assert row["strict_improved"] is False and row["comparison"]["metric_deltas"]["total_tardiness_hours"] == 0.0
    clock.value = 0.75
    search._consider_for_incumbent(improved, capture_of=None)
    row = search.attempts[-1]
    assert tracker.best is improved and search.improved_incumbent is True
    assert row["elapsed_ms"] == 750 and row["accepted"] is True and row["strict_improved"] is True
    assert row["comparison"]["kind"] == "incumbent"
    assert row["comparison"]["reference_score"] == list(original["score"])
    assert row["comparison"]["metric_deltas"]["total_tardiness_hours"] == -12.0


def test_report_uses_archive_identity_and_evaluation_without_scanning_schedule_rows():
    from tests._support.shared_schedule_archive import _archive, _result
    from tests._support.shared_schedule_archive import _candidate as archive_candidate

    class RegisteredRows(list):
        def __iter__(self):
            raise AssertionError("the report must consume the archive identity, not walk the schedule")

    archive = _archive()
    candidate = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    _register_decode(archive, candidate)
    candidate["results"] = RegisteredRows(candidate["results"])
    report = OptimizationSearchReportState(objective_name="min_tardiness", started_at=0.0)
    initial = report.mark_candidate_evaluated(candidate, origin="baseline")
    report.mark_candidate_accepted(candidate, origin="baseline", fingerprint=initial)
    duplicate = dict(candidate, order=["B3", "B2", "B1"], params={"other_decision": True})
    repeated = report.mark_candidate_evaluated(duplicate, origin="multi_start")
    assert repeated.same_as_seen and repeated.same_as_parent
    assert len(report.candidate_fingerprints) == 1
    # Arrangement identity stays fixed while real completion and objective values remain comparison inputs.
    different_evaluation = dict(candidate, metrics=replace(candidate["metrics"], total_tardiness_hours=5.0))
    changed = report.mark_candidate_evaluated(different_evaluation, origin="validated_evidence")
    assert changed.output_key != initial.output_key
    other_objective = OptimizationSearchReportState(objective_name="min_changeover", started_at=0.0)
    alternative = other_objective.mark_candidate_evaluated(candidate, origin="shared_reference")
    assert alternative.output_key != initial.output_key
    trial_rows = archive_candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
    _register_decode(archive, trial_rows, verified=False)
    previous = set(report.candidate_fingerprints)
    report.mark_candidate_evaluated(trial_rows, origin="checkpoint_trial", remember_fingerprint=False)
    assert report.candidate_fingerprints == previous
    assert trial_rows["archive_ref"].entry_id not in archive
