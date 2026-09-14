"""Outer candidates with identical optimizer inputs reuse one plan and hand their slice to plans that need a search."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.services.scheduler.run.schedule_candidate_runner as runner
from core.services.scheduler.run.schedule_candidate_dedup import optimizer_input_fingerprint
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_public_summary
from tests.candidate.test_scheduler_candidate_runner_contract import _cfg, _outcome, _schedule_input, _StepClock


def _prep(context, **extra):
    return SimpleNamespace(
        graph_analysis_public=None if context is None else {"status": "available"},
        graph_analysis_diagnostics=None,
        graph_ready_context=context,
        graph_dispatch_mode_override=None if context is None else "sgs",
        **extra,
    )


def _same_order_prepare(schedule_input):
    """Keys scale with the tier weight, so every tier induces the same weak order (op 1 ties op 3)."""
    cfg = schedule_input.cfg
    if cfg.graph_analysis_mode == "off":
        return _prep(None)
    weight = float(cfg.graph_critical_weight)
    keys = {1: (weight * 1.0, 0.0), 2: (weight * 2.0, 0.0), 3: (weight * 1.0, 0.0)}
    return _prep({
        "enabled": True, "score_enabled": True, "graph_priority_key_by_op_id": keys,
        "score_weights": {"critical_weight": int(weight)}, "predecessor_op_ids_by_op_id": {1: set(), 2: {1}, 3: set()},
    })


def _parity_prepare(schedule_input):
    """Odd and even tier weights flip the order of op 1 and op 2."""
    cfg = schedule_input.cfg
    if cfg.graph_analysis_mode == "off":
        return _prep(None)
    first = 1.0 if cfg.graph_critical_weight % 2 else 2.0
    return _prep({"graph_priority_key_by_op_id": {1: (first,), 2: (3.0 - first,)}})


def _counting_optimize(calls, *, fail_weight=None):
    def optimize(**kwargs):
        weight = kwargs["cfg"].graph_critical_weight
        calls.append(weight)
        if fail_weight is not None and weight == fail_weight:
            raise runner.CandidateTrialFailure("tier failed")
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)
    return optimize


def test_tiers_with_the_same_key_order_reuse_the_first_completed_plan():
    calls = []
    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_same_order_prepare,
        optimize_schedule_fn=_counting_optimize(calls), weight_count=5, selection_policy="score_only",
        clock=_StepClock([0] * 200),
    )
    assert calls == [0, 250]
    assert [candidate.status for candidate in outcome.candidates] == ["completed"] * 6
    assert [candidate.reused_from_candidate_key for candidate in outcome.candidates] == [None, None] + ["graph_w1_of_5"] * 4
    assert outcome.reused_count == 4 and outcome.completed_count == 6
    first_label = outcome.candidates[1].label
    public = candidate_comparison_public_summary(outcome)
    assert public["reused_candidate_count"] == 4 and public["completed_candidate_count"] == 6
    assert [candidate.get("reused_from_label") for candidate in public["candidates"]] == [None, None] + [first_label] * 4
    assert all("candidate_key" not in candidate for candidate in public["candidates"])
    reused = outcome.candidates[3]
    assert reused.results == outcome.candidates[1].results and reused.results is not outcome.candidates[1].results
    assert (reused.sequence, reused.candidate_key, reused.graph_critical_weight) == (3, "graph_w3_of_5", 500)


def test_tiers_whose_key_order_differs_each_run_their_own_search():
    calls = []
    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_parity_prepare,
        optimize_schedule_fn=_counting_optimize(calls), weight_count=5, selection_policy="score_only",
        clock=_StepClock([0] * 200),
    )
    assert calls == [0, 250, 375]
    assert [candidate.reused_from_candidate_key for candidate in outcome.candidates] == [
        None, None, None, "graph_w1_of_5", "graph_w2_of_5", "graph_w1_of_5",
    ]


def test_a_failed_sibling_is_not_reused_and_the_next_identical_tier_searches():
    calls = []
    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_same_order_prepare,
        optimize_schedule_fn=_counting_optimize(calls, fail_weight=250), weight_count=5, selection_policy="score_only",
        clock=_StepClock([0] * 200),
    )
    assert calls == [0, 250, 375]
    assert [candidate.status for candidate in outcome.candidates] == ["completed", "failed"] + ["completed"] * 4
    assert [candidate.reused_from_candidate_key for candidate in outcome.candidates] == [None, None, None] + ["graph_w2_of_5"] * 3
    assert outcome.failed_count == 1 and outcome.reused_count == 3


def test_budget_is_split_among_plans_that_still_need_a_search():
    now = [0.0]
    budgets = []

    def optimize(**kwargs):
        budgets.append(kwargs["search_budget"].assigned_seconds)
        now[0] += 0.5
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=_same_order_prepare, optimize_schedule_fn=optimize,
        clock=lambda: now[0], weight_count=5, run_time_budget_seconds=12.0, selection_policy="score_only",
    )
    # Before any graph preparation every advertised plan keeps a slot; once the five tiers prove identical
    # the first tier receives everything that is left instead of one fifth of it.
    assert budgets == pytest.approx([2.0, 11.5])
    assert outcome.reused_count == 4 and not outcome.time_budget_reached


def test_fingerprint_ignores_raw_weights_but_not_other_inputs():
    keys = {1: (250.0, 5.0), 2: (500.0, 5.0)}
    scaled = {1: (500.0, 10.0), 2: (1000.0, 10.0)}
    flipped = {1: (500.0, 5.0), 2: (250.0, 5.0)}
    base = _cfg(graph_analysis_mode="on")
    heavier = _cfg(graph_analysis_mode="on", graph_critical_weight=1000, graph_impact_weight=20, graph_downstream_weight=2)
    assert optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": keys, "score_weights": {"critical_weight": 500}})) == \
        optimizer_input_fingerprint(heavier, _prep({"graph_priority_key_by_op_id": scaled, "score_weights": {"critical_weight": 1000}}))
    assert optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": keys})) != \
        optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": flipped}))
    assert optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": keys, "fixed_op_ids": [7]})) != \
        optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": keys, "fixed_op_ids": []}))
    assert optimizer_input_fingerprint(base, _prep(None)) != optimizer_input_fingerprint(_cfg(graph_analysis_mode="off"), _prep(None))
    assert optimizer_input_fingerprint(base, _prep(None)) != optimizer_input_fingerprint(
        base, SimpleNamespace(graph_analysis_public=None, graph_analysis_diagnostics=None, graph_ready_context=None, graph_dispatch_mode_override="sgs"))
    assert optimizer_input_fingerprint(base, _prep(object())) is None
    assert optimizer_input_fingerprint(base, _prep({"graph_priority_key_by_op_id": {1: (1.0,), 2: (1.0, 2.0)}})) is None
