"""A profile must not consume the last IG time with a known-unaffordable full decode."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.services.scheduler.run.optimizer_deadline_guard import prefer_ig_startup
from core.services.scheduler.run.optimizer_graph_ready_budget import GraphReadySearchBudget
from core.services.scheduler.run.optimizer_graph_ready_predecode import GraphReadyProfileSearch
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import resolve_elite_repair_limits


def test_profile_constructs_its_decision_but_skips_an_unaffordable_new_decode():
    decode = Mock()

    def evaluate(*, inspect_decision, **_kwargs):
        inspect_decision({"graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)}})
        return decode()

    budget = GraphReadySearchBudget(limits=resolve_elite_repair_limits(None, enabled=True), deadline=1.0, clock=lambda: 0.0)
    search = GraphReadyProfileSearch(evaluate=evaluate, pool=Mock(), budget=budget, profile_count=1, initial_decode_seconds=2.0)
    assert search.evaluate(profile=Mock(), order=["B"]) is None
    decode.assert_not_called()
    assert search.report["skipped_before_decode"] == search.report["skipped_by_estimated_decode_cost"] == 1
    assert not search.can_start() and budget.stop_reason is None


@pytest.mark.parametrize("cost,remaining,success,failed,expected", [
    (0, 10, True, 0, False), (1000, 2, True, 0, False),
    (1000, 1.999, True, 0, True), (7000, 9, True, 0, True),
    (7000, 9, False, 1, False), (7000, 9, True, 1, False),
])
def test_early_ig_is_only_for_measured_costly_valid_incumbents(cost, remaining, success, failed, expected):
    best = {"initial_decode_runtime_ms": cost, "summary": SimpleNamespace(success=success, failed_ops=failed)}
    assert prefer_ig_startup(best, clock=lambda: 5.0, deadline=5.0 + remaining) is expected


def test_costly_incumbent_gets_ig_before_another_profile_in_the_real_stage_runner(monkeypatch):
    from tests._support import optimizer_smtwt_compare_context as smtwt
    from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
    from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case, smtwt_repair_context

    original = smtwt.baseline_candidate

    def baseline(**kwargs):
        result = original(**kwargs)
        result["initial_decode_runtime_ms"] = 1500.0
        return result

    monkeypatch.setattr(smtwt, "baseline_candidate", baseline)
    now, starts = [0.0], []

    def schedule(scheduler, **kwargs):
        starts.append((now[0], kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"]))
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += 1.0
        return result

    result = run_production_repair_case(case=smtwt_repair_context(size=40, index=0), clock=lambda: now[0],
                                      schedule_fn=schedule, time_budget_seconds=2.0)
    assert starts[0] == (0.0, "graph_ready_v2_iterated_greedy")
    assert all(start < 2.0 for start, _origin in starts)
    assert result["iterated_greedy"]["decodes"] >= 1
    assert result["best"]["score"] <= result["baseline"]["score"]


def test_seed_construction_cannot_spend_the_remaining_formal_decode_budget(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_seed as seed_module
    from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_start import _due_date_reference

    builder = Mock(return_value={"order": None, "construction_stop": "time_budget"})
    monkeypatch.setattr(seed_module, "build_due_date_seed", builder)
    search = SimpleNamespace(report={"initial_seed": {}, "objective_name": "min_overdue"},
        limits=SimpleNamespace(due_date_seed=True), graph_context={}, parent=None, metrics={}, start_dt=None,
        clock=lambda: 4.0, deadline=24.0)
    assert _due_date_reference(search, {}) is None
    assert builder.call_args.kwargs["deadline"] == 5.0
    assert search.deadline == 24.0 and search.report["initial_seed"]["construction_time_budget_ms"] == 1000
