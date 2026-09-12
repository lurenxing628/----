"""Objective-specific candidates and operation-local due signals use real SGS."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms import SortStrategy
from core.algorithms.evaluation import objective_score
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_candidates import (
    build_v2_common_rank_cache,
    context_for_profile,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer_graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
    select_profile_metrics,
)
from core.services.scheduler.run.optimizer_graph_ready_profile_selection import resolve_graph_ready_profiles_and_metrics
from core.services.scheduler.run.optimizer_graph_ready_profiles import graph_ready_v2_profiles
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from tests._support.optimizer_graph_ready_benchmark import (
    ContinuousCalendar,
    _operation,
    _schedule_with_scheduler,
    _scheduler,
)

START = datetime(2026, 1, 1, 8)
OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")


def _batch(quantity=1, priority="normal"):
    return SimpleNamespace(quantity=quantity, priority=priority, due_date="2026-01-01", ready_date=None, ready_status="yes")


def _context(operations, predecessors=None, fixed=()):
    ids = {op.id for op in operations}
    parents = predecessors or {key: set() for key in ids}
    successors = {key: set() for key in ids.union(fixed)}
    for child, values in parents.items():
        for parent in values:
            successors[parent].add(child)
    return dict(enabled=True, schedulable_op_ids=ids, fixed_op_ids=set(fixed),
                predecessor_op_ids_by_op_id=parents, successor_op_ids_by_op_id=successors,
                sort_key_by_op_id={key: (0, key, key) for key in ids},
                graph_priority_key_by_op_id={key: (0.0,) for key in ids},
                node_metrics_by_op_id={key: dict(is_on_critical_path=False, critical_path_rank=None,
                    impact_count=0, downstream_critical_minutes=0, bottleneck_machine_score=1.0) for key in ids})


def _enrich(operations, batches, *, context=None, calendar=None, **kwargs):
    metrics = (context or _context(operations))["node_metrics_by_op_id"]
    return enrich_graph_ready_v2_metrics(metrics, operations=operations, batches=batches, start_dt=START,
                                        graph_ready_context=context, calendar_service=calendar, **kwargs)


def _evaluate(profile, operations, batches, context, metrics, objective):
    return evaluate_graph_ready_candidate(
        profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, scheduler=_scheduler(),
        strict_mode=True, algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST,
        params={}, start_dt=START, end_date=None, downtime_map={}, order=list(batches), seed_sr_list=[],
        dispatch_rule="slack", resource_pool=None, objective_name=objective, optimizer_algo_stats=None,
        schedule_fn=_schedule_with_scheduler, readiness_gate_enabled=False, version=1, clock=lambda: 0.0,
    )


def test_two_four_hour_operations_do_not_charge_first_work_against_second_window():
    class DayPolicy:
        efficiency = 1.0

        def __init__(self, dt):
            self.dt = dt

        def work_window(self):
            begin = self.dt.replace(hour=8, minute=0, second=0, microsecond=0)
            return begin, begin + timedelta(hours=8)

    calendar = SimpleNamespace(policy_for_datetime=lambda dt, operator_id=None: DayPolicy(dt))
    operations = [_operation(1, "B", hours=4), _operation(2, "B", hours=4)]
    operations[1].seq = 20
    context = _context(operations, {1: set(), 2: {1}})
    rows = _enrich(operations, {"B": _batch()}, context=context, calendar=calendar,
                   downtime_map={"MC-BENCH": [(START + timedelta(hours=4), START + timedelta(hours=6))]})
    assert [rows[key]["remaining_due_burden_hours"] for key in (1, 2)] == [8, 4]
    assert [rows[key]["due_budget_hours"] for key in (1, 2)] == [8, 4]
    assert [rows[key]["critical_ratio"] for key in (1, 2)] == [1, 1]
    assert rows[2]["residual_capacity_start_offset_hours"] == 4
    assert rows[2]["residual_capacity_hours"] == 2
    assert rows[2]["due_budget_hours"] != rows[2]["residual_capacity_hours"]


def test_piece_diamond_uses_operation_quantity_and_counts_shared_descendant_once():
    operations = [_operation(key, "B", hours=0) for key in (1, 2, 3, 4)]
    operations[0].unit_hours = 2
    for op, piece in zip(operations[1:3], ("P1", "P2")):
        op.piece_id, op.unit_hours = piece, 2
    operations[3].setup_hours = 3
    context = _context(operations, {1: set(), 2: {1}, 3: {1}, 4: {2, 3}})
    rows = _enrich(operations, {"B": _batch(quantity=4)}, context=context, calendar=ContinuousCalendar())
    assert [rows[key]["remaining_due_burden_hours"] for key in (1, 2, 3, 4)] == [15, 5, 5, 3]
    assert [rows[key]["residual_capacity_start_offset_hours"] for key in (1, 2, 3, 4)] == [0, 8, 8, 10]


def test_merged_external_same_group_is_independent_for_distinct_pieces():
    operations = [_operation(key, "B", hours=1) for key in range(1, 6)]
    for op, piece in zip(operations[1:], ("P1", "P1", "P2", "P2")):
        op.source, op.piece_id, op.ext_merge_mode = "external", piece, "merged"
        op.ext_group_id, op.ext_group_total_days = "G", 1.0
    context = _context(operations, {1: set(), 2: {1}, 3: {2}, 4: {1}, 5: {4}})
    rows = _enrich(operations, {"B": _batch(quantity=2)}, context=context)
    assert rows[1]["remaining_due_burden_hours"] == 49
    assert [rows[key]["remaining_due_burden_hours"] for key in (2, 3, 4, 5)] == [24] * 4
    assert [rows[key]["residual_capacity_start_offset_hours"] for key in (2, 3, 4, 5)] == [1] * 4


def test_fixed_predecessor_uses_seed_end_without_adding_seed_work():
    op = _operation(2, "B", hours=4)
    context = _context([op], {2: {1}}, fixed={1})
    rows = _enrich([op], {"B": _batch()}, context=context,
                   seed_results=[SimpleNamespace(op_id=1, end_time=START + timedelta(hours=6))])
    assert rows[2]["remaining_due_burden_hours"] == 4
    assert rows[2]["residual_capacity_start_offset_hours"] == 6
    assert rows[2]["due_budget_hours"] == 10


def test_predecessor_release_uses_gross_work_calendar_across_days():
    class EightHourCalendar(ContinuousCalendar):
        def add_working_hours(self, dt, hours, **kwargs):
            while hours:
                dt = max(dt, dt.replace(hour=8, minute=0, second=0))
                end = dt.replace(hour=16, minute=0, second=0)
                available = max((end - dt).total_seconds() / 3600, 0)
                used = min(available, hours)
                dt, hours = dt + timedelta(hours=used), hours - used
                if hours:
                    dt = (dt + timedelta(days=1)).replace(hour=8, minute=0, second=0)
            return dt

    operations = [_operation(1, "B", hours=12), _operation(2, "B", hours=4)]
    context = _context(operations, {1: set(), 2: {1}})
    batch = _batch()
    batch.due_date = "2026-01-02"
    rows = _enrich(operations, {"B": batch}, context=context, calendar=EightHourCalendar())
    assert rows[2]["residual_capacity_start_offset_hours"] == 28
    assert rows[2]["remaining_due_burden_hours"] == 4


def test_inconsistent_merged_group_duration_is_rejected():
    operations = [_operation(key, "B", hours=0) for key in (1, 2)]
    for op in operations:
        op.source, op.ext_merge_mode, op.ext_group_id = "external", "merged", "G"
        op.ext_group_total_days = float(op.id)
    with pytest.raises(ValidationError, match="总工时不一致"):
        _enrich(operations, {"B": _batch()}, context=_context(operations))


@pytest.mark.parametrize("parents", [{1: {2}, 2: {1}}, {1: set(), 2: {99}}, {1: set(), 2: {True}}])
def test_invalid_graph_never_becomes_linear_fallback(parents):
    operations = [_operation(key, "B", hours=1) for key in (1, 2)]
    context = _context(operations)
    context["predecessor_op_ids_by_op_id"] = parents
    with pytest.raises(ValidationError):
        _enrich(operations, {"B": _batch()}, context=context)


def test_piece_without_explicit_graph_fails_and_bad_due_remains_an_error():
    op = _operation(1, "B", hours=1)
    op.piece_id = "P1"
    with pytest.raises(ValidationError, match="Piece"):
        _enrich([op], {"B": _batch()})
    batch = _batch()
    batch.due_date = "broken"
    with pytest.raises(ValidationError, match="交期格式"):
        _enrich([op], {"B": batch}, context=_context([op]))


@pytest.mark.parametrize("objective,first,count", [
    ("min_overdue", "micro_perturbation", 29), ("min_tardiness", "spt", 29),
    ("min_weighted_tardiness", "weighted_spt", 31), ("min_changeover", "type_group", 31),
])
def test_objective_portfolio_is_bounded_and_keeps_original_candidates(objective, first, count):
    baseline = graph_ready_v2_profiles(max_candidate_profiles=60)[0]
    profiles, truncated, _ = graph_ready_v2_profiles(max_candidate_profiles=60, objective_name=objective)
    assert len(profiles) == count and not truncated
    assert {item.slug for item in baseline}.issubset({item.slug for item in profiles})
    assert [item.slug for item in profiles[:3]] == ["balanced", "v2_seeded_micro_perturbation", "v2_edd"]
    assert profiles[3].formula_slug == first and profiles[3].feature_basis == SUCCESSOR_WORKLOAD_BASIS
    assert [item.feature_basis for item in profiles[1:3]] == [BATCH_WORKLOAD_BASIS] * 2
    assert len({item.slug for item in profiles}) == count
    assert {item.objective_name for item in profiles} == {objective}
    assert len(graph_ready_v2_profiles(max_candidate_profiles=2, objective_name=objective)[0]) == 2


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_objective_reaches_profiles_features_and_real_sgs_score(objective):
    operations = [_operation(key, "B" + str(key), hours=key) for key in (1, 2, 3)]
    batches = {op.batch_id: _batch(priority="critical" if op.id == 3 else "normal") for op in operations}
    context = _context(operations)
    profiles, summary, rows = resolve_graph_ready_profiles_and_metrics(
        context["node_metrics_by_op_id"], max_weight_profiles=9, profiles_override=None,
        profile_summary_override=None, candidate_construction={"graph_ready_optimization": {
            "candidate_policy": "objective_aware_portfolio", "max_candidate_profiles": 60}},
        version=1, scheduler=_scheduler(), algo_ops_to_schedule=operations, batches=batches, start_dt=START,
        downtime_map={}, seed_sr_list=[], resource_pool=None, strict_mode=True,
        objective_name=objective, graph_ready_context=context,
    )
    assert summary["objective_name"] == objective
    assert {row["graph_ready_objective_name"] for row in rows.values()} == {objective}
    candidate = _evaluate(profiles[1], operations, batches, context, rows, objective)
    assert candidate["summary"].failed_ops == 0
    assert candidate["score"] == (0.0,) + objective_score(objective, candidate["metrics"])
    assert {row.op_id for row in candidate["results"]} == {1, 2, 3}


def test_weighted_and_changeover_formulas_change_real_sgs_decisions():
    operations = [_operation(key, "B" + str(key), hours=4) for key in (1, 2, 3, 4)]
    batches = {op.batch_id: _batch(priority="critical" if op.id == 2 else "normal") for op in operations}
    for op in operations:
        op.op_type_name = "A" if op.id in (1, 3) else "B"
    context = _context(operations)
    for key, metric in context["node_metrics_by_op_id"].items():
        metric["impact_count"] = 5 - key
    rows = _enrich(operations, batches, context=context)
    weighted = graph_ready_v2_profiles(max_candidate_profiles=60, objective_name="min_weighted_tardiness")[0][3]
    candidate = _evaluate(weighted, operations, batches, context, rows, "min_weighted_tardiness")
    assert min(candidate["results"], key=lambda row: row.start_time).op_id == 2
    profiles = graph_ready_v2_profiles(max_candidate_profiles=60, objective_name="min_changeover")[0]
    original = _evaluate(profiles[0], operations, batches, context, rows, "min_changeover")
    grouped = _evaluate(profiles[3], operations, batches, context, rows, "min_changeover")
    assert original["metrics"].changeover_count == 3
    assert grouped["metrics"].changeover_count == 1
    assert grouped["score"] < original["score"]


def test_targeted_formula_requires_its_own_feature():
    operations = [_operation(1, "B", hours=1)]
    rows = _enrich(operations, {"B": _batch()})
    rows[1].pop("weighted_processing_hours")
    profile = graph_ready_v2_profiles(max_candidate_profiles=60, objective_name="min_weighted_tardiness")[0][3]
    with pytest.raises(ValidationError, match="weighted_processing_hours"):
        context_for_profile(graph_ready_context={}, metrics_by_op_id=rows, profile=profile)


def _resolve_empty(**overrides):
    kwargs = dict(max_weight_profiles=9, profiles_override=None, profile_summary_override=None,
                  candidate_construction=None, version=1, scheduler=_scheduler(), algo_ops_to_schedule=[],
                  batches={}, start_dt=START, downtime_map={}, seed_sr_list=[], resource_pool=None, strict_mode=True)
    kwargs.update(overrides)
    return resolve_graph_ready_profiles_and_metrics({}, **kwargs)


def test_explicit_profile_override_keeps_formula_but_records_actual_objective():
    original = graph_ready_v2_profiles(max_candidate_profiles=60)[0][0]
    profiles, summary, _ = _resolve_empty(profiles_override=[original], objective_name="min_changeover")
    assert profiles[0].formula_slug == original.formula_slug
    assert profiles[0].objective_name == summary["objective_name"] == "min_changeover"
    assert original.objective_name == "min_overdue"


@pytest.mark.parametrize("policy,expected", [("weight_grid", RuntimeError), ("bad_policy", ValidationError)])
def test_config_validation_precedes_feature_budget_callback(policy, expected):
    def exhausted():
        raise RuntimeError("deadline reached")

    with pytest.raises(expected):
        _resolve_empty(candidate_construction={"graph_ready_optimization": {"candidate_policy": policy}},
                       before_metrics=exhausted)


def test_baseline_and_successor_keep_distinct_units_and_cached_priority_orders():
    operations = [_operation(1, "A", hours=4), _operation(2, "A", hours=4), _operation(3, "B", hours=6)]
    operations[1].seq = 2
    context = _context(operations, {1: set(), 2: {1}, 3: set()})
    rows = _enrich(operations, {"A": _batch(), "B": _batch()}, context=context)
    baseline = rows[2][BASELINE_ORDERING_FIELD]
    assert (baseline["remaining_due_burden_hours"], baseline["due_budget_hours"]) == (8, 16)
    assert (rows[2]["remaining_due_burden_hours"], rows[2]["due_budget_hours"]) == (4, 12)
    assert baseline["graph_ready_workload_version"] == BATCH_WORKLOAD_BASIS
    assert rows[2]["graph_ready_workload_version"] == SUCCESSOR_WORKLOAD_BASIS
    profiles = graph_ready_v2_profiles(max_candidate_profiles=60, seed=7)[0]
    cache = build_v2_common_rank_cache(rows)
    keys = {}
    for profile in profiles:
        fresh = context_for_profile(graph_ready_context=context, metrics_by_op_id=rows, profile=profile)
        cached = context_for_profile(graph_ready_context=context, metrics_by_op_id=rows, profile=profile,
                                     v2_common_rank_cache=cache)
        keys[profile.slug] = fresh["graph_priority_key_by_op_id"]
        assert cached["graph_priority_key_by_op_id"] == keys[profile.slug]
    assert keys["v2_seeded_micro_perturbation"] != keys["v2_successor_seeded_micro_perturbation"]


def test_baseline_profile_rejects_successor_only_rows_instead_of_relabeling_them():
    operations = [_operation(1, "B", hours=2)]
    context = _context(operations)
    rows = _enrich(operations, {"B": _batch()}, context=context, include_baseline_ordering=False)
    profile = graph_ready_v2_profiles(max_candidate_profiles=60)[0][1]
    with pytest.raises(ValidationError, match="整批工时特征"):
        context_for_profile(graph_ready_context=context, metrics_by_op_id=rows, profile=profile)


def test_established_edd_parent_still_generates_recorded_tardy_boundary_decision():
    from dataclasses import replace
    from time import perf_counter

    from core.algorithms import GreedyScheduler
    from core.services.scheduler.run.optimizer_graph_ready_profiles import GRAPH_READY_V2_REPAIRED_ORIGIN
    from core.services.scheduler.run.optimizer_graph_ready_repair_neighbors import build_repair_neighborhood
    from tests._support.optimizer_end_to_end_cases import case_environment, fixture_data
    from tests._support.optimizer_quality_matrix_cases import graph_context

    with case_environment(fixture_data("shift_pool"), "min_tardiness", {"seed": 0, "time_budget_seconds": 1}) as env:
        context = graph_context(env.algo_ops_to_schedule, env.batches, env.resource_pool)
        rows = enrich_graph_ready_v2_metrics(
            context["node_metrics_by_op_id"], operations=env.algo_ops_to_schedule, batches=env.batches,
            start_dt=env.start_dt_norm, calendar_service=env.cal_svc, downtime_map=env.downtime_map,
            resource_pool=env.resource_pool, graph_ready_context=context, strict_mode=True)
        profiles = {profile.slug: profile for profile in graph_ready_v2_profiles(max_candidate_profiles=60, seed=0)[0]}
        inputs = dict(graph_ready_context=context, metrics_by_op_id=rows, scheduler=GreedyScheduler(env.cal_svc, env.cfg),
                      strict_mode=True, algo_ops_to_schedule=env.algo_ops_to_schedule, batches=env.batches,
                      strategy=SortStrategy.FIFO, params={}, start_dt=env.start_dt_norm, end_date=None,
                      downtime_map=env.downtime_map, order=list(env.batches), seed_sr_list=[], dispatch_rule="slack",
                      resource_pool=env.resource_pool, objective_name="min_tardiness", optimizer_algo_stats=None,
                      schedule_fn=_schedule_with_scheduler, readiness_gate_enabled=False, version=0, clock=perf_counter)
        parent = evaluate_graph_ready_candidate(profile=profiles["v2_edd"], **inputs)
        assert parent["score"] == (0.0, 1536.5, 12.0, 3588.5, 289.5, 0.0)
        neighborhood = build_repair_neighborhood(
            parent, operations=env.algo_ops_to_schedule,
            metrics_by_op_id=select_profile_metrics(rows, profile=profiles["v2_edd"]),
            start_dt=env.start_dt_norm, seed=0, objective_name="min_tardiness")
        order = next(order for kind, order in neighborhood.neighbors() if kind == "tardy_boundary_move")
        repaired_profile = replace(profiles["v2_edd"], slug="v2_repair_tardy_boundary_move",
                                   candidate_origin=GRAPH_READY_V2_REPAIRED_ORIGIN, candidate_policy="elite_repair")
        repaired = evaluate_graph_ready_candidate(profile=repaired_profile, repair_order=order, **dict(inputs, order=order))
        assert repaired["score"] == (0.0, 1423.5, 12.0, 3058.5, 294.5, 0.0)
        enhanced = evaluate_graph_ready_candidate(profile=profiles["v2_successor_seeded_micro_perturbation"], **inputs)
        assert enhanced["score"] == (0.0, 1460.5, 11.0, 2028.0, 268.5, 0.0)
        assert enhanced["decoded_batch_order"] != parent["decoded_batch_order"]
