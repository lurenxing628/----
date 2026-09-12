"""Controlled clocks prove measurement boundaries; their numbers are not performance evidence."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from tests._support import optimizer_compare_algorithms as comparison
from tests._support import optimizer_graph_ready_benchmark as light_graph
from tests._support import optimizer_graph_ready_repair_benchmark as production
from tests._support import optimizer_smtwt_compare_context as smtwt_context
from tests._support import optimizer_smtwt_compare_graph as smtwt_graph
from tests._support import optimizer_smtwt_compare_runners as smtwt_runners


class ControlledClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _candidate(origin="baseline"):
    return {
        "results": [], "score": (0.0, 0.0, 0.0), "candidate_origin": origin,
        "runtime_ms": 99999.0, "metrics": SimpleNamespace(overdue_count=0),
        "summary": SimpleNamespace(failed_ops=0, success=True),
    }


def _state():
    return SimpleNamespace(
        evaluated_candidates=1, accepted_candidates=1, candidate_fingerprints={"baseline"},
        accepted_fingerprints={"baseline"}, rejection_summary={}, candidate_profile={},
        mark_candidate_evaluated=lambda *args, **kwargs: None,
        mark_candidate_accepted=lambda *args, **kwargs: None,
    )


@pytest.mark.parametrize("profile,returned", [
    ("greedy", "baseline"), ("local_search", "baseline"), ("local_search", "none"),
    ("local_search", "improved"), ("grasp_ig", "baseline"), ("grasp_ig", "none"), ("grasp_ig", "improved"),
])
def test_comparison_times_baseline_and_whole_search_even_without_improvement(monkeypatch, profile, returned):
    clock = ControlledClock()
    baseline = _candidate()
    stage_calls = []
    state_arguments = []
    monkeypatch.setattr(comparison, "time", SimpleNamespace(perf_counter=clock))

    def setup():
        assert clock.now == 100.0
        clock.now += 0.25
        return object(), [], {}, baseline

    def state(**kwargs):
        state_arguments.append(kwargs)
        return _state()

    def search(**kwargs):
        stage_calls.append(kwargs)
        assert clock.now == 100.25
        assert kwargs["t_begin"] == 100.0
        assert kwargs["deadline"] == 101.0
        assert kwargs["clock"] is comparison.time.perf_counter
        clock.now += 0.5
        return None if returned == "none" else baseline if returned == "baseline" else _candidate("improved")

    monkeypatch.setattr(comparison, "_baseline_setup", setup)
    monkeypatch.setattr(comparison, "_state", state)
    monkeypatch.setattr(comparison, "snapshot_algo_stats", lambda scheduler: {})
    monkeypatch.setattr(comparison, "run_local_search", search)
    monkeypatch.setattr(comparison, "run_grasp_ig_candidates", search)
    row = comparison._run_single_profile(profile=profile, seed=3)
    assert row["runtime_ms"] == pytest.approx(250.0 if profile == "greedy" else 750.0)
    assert row["runtime_ms"] != baseline["runtime_ms"]
    assert row["candidate_origin"] == ("improved" if returned == "improved" else "baseline")
    assert len(stage_calls) == (0 if profile == "greedy" else 1)
    if state_arguments:
        assert state_arguments[0]["started"] == 100.0


def _controlled_smtwt_context(monkeypatch, clock):
    case = SimpleNamespace(
        operations=[SimpleNamespace(id=i, setup_hours=1.0) for i in range(1, 5)], batches=[],
        start_dt=datetime(2026, 1, 1), dispatch_rule="slack", objective_name="min_overdue", slug="controlled-clock",
    )

    def forbidden_schedule(*args, **kwargs):
        pytest.fail("no decoder may run outside the stubbed production search phase")

    def baseline(**kwargs):
        assert clock.now == 100.0
        clock.now += 0.25
        return _candidate()

    monkeypatch.setattr(smtwt_context, "time", SimpleNamespace(perf_counter=clock))
    monkeypatch.setattr(smtwt_context, "_operation_object", lambda op: op)
    monkeypatch.setattr(smtwt_context, "batch_objects", lambda source: {})
    monkeypatch.setattr(smtwt_context, "make_scheduler", lambda: SimpleNamespace(schedule=forbidden_schedule))
    monkeypatch.setattr(smtwt_context, "baseline_candidate", baseline)
    context = smtwt_context.build_case_context(case=case, time_budget_seconds=1)
    assert context["started_at"] == 100.0
    assert context["deadline"] == 101.0
    return context


@pytest.mark.parametrize("profile,returned", [
    ("greedy", "baseline"), ("local_search", "baseline"), ("local_search", "none"),
    ("grasp_ig", "baseline"), ("grasp_ig", "none"),
])
def test_smtwt_standard_profiles_share_the_context_clock_and_include_baseline(monkeypatch, profile, returned):
    clock = ControlledClock()
    context = _controlled_smtwt_context(monkeypatch, clock)
    calls = []
    monkeypatch.setattr(smtwt_runners, "time", SimpleNamespace(perf_counter=clock))
    monkeypatch.setattr(smtwt_runners, "make_report_state", lambda **kwargs: _state())
    monkeypatch.setattr(smtwt_runners, "snapshot_algo_stats", lambda scheduler: {})

    def search(**kwargs):
        calls.append(kwargs)
        assert kwargs["deadline"] == context["deadline"] == 101.0
        assert kwargs["t_begin"] == context["started_at"] == 100.0
        assert kwargs["clock"] is smtwt_runners.time.perf_counter
        assert clock.now == 100.25
        clock.now += 0.5
        return None if returned == "none" else context["baseline"]

    monkeypatch.setattr(smtwt_runners, "run_local_search", search)
    monkeypatch.setattr(smtwt_runners, "run_grasp_ig_candidates", search)
    row = smtwt_runners.run_standard_profile(profile=profile, context=context, optimum=0, seed=3)
    assert row["runtime_ms"] == pytest.approx(250.0 if profile == "greedy" else 750.0)
    assert row["runtime_ms"] != context["baseline"]["runtime_ms"]
    assert len(calls) == (0 if profile == "greedy" else 1)


@pytest.mark.parametrize("profile,enabled", [
    ("graph_ready_v1", False), ("graph_ready_v2_no_repair", False), ("graph_ready_v2_with_repair", True),
])
def test_smtwt_graph_repair_stays_inside_one_production_phase_and_budget(monkeypatch, profile, enabled):
    clock = ControlledClock()
    context = _controlled_smtwt_context(monkeypatch, clock)
    calls = []
    monkeypatch.setattr(smtwt_graph, "time", SimpleNamespace(perf_counter=clock))
    monkeypatch.setattr(smtwt_graph, "make_report_state", lambda **kwargs: _state())
    monkeypatch.setattr(smtwt_graph, "snapshot_algo_stats", lambda scheduler: {})

    def phase(**kwargs):
        calls.append(kwargs)
        assert kwargs["clock"] is smtwt_graph.time.perf_counter
        assert kwargs["deadline"] == context["deadline"] == 101.0
        assert kwargs["t_begin"] == context["started_at"] == 100.0
        optimization = kwargs["candidate_construction"]["graph_ready_optimization"]
        assert optimization["elite_repair"]["enabled"] is enabled
        assert optimization["candidate_policy"] == ("weight_grid" if profile == "graph_ready_v1" else "objective_aware_portfolio")
        kwargs["search_report_state"].candidate_profile["graph_ready_optimization"] = {"elite_repair": {"production_marker": True}}
        assert clock.now == 100.25
        clock.now += 0.5
        return None

    monkeypatch.setattr(smtwt_graph, "run_graph_ready_candidates", phase)
    row = smtwt_graph.run_graph_profile(profile=profile, context=context, optimum=0, seed=3)
    assert len(calls) == 1
    assert row["runtime_ms"] == pytest.approx(750.0)
    assert row["repair_scope"] == "production_core"
    assert row["repair"] == {"production_marker": True}
    assert row["candidate_origin"] == "baseline"


@pytest.mark.parametrize("v2,enabled", [(False, False), (True, False), (True, True)])
def test_production_helper_elapsed_includes_baseline_and_repair(monkeypatch, v2, enabled):
    clock = ControlledClock()
    baseline = _candidate()
    calls = []
    monkeypatch.setattr(production, "_scheduler", lambda: object())
    monkeypatch.setattr(production, "graph_ready_benchmark_operations", lambda: [])
    monkeypatch.setattr(production, "graph_ready_benchmark_batches", lambda: {})
    monkeypatch.setattr(production, "graph_ready_benchmark_context", lambda: {})
    monkeypatch.setattr(production, "OptimizationSearchReportState", lambda **kwargs: _state())

    def prepare(**kwargs):
        assert clock.now == 100.0
        clock.now += 0.25
        return baseline

    def phase(**kwargs):
        calls.append(kwargs)
        assert kwargs["clock"] is clock
        assert kwargs["t_begin"] == 100.0 and kwargs["deadline"] == 101.0
        assert kwargs["candidate_construction"]["graph_ready_optimization"]["elite_repair"]["enabled"] is enabled
        kwargs["search_report_state"].candidate_profile["graph_ready_optimization"] = {"elite_repair": {"production_marker": True}}
        clock.now += 0.5
        return baseline

    monkeypatch.setattr(production, "_baseline_candidate", prepare)
    monkeypatch.setattr(production, "run_graph_ready_candidates", phase)
    result = production.run_production_repair_case(clock=clock, enabled=enabled, v2=v2)
    assert len(calls) == 1
    assert result["runtime_ms"] == pytest.approx(750.0)
    assert result["best"]["runtime_ms"] == 99999.0
    assert result["clock_scope"] == "test_injected_clock"

    def measured_result(**kwargs):
        assert kwargs["v2"] is v2 and kwargs["enabled"] is enabled
        return result

    monkeypatch.setattr(comparison, "run_production_repair_case", measured_result)
    row = comparison._graph_ready_row(seed=0, v2=v2, with_repair=enabled)
    assert row["runtime_ms"] == pytest.approx(750.0)
    assert row["repair"] == {"production_marker": True}


def test_four_operation_greedy_row_has_a_real_positive_elapsed_time():
    row = comparison._baseline_row(seed=0)
    assert row["status"] == "passed"
    assert row["failed_ops"] == 0
    assert len(row["best_order"]) == 4
    assert row["runtime_ms"] > 0.0


def test_light_graph_helper_uses_wall_clock_and_whole_phase(monkeypatch):
    clock = ControlledClock()
    baseline = _candidate()
    monkeypatch.setattr(light_graph, "perf_counter", clock)
    monkeypatch.setattr(light_graph, "_scheduler", lambda: object())
    monkeypatch.setattr(light_graph, "OptimizationSearchReportState", lambda **kwargs: _state())
    monkeypatch.setattr(light_graph, "snapshot_algo_stats", lambda scheduler: {})
    monkeypatch.setattr(light_graph, "_row_passes", lambda row: True)
    monkeypatch.setattr(light_graph, "_benchmark_row", lambda **kwargs: {"runtime_ms": kwargs["runtime_ms"]})

    def baseline_phase(**kwargs):
        clock.now += 0.25
        return baseline

    def search_phase(**kwargs):
        assert kwargs["clock"] is light_graph.perf_counter
        assert kwargs["deadline"] == 101.0 and kwargs["t_begin"] == 100.0
        clock.now += 0.5
        return baseline

    monkeypatch.setattr(light_graph, "_baseline_candidate", baseline_phase)
    monkeypatch.setattr(light_graph, "run_graph_ready_candidates", search_phase)
    row = light_graph.run_graph_ready_real_sgs_case()
    assert row["runtime_ms"] == pytest.approx(750.0)
    assert row["clock_scope"] == "time.perf_counter"


def test_incomplete_baseline_cannot_be_reported_as_passed_comparison(monkeypatch):
    failed = _candidate()
    failed["summary"] = SimpleNamespace(failed_ops=1, success=False)
    monkeypatch.setattr(comparison, "_baseline_setup", lambda: (object(), [], {}, failed))
    row = comparison._baseline_row(seed=0)
    assert row["status"] == "failed"
    assert row["failed_ops"] == 1
