from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from types import MappingProxyType
from typing import TYPE_CHECKING, AbstractSet, Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from core.algorithm_runtime.graph_cycle import kahn_unreachable_op_ids
from core.errors import ValidationError
from core.shared.strict_parse import finite_float, is_number

from .sgs_priority_keys import ValidatedGraphPriorityKeys
from .sgs_scoring import _collect_sgs_candidates

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo


@dataclass(frozen=True)
class PreparedGraphReadyTopology:
    """Decode-independent graph facts compiled once per preparation; progress and keys belong to each decode.

    ``schedulable_ids`` excludes seeded operations; ``fixed_ids`` holds the frozen and seeded ones.
    """

    schedulable_ids: FrozenSet[int]
    fixed_ids: FrozenSet[int]
    predecessors: Mapping[int, FrozenSet[int]]
    successors: Mapping[int, FrozenSet[int]]
    sort_keys: Mapping[int, Tuple[int, int, int]]
    initial_remaining_counts: Mapping[int, int]
    initial_ready: FrozenSet[int]


def prepare_graph_ready_topology(context: Any, operations: List[OpForScheduleAlgo]) -> PreparedGraphReadyTopology:
    """Validate the graph input once against the unseeded operations it schedules."""
    if not isinstance(context, dict) or not context.get("enabled"):
        raise ValidationError("图 ready 队列上下文无效，不能启用图排产候选。", field="graph_ready_context")
    op_ids: Set[int] = set()
    for op in operations:
        if op.id in op_ids:
            raise ValidationError(f"图 ready 队列上下文发现重复 op_id：{op.id}", field="graph_ready_context")
        op_ids.add(op.id)
    schedulable_ids = _op_id_set(context.get("schedulable_op_ids"), field="schedulable_op_ids")
    fixed_op_ids = _op_id_set(context.get("fixed_op_ids"), field="fixed_op_ids")
    overlap = sorted(schedulable_ids.intersection(fixed_op_ids))
    if overlap:
        sample = overlap[:20]
        raise ValidationError(
            f"图 ready 队列上下文不一致：待排工序不能同时是固定/已完成工序：{sample}",
            field="graph_ready_context",
            details={
                "reason": "schedulable_fixed_overlap",
                "overlap_count": len(overlap),
                "overlap_sample": sample,
            },
        )
    if schedulable_ids != op_ids:
        raise ValidationError("图 ready 队列上下文和本次待排工序不一致。", field="graph_ready_context")
    predecessor_map, successor_map = _validate_graph_ready_links(
        op_ids=schedulable_ids.union(fixed_op_ids),
        predecessor_map=context.get("predecessor_op_ids_by_op_id"),
        successor_map=context.get("successor_op_ids_by_op_id"),
    )
    initial_remaining_counts = {
        op_id: sum(1 for predecessor_id in predecessor_map[op_id] if predecessor_id in schedulable_ids)
        for op_id in sorted(schedulable_ids)
    }
    initial_ready = frozenset(
        op_id for op_id, count in initial_remaining_counts.items() if count == 0
    )
    if kahn_unreachable_op_ids(
        schedulable_ids=schedulable_ids,
        successor_map=successor_map,
        initial_remaining_counts=initial_remaining_counts,
    ):
        raise ValidationError("图 ready 队列上下文包含环形前后置关系。", field="graph_ready_context")
    sort_keys = _graph_sort_key_map(context.get("sort_key_by_op_id"), schedulable_ids=schedulable_ids)
    return PreparedGraphReadyTopology(
        schedulable_ids, fixed_op_ids,
        MappingProxyType(predecessor_map),
        MappingProxyType(successor_map),
        MappingProxyType(sort_keys),
        MappingProxyType(initial_remaining_counts),
        initial_ready,
    )


def _op_id_set(value: Any, *, field: str) -> FrozenSet[int]:
    if not isinstance(value, (set, frozenset, list, tuple)) or not all(type(item) is int and item > 0 for item in value):
        raise ValidationError(f"图 ready 队列上下文 {field} 必须是正整数 op_id 集合。", field="graph_ready_context")
    return frozenset(value)


def _prepare_graph_ready_state(
    topology: PreparedGraphReadyTopology,
    context: Dict[str, Any],
    *,
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    skip_initial_frontier: bool,
) -> Dict[str, Any]:
    """Independent progress for one decode over the compiled topology; the request supplies its keys."""
    op_by_id: Dict[int, Tuple[str, OpForScheduleAlgo]] = {
        op.id: (batch_id, op) for batch_id, operations in ops_by_batch.items() for op in operations
    }
    fixed_op_ids = set(topology.fixed_ids)
    if skip_initial_frontier:
        remaining_predecessor_count_by_op_id: Dict[int, int] = {}
        ready_op_ids: Set[int] = set()
    else:
        remaining_predecessor_count_by_op_id = dict(topology.initial_remaining_counts)
        ready_op_ids = set(topology.initial_ready)
    score_enabled = context["score_enabled"]
    return {
        "op_by_id": op_by_id,
        "completed_or_fixed_op_ids": fixed_op_ids,
        # completed_or_fixed_op_ids 会随本趟排产成功不断并入新完成工序；
        # input_fixed_op_ids 是"输入即固定"（冻结窗/执行报工 seed）的快照，供失败阻塞
        # 传播区分"撞到已报工的固定后继（现场乱序报工，按批降级）"和
        # "撞到本趟已完成工序（内部不变量破坏，fail-loud）"（审计 A02）。
        "input_fixed_op_ids": topology.fixed_ids,
        "blocked_op_ids": set(),
        "predecessor_op_ids_by_op_id": topology.predecessors,
        "successor_op_ids_by_op_id": topology.successors,
        "sort_key_by_op_id": topology.sort_keys,
        "remaining_predecessor_count_by_op_id": remaining_predecessor_count_by_op_id,
        "ready_op_ids": ready_op_ids,
        "score_enabled": score_enabled,
        "graph_priority_key_by_op_id": context["graph_priority_key_by_op_id"] if score_enabled else {},
    }


def _graph_priority_key_number(value: Any) -> float:
    if not is_number(value):
        raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context")
    number = finite_float(value)
    if number is None:
        raise ValidationError("图评分 key 不能包含 NaN 或 Inf。", field="graph_ready_context")
    return number


def graph_priority_key_map(value: Any, *, schedulable_ids: AbstractSet[int]) -> ValidatedGraphPriorityKeys:
    """Admit keys once per exact operation set, producing their static order and weak order.

    Every producer passes the preparation's own ``topology.schedulable_ids`` instance, so keys
    already admitted against that instance come back as is. SGS compares ``(penalty, *graph key,
    *dispatch key)``; one common width keeps the weak order exact, while mixed widths would let a
    shorter key's prefix swallow dispatch-key positions, so admission rejects them.
    """
    if type(value) is ValidatedGraphPriorityKeys and (
            value.schedulable_ids is schedulable_ids or value.schedulable_ids == schedulable_ids):
        return value
    if not isinstance(value, dict):
        raise ValidationError("图评分上下文缺少 graph_priority_key_by_op_id 映射。", field="graph_ready_context")
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, label="图评分 key")
    normalized: Dict[int, Tuple[float, ...]] = {}
    width: Optional[int] = None
    for op_id in sorted(schedulable_ids):
        raw_key = value[op_id]
        if not isinstance(raw_key, (tuple, list)):
            raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context")
        key = tuple(_graph_priority_key_number(item) for item in raw_key)
        if not key:
            raise ValidationError("图评分 key 不能为空。", field="graph_ready_context")
        if width is None:
            width = len(key)
        elif len(key) != width:
            raise ValidationError("图评分 key 长度必须一致。", field="graph_ready_context")
        normalized[op_id] = key
    order = tuple(sorted(normalized, key=lambda op_id: (normalized[op_id], op_id)))
    preorder = tuple(tuple(group) for _key, group in groupby(order, key=normalized.__getitem__))
    return ValidatedGraphPriorityKeys(normalized, schedulable_ids=frozenset(schedulable_ids),
                                      order=order, preorder=preorder)


def _graph_sort_key_map(value: Any, *, schedulable_ids: FrozenSet[int]) -> Dict[int, Tuple[int, int, int]]:
    if not isinstance(value, dict):
        raise ValidationError("图 ready 队列上下文 sort_key_by_op_id 必须是映射。", field="graph_ready_context")
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, label="图 ready 队列上下文 sort_key_by_op_id")
    normalized: Dict[int, Tuple[int, int, int]] = {}
    for op_id in sorted(schedulable_ids):
        raw_key = value[op_id]
        if type(raw_key) is not tuple or len(raw_key) != 3 or not all(type(part) is int for part in raw_key):
            raise ValidationError(f"图 ready 队列工序 {op_id} 的排序 key 必须是三个整数组成的 tuple。",
                                  field="graph_ready_context")
        normalized[op_id] = raw_key
    return normalized


def _validate_exact_key_set(value: Dict[Any, Any], *, schedulable_ids: AbstractSet[int], label: str) -> None:
    """Callers index ``value`` by int op_id next, so keys must already be exact positive ints."""
    for raw_op_id in value:
        if type(raw_op_id) is not int or raw_op_id <= 0:
            raise ValidationError(f"{label} 的 key 必须是正整数 op_id。", field="graph_ready_context")
    if value.keys() != schedulable_ids:
        raise ValidationError(f"{label} 的 key 必须和待排工序完全一致。", field="graph_ready_context")


def _normalize_link_map(value: Any, *, field: str) -> Dict[int, FrozenSet[int]]:
    if not isinstance(value, dict):
        raise ValidationError(f"图 ready 队列上下文缺少 {field} 映射。", field="graph_ready_context")
    # Unknown or non-integer keys fail the scope check that follows.
    return {op_id: _op_id_set(linked_ids, field=field) for op_id, linked_ids in value.items()}


def _validate_graph_ready_links(
    *, op_ids: AbstractSet[int], predecessor_map: Any, successor_map: Any,
) -> Tuple[Dict[int, FrozenSet[int]], Dict[int, FrozenSet[int]]]:
    predecessors = _normalize_link_map(predecessor_map, field="predecessor_op_ids_by_op_id")
    successors = _normalize_link_map(successor_map, field="successor_op_ids_by_op_id")
    _validate_link_scope(
        link_map=predecessors,
        known_op_ids=op_ids,
        link_label="前置工序",
    )
    _validate_link_scope(
        link_map=successors,
        known_op_ids=op_ids,
        link_label="后继工序",
    )
    for op_id in op_ids:
        predecessors.setdefault(op_id, frozenset())
        successors.setdefault(op_id, frozenset())
    return predecessors, successors


def _validate_link_scope(*, link_map: Mapping[int, AbstractSet[int]], known_op_ids: AbstractSet[int], link_label: str) -> None:
    for op_id, linked_ids in link_map.items():
        if op_id not in known_op_ids:
            raise ValidationError(f"图 ready 队列上下文不完整：工序 {op_id} 不在待排或已固定集合里。", field="graph_ready_context")
        for linked_id in linked_ids:
            if linked_id not in known_op_ids:
                raise ValidationError(
                    f"图 ready 队列上下文不完整：工序 {op_id} 的{link_label} {linked_id} 既不是待排也不是固定/已完成。",
                    field="graph_ready_context",
                )


def _collect_candidates(
    *,
    graph_state: Optional[Dict[str, Any]],
    batch_ids: List[str],
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    next_idx: Dict[str, int],
    blocked_batches: set,
) -> List[Tuple[str, OpForScheduleAlgo]]:
    if graph_state is None:
        return _collect_sgs_candidates(
            batch_ids_in_order=batch_ids,
            ops_by_batch=ops_by_batch,
            next_idx=next_idx,
            blocked_batches=blocked_batches,
        )
    ready_op_ids: List[int] = []
    for op_id in graph_state["ready_op_ids"]:
        if op_id in graph_state["completed_or_fixed_op_ids"] or op_id in graph_state["blocked_op_ids"]:
            continue
        batch_id, _op = graph_state["op_by_id"][op_id]
        if batch_id in blocked_batches:
            continue
        ready_op_ids.append(op_id)
    # The pick itself is order-free (every dispatch key ends with the op_id), but scoring stops at the
    # first candidate that raises, so the sort keeps *which* invalid operation surfaces deterministic.
    # Measured at 0.2% of a 300-operation graph decode; keyed on the map's own lookup, no lambda.
    if len(ready_op_ids) > 1:
        ready_op_ids.sort(key=graph_state["sort_key_by_op_id"].__getitem__)
    return [graph_state["op_by_id"][op_id] for op_id in ready_op_ids]


def _ensure_graph_ready_complete(
    *, graph_state: Dict[str, Any], ops_by_batch: Dict[str, List[OpForScheduleAlgo]], blocked_batches: set,
) -> None:
    expected = set(graph_state["op_by_id"])
    finished = graph_state["completed_or_fixed_op_ids"]
    blocked = set(graph_state["blocked_op_ids"])
    for batch_id in blocked_batches:
        blocked.update(op.id for op in ops_by_batch.get(batch_id, []))
    if expected.issubset(finished.union(blocked)):
        return
    remaining = sorted(expected.difference(finished).difference(blocked))
    raise ValidationError(f"图 ready 队列没有可排工序，但仍有未完成工序：{remaining}", field="graph_ready_context")


def mark_graph_operation_completed(graph_state: Dict[str, Any], op_id: int) -> None:
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    completed_or_fixed.add(op_id)
    graph_state["ready_op_ids"].discard(op_id)
    for successor_id in graph_state["successor_op_ids_by_op_id"][op_id]:
        if successor_id not in graph_state["op_by_id"]:
            continue
        if successor_id in completed_or_fixed or successor_id in graph_state["blocked_op_ids"]:
            continue
        remaining = graph_state["remaining_predecessor_count_by_op_id"][successor_id] - 1
        graph_state["remaining_predecessor_count_by_op_id"][successor_id] = remaining
        if remaining == 0:
            graph_state["ready_op_ids"].add(successor_id)
