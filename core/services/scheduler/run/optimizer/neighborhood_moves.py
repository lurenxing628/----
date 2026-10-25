from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .neighborhood_move_support import (
    batch_id,
    bottleneck_machine_rows,
    earliest_due_pressure_batch,
    finish_by_batch,
    first_changeover_pair,
    latest_result,
    most_tardy_batch,
    pick_resource_pair,
)

CRITICAL_CHAIN = "critical_chain"
TARDY_WINDOW = "tardy_window"
BOTTLENECK_MACHINE = "bottleneck_machine"
CHANGEOVER_BLOCK = "changeover_block"
RESOURCE_ALTERNATIVE = "resource_alternative"
TIME_WINDOW = "time_window"
SGS_DISPATCH_RULE = "sgs_dispatch_rule"
DEFAULT_SGS_DISPATCH_RULES: Tuple[str, ...] = ("slack", "cr", "atc")

BUSINESS_NEIGHBORHOODS: Tuple[str, ...] = (
    CRITICAL_CHAIN,
    TARDY_WINDOW,
    BOTTLENECK_MACHINE,
    CHANGEOVER_BLOCK,
    RESOURCE_ALTERNATIVE,
    TIME_WINDOW,
)
ALLOWED_NEIGHBORHOODS: Tuple[str, ...] = BUSINESS_NEIGHBORHOODS + (SGS_DISPATCH_RULE,)


@dataclass(frozen=True)
class NeighborhoodMove:
    neighborhood_name: str
    batch_order: Tuple[str, ...]
    dispatch_mode: str = ""
    dispatch_rule: str = ""
    noop: bool = False
    resource_pair_rank: Optional[Dict[Tuple[str, str], int]] = None


def noop_move(name: str, *, order: List[str]) -> NeighborhoodMove:
    return NeighborhoodMove(
        neighborhood_name=str(name),
        batch_order=tuple(order or []),
        noop=True,
    )


def critical_chain_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    latest = latest_result(results)
    if latest is None:
        return noop_move(CRITICAL_CHAIN, order=order)
    return _pull_batch_earlier(CRITICAL_CHAIN, order, batch_id=batch_id(latest))


def tardy_window_move(order: List[str], results: List[Any], batches: Dict[str, Any]) -> NeighborhoodMove:
    finish_rows = finish_by_batch(results)
    bid = most_tardy_batch(finish_by_batch_rows=finish_rows, batches=batches)
    if not bid:
        return noop_move(TARDY_WINDOW, order=order)
    return _pull_batch_earlier(TARDY_WINDOW, order, batch_id=bid)


def bottleneck_machine_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    rows = bottleneck_machine_rows(results)
    if not rows:
        return noop_move(BOTTLENECK_MACHINE, order=order)
    latest = latest_result(rows)
    if latest is None:
        return noop_move(BOTTLENECK_MACHINE, order=order)
    return _pull_batch_earlier(BOTTLENECK_MACHINE, order, batch_id=batch_id(latest))


def changeover_block_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    pair = first_changeover_pair(results)
    if pair is None:
        fallback = critical_chain_move(order, results)
        if fallback.noop:
            return noop_move(CHANGEOVER_BLOCK, order=order)
        return NeighborhoodMove(
            neighborhood_name=CHANGEOVER_BLOCK,
            batch_order=fallback.batch_order,
            dispatch_mode=fallback.dispatch_mode,
            dispatch_rule=fallback.dispatch_rule,
        )
    previous, current = pair
    out = _move_before(order, batch_id(current), batch_id(previous))
    return _order_move(CHANGEOVER_BLOCK, order, out)


def resource_alternative_move(order: List[str], resource_pool: Optional[Dict[str, Any]]) -> NeighborhoodMove:
    pool = resource_pool or {}
    picked = pick_resource_pair(pool)
    if picked is None:
        return noop_move(RESOURCE_ALTERNATIVE, order=order)
    operator_id, machine_id, _old_rank = picked
    return NeighborhoodMove(
        neighborhood_name=RESOURCE_ALTERNATIVE,
        batch_order=tuple(order or []),
        resource_pair_rank={(operator_id, machine_id): -1},
    )


def time_window_move(order: List[str], results: List[Any], batches: Dict[str, Any]) -> NeighborhoodMove:
    finish_rows = finish_by_batch(results)
    bid = earliest_due_pressure_batch(finish_by_batch_rows=finish_rows, batches=batches)
    if not bid:
        return noop_move(TIME_WINDOW, order=order)
    return _pull_batch_earlier(TIME_WINDOW, order, batch_id=bid)


def pick_sgs_dispatch_rule(
    current_rule: str,
    valid_dispatch_rules: List[str],
    rnd: Any = None,
    *,
    tried_rules: Optional[Set[str]] = None,
) -> Optional[str]:
    current = str(current_rule or "").strip().lower()
    candidates = [
        item for item in valid_dispatch_rules
        if item != current and (tried_rules is None or item not in tried_rules)
    ]
    if not candidates and tried_rules is not None:
        candidates = [item for item in valid_dispatch_rules if item != current]
    if not candidates:
        return None
    index = int(rnd.randrange(len(candidates))) if rnd is not None and len(candidates) > 1 else 0
    picked = candidates[index]
    if tried_rules is not None:
        tried_rules.add(picked)
    return picked


def sgs_dispatch_rule_move(order: List[str], current_rule: str, valid_dispatch_rules: List[str], rnd: Any = None) -> NeighborhoodMove:
    picked = pick_sgs_dispatch_rule(current_rule, valid_dispatch_rules, rnd)
    if picked is None:
        return noop_move(SGS_DISPATCH_RULE, order=order)
    return NeighborhoodMove(
        neighborhood_name=SGS_DISPATCH_RULE,
        batch_order=tuple(order or []),
        dispatch_mode="sgs",
        dispatch_rule=picked,
    )


def _order_move(name: str, before: List[str], after: List[str]) -> NeighborhoodMove:
    if before == after:
        return noop_move(name, order=before)
    return NeighborhoodMove(
        neighborhood_name=str(name),
        batch_order=tuple(after),
    )


def _pull_batch_earlier(name: str, order: List[str], *, batch_id: str) -> NeighborhoodMove:
    batch_id = str(batch_id or "").strip()
    if not batch_id or batch_id not in order:
        return noop_move(name, order=order)
    index = order.index(batch_id)
    if index <= 0:
        return noop_move(name, order=order)
    out = list(order)
    item = out.pop(index)
    out.insert(max(index - 2, 0), item)
    return _order_move(name, order, out)


def _move_before(order: List[str], moving_batch: str, before_batch: str) -> List[str]:
    moving_batch = str(moving_batch or "").strip()
    before_batch = str(before_batch or "").strip()
    out = list(order or [])
    if not moving_batch or not before_batch or moving_batch == before_batch:
        return out
    try:
        moving_index = out.index(moving_batch)
        before_index = out.index(before_batch)
    except ValueError:
        return out
    out.pop(moving_index)
    if moving_index < before_index:
        before_index -= 1
    out.insert(before_index, moving_batch)
    return out


__all__ = [
    "ALLOWED_NEIGHBORHOODS",
    "BOTTLENECK_MACHINE",
    "BUSINESS_NEIGHBORHOODS",
    "CHANGEOVER_BLOCK",
    "CRITICAL_CHAIN",
    "DEFAULT_SGS_DISPATCH_RULES",
    "RESOURCE_ALTERNATIVE",
    "SGS_DISPATCH_RULE",
    "TARDY_WINDOW",
    "TIME_WINDOW",
    "NeighborhoodMove",
    "bottleneck_machine_move",
    "changeover_block_move",
    "critical_chain_move",
    "noop_move",
    "pick_sgs_dispatch_rule",
    "resource_alternative_move",
    "sgs_dispatch_rule_move",
    "tardy_window_move",
    "time_window_move",
]
