"""Graph candidates open the rule pool only where the rule can still decide a pick (2026-09-18).

SGS orders candidates by ``(penalty, *graph_key, *dispatch_key)``: with pairwise distinct graph
keys the dispatch rule never breaks a tie, so every rule start decodes the same schedule and a
graph tier decodes the configured rule only. Ties hand the pick to the rule key, so the registry
rules and the ATC k ladder are all worth a start. The graph stages then build on the rule the
incumbent adopted, and GRASP/IG starts never rotate a rule the batch-order decode ignores.
"""

from __future__ import annotations

import random
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithms.sort_strategies import SortStrategy
from core.services.scheduler.run import optimizer_multi_start as multi
from core.services.scheduler.run.optimizer_candidate_phases import (
    graph_phase_dispatch_rule,
    run_heuristic_candidate_phases,
)
from core.services.scheduler.run.optimizer_grasp_ig_specs import build_grasp_ig_candidate_specs
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer_search_state import OptimizerSearchState
from core.services.scheduler.run.schedule_optimizer import _adopted_dispatch_rule
from tests.algorithm.test_optimizer_multi_start_budget_integration import KEYS, REGISTRY, _run
from tests.algorithm.test_optimizer_multi_start_decision_dedup import _inputs

POOL = dispatch_rule_search_pool(REGISTRY)


def _scope(keys: Dict[int, Any], *, score_enabled: Any = True) -> Dict[str, Any]:
    scope = multi.graph_rule_search_scope({"score_enabled": score_enabled, "graph_priority_key_by_op_id": keys})
    assert scope is not None
    return scope


def test_scope_is_absent_without_a_graph_context() -> None:
    assert multi.graph_rule_search_scope(None) is None


def test_pairwise_distinct_graph_keys_prove_the_rule_irrelevant() -> None:
    scope = _scope({1: (0.0, 2.0), 2: (1.0, 2.0), 3: (1.0, 3.0)})
    assert scope["policy"] == multi.GRAPH_RULE_SCOPE_CONFIGURED_ONLY
    assert scope["reason"] == "graph_keys_pairwise_distinct"
    assert (scope["operation_count"], scope["distinct_key_count"]) == (3, 3)


def test_graph_key_ties_open_the_registry_and_the_ladder() -> None:
    scope = _scope({1: (0.0,), 2: (0.0,), 3: (1.0,)})
    assert scope["policy"] == multi.GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER
    assert scope["reason"] == "graph_key_ties"
    assert (scope["operation_count"], scope["distinct_key_count"]) == (3, 2)


@pytest.mark.parametrize("context, reason", [
    ({"score_enabled": False, "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)}}, "graph_score_disabled"),
    ({"graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)}}, "graph_score_disabled"),
    ({"score_enabled": True}, "graph_keys_missing"),
    ({"score_enabled": True, "graph_priority_key_by_op_id": {}}, "graph_keys_missing"),
    ({"score_enabled": True, "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0, 2.0)}}, "graph_keys_not_uniform_finite"),
    ({"score_enabled": True, "graph_priority_key_by_op_id": {1: (float("nan"),), 2: (1.0,)}}, "graph_keys_not_uniform_finite"),
    ({"score_enabled": True, "graph_priority_key_by_op_id": {1: "0", 2: (1.0,)}}, "graph_keys_not_uniform_finite"),
    ({"score_enabled": True, "graph_priority_key_by_op_id": {1: (True,), 2: (1.0,)}}, "graph_keys_not_uniform_finite"),
])
def test_unprovable_contexts_keep_the_whole_pool_and_say_why(context, reason) -> None:
    scope = multi.graph_rule_search_scope(context)
    assert scope is not None
    assert scope["policy"] == multi.GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER and scope["reason"] == reason


def test_rule_list_follows_the_scope_and_the_dispatch_mode() -> None:
    configured_only = {"policy": multi.GRAPH_RULE_SCOPE_CONFIGURED_ONLY}
    assert multi._dispatch_rules_for_mode("sgs", "slack", REGISTRY, graph_rule_scope=configured_only) == ["slack"]
    assert multi._dispatch_rules_for_mode("sgs", "slack", REGISTRY, graph_rule_scope=None) == list(POOL)
    assert multi._dispatch_rules_for_mode("sgs", "cr", REGISTRY, graph_rule_scope=_scope({1: (0.0,), 2: (0.0,)})) == (
        ["cr"] + [rule for rule in POOL if rule != "cr"]
    )
    assert multi._dispatch_rules_for_mode("batch_order", "slack", REGISTRY, graph_rule_scope=None) == ["slack"]


def test_graph_tier_without_ties_starts_the_configured_rule_only(schema_conn) -> None:
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn, graph=True)
    inputs["graph_ready_context"]["score_enabled"] = True
    best, state, attempts = _run(inputs)
    assert best is not None and best["summary"].failed_ops == 0
    assert state.candidate_profile is not None
    efficiency = state.candidate_profile["multi_start_efficiency"]
    assert efficiency["graph_rule_scope"]["policy"] == multi.GRAPH_RULE_SCOPE_CONFIGURED_ONLY
    assert efficiency["configured_candidates"] == len(KEYS)
    # Every strategy builds the same two-batch order: one decode, the rest pruned as equivalent.
    assert efficiency["decoded_candidates"] == state.evaluated_candidates == 1
    assert efficiency["predecode_pruned_candidates"] == len(KEYS) - 1
    assert {row["dispatch_rule"] for row in attempts if row.get("candidate_status") == "pruned"} == {"slack"}


def test_graph_tier_with_ties_starts_the_registry_and_the_ladder(schema_conn) -> None:
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn, graph=True)
    inputs["graph_ready_context"]["score_enabled"] = True
    inputs["graph_ready_context"]["graph_priority_key_by_op_id"] = {1: (0.0,), 2: (0.0,)}
    best, state, attempts = _run(inputs)
    assert best is not None and best["summary"].failed_ops == 0
    assert state.candidate_profile is not None
    efficiency = state.candidate_profile["multi_start_efficiency"]
    assert efficiency["graph_rule_scope"]["policy"] == multi.GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER
    assert efficiency["configured_candidates"] == len(KEYS) * len(POOL)
    # Each rule token is a distinct decision; the configured rule comes first and the ladder is
    # ordered nearest to the default k first, so a short slice truncates the far end.
    assert efficiency["decoded_candidates"] == state.evaluated_candidates == len(POOL)
    started = [row["dispatch_rule"] for row in attempts if str(row.get("tag", "")).startswith("start:") and row.get("candidate_status") != "pruned"]
    assert started == list(POOL)


def test_graph_phase_decodes_with_the_incumbent_rule_or_the_configured_one() -> None:
    assert graph_phase_dispatch_rule({"dispatch_mode": "sgs", "dispatch_rule": "atc:k=4.0"}, configured_rule="slack") == ("atc:k=4.0", "incumbent")
    assert graph_phase_dispatch_rule({"dispatch_mode": "batch_order", "dispatch_rule": "cr"}, configured_rule="slack") == ("slack", "configured")
    assert graph_phase_dispatch_rule({"dispatch_mode": "sgs", "dispatch_rule": ""}, configured_rule="Slack") == ("slack", "configured")
    assert graph_phase_dispatch_rule(None, configured_rule="cr") == ("cr", "configured")


def test_graph_phase_receives_the_adopted_rule_and_reports_its_source() -> None:
    received: List[Dict[str, Any]] = []

    def _graph_phase(**kwargs: Any) -> Dict[str, Any]:
        received.append(kwargs)
        return kwargs["best"]

    incumbent = {"dispatch_mode": "sgs", "dispatch_rule": "atc:k=16.0", "order": ["B1", "B2"], "score": (0.0,)}
    state = OptimizerSearchState(best=incumbent)
    report_state = OptimizationSearchReportState("graph_ready", 7, 1, "min_overdue", 1000.0)
    runtime = OptimizerRuntime(
        scheduler_factory=lambda *a, **k: None, clock=lambda: 1000.0, rng_factory=random.Random,
        run_ortools_warmstart=lambda **k: None, run_multi_start=lambda **k: None, run_local_search=lambda **k: None,
        run_grasp_ig_candidates=None, run_graph_ready_candidates=_graph_phase,
    )
    optimizer_cfg = SimpleNamespace(
        algo_mode="improve", dispatch_rule="slack", strategy_enum=SortStrategy.PRIORITY_FIRST, strategy_params={},
        objective_name="min_overdue", valid_dispatch_rules=list(REGISTRY),
    )
    best = run_heuristic_candidate_phases(
        runtime=runtime, optimizer_cfg=optimizer_cfg, candidate_profile=SimpleNamespace(seed=7, candidate_construction={}),
        state=state, scheduler=None, algo_ops_to_schedule=[], batches={}, start_dt=datetime(2026, 1, 1, 8, 0, 0), end_date=None, downtime_map={},
        seed_sr_list=[], build_order=lambda *_a: [], dispatch_modes=["sgs"], resource_pool=None, deadline=2000.0,
        optimizer_algo_stats={}, t_begin=1000.0, readiness_gate_enabled=False, strict_mode=True,
        graph_ready_context={"score_enabled": True}, search_report_state=report_state, schedule_fn=lambda *a, **k: None,
    )
    assert best is incumbent
    assert received and received[0]["dispatch_rule_cfg"] == "atc:k=16.0"
    assert report_state.candidate_profile is not None
    assert report_state.candidate_profile["graph_phase_dispatch_rule"] == "atc:k=16.0"
    assert report_state.candidate_profile["graph_phase_dispatch_rule_source"] == "incumbent"


def _specs(dispatch_mode: str) -> List[Dict[str, Any]]:
    construction = {
        "grasp": {"effective_restarts": 3, "effective_rcl_size": 2},
        "iterated_greedy": {"effective_restarts": 2, "effective_destruction_size": 1},
    }
    return build_grasp_ig_candidate_specs(
        base_order=["B1", "B2", "B3"], parent_order=["B3", "B2", "B1"], version=5, candidate_construction=construction,
        dispatch_rule_cfg="slack", valid_dispatch_rules=list(REGISTRY), rng_factory=random.Random, dispatch_mode=dispatch_mode,
    )


def test_grasp_ig_starts_rotate_rules_only_when_the_decode_consumes_them() -> None:
    batch_order = _specs("batch_order")
    assert [spec["dispatch_mode"] for spec in batch_order] == ["batch_order"] * 5
    assert {spec["dispatch_rule"] for spec in batch_order} == {"slack"}
    sgs = _specs("sgs")
    assert [spec["dispatch_mode"] for spec in sgs] == ["sgs"] * 5
    assert [spec["dispatch_rule"] for spec in sgs] == ["slack", "cr", "atc", "slack", "cr"]


def test_adopted_rule_is_the_configured_rule_unless_the_adopted_mode_is_sgs() -> None:
    assert _adopted_dispatch_rule({"dispatch_rule": "cr"}, adopted_mode="batch_order", configured_rule="slack") == "slack"
    assert _adopted_dispatch_rule({"dispatch_rule": "atc:k=8.0"}, adopted_mode="sgs", configured_rule="slack") == "atc:k=8.0"
    assert _adopted_dispatch_rule({}, adopted_mode="sgs", configured_rule="slack") == "slack"
