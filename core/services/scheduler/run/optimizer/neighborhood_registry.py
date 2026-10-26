from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.errors import ValidationError

from .neighborhood_moves import (
    ALLOWED_NEIGHBORHOODS,
    BOTTLENECK_MACHINE,
    CHANGEOVER_BLOCK,
    CRITICAL_CHAIN,
    RESOURCE_ALTERNATIVE,
    TARDY_WINDOW,
    TIME_WINDOW,
    NeighborhoodMove,
    bottleneck_machine_move,
    changeover_block_move,
    critical_chain_move,
    resource_alternative_move,
    sgs_dispatch_rule_move,
    tardy_window_move,
    time_window_move,
)

_ALLOWED_SET = frozenset(ALLOWED_NEIGHBORHOODS)


def validate_neighborhood_name(name: Any) -> str:
    text = str(name).strip().lower()
    if text not in _ALLOWED_SET:
        raise ValidationError(
            f"未知业务邻域“{name}”，本阶段只允许：{', '.join(ALLOWED_NEIGHBORHOODS)}。",
            field="neighborhood",
        )
    return text


def build_neighborhood_move(
    name: str,
    *,
    order: List[str],
    results: List[Any],
    batches: Dict[str, Any],
    resource_pool: Optional[Dict[str, Any]],
    rnd: Any,
    current_dispatch_rule: str = "",
    valid_dispatch_rules: List[str],
) -> NeighborhoodMove:
    key = validate_neighborhood_name(name)
    if key == CRITICAL_CHAIN:
        return critical_chain_move(order, results)
    if key == TARDY_WINDOW:
        return tardy_window_move(order, results, batches)
    if key == BOTTLENECK_MACHINE:
        return bottleneck_machine_move(order, results)
    if key == CHANGEOVER_BLOCK:
        return changeover_block_move(order, results)
    if key == RESOURCE_ALTERNATIVE:
        return resource_alternative_move(order, resource_pool)
    if key == TIME_WINDOW:
        return time_window_move(order, results, batches)
    return sgs_dispatch_rule_move(order, current_dispatch_rule, valid_dispatch_rules, rnd)


__all__ = [
    "build_neighborhood_move",
    "validate_neighborhood_name",
]
