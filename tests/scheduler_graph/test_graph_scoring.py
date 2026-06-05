"""单元测试：图调度评分契约 graph_score_bonus / graph_priority_key_component——按 critical/impact/downstream 权重叠加奖励、非关键节点不计关键权重、零权重得 0；缺字段或字段/权重为负数或 bool 时抛 GraphScoringContractError；优先级 key 让大奖励排前、并以 critical_path_rank 作平局裁决。"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from core.services.scheduler.graph.scoring import (
    GraphScoringContractError,
    graph_priority_key_component,
    graph_score_bonus,
)


def _metric(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "is_on_critical_path": True,
        "critical_path_rank": 0,
        "impact_count": 3,
        "downstream_critical_minutes": 120,
    }
    data.update(overrides)
    return data


def test_graph_score_bonus_adds_critical_impact_and_downstream_components() -> None:
    assert (
        graph_score_bonus(
            _metric(),
            critical_weight=500,
            impact_weight=10,
            downstream_minutes_weight=1,
        )
        == 650
    )


def test_graph_score_bonus_respects_zero_weights() -> None:
    assert (
        graph_score_bonus(
            _metric(),
            critical_weight=0,
            impact_weight=0,
            downstream_minutes_weight=0,
        )
        == 0
    )


def test_graph_score_bonus_omits_critical_weight_for_non_critical_node() -> None:
    assert (
        graph_score_bonus(
            _metric(is_on_critical_path=False, critical_path_rank=None),
            critical_weight=500,
            impact_weight=10,
            downstream_minutes_weight=1,
        )
        == 150
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "is_on_critical_path",
        "critical_path_rank",
        "impact_count",
        "downstream_critical_minutes",
    ],
)
def test_graph_score_bonus_rejects_missing_metric_fields(missing_field: str) -> None:
    metric = _metric()
    metric.pop(missing_field)

    with pytest.raises(GraphScoringContractError):
        graph_score_bonus(metric, critical_weight=500, impact_weight=10)


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_on_critical_path", 1),
        ("critical_path_rank", -1),
        ("critical_path_rank", True),
        ("impact_count", -1),
        ("impact_count", True),
        ("downstream_critical_minutes", -1),
        ("downstream_critical_minutes", True),
    ],
)
def test_graph_score_bonus_rejects_bad_metric_values(field: str, value: Any) -> None:
    with pytest.raises(GraphScoringContractError):
        graph_score_bonus(_metric(**{field: value}), critical_weight=500, impact_weight=10)


@pytest.mark.parametrize(
    "weights",
    [
        {"critical_weight": -1, "impact_weight": 10, "downstream_minutes_weight": 1},
        {"critical_weight": True, "impact_weight": 10, "downstream_minutes_weight": 1},
        {"critical_weight": 500, "impact_weight": -1, "downstream_minutes_weight": 1},
        {"critical_weight": 500, "impact_weight": True, "downstream_minutes_weight": 1},
        {"critical_weight": 500, "impact_weight": 10, "downstream_minutes_weight": -1},
        {"critical_weight": 500, "impact_weight": 10, "downstream_minutes_weight": True},
    ],
)
def test_graph_score_bonus_rejects_bad_weights(weights: Dict[str, Any]) -> None:
    with pytest.raises(GraphScoringContractError):
        graph_score_bonus(_metric(), **weights)


def test_graph_priority_key_component_makes_larger_bonus_sort_first() -> None:
    high_bonus_key = graph_priority_key_component(
        _metric(impact_count=8, downstream_critical_minutes=300),
        critical_weight=500,
        impact_weight=10,
    )
    low_bonus_key = graph_priority_key_component(
        _metric(impact_count=1, downstream_critical_minutes=10),
        critical_weight=500,
        impact_weight=10,
    )

    assert high_bonus_key < low_bonus_key


def test_graph_priority_key_component_uses_critical_path_rank_as_tie_breaker() -> None:
    earlier_rank_key = graph_priority_key_component(
        _metric(critical_path_rank=1, impact_count=3, downstream_critical_minutes=120),
        critical_weight=500,
        impact_weight=10,
    )
    later_rank_key = graph_priority_key_component(
        _metric(critical_path_rank=5, impact_count=3, downstream_critical_minutes=120),
        critical_weight=500,
        impact_weight=10,
    )
    non_critical_key = graph_priority_key_component(
        _metric(
            is_on_critical_path=False,
            critical_path_rank=None,
            impact_count=53,
            downstream_critical_minutes=120,
        ),
        critical_weight=0,
        impact_weight=10,
    )

    assert earlier_rank_key < later_rank_key
    assert earlier_rank_key < non_critical_key
