"""回归测试：图 ready 候选搜索合同。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_candidates import context_for_profile, priority_key_for_metric
from core.services.scheduler.run.optimizer_graph_ready_context import (
    graph_node_metrics_by_op_id,
    validate_graph_ready_context,
)
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_GENERATED_ORIGIN,
    GraphReadyWeightProfile,
    default_weight_profiles,
    graph_ready_v2_profiles,
    graph_ready_weight_profile_summary,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from tests._support.optimizer_graph_ready_benchmark import (
    ContinuousCalendar,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
    run_graph_ready_flexible_machine_metric_case,
    run_graph_ready_real_sgs_case,
)
from tests._support.optimizer_graph_ready_v2_benchmark import (
    _v2_row_passes,
    graph_ready_v2_benchmark_context,
    run_graph_ready_v2_real_sgs_case,
)

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        self._now += 0.01
        return self._now


def _op(op_id: int, batch_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=op_id, batch_id=batch_id)


def _result(op_id: int, batch_id: str, offset: int) -> ScheduleResult:
    start_time = _START + timedelta(hours=offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-{op_id}",
        batch_id=batch_id,
        seq=op_id * 10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name="cut",
    )


def _summary(results: List[ScheduleResult], *, failed_ops: int = 0) -> ScheduleSummary:
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=len(results),
        scheduled_ops=len(results),
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _batches() -> Dict[str, Any]:
    return {
        batch_id: SimpleNamespace(batch_id=batch_id, priority="normal", due_date="2026-01-10", ready_status="yes")
        for batch_id in ("B1", "B2")
    }


def _graph_v2_metric(index: int = 0) -> Dict[str, Any]:
    return {
        "is_on_critical_path": False,
        "critical_path_rank": None,
        "impact_count": 0,
        "generation_index": int(index),
        "downstream_critical_minutes": 0,
        "bottleneck_machine_score": 1.0,
    }


def _graph_v2_priority_metric(**overrides: Any) -> Dict[str, Any]:
    row = _graph_v2_metric()
    row.update(
        {
            "due_deadline_hours": 24.0,
            "due_pressure": 0.5,
            "slack_hours": 12.0,
            "remaining_work_hours": 8.0,
            "saveability": 0.5,
            "processing_time_rank": 0.0,
            "sacrifice_penalty": 0.0,
            "critical_ratio": 3.0,
            "bottleneck_due_gate": 0.5,
        }
    )
    row.update(overrides)
    return row


def _v2_profile(formula_slug: str) -> GraphReadyWeightProfile:
    return GraphReadyWeightProfile(
        slug="test_v2_" + formula_slug,
        profile_order=0,
        raw_weights={
            "critical_path": 0.0,
            "successor_count": 0.0,
            "downstream_work_hours": 0.0,
            "bottleneck_machine": 0.0,
        },
        effective_weights={
            "critical_path": 0.0,
            "successor_count": 0.0,
            "downstream_work_hours": 0.0,
            "bottleneck_machine": 0.0,
        },
        candidate_origin=GRAPH_READY_V2_GENERATED_ORIGIN,
        candidate_policy="objective_aware_portfolio",
        formula_slug=formula_slug,
        formula_version="graph_ready_v2_objective_features_v2",
        jitter_seed=0,
    )


def _context() -> Dict[str, Any]:
    return {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 0, 1), 2: (1, 0, 2)},
        "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)},
        "node_metrics_by_op_id": {
            1: {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 1,
                "downstream_critical_minutes": 60,
                "bottleneck_machine_score": 2.0,
            },
            2: {
                "is_on_critical_path": False,
                "critical_path_rank": 1,
                "impact_count": 0,
                "downstream_critical_minutes": 0,
                "bottleneck_machine_score": 1.0,
            },
        },
    }


def _candidate(results: List[ScheduleResult], *, failed_ops: int = 0) -> Dict[str, Any]:
    metrics = compute_metrics(results, _batches())
    return {
        "results": results,
        "summary": _summary(results, failed_ops=failed_ops),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": metrics,
        "score": (float(failed_ops),) + objective_score(_OBJECTIVE, metrics),
        "algo_stats": {},
    }


def _state() -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile="graph_ready",
        seed=42,
        time_budget_seconds=5,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
    )


def _same_schedule(*args: Any, **kwargs: Any):
    results = [_result(1, "B1", 0), _result(2, "B2", 1)]
    return results, _summary(results), kwargs["strategy"], dict(kwargs.get("strategy_params") or {})


def test_graph_ready_weight_profile_summary_lists_nine_profiles() -> None:
    summary = graph_ready_weight_profile_summary()
    assert summary["effective_weight_profile_count"] == 9
    assert summary["weight_profile_slugs"] == [
        "balanced",
        "critical_path_first",
        "successor_fanout_first",
        "downstream_work_first",
        "bottleneck_relief",
        "critical_bottleneck",
        "fanout_downstream",
        "bottleneck_downstream",
        "graph_neutral",
    ]
    assert summary["selection_tiebreaker"] == [
        "failed_ops",
        "objective_score",
        "best_fingerprint_changed",
        "runtime_ms",
        "candidate_origin",
    ]


def test_graph_ready_context_rejects_cycle_and_extra_keys() -> None:
    bad = _context()
    bad["predecessor_op_ids_by_op_id"] = {1: {2}, 2: {1}}
    bad["successor_op_ids_by_op_id"] = {1: {2}, 2: {1}}
    with pytest.raises(ValidationError, match="环形"):
        validate_graph_ready_context(bad, algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")])

    bad = _context()
    bad["sort_key_by_op_id"][3] = (2, 0, 3)
    with pytest.raises(ValidationError, match="完全一致"):
        validate_graph_ready_context(bad, algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")])


def test_graph_ready_requires_node_metrics_for_weight_grid() -> None:
    bad = _context()
    bad.pop("node_metrics_by_op_id")
    with pytest.raises(ValidationError, match="node_metrics_by_op_id"):
        graph_node_metrics_by_op_id(bad)


def test_graph_ready_rejects_missing_bottleneck_machine_metric_loudly() -> None:
    bad = graph_ready_benchmark_context(include_bottleneck=False)
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    with pytest.raises(ValidationError, match="bottleneck_machine_score"):
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=42,
            scheduler=GreedyScheduler(calendar_service=ContinuousCalendar()),
            algo_ops_to_schedule=graph_ready_benchmark_operations(),
            batches={
                "B_LONG": _batches()["B1"],
                "B_MED": _batches()["B2"],
                "B_SHORT_A": _batches()["B1"],
                "B_SHORT_B": _batches()["B2"],
            },
            start_dt=_START,
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            base_strategy=SortStrategy.PRIORITY_FIRST,
            base_params={},
            build_order=lambda _strategy, _params: ["B_LONG", "B_MED", "B_SHORT_A", "B_SHORT_B"],
            dispatch_rule_cfg="slack",
            resource_pool=None,
            objective_name=_OBJECTIVE,
            deadline=2000.0,
            attempts=[],
            improvement_trace=[],
            optimizer_algo_stats={},
            t_begin=1000.0,
            readiness_gate_enabled=False,
            strict_mode=True,
            graph_ready_context=bad,
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=_state(),
        )


def test_graph_ready_weight_grid_uses_bottleneck_metric_in_priority_keys() -> None:
    metrics_by_op_id = graph_ready_benchmark_context()["node_metrics_by_op_id"]
    profiles, truncated, reason = default_weight_profiles(max_weight_profiles=9)
    assert truncated is False
    assert reason is None

    orders = {
        profile.slug: tuple(
            sorted(
                metrics_by_op_id,
                key=lambda op_id: priority_key_for_metric(metrics_by_op_id[op_id], profile=profile),
            )
        )
        for profile in profiles
    }

    assert len(set(orders.values())) >= 3
    assert orders["downstream_work_first"][0] == 1
    assert orders["successor_fanout_first"][0] == 2
    assert orders["bottleneck_relief"][0] == 3


def test_graph_ready_candidates_run_real_sgs_weight_grid() -> None:
    row = run_graph_ready_real_sgs_case(seed=0)

    assert row["status"] == "passed"
    assert row["candidate_profile_count"] == 9
    assert row["evaluated_candidates"] >= 10
    assert row["distinct_candidates"] >= 3
    assert row["accepted_distinct_candidates"] >= 2
    assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])
    assert row["best_origin"] == "graph_ready_weight_grid"
    assert tuple(row["objective_score"]) < tuple(row["baseline_objective_score"])
    assert row["best_order"] != row["baseline_order"]


def test_graph_ready_v2_context_adds_objective_aware_features() -> None:
    metrics_by_op_id = graph_ready_v2_benchmark_context()["node_metrics_by_op_id"]
    row = metrics_by_op_id[1]

    for field in (
        "due_pressure",
        "slack_hours",
        "remaining_work_hours",
        "saveability",
        "processing_time_rank",
        "sacrifice_penalty",
        "bottleneck_on",
        "bottleneck_release",
    ):
        assert field in row
    assert "residual_capacity_hours" not in row
    assert row["remaining_work_hours"] == 12.0
    assert row["sacrifice_penalty"] > metrics_by_op_id[2]["sacrifice_penalty"]
    assert row["graph_ready_v2_feature_version"] == "graph_ready_v2_objective_features_v2"


def test_graph_ready_v2_remaining_work_sums_only_schedulable_batch_operations() -> None:
    operations = [
        SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B1", setup_hours=5.0, unit_hours=0.0),
        SimpleNamespace(id=3, batch_id="B1", setup_hours=99.0, unit_hours=0.0),
    ]
    metrics = {1: _graph_v2_metric(0), 2: _graph_v2_metric(1)}
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(metrics, operations=operations, batches=batches, start_dt=_START)

    assert set(enriched) == {1, 2}
    assert enriched[1]["remaining_work_hours"] == 7.0
    assert enriched[2]["remaining_work_hours"] == 7.0


def test_graph_ready_v2_duplicate_normalized_metric_ids_fail_loud() -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=0.0)
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)}

    with pytest.raises(ValidationError, match="重复 node_metrics_by_op_id"):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric(0), "1": _graph_v2_metric(1)},
            operations=[op],
            batches=batches,
            start_dt=_START,
        )


@pytest.mark.parametrize("missing_field", ["unit_hours", "setup_hours", "quantity"])
def test_graph_ready_v2_required_duration_fields_fail_loud(missing_field: str) -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=3.0)
    batch = SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)
    if missing_field == "quantity":
        delattr(batch, missing_field)
    else:
        delattr(op, missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches={"B1": batch},
            start_dt=_START,
        )


@pytest.mark.parametrize("nonfinite", [float("inf"), float("-inf"), float("nan")])
@pytest.mark.parametrize("field_name", ["setup_hours", "unit_hours", "quantity"])
def test_graph_ready_v2_nonfinite_duration_fields_fail_loud(field_name: str, nonfinite: float) -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=3.0)
    batch = SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)
    if field_name == "quantity":
        batch.quantity = nonfinite
    else:
        setattr(op, field_name, nonfinite)

    with pytest.raises(ValidationError, match=field_name):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches={"B1": batch},
            start_dt=_START,
        )


def test_graph_ready_v2_priority_normalization_is_translation_invariant() -> None:
    profile = _v2_profile("edd")
    metrics = {
        1: _graph_v2_priority_metric(due_deadline_hours=24.0, slack_hours=12.0),
        2: _graph_v2_priority_metric(due_deadline_hours=48.0, slack_hours=36.0),
    }
    shifted = {
        op_id: dict(row, due_deadline_hours=row["due_deadline_hours"] + 1000.0, slack_hours=row["slack_hours"] + 1000.0)
        for op_id, row in metrics.items()
    }

    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]
    shifted_keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=shifted, profile=profile)["graph_priority_key_by_op_id"]

    assert tuple(sorted(keys, key=lambda op_id: keys[op_id])) == (1, 2)
    assert tuple(sorted(shifted_keys, key=lambda op_id: shifted_keys[op_id])) == (1, 2)
    assert keys[1][0] == shifted_keys[1][0] == 0.0
    assert keys[2][0] == shifted_keys[2][0] == 1.0


def test_graph_ready_v2_saveability_formula_prioritizes_more_saveable_batch() -> None:
    profile = _v2_profile("saveability")
    metrics = {
        1: _graph_v2_priority_metric(saveability=0.9, remaining_work_hours=2.0),
        2: _graph_v2_priority_metric(saveability=0.2, remaining_work_hours=10.0),
    }

    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]

    assert tuple(sorted(keys, key=lambda op_id: keys[op_id])) == (1, 2)


@pytest.mark.parametrize(
    "formula_slug, metric_overrides, match",
    [
        ("unknown_formula", {}, "不支持候选公式"),
        ("edd", {"due_pressure": -1.0}, "必须是非负数"),
        ("edd", {"remaining_work_hours": 0.0}, "必须大于 0"),
    ],
)
def test_graph_ready_v2_bad_formula_or_bad_features_fail_loud(
    formula_slug: str,
    metric_overrides: Dict[str, Any],
    match: str,
) -> None:
    metrics = {1: _graph_v2_priority_metric(**metric_overrides)}

    with pytest.raises(ValidationError, match=match):
        context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=_v2_profile(formula_slug))


def test_graph_ready_v2_missing_feature_fails_loud() -> None:
    metric = _graph_v2_priority_metric()
    metric.pop("due_pressure")

    with pytest.raises(ValidationError, match="due_pressure"):
        context_for_profile(graph_ready_context={}, metrics_by_op_id={1: metric}, profile=_v2_profile("edd"))


def test_graph_ready_v2_profiles_include_named_candidate_families() -> None:
    profiles, truncated, reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=3)
    by_slug = {profile.slug: profile for profile in profiles}

    assert truncated is False
    assert reason is None
    assert by_slug["v2_edd"].formula_slug == "edd"
    assert by_slug["v2_spt"].formula_slug == "spt"
    assert by_slug["v2_min_slack"].formula_slug == "min_slack"
    assert by_slug["v2_critical_ratio"].formula_slug == "critical_ratio"
    assert by_slug["v2_atc_like"].formula_slug == "atc_like"
    assert by_slug["v2_saveability"].formula_slug == "saveability"
    assert by_slug["v2_sacrifice_long"].formula_slug == "sacrifice_long"
    assert by_slug["v2_graph_due_hybrid"].formula_slug == "graph_due_hybrid"
    assert by_slug["v2_bottleneck_due_gated"].formula_slug == "bottleneck_due_gated"
    assert by_slug["v2_seeded_micro_perturbation"].formula_slug == "micro_perturbation"


def test_graph_ready_v2_runs_real_sgs_and_keeps_repair_attribution_separate() -> None:
    v1 = run_graph_ready_real_sgs_case(seed=0)
    no_repair = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=False)
    with_repair = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=True)

    assert no_repair["status"] == "passed"
    assert with_repair["status"] == "passed"
    assert no_repair["algorithm_profile"] == "graph_ready_v2_no_repair"
    assert with_repair["algorithm_profile"] == "graph_ready_v2_with_repair"
    assert no_repair["best_origin"] == "graph_ready_v2_generated"
    assert no_repair["formula_versions"] == ["graph_ready_v1", "graph_ready_v2_objective_features_v2"]
    assert no_repair["comparison_to_graph_ready_v1"]["status"] == "improved"
    assert no_repair["oracle_status"] == "not_run"
    assert no_repair["gap_to_oracle_pct"] is None
    assert no_repair["accepted_distinct_candidates"] == len(no_repair["accepted_output_fingerprints"])
    assert with_repair["repair_scope"] == "benchmark_support_only_not_core"
    assert with_repair["accepted_distinct_candidates"] == len(with_repair["accepted_output_fingerprints"])
    assert "saveability" in no_repair["candidate_families"]
    assert with_repair["repair_evaluated_candidates"] > 0
    assert tuple(no_repair["objective_score"]) < tuple(v1["objective_score"])
    assert tuple(with_repair["objective_score"]) <= tuple(no_repair["objective_score"])


def test_graph_ready_v2_row_status_rejects_v1_origin_or_non_improvement() -> None:
    row = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=False)

    v1_origin = dict(row)
    v1_origin["best_origin"] = "graph_ready_weight_grid"
    assert _v2_row_passes(v1_origin) is False

    not_better_than_v1 = dict(row)
    not_better_than_v1["comparison_to_graph_ready_v1"] = {"status": "same"}
    not_better_than_v1["v1_reference_objective_score"] = list(not_better_than_v1["objective_score"])
    assert _v2_row_passes(not_better_than_v1) is False


def test_graph_ready_v2_seeded_micro_perturbation_changes_candidate_order_without_worse_score() -> None:
    rows = [run_graph_ready_v2_real_sgs_case(seed=seed, with_repair=False) for seed in range(8)]
    orders = {tuple(row["best_order"]) for row in rows}
    v1_score = tuple(run_graph_ready_real_sgs_case(seed=0)["objective_score"])

    assert len(orders) > 1
    assert all(row["best_origin"] == "graph_ready_v2_generated" for row in rows)
    assert all(tuple(row["objective_score"]) < v1_score for row in rows)


def test_graph_ready_v2_micro_perturbation_keeps_due_pressure_ahead_of_jitter() -> None:
    # 门控合同:micro_perturbation 的 jitter 必须排在主交期目标(牺牲度、交期压力)之后,不得跨交期分数重排。
    profile = _v2_profile("micro_perturbation")
    metrics = {
        1: _graph_v2_priority_metric(sacrifice_penalty=0.0, due_pressure=0.9),
        2: _graph_v2_priority_metric(sacrifice_penalty=0.0, due_pressure=0.1),
    }
    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]

    # 两候选牺牲度相同(rank01 均 0.5),交期压力更高的 op1 应严格优先,且由第 2 位 -due_pressure_rank01 决定,而非 jitter。
    assert keys[1][0] == keys[2][0] == 0.5
    assert keys[1][1] == -1.0
    assert keys[2][1] == 0.0
    assert keys[1] < keys[2]


def test_graph_ready_flexible_machine_metric_case_keeps_candidates_from_collapsing_to_busy_machine() -> None:
    row = run_graph_ready_flexible_machine_metric_case()
    scores = row["bottleneck_scores"]

    assert row["status"] == "passed"
    assert scores["busy"] == 2.5
    assert scores["light"] == 1.0
    assert scores["flex"] == 0.707107
    assert scores["flex"] < scores["light"] < scores["busy"]


def test_graph_ready_candidates_deduplicate_same_output_fingerprint() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state.mark_candidate_accepted(baseline, origin="baseline")

    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=42,
        scheduler=SimpleNamespace(_last_algo_stats={}),
        algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")],
        batches=_batches(),
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: ["B1", "B2"],
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=_OBJECTIVE,
        deadline=2000.0,
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
    )

    assert best["candidate_origin"] == "graph_ready_base"
    assert state.rejection_summary["same_fingerprint"] >= 1


def test_graph_ready_public_projection_does_not_leak_internal_context() -> None:
    report = {
        "schema_version": 1,
        "algorithm_profile": "graph_ready",
        "candidate_profile": {
            "profile": "graph_ready",
            "candidate_strategy_families": ["graph_ready_base", "graph_ready_weight_grid"],
            "candidate_construction": {"graph_ready_optimization": graph_ready_weight_profile_summary()},
            "graph_ready_context": {
                "schedulable_op_ids": ["op:SECRET"],
                "predecessor_op_ids_by_op_id": {"op:SECRET": ["other"]},
                "graph_priority_key_by_op_id": {"op:SECRET": [1.0]},
            },
        },
    }
    public, diagnostics = project_search_report(report)
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    diagnostic_text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)

    assert "graph_ready_weight_grid" in public_text
    assert "graph_ready_optimization" in diagnostic_text
    assert "schedulable_op_ids" not in public_text
    assert "predecessor_op_ids_by_op_id" not in public_text
    assert "graph_priority_key_by_op_id" not in public_text
    assert "op:SECRET" not in public_text
