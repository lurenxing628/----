from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .optimizer_neighborhood_move_support import (
    batch_id,
    bottleneck_machine_rows,
    changeover_count,
    copy_resource_pool,
    due_batch_count,
    earliest_due_pressure_batch,
    finish_by_batch,
    first_changeover_pair,
    latest_result,
    most_tardy_batch,
    pick_resource_pair,
    positive_count,
    resource_pair_count,
    tardy_batch_count,
)

NEIGHBORHOOD_MOVE_SCHEMA_VERSION = 1

CRITICAL_CHAIN = "critical_chain"
TARDY_WINDOW = "tardy_window"
BOTTLENECK_MACHINE = "bottleneck_machine"
CHANGEOVER_BLOCK = "changeover_block"
RESOURCE_ALTERNATIVE = "resource_alternative"
TIME_WINDOW = "time_window"

BUSINESS_NEIGHBORHOODS: Tuple[str, ...] = (
    CRITICAL_CHAIN,
    TARDY_WINDOW,
    BOTTLENECK_MACHINE,
    CHANGEOVER_BLOCK,
    RESOURCE_ALTERNATIVE,
    TIME_WINDOW,
)
ALLOWED_NEIGHBORHOODS: Tuple[str, ...] = BUSINESS_NEIGHBORHOODS


@dataclass(frozen=True)
class NeighborhoodMove:
    schema_version: int
    neighborhood_name: str
    move_kind: str
    input_scope: str
    batch_order: Tuple[str, ...]
    changed_decision_count: int
    expected_effect: str
    noop: bool = False
    fallback_used: bool = False
    fallback_reason: str = ""
    candidate_rejected: str = ""
    resource_pool: Optional[Dict[str, Any]] = None
    diagnostics: Optional[Dict[str, Any]] = None
    decision_key: Tuple[Any, ...] = ()
    selected_operation_ids: Tuple[str, ...] = ()
    selected_batch_ids: Tuple[str, ...] = ()
    selected_machine_ids: Tuple[str, ...] = ()
    reason: str = ""

    def to_report_dict(self) -> Dict[str, Any]:
        row = {
            "schema_version": int(self.schema_version),
            "name": str(self.neighborhood_name),
            "neighborhood_name": str(self.neighborhood_name),
            "scope": str(self.input_scope),
            "move_kind": str(self.move_kind),
            "input_scope": str(self.input_scope),
            "selected_operation_ids": list(self.selected_operation_ids),
            "selected_batch_ids": list(self.selected_batch_ids),
            "selected_machine_ids": list(self.selected_machine_ids),
            "reason": str(self.reason or ""),
            "changed_decision_count": int(self.changed_decision_count),
            "expected_effect": str(self.expected_effect),
            "noop": bool(self.noop),
            "fallback_used": bool(self.fallback_used),
            "candidate_rejected": str(self.candidate_rejected or ""),
            "diagnostics": dict(self.diagnostics or {}),
        }
        if self.fallback_reason:
            row["fallback_reason"] = str(self.fallback_reason)
        return row


def noop_move(name: str, *, reason: str, order: List[str], input_scope: str = "batch_order") -> NeighborhoodMove:
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=str(name),
        move_kind="noop",
        input_scope=str(input_scope),
        batch_order=tuple(order or []),
        changed_decision_count=0,
        expected_effect="none",
        noop=True,
        candidate_rejected="noop_neighbor",
        diagnostics={"reason": str(reason or "noop")},
        decision_key=tuple(order or []),
        reason=str(reason or "noop"),
    )


def critical_chain_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    latest = latest_result(results)
    if latest is None:
        return noop_move(CRITICAL_CHAIN, reason="critical_chain_missing", order=order, input_scope="decoded_output")
    bid = batch_id(latest)
    return _pull_batch_earlier(
        CRITICAL_CHAIN,
        order,
        batch_id=bid,
        move_kind="pull_latest_chain_batch",
        expected_effect="pull_latest_chain_batch_earlier",
        reason_when_first="critical_chain_batch_already_first",
        reason="critical_path",
        diagnostics={"chain_node_count": positive_count(results)},
    )


def tardy_window_move(order: List[str], results: List[Any], batches: Dict[str, Any]) -> NeighborhoodMove:
    finish_rows = finish_by_batch(results)
    picked = most_tardy_batch(finish_by_batch_rows=finish_rows, batches=batches)
    if not picked:
        return noop_move(TARDY_WINDOW, reason="no_tardy_batch", order=order, input_scope="due_window")
    batch_id, tardiness_hours = picked
    return _pull_batch_earlier(
        TARDY_WINDOW,
        order,
        batch_id=batch_id,
        move_kind="pull_tardy_batch",
        expected_effect="reduce_tardy_window_pressure",
        reason_when_first="tardy_batch_already_first",
        reason="overdue",
        diagnostics={"tardy_batch_count": tardy_batch_count(finish_rows, batches), "tardiness_hours": round(tardiness_hours, 4)},
    )


def bottleneck_machine_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    machine_id, rows = bottleneck_machine_rows(results)
    if not machine_id or not rows:
        return noop_move(BOTTLENECK_MACHINE, reason="bottleneck_machine_missing", order=order, input_scope="machine_load")
    latest = latest_result(rows)
    return _pull_batch_earlier(
        BOTTLENECK_MACHINE,
        order,
        batch_id=batch_id(latest),
        move_kind="pull_bottleneck_machine_batch",
        expected_effect="relieve_bottleneck_machine_tail",
        reason_when_first="bottleneck_batch_already_first",
        reason="bottleneck",
        diagnostics={"bottleneck_machine_count": 1, "operation_count": len(rows)},
        selected_machine_ids=(machine_id,),
    )


def changeover_block_move(order: List[str], results: List[Any]) -> NeighborhoodMove:
    pair = first_changeover_pair(results)
    if pair is None:
        fallback = critical_chain_move(order, results)
        if fallback.noop:
            return noop_move(CHANGEOVER_BLOCK, reason="changeover_block_missing", order=order, input_scope="machine_changeover")
        return _with_fallback(fallback, neighborhood_name=CHANGEOVER_BLOCK, fallback_reason="changeover_block_missing")
    previous, current = pair
    before_batch = batch_id(previous)
    moving_batch = batch_id(current)
    out = _move_before(order, moving_batch, before_batch)
    return _order_move(
        CHANGEOVER_BLOCK,
        "group_changeover_block",
        order,
        out,
        "try_reduce_machine_changeover",
        reason="changeover",
        diagnostics={"changeover_count": changeover_count(results)},
        selected_machine_ids=(str(getattr(current, "machine_id", "") or "").strip(),),
    )


def resource_alternative_move(order: List[str], resource_pool: Optional[Dict[str, Any]]) -> NeighborhoodMove:
    pool = copy_resource_pool(resource_pool)
    picked = pick_resource_pair(pool)
    if picked is None:
        return noop_move(RESOURCE_ALTERNATIVE, reason="no_alternative_resource_pair", order=order, input_scope="resource_pool")
    operator_id, machine_id, old_rank = picked
    pair_rank = pool.setdefault("pair_rank", {})
    pair_rank[(operator_id, machine_id)] = min(int(old_rank), -1)
    diagnostics = {"alternative_pair_count": 1, "resource_pool_adjusted": True}
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=RESOURCE_ALTERNATIVE,
        move_kind="promote_alternative_resource_pair",
        input_scope="resource_pool",
        batch_order=tuple(order or []),
        changed_decision_count=1,
        expected_effect="try_alternative_resource_assignment",
        resource_pool=pool,
        diagnostics=diagnostics,
        decision_key=("resource_alternative", tuple(order or []), resource_pair_count(pool)),
        selected_machine_ids=(machine_id,),
        reason="unmatched_resource",
    )


def time_window_move(order: List[str], results: List[Any], batches: Dict[str, Any]) -> NeighborhoodMove:
    finish_rows = finish_by_batch(results)
    bid = earliest_due_pressure_batch(finish_by_batch_rows=finish_rows, batches=batches)
    if not bid:
        return noop_move(TIME_WINDOW, reason="no_time_window_pressure", order=order, input_scope="due_window")
    return _pull_batch_earlier(
        TIME_WINDOW,
        order,
        batch_id=bid,
        move_kind="pull_due_window_batch",
        expected_effect="repair_due_window_pressure",
        reason_when_first="time_window_batch_already_first",
        reason="time_window",
        diagnostics={"due_window_batch_count": due_batch_count(batches)},
    )


def _with_fallback(move: NeighborhoodMove, *, neighborhood_name: str, fallback_reason: str) -> NeighborhoodMove:
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=neighborhood_name,
        move_kind=move.move_kind,
        input_scope=move.input_scope,
        batch_order=move.batch_order,
        changed_decision_count=move.changed_decision_count,
        expected_effect=move.expected_effect,
        fallback_used=True,
        fallback_reason=fallback_reason,
        diagnostics=dict(move.diagnostics or {}),
        decision_key=move.decision_key,
        selected_operation_ids=move.selected_operation_ids,
        selected_batch_ids=move.selected_batch_ids,
        selected_machine_ids=move.selected_machine_ids,
        reason=move.reason or fallback_reason,
    )


def _order_move(
    name: str,
    move_kind: str,
    before: List[str],
    after: List[str],
    expected_effect: str,
    *,
    reason: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    selected_machine_ids: Tuple[str, ...] = (),
) -> NeighborhoodMove:
    changed = _changed_positions(before, after)
    if changed <= 0:
        return noop_move(name, reason="unchanged_batch_order", order=before)
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=str(name),
        move_kind=str(move_kind),
        input_scope="batch_order",
        batch_order=tuple(after),
        changed_decision_count=changed,
        expected_effect=str(expected_effect),
        diagnostics=dict(diagnostics or {}),
        decision_key=tuple(after),
        selected_batch_ids=tuple(_changed_batch_ids(before, after)),
        selected_machine_ids=tuple(item for item in selected_machine_ids if item),
        reason=str(reason),
    )


def _pull_batch_earlier(
    name: str,
    order: List[str],
    *,
    batch_id: str,
    move_kind: str,
    expected_effect: str,
    reason_when_first: str,
    reason: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    selected_machine_ids: Tuple[str, ...] = (),
) -> NeighborhoodMove:
    batch_id = str(batch_id or "").strip()
    if not batch_id or batch_id not in order:
        return noop_move(name, reason="batch_not_in_order", order=order)
    index = order.index(batch_id)
    if index <= 0:
        return noop_move(name, reason=reason_when_first, order=order)
    out = list(order)
    item = out.pop(index)
    out.insert(max(index - 2, 0), item)
    return _order_move(
        name,
        move_kind,
        order,
        out,
        expected_effect,
        reason=reason,
        diagnostics=diagnostics,
        selected_machine_ids=selected_machine_ids,
    )


def _move_before(order: List[str], moving_batch: str, before_batch: str) -> List[str]:
    moving_batch = str(moving_batch or "").strip()
    before_batch = str(before_batch or "").strip()
    out = list(order or [])
    if not moving_batch or not before_batch or moving_batch == before_batch:
        return out
    if moving_batch not in out or before_batch not in out:
        return out
    out.remove(moving_batch)
    target = out.index(before_batch)
    out.insert(target, moving_batch)
    return out


def _changed_positions(before: List[str], after: List[str]) -> int:
    if len(before) != len(after):
        return max(len(before), len(after))
    return sum(1 for left, right in zip(before, after) if left != right)


def _changed_batch_ids(before: List[str], after: List[str]) -> List[str]:
    changed: List[str] = []
    for left, right in zip(before, after):
        if left == right:
            continue
        for item in (left, right):
            text = str(item or "").strip()
            if text and text not in changed:
                changed.append(text)
    return changed


__all__ = [
    "ALLOWED_NEIGHBORHOODS",
    "BOTTLENECK_MACHINE",
    "BUSINESS_NEIGHBORHOODS",
    "CHANGEOVER_BLOCK",
    "CRITICAL_CHAIN",
    "NEIGHBORHOOD_MOVE_SCHEMA_VERSION",
    "RESOURCE_ALTERNATIVE",
    "TARDY_WINDOW",
    "TIME_WINDOW",
    "NeighborhoodMove",
    "bottleneck_machine_move",
    "changeover_block_move",
    "critical_chain_move",
    "noop_move",
    "resource_alternative_move",
    "tardy_window_move",
    "time_window_move",
]
