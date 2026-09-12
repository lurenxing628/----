"""Graph-aware scheduler scoring helpers.

This module deliberately accepts only plain Python data.  NetworkX objects,
database handles, config services, loggers, and scheduler runtime state all stay
outside this boundary.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

_NON_CRITICAL_PATH_RANK = 1_000_000_000


class GraphScoringContractError(ValueError):
    """Raised when graph scoring input violates the PR-6 scoring contract."""


def _require_metric_field(metric: Dict[str, Any], field: str) -> Any:
    if field not in metric:
        raise GraphScoringContractError(f"图评分指标缺少字段：{field}")
    return metric[field]


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise GraphScoringContractError(f"图评分字段 {field} 必须是 bool。")
    return bool(value)


def _require_non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GraphScoringContractError(f"图评分字段 {field} 必须是非负整数。")
    return int(value)


def _require_optional_non_negative_int(value: Any, *, field: str) -> Optional[int]:
    if value is None:
        return None
    return _require_non_negative_int(value, field=field)


def _require_weight(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GraphScoringContractError(f"图评分权重 {field} 必须是非负整数。")
    return int(value)


def _normalized_metric(metric: Dict[str, Any]) -> Tuple[bool, Optional[int], int, int]:
    is_on_critical_path = _require_bool(
        _require_metric_field(metric, "is_on_critical_path"),
        field="is_on_critical_path",
    )
    critical_path_rank = _require_optional_non_negative_int(
        _require_metric_field(metric, "critical_path_rank"),
        field="critical_path_rank",
    )
    impact_count = _require_non_negative_int(
        _require_metric_field(metric, "impact_count"),
        field="impact_count",
    )
    downstream_critical_minutes = _require_non_negative_int(
        _require_metric_field(metric, "downstream_critical_minutes"),
        field="downstream_critical_minutes",
    )
    return is_on_critical_path, critical_path_rank, impact_count, downstream_critical_minutes


def _graph_score_values(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[int, Optional[int]]:
    is_on_critical_path, rank, impact_count, downstream_critical_minutes = _normalized_metric(node_metric)
    critical_weight = _require_weight(critical_weight, field="critical_weight")
    impact_weight = _require_weight(impact_weight, field="impact_weight")
    downstream_minutes_weight = _require_weight(
        downstream_minutes_weight,
        field="downstream_minutes_weight",
    )
    bonus = int(
        (critical_weight if is_on_critical_path else 0)
        + impact_count * impact_weight
        + downstream_critical_minutes * downstream_minutes_weight
    )
    return bonus, rank


def graph_score_bonus(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> int:
    """Return a positive bonus without converting its exact integer to float."""
    bonus, _rank = _graph_score_values(
        node_metric,
        critical_weight=critical_weight,
        impact_weight=impact_weight,
        downstream_minutes_weight=downstream_minutes_weight,
    )
    return bonus


def graph_score_components(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[int, Tuple[float, ...]]:
    """Validate once and return the exact bonus together with its dispatch key."""
    bonus, rank = _graph_score_values(
        node_metric,
        critical_weight=critical_weight,
        impact_weight=impact_weight,
        downstream_minutes_weight=downstream_minutes_weight,
    )
    return bonus, (
        float(-bonus),
        float(rank if rank is not None else _NON_CRITICAL_PATH_RANK),
    )


def graph_priority_key_component(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[float, ...]:
    """Return a sortable key component for SGS, where smaller means earlier."""
    _bonus, key = graph_score_components(
        node_metric,
        critical_weight=critical_weight,
        impact_weight=impact_weight,
        downstream_minutes_weight=downstream_minutes_weight,
    )
    return key


__all__ = [
    "GraphScoringContractError",
    "graph_priority_key_component",
    "graph_score_bonus",
    "graph_score_components",
]
