"""Real SGS regression for bounded improvement from previously repaired elites."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_graph_ready_repair as repair
from core.services.scheduler.run.optimizer_graph_ready_feature_basis import select_profile_metrics
from core.services.scheduler.run.optimizer_graph_ready_profiles import graph_ready_v2_profiles
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import (
    EliteRepairLimits,
    resolve_elite_repair_limits,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case, smtwt_repair_context


def test_new_round_decodes_from_accepted_elites_and_improves_known_small_case(monkeypatch):
    context = smtwt_repair_context()
    original = repair.EliteRepairPool.make_elite

    def check_no_unused_next_round(self, candidate, profile):
        assert profile.candidate_origin != "graph_ready_v2_repaired"
        return original(self, candidate, profile)

    monkeypatch.setattr(repair.EliteRepairPool, "make_elite", check_no_unused_next_round)
    # Repair-round contracts: a frozen clock would let the iterated greedy stage run to its decode cap.
    once = run_production_repair_case(case=context, clock=lambda: 0.0, limits={"max_rounds": 1}, iterated_greedy={"enabled": False})
    monkeypatch.setattr(repair.EliteRepairPool, "make_elite", original)
    repeated = run_production_repair_case(case=context, clock=lambda: 0.0, limits={"max_rounds": 3}, iterated_greedy={"enabled": False})
    assert once["repair"]["repair_stop_reason"] == "max_rounds"
    assert once["repair"]["repair_rounds_completed"] == 1
    assert repeated["repair"]["repair_rounds_completed"] > 1
    assert any(count > 0 for count in repeated["repair"]["repair_round_improvements"])
    assert repeated["best"]["score"] < once["best"]["score"]
    assert repeated["best"]["summary"].failed_ops == 0
    assert len(repeated["calls"]) <= repeated["max_candidates"]
    assert repeated["repair"]["repair_stop_reason"] in {"candidate_budget", "max_rounds", "no_improvement"}
    assert repeated["state"].best_acceptance_passed


@pytest.mark.parametrize("neighbors,stop,cap", [(8, "max_rounds", 60), (32, "no_improvement", 200)])
def test_no_improvement_means_all_selected_parent_tails_are_exhausted(neighbors, stop, cap):
    # The exhaustion case gives late profile parents room; cap=60 has separate conservation tests.
    result = run_production_repair_case(clock=lambda: 0.0, max_candidates=cap, limits={"max_neighbors_per_elite": neighbors},
                                        iterated_greedy={"enabled": False})
    report = result["repair"]
    assert report["repair_stop_reason"] == stop
    # Profiles can supply a new parent between repair tasks, requiring another bounded round.
    rounds = report["repair_rounds_completed"]
    assert 1 <= rounds <= report["repair_max_rounds"]
    assert report["repair_round_improvements"] == [0] * rounds
    pruning = report["repair_pruning_report"]
    unvisited = pruning["skipped_by_budget"] - report["skipped_neighbors_by_top_k"]
    assert (unvisited == 0) == (stop == "no_improvement")
    assert result["best"]["score"] <= result["baseline"]["score"]


def test_real_improvement_gets_next_round_before_older_elites(monkeypatch):
    calls = []
    original = repair._repair_one_elite

    def observe(pool, **kwargs):
        before = len(kwargs["improved_elites"])
        round_index = pool.report["repair_rounds_completed"]
        try:
            yield from original(pool, **kwargs)
        finally:
            calls.append((round_index, kwargs["elite"]["profile"].candidate_origin,
                          len(kwargs["improved_elites"]) > before))

    monkeypatch.setattr(repair, "_repair_one_elite", observe)
    result = run_production_repair_case(case=smtwt_repair_context(), clock=lambda: 0.0, limits={"max_rounds": 3},
                                        iterated_greedy={"enabled": False})
    transitions = [(previous, following) for previous, following in zip(calls, calls[1:])
                   if previous[2] and previous[0] < 2]
    assert transitions, "the real fixture must exercise an improving round"
    assert all(following[0] == previous[0] + 1 and following[1] == "graph_ready_v2_repaired"
               for previous, following in transitions)
    assert result["repair"]["repair_round_policy"] == "improvement_first"
    assert result["repair"]["repair_deferred_by_improvement"] > 0
    assert result["best"]["summary"].failed_ops == 0
    assert len(result["calls"]) <= result["max_candidates"]
    pruning = result["repair"]["repair_pruning_report"]
    assert pruning["generated_candidates"] == pruning["evaluated_candidates"] + pruning["pruned_candidates"]
    assert pruning["skipped_by_budget"] == (result["repair"]["skipped_neighbors_by_top_k"]
                                            + pruning["candidate_space_total"] - pruning["generated_candidates"])


def test_improving_elite_retains_its_unvisited_tail_with_bounded_visits(monkeypatch):
    from tests._support import optimizer_end_to_end_runner as runner

    visits = []
    original = repair._repair_one_elite

    def observe(pool, **kwargs):
        elite = kwargs["elite"]
        start = elite.get("decision_offset", 0)
        round_index = pool.report["repair_rounds_completed"]
        assert kwargs["elite_index"] < pool.limits.top_k
        try:
            yield from original(pool, **kwargs)
        finally:
            visits.append((pool, elite, start, elite["decision_offset"], round_index))

    monkeypatch.setattr(repair, "_repair_one_elite", observe)
    # This is a deterministic production-path contract, not a runtime benchmark.
    monkeypatch.setattr(runner, "perf_counter", lambda: 0.0)
    result = runner.run_case("frozen_ready_external", "min_tardiness")
    assert result["status"] == "passed"
    assert result["selected"]["quality_vectors"]["min_tardiness"] == [0.0, 171.0, 4.0, 285.5, 135.0, 1.0]
    assert any(start > 0 and end > start for _, _, start, end, _ in visits)
    consumed = {}
    pools = {}
    active_visits = {}
    for pool, elite, start, end, round_index in visits:
        pools[id(pool)] = pool
        assert 0 <= end - start <= pool.limits.max_neighbors_per_elite == 8
        key = (id(pool), id(elite))
        assert start == consumed.get(key, 0), "resuming an elite must continue after its consumed prefix"
        consumed[key] = end
        round_key = (id(pool), round_index)
        active_visits[round_key] = active_visits.get(round_key, 0) + 1
        assert active_visits[round_key] <= pool.limits.top_k
    for pool in pools.values():
        report = pool.report
        pruning = report["repair_pruning_report"]
        assert pruning["evaluated_candidates"] <= report["repair_candidate_budget"] <= 60
        assert pruning["generated_candidates"] == pruning["evaluated_candidates"] + pruning["pruned_candidates"]
        assert pruning["skipped_by_budget"] == (report["skipped_neighbors_by_top_k"]
                                                + pruning["candidate_space_total"] - pruning["generated_candidates"])


def test_profile_improvement_supersedes_an_older_repair_round_priority():
    from core.services.scheduler.run.optimizer_graph_ready_repair_rotation import (
        _current_improvements,
        _fill_round_slots,
    )

    old = {"candidate": {"score": (0, 216)}, "neighborhood": SimpleNamespace(candidate_count=12), "decision_offset": 8}
    fresh = {"candidate": {"score": (0, 171)}, "neighborhood": SimpleNamespace(candidate_count=10), "decision_offset": 0}
    events = [old]
    pool = SimpleNamespace(limits=EliteRepairLimits(top_k=2), elites=[fresh], report={"repair_deferred_by_improvement": 0})
    current = _current_improvements(events, fresh["candidate"])
    assert not repair._defer_to_improved_elites(pool, [old], 0, 0, current)
    assert pool.report["repair_deferred_by_improvement"] == 0
    assert events == [old], "the historical strict improvement still belongs in the round report"
    active, queued = [old], []
    _fill_round_slots(active, queued, [old], pool)
    assert active == [old, fresh] and queued == []
    # Once the active cap is filled, another new parent waits instead of extending the round.
    later = {"candidate": {"score": (0, 170)}, "neighborhood": SimpleNamespace(candidate_count=4), "decision_offset": 0}
    pool.elites = [later]
    _fill_round_slots(active, queued, [old], pool)
    assert active == [old, fresh] and queued == [later]


def test_tiny_changeover_keeps_distinct_parents_and_consumes_shared_variant_tails(monkeypatch):
    from tests._support.optimizer_quality_matrix import run_case

    visits = []
    decoded = []
    original_visit, original_evaluate = repair._repair_one_elite, repair._evaluate_neighbor

    def visit(pool, **kwargs):
        elite = kwargs["elite"]
        start = elite["decision_offset"]
        round_index = pool.report["repair_rounds_completed"]
        try:
            yield from original_visit(pool, **kwargs)
        finally:
            visits.append((pool, elite, round_index, start, elite["decision_offset"]))

    def evaluate(*args, **kwargs):
        result = original_evaluate(*args, **kwargs)
        if result is not None:
            decoded.append((kwargs["profile"].feature_basis, kwargs["decision"]))
        return result

    monkeypatch.setattr(repair, "_repair_one_elite", visit)
    monkeypatch.setattr(repair, "_evaluate_neighbor", evaluate)
    result = run_case("tiny", "min_changeover")
    assert result["status"] == "passed"
    # Keep the measured two-changeover quality floor while repair and IG share the phase by time.
    assert result["improved"]["objective_score"] == [0.0, 2.0, 2.0, 15.5, 35.5, 26.0]
    assert result["counts"]["graph_decode_count"] + result["counts"]["repair_decode_count"] <= 60
    pool = visits[0][0]
    assert len(pool.elites) == len({elite["fingerprint"].output_fingerprint for elite in pool.elites}) == 3
    assert any(len(elite["neighborhood"].variants) > 1 for elite in pool.elites)
    assert any(value > 0 for value in pool.report["repair_round_improvements"])
    per_round = {}
    for _pool, elite, round_index, start, end in visits:
        assert 0 <= end - start <= 8, "the eight-item cap covers all basis variants together"
        per_round.setdefault(round_index, []).append(id(elite))
    assert all(len(parents) == len(set(parents)) <= 3 for parents in per_round.values())
    assert len(decoded) == len(set(decoded)) == result["counts"]["repair_decode_count"]
    by_decision = {}
    for basis, decision in decoded:
        by_decision.setdefault(decision, set()).add(basis)
    assert any(len(bases) > 1 for bases in by_decision.values()), "different bases require an explicit equivalence proof"


def test_same_parent_in_distinct_feature_bases_keeps_both_repair_opportunities(monkeypatch):
    profiles = {profile.slug: profile for profile in graph_ready_v2_profiles(max_candidate_profiles=60)[0]}
    baseline, enhanced = profiles["v2_edd"], profiles["v2_successor_edd"]
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                            batches=batches, start_dt=START_DT)
    parent = run_production_repair_case(clock=lambda: 0.0)["best"]
    seen_metrics = []
    original = repair.build_repair_portfolio

    def build(candidate, **kwargs):
        seen_metrics.append(kwargs["metrics_by_op_id"])
        return original(candidate, **kwargs)

    monkeypatch.setattr(repair, "build_repair_portfolio", build)
    pool = repair.EliteRepairPool(limits=EliteRepairLimits(top_k=2), objective_name="min_overdue",
                                  operations=operations, metrics_by_op_id=metrics, start_dt=START_DT,
                                  seed=0, best=None, report_state=None, graph_context=context)
    pool.observe(parent, baseline)
    pool.observe(parent, enhanced)
    pool.observe(parent, baseline)
    assert len(pool.elites) == pool.report["eligible_elites"] == 1
    assert pool.elites[0]["candidate"] is parent
    assert set(pool.elites[0]["neighborhood"].feature_bases) == {baseline.feature_basis, enhanced.feature_basis}
    assert seen_metrics == [select_profile_metrics(metrics, profile=baseline), metrics]
    assert len({elite["fingerprint"].output_fingerprint for elite in pool.elites}) == 1


@pytest.mark.parametrize("top_k", [1, 2, 3])
def test_basis_diversity_uses_existing_top_k_and_fills_remaining_slots_by_score(monkeypatch, top_k):
    profiles = {profile.slug: profile for profile in graph_ready_v2_profiles(max_candidate_profiles=60)[0]}
    pool = repair.EliteRepairPool(limits=EliteRepairLimits(top_k=top_k), objective_name="min_overdue",
                                  operations=[], metrics_by_op_id={}, start_dt=START_DT,
                                  seed=0, best=None, report_state=None)
    monkeypatch.setattr(pool, "fingerprint", lambda candidate: SimpleNamespace(output_fingerprint=candidate["id"]))
    monkeypatch.setattr(pool, "make_elite", lambda candidate, profile: {
        "candidate": candidate, "profile": profile,
        "neighborhood": SimpleNamespace(candidate_count=1, feature_bases=(profile.feature_basis,))})
    for index, score in enumerate((10, 11, 12, 1, 2, 3)):
        template = profiles["v2_edd" if index < 3 else "v2_successor_edd"]
        profile = replace(template, slug="candidate_" + str(index), profile_order=index)
        pool.observe({"id": str(index), "score": (0, score),
                      "summary": SimpleNamespace(success=True, failed_ops=0)}, profile)
        assert len(pool.elites) <= top_k
    assert [elite["candidate"]["score"][1] for elite in pool.elites] == {
        1: [1], 2: [1, 10], 3: [1, 2, 10]}[top_k]
    assert pool.report["eligible_elites"] == 6
    assert pool.report["skipped_elites_by_top_k"] == pool.report["skipped_neighbors_by_top_k"] == 6 - top_k


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3"])
def test_round_limit_rejects_invalid_configuration(value):
    with pytest.raises(ValidationError):
        resolve_elite_repair_limits({"graph_ready_optimization": {"elite_repair": {"max_rounds": value}}}, enabled=True)


def test_round_limit_is_bounded_independently_of_time_budget():
    limits = resolve_elite_repair_limits({"graph_ready_optimization": {"elite_repair": {"max_rounds": 999}}}, enabled=True)
    assert limits.max_rounds == 8
