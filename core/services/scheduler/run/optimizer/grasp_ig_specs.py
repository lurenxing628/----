from __future__ import annotations

from typing import Any, Callable, Dict, List

GRASP_ORIGIN = "grasp"
IG_ORIGIN = "ig"


def _grasp_order(base_order: List[str], *, rnd: Any, rcl_size: int) -> List[str]:
    remaining = list(base_order)
    out: List[str] = []
    while remaining:
        window = min(rcl_size, len(remaining))
        index = rnd.randrange(window)
        out.append(remaining.pop(index))
    return out


def _ig_order(parent_order: List[str], *, rnd: Any, destruction_size: int) -> List[str]:
    if len(parent_order) < 2:
        return list(parent_order)
    order = list(parent_order)
    remove_count = min(destruction_size, len(order) - 1)
    positions = sorted(rnd.sample(range(len(order)), remove_count), reverse=True)
    removed: List[str] = []
    for position in positions:
        removed.append(order.pop(position))
    for batch_id in removed:
        insert_at = rnd.randrange(len(order) + 1)
        order.insert(insert_at, batch_id)
    return order


def build_grasp_ig_candidate_specs(
    *,
    base_order: List[str],
    parent_order: List[str],
    version: int,
    candidate_construction: Dict[str, Any],
    dispatch_rule_cfg: str,
    rng_factory: Callable[[int], Any],
) -> List[Dict[str, Any]]:
    grasp_limits = candidate_construction["grasp"]
    ig_limits = candidate_construction["iterated_greedy"]
    grasp_restarts = grasp_limits["effective_restarts"]
    ig_restarts = ig_limits["effective_restarts"]
    rcl_size = grasp_limits["effective_rcl_size"]
    destruction_size = ig_limits["effective_destruction_size"]
    specs: List[Dict[str, Any]] = []

    for index in range(grasp_restarts):
        rnd = rng_factory(int(version) + 1009 + index)
        specs.append(
            {
                "origin": GRASP_ORIGIN,
                "restart_index": index,
                "dispatch_mode": "batch_order",
                "dispatch_rule": dispatch_rule_cfg,
                "order": _grasp_order(base_order, rnd=rnd, rcl_size=rcl_size),
            }
        )

    for index in range(ig_restarts):
        rnd = rng_factory(int(version) + 2003 + index)
        specs.append(
            {
                "origin": IG_ORIGIN,
                "restart_index": index,
                "dispatch_mode": "batch_order",
                "dispatch_rule": dispatch_rule_cfg,
                "order": _ig_order(parent_order, rnd=rnd, destruction_size=destruction_size),
            }
        )
    return specs


__all__ = [
    "GRASP_ORIGIN",
    "IG_ORIGIN",
    "build_grasp_ig_candidate_specs",
]
