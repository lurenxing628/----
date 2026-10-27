"""Graph-aware scheduler scoring helpers.

This module deliberately accepts only plain Python data.  NetworkX objects,
database handles, config services, loggers, and scheduler runtime state all stay
outside this boundary.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

_NON_CRITICAL_PATH_RANK = 1_000_000_000


def _graph_score_values(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[int, Optional[int]]:
    is_on_critical_path = node_metric["is_on_critical_path"]
    rank = node_metric["critical_path_rank"]
    impact_count = node_metric["impact_count"]
    downstream_critical_minutes = node_metric["downstream_critical_minutes"]
    bonus = int(
        (critical_weight if is_on_critical_path else 0)
        + impact_count * impact_weight
        + downstream_critical_minutes * downstream_minutes_weight
    )
    return bonus, rank


def graph_score_components(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[int, Tuple[float, ...]]:
    """Return the exact bonus together with its dispatch key."""
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


__all__ = [
    "graph_score_components",
]
