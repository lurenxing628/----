from __future__ import annotations

from typing import Any, Callable, Dict, List

GRASP_ORIGIN = "grasp"
IG_ORIGIN = "ig"


def _construction_limits(candidate_construction: Dict[str, Any], family: str) -> Dict[str, Any]:
    value = candidate_construction.get(family)
    return value if isinstance(value, dict) else {}


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)
    return number if number > 0 else int(default)


def _dispatch_rules(dispatch_rule_cfg: str, valid_dispatch_rules: List[str]) -> List[str]:
    out: List[str] = []
    for item in [dispatch_rule_cfg] + list(valid_dispatch_rules or []):
        text = str(item or "").strip().lower()
        if text and text not in out:
            out.append(text)
    return out or [str(dispatch_rule_cfg or "").strip().lower()]


def _grasp_order(base_order: List[str], *, rnd: Any, rcl_size: int) -> List[str]:
    remaining = list(base_order)
    out: List[str] = []
    while remaining:
        window = min(max(int(rcl_size), 1), len(remaining))
        index = rnd.randrange(window)
        out.append(remaining.pop(index))
    return out


def _ig_order(parent_order: List[str], *, rnd: Any, destruction_size: int) -> List[str]:
    if len(parent_order) < 2:
        return list(parent_order)
    order = list(parent_order)
    remove_count = min(max(int(destruction_size), 1), len(order) - 1)
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
    valid_dispatch_rules: List[str],
    rng_factory: Callable[[int], Any],
) -> List[Dict[str, Any]]:
    grasp_limits = _construction_limits(candidate_construction, "grasp")
    ig_limits = _construction_limits(candidate_construction, "iterated_greedy")
    grasp_restarts = _positive_int(grasp_limits.get("effective_restarts"), default=0)
    ig_restarts = _positive_int(ig_limits.get("effective_restarts"), default=0)
    rcl_size = _positive_int(grasp_limits.get("effective_rcl_size"), default=3)
    destruction_size = _positive_int(ig_limits.get("effective_destruction_size"), default=3)
    rules = _dispatch_rules(dispatch_rule_cfg, valid_dispatch_rules)
    specs: List[Dict[str, Any]] = []

    for index in range(grasp_restarts):
        rnd = rng_factory(int(version) + 1009 + index)
        specs.append(
            {
                "origin": GRASP_ORIGIN,
                "restart_index": index,
                "dispatch_rule": rules[index % len(rules)],
                "order": _grasp_order(base_order, rnd=rnd, rcl_size=rcl_size),
                "construction": {"family": GRASP_ORIGIN, "restart_index": index, "rcl_size": rcl_size},
            }
        )

    for index in range(ig_restarts):
        rnd = rng_factory(int(version) + 2003 + index)
        specs.append(
            {
                "origin": IG_ORIGIN,
                "restart_index": index,
                "dispatch_rule": rules[index % len(rules)],
                "order": _ig_order(parent_order, rnd=rnd, destruction_size=destruction_size),
                "construction": {
                    "family": "iterated_greedy",
                    "restart_index": index,
                    "destruction_size": destruction_size,
                },
            }
        )
    return specs


__all__ = [
    "GRASP_ORIGIN",
    "IG_ORIGIN",
    "build_grasp_ig_candidate_specs",
]
