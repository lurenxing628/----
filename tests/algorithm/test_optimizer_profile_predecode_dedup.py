"""Exact decision proof, backed by unmodified production SGS differential runs."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from functools import partial
from itertools import product

import pytest

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy
from core.algorithms.greedy.dispatch.sgs_scoring import with_graph_priority_key
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_budget import GraphReadySearchBudget
from core.services.scheduler.run.optimizer_graph_ready_candidates import (
    context_for_profile,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer_graph_ready_predecode import GraphReadyProfileSearch, graph_priority_preorder
from core.services.scheduler.run.optimizer_graph_ready_profiles import default_weight_profiles, graph_ready_v2_profiles
from core.services.scheduler.run.optimizer_graph_ready_repair import EliteRepairPool
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    ContinuousCalendar,
    _default_config,
    _schedule_with_scheduler,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def test_preorder_keeps_ties_and_exact_float_differences():
    tied = {1: (0.0, 0.0), 2: (0.0, 0.0), 3: (1.0, 0.0)}
    scaled = {1: (-7.0,), 2: (-7.0,), 3: (900.0,)}
    split = {1: (0.0,), 2: (1e-12,), 3: (1.0,)}
    assert graph_priority_preorder(tied) == graph_priority_preorder(scaled) == ((1, 2), (3,))
    assert sorted(tied, key=tied.get) == sorted(split, key=split.get)
    assert graph_priority_preorder(split) != graph_priority_preorder(tied)


def test_exact_preorder_preserves_arbitrary_dynamic_prefix_and_resource_suffix():
    left = {1: (-4.0, 3.0), 2: (-4.0, 3.0), 3: (9.0, 0.0)}
    right = {1: (0.0,), 2: (0.0,), 3: (1.0,)}
    assert graph_priority_preorder(left) == graph_priority_preorder(right)
    for a, b, penalty_a, penalty_b, resource_a, resource_b in product(
        left, left, (0.0, 1.0), (0.0, 1.0), (-10.0, 0.0, 20.0), (-10.0, 0.0, 20.0)
    ):
        base_a, base_b = (penalty_a, resource_a, float(a)), (penalty_b, resource_b, float(b))
        lhs = with_graph_priority_key(base_a, left[a]) < with_graph_priority_key(base_b, left[b])
        rhs = with_graph_priority_key(base_a, right[a]) < with_graph_priority_key(base_b, right[b])
        assert lhs == rhs


@pytest.mark.parametrize("keys", [{1: ()}, {1: (float("inf"),)}, {1: (float("nan"),)},
                                  {1: (True,)}, {1: (0.0,), 2: (0.0, 1.0)}])
def test_unproved_key_domains_fail_loud(keys):
    with pytest.raises(ValidationError) as exc:
        graph_priority_preorder(keys)
    assert exc.value.field == "graph_ready_predecode"


def _inputs(variant="plain", dispatch_rule="slack"):
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    scheduler = _scheduler()
    seed, downtime, resources = [], {}, None
    if variant in {"seed_dependency", "automatic_resources", "window"}:
        seed = [ScheduleResult(op_id=99, op_code="LOCKED", batch_id="B_LONG", seq=0,
                               machine_id="MC-BENCH", operator_id="OP-BENCH", op_type_name="OTHER",
                               start_time=START_DT, end_time=START_DT + timedelta(hours=2))]
        context["fixed_op_ids"] = {99}
        context["fixed_op_sources_by_op_id"] = {99: "seed"}
        context["predecessor_op_ids_by_op_id"].update({99: set(), 1: {99}, 2: {1}})
        context["successor_op_ids_by_op_id"].update({99: {1}, 1: {2}})
        downtime = {"MC-BENCH": [(START_DT + timedelta(hours=4), START_DT + timedelta(hours=6))]}
    if variant == "automatic_resources":
        config = _default_config()
        config.auto_assign_enabled = "yes"
        scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=config)
        for op in operations:
            op.machine_id = op.operator_id = ""
        resources = {
            "machines_by_op_type": {"OT-BENCH": ["MC-ALT", "MC-BENCH"]},
            "operators_by_machine": {"MC-ALT": ["OP-ALT"], "MC-BENCH": ["OP-BENCH"]},
            "pair_rank": {("OP-ALT", "MC-ALT"): 0, ("OP-BENCH", "MC-BENCH"): 1},
        }
    metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations, batches=batches,
                                             start_dt=START_DT, calendar_service=scheduler.calendar,
                                             seed_results=seed, downtime_map=downtime, resource_pool=resources)
    return dict(graph_ready_context=context, metrics_by_op_id=metrics, scheduler=scheduler, strict_mode=True,
                algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={},
                start_dt=START_DT, end_date=START_DT.date() if variant == "window" else None,
                downtime_map=downtime, seed_sr_list=seed, dispatch_rule=dispatch_rule, resource_pool=resources,
                objective_name=OBJECTIVE_NAME, optimizer_algo_stats=None, readiness_gate_enabled=False,
                version=7, clock=lambda: 0.0)


def _search(inputs, schedule_fn=_schedule_with_scheduler, *, enabled=False):
    limits = EliteRepairLimits(enabled=enabled)
    pool = EliteRepairPool(limits=limits, objective_name=OBJECTIVE_NAME, operations=inputs["algo_ops_to_schedule"],
                           metrics_by_op_id=inputs["metrics_by_op_id"], start_dt=START_DT, seed=7,
                           best=None, report_state=None)
    return GraphReadyProfileSearch(
        evaluate=partial(evaluate_graph_ready_candidate, **inputs, schedule_fn=schedule_fn), pool=pool,
        budget=GraphReadySearchBudget(limits=limits, deadline=1000.0, clock=inputs["clock"]), profile_count=19,
    )


def _outcome(candidate):
    summary = candidate["summary"]
    return (candidate["results"], summary.success, summary.failed_ops, summary.scheduled_ops,
            summary.warnings, summary.errors, getattr(summary, "failure_details", ()),
            candidate["metrics"].to_dict(), candidate["score"])


@pytest.mark.parametrize("variant", ["plain", "seed_dependency", "automatic_resources", "window"])
@pytest.mark.parametrize("dispatch_rule", ["slack", "cr", "atc"])
def test_every_pruned_profile_matches_full_real_sgs_output(variant, dispatch_rule):
    inputs = _inputs(variant, dispatch_rule)
    profiles = graph_ready_v2_profiles(max_candidate_profiles=60, seed=7)[0]
    exhaustive = {}
    for profile in profiles:
        context = context_for_profile(graph_ready_context=inputs["graph_ready_context"],
                                      metrics_by_op_id=inputs["metrics_by_op_id"], profile=profile)
        key = graph_priority_preorder(context["graph_priority_key_by_op_id"])
        full = evaluate_graph_ready_candidate(**inputs, profile=profile, order=list(BASE_BATCH_ORDER),
                                               schedule_fn=_schedule_with_scheduler)
        if key in exhaustive:
            assert _outcome(full) == _outcome(exhaustive[key])
        else:
            exhaustive[key] = full
        if inputs["seed_sr_list"]:
            assert next(row for row in full["results"] if row.op_id == 99) == inputs["seed_sr_list"][0]

    calls = []

    def schedule(scheduler, **kwargs):
        calls.append(kwargs)
        return _schedule_with_scheduler(scheduler, **kwargs)

    search = _search(inputs, schedule)
    retained = []
    for profile in profiles:
        candidate = search.evaluate(profile=profile, order=list(BASE_BATCH_ORDER))
        if candidate is not None:
            retained.append(_outcome(candidate))
    assert len(calls) == len(retained) == len(exhaustive) < len(profiles)
    assert search.report["predecode_pruned_profiles"] == len(profiles) - len(calls)
    assert all(_outcome(full) in retained for full in exhaustive.values())
    assert all(call["resource_pool"] is inputs["resource_pool"] for call in calls)


def test_same_sorted_ids_but_different_ties_can_change_real_sgs():
    inputs = _inputs()
    context = inputs["graph_ready_context"]
    results = []
    # ATC prefers a short operation inside an all-tied graph group. A strict
    # graph order can override that dynamic dispatch key, despite identical IDs.
    for keys in ({1: (0.0,), 2: (0.0,), 3: (0.0,), 4: (0.0,)},
                 {1: (0.0,), 2: (0.0,), 3: (1.0,), 4: (1.0,)}):
        current = dict(context, score_enabled=True, graph_priority_key_by_op_id=keys)
        decoded = inputs["scheduler"].schedule(operations=inputs["algo_ops_to_schedule"], batches=inputs["batches"],
                                               strategy=SortStrategy.PRIORITY_FIRST, strategy_params={},
                                               start_dt=START_DT, dispatch_mode="sgs", dispatch_rule="atc",
                                               batch_order_override=list(BASE_BATCH_ORDER), graph_ready_context=current,
                                               seed_results=[], strict_mode=True)
        results.append(decoded[0])
    assert results[0] != results[1]


def test_real_window_scores_exercise_both_dynamic_penalties(monkeypatch):
    from core.algorithms.greedy.dispatch import sgs
    original = sgs._score_candidate
    penalties = set()

    def score(*args, **kwargs):
        key = original(*args, **kwargs)
        penalties.add(key[0])
        return key

    monkeypatch.setattr(sgs, "_score_candidate", score)
    inputs = _inputs("window")
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    result = evaluate_graph_ready_candidate(**inputs, profile=profile, order=list(BASE_BATCH_ORDER),
                                             schedule_fn=_schedule_with_scheduler)
    assert penalties == {0.0, 1.0}
    assert result["summary"].failed_ops > 0


def test_distinct_graph_decisions_still_use_output_fingerprint_rejection():
    from core.services.scheduler.run.optimizer_graph_ready import _candidate_should_replace_best
    from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
    inputs = _inputs()
    context = inputs["graph_ready_context"]
    context["predecessor_op_ids_by_op_id"] = {1: set(), 2: {1}, 3: {2}, 4: {3}}
    context["successor_op_ids_by_op_id"] = {1: {2}, 2: {3}, 3: {4}, 4: set()}
    profiles = default_weight_profiles(max_weight_profiles=9)[0]
    search = _search(inputs)
    first = search.evaluate(profile=profiles[0], order=list(BASE_BATCH_ORDER))
    other = search.evaluate(profile=profiles[2], order=list(BASE_BATCH_ORDER))
    assert first is not None and other is not None
    assert _outcome(first) == _outcome(other)
    state = OptimizationSearchReportState(algorithm_profile="test", seed=7, time_budget_seconds=1,
                                          objective_name=OBJECTIVE_NAME, started_at=0.0,
                                          candidate_profile={"acceptance": "improve_only"})
    state.mark_candidate_accepted(first, origin="baseline")
    assert not _candidate_should_replace_best(other, profile=profiles[2], best=first, attempts=[], search_report_state=state)
    assert state.rejection_summary["same_fingerprint"] == 1
    assert state.acceptance_events == []


def test_names_do_not_define_equivalence_and_order_remains_part_of_decision():
    inputs = _inputs()
    profiles = default_weight_profiles(max_weight_profiles=9)[0]
    search = _search(inputs)
    first = search.evaluate(profile=profiles[0], order=list(BASE_BATCH_ORDER))
    assert first is not None
    renamed = replace(profiles[0], slug="different_name")
    assert search.evaluate(profile=renamed, order=list(BASE_BATCH_ORDER)) is None
    different = replace(profiles[2], slug=profiles[0].slug)
    assert search.evaluate(profile=different, order=list(BASE_BATCH_ORDER)) is not None
    assert search.evaluate(profile=renamed, order=list(reversed(BASE_BATCH_ORDER))) is not None


def test_resource_pool_changes_do_not_reuse_another_search_cache():
    left = _inputs("automatic_resources")
    right = _inputs("automatic_resources")
    right["resource_pool"] = dict(right["resource_pool"], machines_by_op_type={"OT-BENCH": ["MC-BENCH"]})
    profile = graph_ready_v2_profiles(max_candidate_profiles=60)[0][1]
    a, b = _search(left), _search(right)
    result_a = a.evaluate(profile=profile, order=list(BASE_BATCH_ORDER))
    result_b = b.evaluate(profile=profile, order=list(BASE_BATCH_ORDER))
    assert result_a is not None and result_b is not None
    assert result_a["results"] != result_b["results"]
    assert a.budget.profile_decodes == b.budget.profile_decodes == 1


def test_equivalent_v2_alias_can_supply_an_elite_without_relabeling_decode():
    inputs = _inputs()
    profiles = graph_ready_v2_profiles(max_candidate_profiles=60)[0]
    search = _search(inputs, enabled=True)
    seen = {}
    for profile in profiles:
        candidate = search.evaluate(profile=profile, order=list(BASE_BATCH_ORDER))
        if candidate is not None:
            seen[candidate["graph_ready_profile"]["weight_profile_slug"]] = candidate
    assert search.pool.elites
    for elite in search.pool.elites:
        assert elite["candidate"] is seen[elite["candidate"]["graph_ready_profile"]["weight_profile_slug"]]
        assert elite["profile"].formula_version.startswith("graph_ready_v2")


def test_a18_evaluation_receives_real_operations_seed_and_summary_details(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_candidates as candidates
    original = candidates.compute_metrics
    inputs = _inputs("seed_dependency")
    received = []

    def metrics(results, batches, **kwargs):
        received.append(kwargs)
        return original(results, batches, **kwargs)

    monkeypatch.setattr(candidates, "compute_metrics", metrics)
    result = evaluate_graph_ready_candidate(**inputs, profile=default_weight_profiles(max_weight_profiles=1)[0][0],
                                             order=list(BASE_BATCH_ORDER), schedule_fn=_schedule_with_scheduler)
    assert received[0]["expected_operations"] is inputs["algo_ops_to_schedule"]
    assert received[0]["seed_results"] is inputs["seed_sr_list"]
    assert received[0]["failure_details"] is result["summary"].failure_details
