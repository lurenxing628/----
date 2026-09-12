"""Comparison cache isolation and single-pass graph scoring contracts."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.graph import analysis_service, resource_matching, scoring
from core.services.scheduler.run import schedule_graph_cached_projection as projections
from core.services.scheduler.run.schedule_graph_report import (
    make_cached_graph_preparation_fn,
    prepare_schedule_graph_for_dispatch,
)


def _config(weight: int = 1, *, mode: str = "on", scored: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        graph_analysis_mode=mode,
        graph_block_on_cycle="no",
        graph_critical_weight=weight * 100 if scored else 0,
        graph_impact_weight=weight if scored else 0,
        graph_downstream_weight=1 if scored else 0,
    )


def _input() -> SimpleNamespace:
    batches = {
        key: SimpleNamespace(batch_id=key, quantity=1, priority="normal")
        for key in ("B1", "B2")
    }
    operations = [
        SimpleNamespace(
            id=index,
            batch_id="B1" if index <= 20 else "B2",
            op_code="OP" + str(index),
            seq=index,
            source="internal",
            setup_hours=0.0,
            unit_hours=1.0,
            op_type_id="TURNING",
        )
        for index in range(1, 41)
    ]
    return SimpleNamespace(
        cfg=_config(),
        algo_ops=operations,
        algo_ops_to_schedule=[op for op in operations if op.id not in {1, 21}],
        batches=batches,
        frozen_op_ids={1},
        seed_results=[{"op_id": 21}],
        resource_pool={"machines_by_op_type": {"TURNING": ["MC1", "MC2"]}},
    )


def _candidate(base: SimpleNamespace, **config: Any) -> SimpleNamespace:
    values = dict(vars(base))
    values["cfg"] = _config(**config)
    return SimpleNamespace(**values)


def _without_timing(preparation: Any) -> Dict[str, Any]:
    value = asdict(preparation)
    if value["graph_analysis_public"] is not None:
        value["graph_analysis_public"].pop("time_cost_ms")
    return value


def _counted(counts: Counter, name: str, function: Any) -> Any:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        counts[name] += 1
        return function(*args, **kwargs)
    return wrapped


def test_comparison_builds_invariant_projections_once_and_validates_scores_once(monkeypatch: pytest.MonkeyPatch) -> None:
    counts: Counter = Counter()
    targets = [
        (analysis_service.ScheduleGraphAnalysisService, "analyze_linear_batches"),
        (projections, "build_graph_health_context"),
        (projections, "build_graph_ready_context"),
        (resource_matching, "summarize_operation_machine_matching"),
        (scoring, "_normalized_metric"),
    ]
    for owner, name in targets:
        monkeypatch.setattr(owner, name, _counted(counts, name, getattr(owner, name)))
    base = _input()
    prepare = make_cached_graph_preparation_fn()
    outcomes = [prepare(_candidate(base, weight=weight)) for weight in range(1, 6)]

    assert counts == {
        "analyze_linear_batches": 1,
        "build_graph_health_context": 1,
        "build_graph_ready_context": 1,
        "summarize_operation_machine_matching": 1,
        "_normalized_metric": 5 * len(base.algo_ops_to_schedule),
    }
    keys = [outcome.graph_ready_context["graph_priority_key_by_op_id"][2] for outcome in outcomes]
    assert len(set(keys)) == 5
    assert all(outcome.graph_health_context == outcomes[0].graph_health_context for outcome in outcomes)


@pytest.mark.parametrize("mode,scored", [("on", True), ("on", False), ("report", True), ("off", True)])
def test_cached_preparations_match_independent_preparations(mode: str, scored: bool) -> None:
    base = _input()
    prepare = make_cached_graph_preparation_fn()
    for weight in (1, 3, 5):
        candidate = _candidate(base, weight=weight, mode=mode, scored=scored)
        assert _without_timing(prepare(candidate)) == _without_timing(prepare_schedule_graph_for_dispatch(candidate))


def test_mutating_candidate_context_and_diagnostics_cannot_poison_cache() -> None:
    base = _input()
    prepare = make_cached_graph_preparation_fn()
    first = prepare(base)
    ready = first.graph_ready_context
    ready["schedulable_op_ids"].clear()
    ready["fixed_op_ids"].add(999)
    ready["predecessor_op_ids_by_op_id"][2].add(999)
    ready["successor_op_ids_by_op_id"][2].clear()
    ready["sort_key_by_op_id"][2] = (999, 999, 999)
    ready["fixed_op_sources_by_op_id"][1] = "changed"
    ready["graph_priority_key_by_op_id"][2] = (999.0,)
    ready["node_metrics_by_op_id"][2]["impact_count"] = 999
    first.graph_health_context["critical_path_op_ids"].clear()
    first.graph_health_context["top_impact_op_ids"].append(999)
    first.graph_analysis_public["resource_matching"]["matched_operation_count"] = 999
    first.graph_analysis_diagnostics["resource_matching"]["matches_sample"][0]["machine_id"] = "changed"

    assert _without_timing(prepare(base)) == _without_timing(prepare_schedule_graph_for_dispatch(base))


def test_report_and_unscored_on_do_not_share_different_ready_templates() -> None:
    base = _input()
    prepare = make_cached_graph_preparation_fn()
    report = prepare(_candidate(base, mode="report", scored=False))
    on = prepare(_candidate(base, mode="on", scored=False))
    assert report.graph_ready_context is None
    assert on.graph_ready_context["enabled"] is True
    assert on.graph_ready_context["score_enabled"] is False
    assert _without_timing(on) == _without_timing(prepare_schedule_graph_for_dispatch(_candidate(base, scored=False)))


def test_failed_resource_contract_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    original = resource_matching.summarize_operation_machine_matching
    calls = []

    def fail_first(nodes: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise resource_matching.GraphResourceMatchingContractError("invalid candidates")
        return original(nodes)

    monkeypatch.setattr(resource_matching, "summarize_operation_machine_matching", fail_first)
    prepare = make_cached_graph_preparation_fn()
    base = _input()
    assert prepare(base).graph_analysis_public["resource_matching"]["status"] == "error"
    assert prepare(base).graph_analysis_public["resource_matching"]["status"] == "available"
    assert len(calls) == 2


def test_each_comparison_owns_its_invariant_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    counts: Counter = Counter()
    name = "summarize_operation_machine_matching"
    monkeypatch.setattr(resource_matching, name, _counted(counts, name, getattr(resource_matching, name)))
    base = _input()
    for _index in range(2):
        prepare = make_cached_graph_preparation_fn()
        prepare(base)
        prepare(_candidate(base, weight=2))
    assert counts[name] == 2


def test_cached_invariants_do_not_skip_metric_or_weight_contracts() -> None:
    base = _input()
    cache: Dict[str, Any] = {}
    prepare_schedule_graph_for_dispatch(base, core_cache=cache)
    nodes, _edges, payload = cache["full"]
    node_id = next(node.node_id for node in nodes if node.raw["id"] == 2)
    payload["node_metrics"][node_id].pop("impact_count")
    with pytest.raises(ValidationError, match="impact_count"):
        prepare_schedule_graph_for_dispatch(base, core_cache=cache)
    candidate = _candidate(base)
    candidate.cfg.graph_impact_weight = True
    with pytest.raises(ValueError, match="graph_impact_weight"):
        prepare_schedule_graph_for_dispatch(candidate, core_cache=cache)


def _metric(**overrides: Any) -> Dict[str, Any]:
    return {
        "is_on_critical_path": True,
        "critical_path_rank": 0,
        "impact_count": 3,
        "downstream_critical_minutes": 120,
        **overrides,
    }


def test_joint_scoring_preserves_exact_bonus_and_standalone_large_integer() -> None:
    exact = 2 ** 60 + 1
    bonus, key = scoring.graph_score_components(
        _metric(downstream_critical_minutes=exact), critical_weight=0, impact_weight=0,
    )
    assert bonus == exact
    assert key == (float(-exact), 0.0)
    huge = 10 ** 1000
    assert scoring.graph_score_bonus(
        _metric(downstream_critical_minutes=huge), critical_weight=0, impact_weight=0,
    ) == huge


@pytest.mark.parametrize("field,value", [
    ("is_on_critical_path", 1), ("critical_path_rank", True),
    ("impact_count", -1), ("downstream_critical_minutes", True),
])
def test_joint_scoring_rejects_bad_metric_values(field: str, value: Any) -> None:
    with pytest.raises(scoring.GraphScoringContractError):
        scoring.graph_score_components(_metric(**{field: value}), critical_weight=1, impact_weight=1)


@pytest.mark.parametrize("field", [
    "is_on_critical_path", "critical_path_rank", "impact_count", "downstream_critical_minutes",
])
def test_joint_scoring_rejects_missing_metric_fields(field: str) -> None:
    metric = _metric()
    metric.pop(field)
    with pytest.raises(scoring.GraphScoringContractError):
        scoring.graph_score_components(metric, critical_weight=1, impact_weight=1)
