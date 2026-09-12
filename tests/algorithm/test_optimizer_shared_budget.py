"""Budget tests advance the clock at real work boundaries, not at clock reads."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_search_budget import (
    CandidateBudgetFeedback,
    SearchBudget,
    SearchBudgetExhausted,
)
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_optimizer import _default_runtime, optimize_schedule
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    ContinuousCalendar,
    _default_config,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests.candidate.test_scheduler_candidate_runner_contract import _outcome, _schedule_input


def _no_graph(_schedule_input):
    return SimpleNamespace(
        graph_analysis_public=None, graph_analysis_diagnostics=None,
        graph_ready_context=None, graph_dispatch_mode_override=None,
    )


def test_outer_slices_share_clock_reclaim_unused_time_and_keep_every_plan():
    now = [0.0]
    clock = lambda: now[0]
    budgets = []

    def optimize(**kwargs):
        budgets.append(kwargs["search_budget"])
        now[0] += 0.5
        return _outcome("candidate", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_no_graph, optimize_schedule_fn=optimize,
        clock=clock, weight_count=3, run_time_budget_seconds=12.0, selection_policy="score_only",
    )
    assert outcome.planned_count == outcome.completed_count == 4
    assert outcome.skipped_count == 0
    assert not outcome.time_budget_reached
    assert all(budget.clock is clock and budget.outer_deadline == 12.0 for budget in budgets)
    assert [budget.assigned_seconds for budget in budgets] == pytest.approx([3.0, 11.5 / 3, 5.5, 10.5])
    assert [budget.started_at for budget in budgets] == [0.0, 0.5, 1.0, 1.5]


def test_graph_preparation_can_use_up_a_slice_without_fake_completed_plan():
    now = [0.0]
    calls = []

    def prepare(schedule_input):
        if schedule_input.cfg.graph_analysis_mode == "off":
            now[0] = 3.0
        return _no_graph(schedule_input)

    def optimize(**kwargs):
        calls.append(kwargs["cfg"].graph_analysis_mode)
        return _outcome("candidate", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=prepare, optimize_schedule_fn=optimize,
        clock=lambda: now[0], weight_count=3, run_time_budget_seconds=12.0, selection_policy="score_only",
    )
    assert calls == ["on", "on", "on"]
    assert outcome.candidates[0].status == "skipped"
    assert outcome.candidates[0].failure_reason == "candidate_time_budget_reached"
    assert outcome.completed_count == 3 and outcome.skipped_count == 1
    assert outcome.baseline_missing_or_failed
    assert not outcome.time_budget_reached


def test_outer_boundary_starts_no_more_plans_and_records_last_decode_overrun():
    now = [0.0]
    calls = []

    def optimize(**kwargs):
        calls.append(kwargs["search_budget"])
        now[0] = 4.0
        return _outcome("baseline", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_no_graph, optimize_schedule_fn=optimize,
        clock=lambda: now[0], weight_count=3, run_time_budget_seconds=4.0, selection_policy="score_only",
    )
    assert len(calls) == outcome.completed_count == 1
    assert outcome.skipped_count == 3 and outcome.time_budget_reached
    assert outcome.candidates[0].status == "completed"


def test_last_plan_finishing_at_total_deadline_reports_budget_reached():
    now = [0.0]

    def optimize(**kwargs):
        now[0] += 1.0
        return _outcome("candidate", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_no_graph, optimize_schedule_fn=optimize,
        clock=lambda: now[0], weight_count=3, run_time_budget_seconds=4.0, selection_policy="score_only",
    )
    assert outcome.completed_count == 4 and outcome.skipped_count == 0
    assert outcome.time_budget_reached


def test_nan_total_budget_is_not_treated_as_an_unlimited_run():
    with pytest.raises(ValidationError) as exc:
        run_candidate_comparison(schedule_input=_schedule_input(), run_time_budget_seconds=float("nan"))
    assert exc.value.field == "run_time_budget_seconds"


def _real_optimizer(*, decode_seconds, assigned_seconds=4.0):
    now = [0.0]
    calls = []

    class TrackedScheduler(GreedyScheduler):
        def schedule(self, **kwargs):
            profile = (kwargs.get("strategy_params") or {}).get("graph_ready_profile") or {}
            calls.append((now[0], profile.get("candidate_origin", "multi_start")))
            result = super().schedule(**kwargs)
            now[0] += decode_seconds
            return result

    cfg = _default_config()
    cfg.algo_mode, cfg.time_budget_seconds = "improve", 5
    budget = SearchBudget(
        clock=lambda: now[0], started_at=0.0, deadline=assigned_seconds,
        outer_deadline=20.0, assigned_seconds=assigned_seconds,
    )
    # An unrelated runtime clock must not restart or extend the outer allocation.
    runtime = replace(_default_runtime(), scheduler_factory=TrackedScheduler, clock=lambda: 999.0)
    result = optimize_schedule(
        calendar_service=ContinuousCalendar(), cfg_svc=SimpleNamespace(), cfg=cfg,
        algo_ops_to_schedule=graph_ready_benchmark_operations(), batches=graph_ready_benchmark_batches(),
        start_dt=START_DT, end_date=None, downtime_map={}, seed_results=[], resource_pool=None,
        version=0, strict_mode=True, graph_ready_context=graph_ready_benchmark_context(),
        search_budget=budget, _runtime=runtime,
    )
    return result, calls, now[0]


def test_real_sgs_baseline_and_graph_repair_share_the_assigned_budget():
    result, calls, finished = _real_optimizer(decode_seconds=0.25)
    assert calls[0][1] == "multi_start"
    assert sum(origin == "multi_start" for _time, origin in calls) < 12
    assert any(origin == "graph_ready_v2_generated" for _time, origin in calls)
    assert any(origin == "graph_ready_v2_repaired" for _time, origin in calls)
    assert all(started < 4.0 for started, _origin in calls)
    assert finished <= 4.25
    assert result.summary.failed_ops == 0
    assert result.search_report["decoder_invocations"] == len(calls)
    profile = result.search_report["candidate_profile"]
    assert profile["assigned_time_budget_ms"] == 4000
    assert profile["optimizer_budget"]["optimizer_time_budget_ms"] == 4000
    assert {"phase": "multi_start", "reason": "reserved_for_later_phases"} in result.search_report["skipped_phases"]


def test_single_real_decode_may_finish_late_but_no_second_decode_starts():
    result, calls, finished = _real_optimizer(decode_seconds=4.5)
    assert calls == [(0.0, "multi_start")]
    assert finished == 4.5
    assert result.summary.failed_ops == 0
    assert result.search_report["stop_reason"] == "time_budget"
    assert result.search_report["decoder_invocations"] == 1
    assert result.search_report["candidate_profile"]["optimizer_budget"]["deadline_overrun_ms"] == 500


def test_no_real_decoder_starts_when_its_slice_is_already_exhausted():
    with pytest.raises(SearchBudgetExhausted, match="candidate_time_budget_reached"):
        _real_optimizer(decode_seconds=0.0, assigned_seconds=0.0)


def test_fallback_baseline_reports_its_actual_native_decoder_count():
    runtime = replace(
        _default_runtime(), clock=lambda: 0.0,
        run_multi_start=lambda **kwargs: None, run_ortools_warmstart=lambda **kwargs: None,
        run_local_search=lambda **kwargs: None, run_graph_ready_candidates=None, run_grasp_ig_candidates=None,
    )
    result = optimize_schedule(
        calendar_service=ContinuousCalendar(), cfg_svc=SimpleNamespace(), cfg=_default_config(),
        algo_ops_to_schedule=graph_ready_benchmark_operations(), batches=graph_ready_benchmark_batches(),
        start_dt=START_DT, end_date=None, downtime_map={}, seed_results=[], resource_pool=None,
        version=0, strict_mode=True, _runtime=runtime,
    )
    assert result.summary.failed_ops == 0
    assert result.search_report["decoder_invocations"] == 1


def test_phase_reservation_does_not_claim_entire_budget_exhausted():
    from core.services.scheduler.run.optimizer_search_budget import ReservedPhaseReport
    from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState

    state = OptimizationSearchReportState("test", 0, 5, "min_overdue", 0.0)
    report = ReservedPhaseReport(state, clock=lambda: 1.0, deadline=5.0, phase="heuristic_candidate_search")
    report.mark_deadline_reached()
    report.mark_phase_skipped("grasp_ig", "time_budget")
    report.iterations = 4
    assert state.iterations == report.iterations == 4
    assert not state.deadline_reached
    assert all(row["reason"] == "reserved_for_later_phases" for row in state.skipped_phases)


_REFERENCE_SCORE = (0.0, 4.0, 40.0, 40.0, 100.0, 3.0)
_IMPROVED_SCORE = (0.0, 3.0, 30.0, 30.0, 100.0, 3.0)


def _feedback_observation(score=_REFERENCE_SCORE, *, elapsed=1.0, sequence=0):
    return SimpleNamespace(
        sequence=sequence, status="completed", objective="min_overdue", objective_name="min_overdue",
        score=score, elapsed_seconds=elapsed, summary=SimpleNamespace(success=True, failed_ops=0),
        metrics=SimpleNamespace(completion=SimpleNamespace(objective_defined=True)),
    )


def test_feedback_rewards_only_observed_strict_improvement_and_accounts_for_measured_cost():
    allocations = []
    for elapsed in (1.0, 4.0):
        feedback = CandidateBudgetFeedback("min_overdue")
        feedback.observe(_feedback_observation())
        feedback.observe(_feedback_observation(_IMPROVED_SCORE, elapsed=elapsed, sequence=1))
        assigned, report = feedback.allocate(12.0, remaining_candidates=3)
        allocations.append(assigned)
        assert report["observed_completed_count"] == 2 and report["observed_improvement_count"] == 1
        assert report["strict_improvement"] is True
        assert report["improvements_per_second"] == pytest.approx(1.0 / elapsed)
        assert report["feedback_applied"] is True
        assert report["minimum_untried_share_ms"] == 2000
        assert report["reserved_for_other_candidates_ms"] >= 4000
    assert allocations == pytest.approx([7.2, 6.0])


@pytest.mark.parametrize("improved", [False, True])
def test_outer_runner_uses_completed_results_to_adapt_the_next_slice(improved):
    now = [0.0]
    allocations = []

    def optimize(**kwargs):
        allocations.append(kwargs["search_budget"])
        score = _IMPROVED_SCORE if improved and len(allocations) >= 2 else _REFERENCE_SCORE
        result = _outcome("measured", score=score, tardiness=score[3])
        result.summary.success = True
        result.metrics.completion = SimpleNamespace(objective_defined=True)
        now[0] += 1.0
        return result

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_no_graph, optimize_schedule_fn=optimize,
        clock=lambda: now[0], weight_count=3, run_time_budget_seconds=12.0, selection_policy="score_only",
    )
    assert outcome.completed_count == outcome.planned_count == 4
    assert outcome.skipped_count == 0 and not outcome.time_budget_reached
    assert [item.assigned_seconds for item in allocations[:2]] == pytest.approx([3.0, 11.0 / 3.0])
    assert allocations[2].assigned_seconds == pytest.approx(7.5 if improved else 2.5)
    assert allocations[3].assigned_seconds == 9.0
    feedback = allocations[2].allocation_feedback
    assert feedback is not None and feedback["candidate_sequence"] == 1
    assert feedback["strict_improvement"] is improved and feedback["elapsed_seconds"] == 1.0
    expected_score = _IMPROVED_SCORE if improved else _REFERENCE_SCORE
    assert outcome.selection.selected_score == expected_score


@pytest.mark.parametrize("changes", [
    {"elapsed_seconds": 0.0}, {"elapsed_seconds": -1.0}, {"elapsed_seconds": float("nan")},
    {"elapsed_seconds": float("inf")}, {"elapsed_seconds": None}, {"elapsed_seconds": True},
    {"status": "failed"}, {"status": "skipped"}, {"objective_name": "min_tardiness"},
    {"objective": "min_tardiness"}, {"score": _IMPROVED_SCORE[:-1]},
    {"score": (False,) + _IMPROVED_SCORE[1:]},
    {"score": (0.0, 3.5) + _IMPROVED_SCORE[2:]},
    {"score": (0.0, 3.0, float("nan"), 30.0, 100.0, 3.0)},
    {"summary": SimpleNamespace(success=False, failed_ops=1)},
    {"metrics": SimpleNamespace(completion=SimpleNamespace(objective_defined=False))},
    {"metrics": SimpleNamespace()},
])
def test_ineligible_observations_neither_earn_rewards_nor_penalize_untried_candidates(changes):
    feedback = CandidateBudgetFeedback("min_overdue")
    feedback.observe(_feedback_observation())
    plan = _feedback_observation(_IMPROVED_SCORE, sequence=1)
    for field, value in changes.items():
        setattr(plan, field, value)
    feedback.observe(plan)
    assigned, report = feedback.allocate(12.0, remaining_candidates=3)
    assert assigned == 4.0
    assert report["observed_completed_count"] == 1 and report["observed_improvement_count"] == 0
    assert not report["feedback_applied"]
    assert report["reason"] == "no_measured_comparable_improvement"


@pytest.mark.parametrize("remaining,count", [(1e-6, 2), (1.0, 3), (12.0, 6), (100.0, 8)])
def test_feedback_always_reserves_a_minimum_share_and_keeps_the_outer_deadline(remaining, count):
    from core.services.scheduler.run.optimizer_search_budget import allocate_candidate_budget

    feedback = CandidateBudgetFeedback("min_overdue")
    feedback.observe(_feedback_observation())
    feedback.observe(_feedback_observation(_IMPROVED_SCORE, elapsed=0.01, sequence=1))
    budget = allocate_candidate_budget(
        clock=lambda: 0.0, started_at=0.0, deadline=remaining,
        remaining_candidates=count, feedback=feedback,
    )
    minimum = remaining / count * 0.5
    assert minimum <= budget.assigned_seconds <= remaining / count * 2.0
    assert remaining - budget.assigned_seconds >= minimum * (count - 1) - 1e-12
    assert budget.deadline <= budget.outer_deadline == remaining
    last, report = feedback.allocate(remaining, remaining_candidates=1)
    assert last == remaining and not report["feedback_applied"]
