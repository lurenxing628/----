"""Production contracts for bounded graph-ready elite repair candidates."""

from __future__ import annotations

import json

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_graph_ready_candidate_payload as payload
from core.services.scheduler.run import optimizer_graph_ready_candidates as candidates
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    graph_ready_v2_profile_summary,
    graph_ready_v2_profiles,
)
from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case


def _is_repair(kwargs):
    return kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"] == "graph_ready_v2_repaired"


def _assert_complete_profile_coverage(result):
    expected = graph_ready_v2_profile_summary(max_candidate_profiles=result["max_candidates"], seed=result["seed"])
    profile = result["state"].candidate_profile["graph_ready_optimization"]
    efficiency = profile["profile_efficiency"]
    decoded = {call["strategy_params"]["graph_ready_profile"]["weight_profile_slug"]
               for call in result["calls"] if not _is_repair(call)}
    pruned = {item["profile_slug"] for item in efficiency["equivalent_profiles"]}
    assert profile["weight_profile_slugs"] == expected["weight_profile_slugs"]
    assert efficiency["configured_profiles"] == efficiency["considered_profiles"] == expected["effective_candidate_profile_count"]
    assert efficiency["profile_decodes"] == len(decoded)
    assert efficiency["predecode_pruned_profiles"] == len(pruned)
    assert not decoded.intersection(pruned)
    assert decoded.union(pruned) == set(expected["weight_profile_slugs"])
    assert efficiency["unvisited_profiles"] == efficiency["construction_rejected_profiles"] == efficiency["skipped_before_decode"] == 0
    return efficiency


def test_production_repair_uses_formal_decode_metrics_objective_and_search_report(monkeypatch):
    calls = {"metrics": 0, "score": 0}
    metrics_fn, score_fn = candidates.compute_metrics, payload.objective_score

    def metrics(*args, **kwargs):
        calls["metrics"] += 1
        return metrics_fn(*args, **kwargs)

    def score(*args, **kwargs):
        calls["score"] += 1
        return score_fn(*args, **kwargs)

    monkeypatch.setattr(candidates, "compute_metrics", metrics)
    monkeypatch.setattr(payload, "objective_score", score)
    result = run_production_repair_case()
    report = result["repair"]
    actual = [call for call in result["calls"] if _is_repair(call)]
    assert len(actual) == report["repair_evaluated_candidates"] > 0
    assert calls == {"metrics": len(result["calls"]), "score": len(result["calls"])}
    assert result["state"].evaluated_candidates == len(result["calls"]) + 1
    assert report["repair_scope"] == "production_core"
    assert all(call["dispatch_mode"] == "sgs" and call["graph_ready_context"]["enabled"] for call in actual)
    assert all(call["seed_results"] == [] for call in actual)
    assert len(result["calls"]) <= result["max_candidates"]
    pruning = report["repair_pruning_report"]
    assert pruning["generated_candidates"] == pruning["evaluated_candidates"] + pruning["pruned_candidates"]
    assert pruning["pruned_by_bound"] == pruning["pruned_by_dominance"] == 0
    assert pruning["candidate_space_total_status"] == "exact"
    assert pruning["skipped_by_budget"] == report["skipped_neighbors_by_top_k"] + pruning["candidate_space_total"] - pruning["generated_candidates"]


def test_top_k_and_neighbor_caps_are_reported():
    result = run_production_repair_case(limits={"top_k": 1, "max_neighbors_per_elite": 2, "max_rounds": 1})
    report = result["repair"]
    assert report["selected_elites"] == 1
    assert report["eligible_elites"] > 1
    assert report["skipped_elites_by_top_k"] == report["eligible_elites"] - 1
    assert report["repair_generated_candidates"] == 2
    assert report["repair_skipped_by_budget"] > 0


def test_remaining_candidate_budget_is_shared_with_reserved_repair():
    result = run_production_repair_case(max_candidates=19, clock=lambda: 0.0)
    assert len(result["calls"]) == 19
    efficiency = _assert_complete_profile_coverage(result)
    report = result["repair"]
    assert efficiency["configured_profiles"] == efficiency["considered_profiles"] == 19
    assert efficiency["profile_decodes"] + efficiency["predecode_pruned_profiles"] == 19
    assert report["repair_candidate_budget"] == result["max_candidates"] - efficiency["profile_decodes"] > 0
    assert report["repair_evaluated_candidates"] == report["repair_candidate_budget"]
    assert len(result["calls"]) == efficiency["profile_decodes"] + report["repair_evaluated_candidates"] <= result["max_candidates"]
    assert report["repair_generated_candidates"] > 0
    assert result["repair"]["repair_skipped_by_budget"] > 0
    assert result["best"]["score"] <= result["baseline"]["score"]


@pytest.mark.parametrize("cap", [1, 9])
def test_profile_cap_keeps_family_coverage_or_reports_no_elite(cap):
    result = run_production_repair_case(max_candidates=cap, clock=lambda: 0.0)
    assert len(result["calls"]) == cap
    report = result["repair"]
    if cap == 1:
        assert report["repair_status"] == "skipped_no_elite"
        assert report["selected_elites"] == report["repair_evaluated_candidates"] == 0
    else:
        profiles = [call["strategy_params"]["graph_ready_profile"] for call in result["calls"] if not _is_repair(call)]
        assert (profiles[0]["weight_profile_slug"], profiles[0]["formula_version"]) == ("balanced", "graph_ready_v1")
        assert (profiles[1]["weight_profile_slug"], profiles[1]["formula_version"], profiles[1]["feature_basis"]) == (
            "v2_seeded_micro_perturbation", "graph_ready_v2_objective_features_v2", "batch_workload_v1",
        )
        assert report["selected_elites"] > 0
        assert 0 < report["repair_evaluated_candidates"] <= report["repair_candidate_budget"]
        assert report["repair_skipped_by_budget"] > 0
    assert result["best"]["summary"].failed_ops == 0
    assert result["best"]["score"] <= result["baseline"]["score"]


def test_local_time_budget_stops_before_next_decode_and_reports_overrun():
    now = [0.0]

    def schedule(scheduler, **kwargs):
        if _is_repair(kwargs):
            now[0] += 0.010
        return _schedule_with_scheduler(scheduler, **kwargs)

    result = run_production_repair_case(limits={"time_budget_ms": 5}, clock=lambda: now[0], schedule_fn=schedule)
    report = result["repair"]
    assert report["repair_time_budget_ms"] == 5
    assert report["repair_evaluated_candidates"] == 1
    assert report["deadline_overrun_ms"] == 5
    assert report["repair_skipped_by_budget"] > 0


def test_global_deadline_blocks_all_repairs():
    now = [0.0]

    def schedule(scheduler, **kwargs):
        result = _schedule_with_scheduler(scheduler, **kwargs)
        profile = kwargs["strategy_params"]["graph_ready_profile"]
        if profile["formula_version"].startswith("graph_ready_v2"):
            now[0] = 1.0
        return result

    result = run_production_repair_case(clock=lambda: now[0], schedule_fn=schedule)
    assert result["repair"]["repair_status"] == "skipped_by_budget"
    assert result["repair"]["repair_time_budget_ms"] == 0
    assert result["repair"]["repair_evaluated_candidates"] == 0
    assert result["state"].deadline_reached
    # The v2 decode exhausted the budget; do not build unused neighborhoods.
    assert result["repair"]["selected_elites"] == 0
    assert result["repair"]["repair_stop_reason"] == "time_budget"
    assert all(not _is_repair(call) for call in result["calls"])
    assert len(result["calls"]) <= result["max_candidates"]
    assert result["best"]["score"] <= result["baseline"]["score"]


def test_budget_spent_during_construction_does_not_start_sgs(monkeypatch):
    now = [0.0]
    original = candidates.context_for_profile

    def build_context(**kwargs):
        result = original(**kwargs)
        if kwargs["profile"].candidate_policy == "elite_repair":
            now[0] += 0.010
        return result

    monkeypatch.setattr(candidates, "context_for_profile", build_context)
    result = run_production_repair_case(limits={"time_budget_ms": 5}, clock=lambda: now[0])
    report = result["repair"]
    assert report["repair_generated_candidates"] == 1
    assert report["repair_evaluated_candidates"] == 0
    assert report["repair_status"] == "skipped_by_budget"
    assert not any(_is_repair(call) for call in result["calls"])
    assert report["repair_pruning_report"]["rejected_candidates"] == 0


def test_repaired_origin_requires_matching_explicit_decision():
    from dataclasses import replace

    profile = next(item for item in graph_ready_v2_profiles(max_candidate_profiles=60)[0] if item.slug == "v2_edd")
    repaired = replace(profile, candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")
    for cur, order, repair_order in ((profile, ["A"], ["A"]), (repaired, ["A"], None), (repaired, ["A"], ["B"])):
        with pytest.raises(ValidationError):
            candidates._validate_repair_decision(cur, order=order, repair_order=repair_order)


def test_duplicate_decisions_pruned_before_decode():
    result = run_production_repair_case()
    report = result["repair"]
    pruning = report["repair_pruning_report"]
    assert pruning["duplicate_decision_pruned"] == report["repair_pruned_candidates"] > 0
    # A repair decision also retains its feature basis for the next neighborhood.
    # Without a cross-basis certificate, only the same basis and full inputs deduplicate.
    decisions = [(call["strategy_params"]["graph_ready_profile"]["feature_basis"], tuple(call["batch_order_override"]),
                  tuple(sorted(call["graph_ready_context"]["graph_priority_key_by_op_id"].items())),
                  tuple((op.id, op.machine_id, op.operator_id) for op in call["operations"]))
                 for call in result["calls"] if _is_repair(call)]
    assert len(decisions) == len(set(decisions)) == report["repair_evaluated_candidates"]


def test_same_decoded_output_rejected_even_without_report_state():
    captured = []

    def schedule(scheduler, **kwargs):
        if _is_repair(kwargs):
            return captured[-1]
        decoded = _schedule_with_scheduler(scheduler, **kwargs)
        captured.append(decoded)
        return decoded

    result = run_production_repair_case(schedule_fn=schedule, keep_report=False)
    report = result["repair"]
    assert report["repair_pruning_report"]["same_fingerprint_rejected"] == report["repair_evaluated_candidates"] > 0
    assert not report["repair_accepted"]
    assert report["repair_status"] == "all_candidates_rejected"


def test_equal_or_worse_score_never_accepted_even_if_comparator_prefers(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_repair as repair
    monkeypatch.setattr(repair, "candidate_is_preferred", lambda **kwargs: True)
    off = run_production_repair_case(enabled=False)
    on = run_production_repair_case()
    assert on["best"]["score"] == off["best"]["score"]
    assert not on["repair"]["repair_accepted"]
    assert on["repair"]["repair_rejection_summary"]["no_strict_improvement"] > 0


@pytest.mark.parametrize("strict", [False, True])
def test_decode_failure_is_rejected_or_fail_loud(strict):
    def schedule(scheduler, **kwargs):
        if _is_repair(kwargs):
            raise ValidationError("repair test failure", field="schedule", details={"reason": "repair_test_failure"})
        return _schedule_with_scheduler(scheduler, **kwargs)

    if strict:
        with pytest.raises(ValidationError, match="repair test failure"):
            run_production_repair_case(schedule_fn=schedule, strict_mode=True)
    else:
        result = run_production_repair_case(schedule_fn=schedule, strict_mode=False)
        report = result["repair"]
        assert report["repair_rejection_summary"]["repair_test_failure"] == report["repair_evaluated_candidates"]
        assert not report["repair_accepted"]
        assert report["repair_status"] == "all_candidates_rejected"


def test_disabled_repair_keeps_production_profile_search():
    result = run_production_repair_case(enabled=False, clock=lambda: 0.0)
    efficiency = _assert_complete_profile_coverage(result)
    assert efficiency["configured_profiles"] == efficiency["considered_profiles"] == 29
    assert efficiency["profile_decodes"] + efficiency["predecode_pruned_profiles"] == 29
    assert efficiency["profile_decodes"] == len(result["calls"]) < 29
    assert len(result["calls"]) <= result["max_candidates"]
    assert efficiency["reserved_repair_candidates"] == efficiency["reserved_repair_time_ms"] == 0
    assert result["repair"]["repair_status"] == "not_run"
    assert result["repair"]["repair_evaluated_candidates"] == 0
    assert not any(_is_repair(call) for call in result["calls"])
    assert result["best"]["summary"].failed_ops == 0
    assert result["best"]["score"] <= result["baseline"]["score"]


def test_repair_report_has_no_raw_ids_or_hashes_in_aggregate_fields():
    result = run_production_repair_case()
    report = dict(result["repair"])
    report.pop("repair_pruning_report")
    text = json.dumps(report)
    for key in ("op_id", "resource_id", result["state"].best_fingerprint, "B_LONG", "MC-BENCH"):
        assert key not in text


def test_actual_public_projection_keeps_safe_message_and_diagnostics_report():
    from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
    result = run_production_repair_case()
    final = result["state"].finalize(runtime_ms=result["runtime_ms"], attempts=result["attempts"], improvement_trace=result["trace"])
    public, diagnostics = project_search_report(final)
    message = public["profile_public"]["message"]
    assert "GraphReady 修补已启用" in message
    assert "精英上限3" in message
    assert "未得到严格更优方案" in message
    assert "预算跳过" in message and "输出重复" in message
    assert any(attempt.get("elite_repair", {}).get("repair_scope") == "production_core" for attempt in diagnostics["attempts"])
    text = json.dumps(public, ensure_ascii=False)
    for key in ("op_id", "resource_id", "rule_trace", result["state"].best_fingerprint, "B_LONG", "MC-BENCH"):
        assert key not in text


def test_real_production_strict_improvement_has_fingerprint_and_acceptance_event():
    from tests._support.optimizer_graph_ready_repair_benchmark import smtwt_repair_context
    context = smtwt_repair_context()
    before = run_production_repair_case(case=context, enabled=False, clock=lambda: 0.0)
    after = run_production_repair_case(case=context, clock=lambda: 0.0)
    assert after["best"]["score"] < before["best"]["score"]
    assert after["repair"]["repair_accepted"]
    assert after["repair"]["repair_status"] == "strict_improvement"
    assert after["state"].best_origin == "graph_ready_v2_repaired"
    assert after["state"].best_fingerprint != before["state"].best_fingerprint
    assert after["state"].best_acceptance_passed
    assert after["state"].acceptance_events[-1]["acceptance_name"] == "improve_only"
    assert after["state"].acceptance_events[-1]["accepted"]


def test_infeasible_decoded_repair_cannot_replace_feasible_best():
    from dataclasses import replace

    def schedule(scheduler, **kwargs):
        results, summary, strategy, params = _schedule_with_scheduler(scheduler, **kwargs)
        if _is_repair(kwargs):
            summary = replace(summary, failed_ops=1, success=False)
        return results, summary, strategy, params

    result = run_production_repair_case(schedule_fn=schedule)
    assert not result["repair"]["repair_accepted"]
    assert result["best"]["summary"].failed_ops == 0
    assert result["repair"]["repair_rejection_summary"]["repair_infeasible"] > 0


def test_formal_repair_sgs_keeps_fixed_seed_and_precedence():
    from dataclasses import replace
    from datetime import timedelta

    from core.algorithms import ScheduleResult, SortStrategy
    from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
    from tests._support.optimizer_graph_ready_benchmark import (
        BASE_BATCH_ORDER,
        OBJECTIVE_NAME,
        START_DT,
        _scheduler,
        graph_ready_benchmark_batches,
        graph_ready_benchmark_context,
        graph_ready_benchmark_operations,
    )

    operations, batches, context = graph_ready_benchmark_operations(), graph_ready_benchmark_batches(), graph_ready_benchmark_context()
    seed = ScheduleResult(op_id=99, op_code="FIXED", batch_id="B_LONG", seq=0,
                          machine_id="MC-BENCH", operator_id="OP-BENCH",
                          start_time=START_DT - timedelta(hours=1), end_time=START_DT, op_type_name="BENCH")
    context["fixed_op_ids"] = {99}
    context["fixed_op_sources_by_op_id"] = {99: "seed"}
    context["predecessor_op_ids_by_op_id"].update({99: set(), 1: {99}, 2: {1}})
    context["successor_op_ids_by_op_id"].update({99: {1}, 1: {2}})
    metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                             batches=batches, start_dt=START_DT, seed_results=[seed])
    profile = next(item for item in graph_ready_v2_profiles(max_candidate_profiles=60)[0] if item.slug == "v2_edd")
    profile = replace(profile, candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")
    order = list(reversed(BASE_BATCH_ORDER))
    result = candidates.evaluate_graph_ready_candidate(
        profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, scheduler=_scheduler(), strict_mode=True,
        algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={},
        start_dt=START_DT, end_date=None, downtime_map={}, order=order, seed_sr_list=[seed], dispatch_rule="slack",
        resource_pool=None, objective_name=OBJECTIVE_NAME, optimizer_algo_stats=None, schedule_fn=_schedule_with_scheduler,
        readiness_gate_enabled=False, version=0, clock=lambda: 0.0, repair_order=order,
    )
    by_id = {item.op_id: item for item in result["results"]}
    assert by_id[99] == seed
    assert by_id[1].start_time >= seed.end_time
    assert by_id[2].start_time >= by_id[1].end_time
    assert result["summary"].failed_ops == 0
    assert set(by_id) == {1, 2, 3, 4, 99}
