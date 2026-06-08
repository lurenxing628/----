"""Graph ready queue helpers for SGS dispatch.

This module works on plain Python values only and must not import NetworkX.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple


class ReadyQueueContractError(ValueError):
    pass


def _normalize_op_id(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ReadyQueueContractError(f"{field} 必须是正整数 op_id：{value!r}")
    try:
        op_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ReadyQueueContractError(f"{field} 必须是正整数 op_id：{value!r}") from exc
    if op_id <= 0:
        raise ReadyQueueContractError(f"{field} 必须是正整数 op_id：{value!r}")
    return op_id


def _op_id_set(values: Iterable[Any], *, field: str) -> Set[int]:
    if values is None:
        raise ReadyQueueContractError(f"{field} 不能为空。")
    if isinstance(values, (str, bytes)):
        raise ReadyQueueContractError(f"{field} 必须是 op_id 集合。")
    if hasattr(values, "nodes") and hasattr(values, "edges"):
        raise ReadyQueueContractError(f"{field} 只能传普通 op_id 集合，不能传图对象。")
    try:
        return {_normalize_op_id(value, field=field) for value in values}
    except TypeError as exc:
        raise ReadyQueueContractError(f"{field} 必须是 op_id 集合。") from exc


def _validate_sort_key_mapping(sort_key_by_op_id: Mapping[int, Tuple[int, int, int]]) -> None:
    if not isinstance(sort_key_by_op_id, Mapping):
        raise ReadyQueueContractError("sort_key_by_op_id 必须是映射。")
    for raw_op_id in sort_key_by_op_id:
        if isinstance(raw_op_id, bool) or not isinstance(raw_op_id, int) or raw_op_id <= 0:
            raise ReadyQueueContractError("sort_key_by_op_id 的 key 必须是正整数 op_id。")


def _predecessor_map(values: Mapping[int, Iterable[Any]]) -> Dict[int, Set[int]]:
    if not isinstance(values, Mapping):
        raise ReadyQueueContractError("predecessor_op_ids_by_op_id 必须是映射。")
    result: Dict[int, Set[int]] = {}
    for raw_op_id, raw_predecessors in values.items():
        op_id = _normalize_op_id(raw_op_id, field="predecessor_op_ids_by_op_id.key")
        if raw_predecessors is None:
            raise ReadyQueueContractError(f"工序 {op_id} 的前置集合不能为空。")
        result[op_id] = _op_id_set(raw_predecessors, field=f"predecessor_op_ids_by_op_id[{op_id}]")
    return result


def _validate_predecessor_scope(
    *,
    predecessor_op_ids_by_op_id: Mapping[int, Set[int]],
    known_op_ids: Set[int],
) -> None:
    for op_id, predecessor_ids in predecessor_op_ids_by_op_id.items():
        if op_id not in known_op_ids:
            raise ReadyQueueContractError(f"ready 队列上下文不完整：工序 {op_id} 不在待排或已固定集合里。")
        for predecessor_id in predecessor_ids:
            if predecessor_id not in known_op_ids:
                raise ReadyQueueContractError(
                    f"ready 队列上下文不完整：工序 {op_id} 的前置工序 {predecessor_id} 既不是待排也不是固定/已完成。"
                )


def _validate_ready_context(
    *,
    schedulable_op_ids: Set[int],
    completed_or_fixed_op_ids: Set[int],
    blocked_op_ids: Set[int],
    predecessor_op_ids_by_op_id: Mapping[int, Set[int]],
) -> None:
    overlap = blocked_op_ids.intersection(completed_or_fixed_op_ids)
    if overlap:
        raise ReadyQueueContractError(f"blocked_op_ids 不能同时出现在 completed_or_fixed_op_ids：{sorted(overlap)}")
    for op_id in schedulable_op_ids:
        if op_id not in predecessor_op_ids_by_op_id:
            raise ReadyQueueContractError(f"ready 队列缺少工序 {op_id} 的前置集合。")


def _sort_key(sort_key_by_op_id: Mapping[int, Tuple[int, int, int]], op_id: int) -> Tuple[int, int, int]:
    if op_id not in sort_key_by_op_id:
        raise ReadyQueueContractError(f"ready 队列缺少工序 {op_id} 的排序 key。")
    raw_key = sort_key_by_op_id[op_id]
    if not isinstance(raw_key, tuple) or len(raw_key) != 3:
        raise ReadyQueueContractError(f"ready 队列工序 {op_id} 的排序 key 必须是三元组。")
    if any(isinstance(item, bool) for item in raw_key):
        raise ReadyQueueContractError(f"ready 队列工序 {op_id} 的排序 key 必须只包含整数。")
    try:
        return (int(raw_key[0]), int(raw_key[1]), int(raw_key[2]))
    except (TypeError, ValueError) as exc:
        raise ReadyQueueContractError(f"ready 队列工序 {op_id} 的排序 key 必须只包含整数。") from exc


def get_ready_operation_ids(
    *,
    schedulable_op_ids: Iterable[Any],
    completed_or_fixed_op_ids: Iterable[Any],
    blocked_op_ids: Iterable[Any],
    predecessor_op_ids_by_op_id: Mapping[int, Iterable[Any]],
    sort_key_by_op_id: Mapping[int, Tuple[int, int, int]],
) -> List[int]:
    """Return schedulable op_ids whose predecessors are all completed or fixed.

    我是故意的：这份全量扫描版保留给测试当差分 oracle，用来对照
    生产 SGS 的增量 ready queue；生产 SGS 不调用这个 helper。
    """

    schedulable_ids = _op_id_set(schedulable_op_ids, field="schedulable_op_ids")
    completed_or_fixed_ids = _op_id_set(completed_or_fixed_op_ids, field="completed_or_fixed_op_ids")
    blocked_ids = _op_id_set(blocked_op_ids, field="blocked_op_ids")
    _validate_sort_key_mapping(sort_key_by_op_id)
    predecessors = _predecessor_map(predecessor_op_ids_by_op_id)
    known_ids = set(schedulable_ids)
    known_ids.update(completed_or_fixed_ids)
    _validate_predecessor_scope(predecessor_op_ids_by_op_id=predecessors, known_op_ids=known_ids)
    _validate_ready_context(
        schedulable_op_ids=schedulable_ids,
        completed_or_fixed_op_ids=completed_or_fixed_ids,
        blocked_op_ids=blocked_ids,
        predecessor_op_ids_by_op_id=predecessors,
    )

    ready_ids: List[int] = []
    for op_id in schedulable_ids:
        if op_id in completed_or_fixed_ids or op_id in blocked_ids:
            continue
        predecessor_ids = predecessors.get(op_id, set())
        if predecessor_ids.issubset(completed_or_fixed_ids):
            ready_ids.append(op_id)
    return sorted(ready_ids, key=lambda item: _sort_key(sort_key_by_op_id, item))


__all__ = ["ReadyQueueContractError", "get_ready_operation_ids"]
