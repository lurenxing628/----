from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int

from .sgs_scoring import _collect_sgs_candidates


def _op_id(op: Any) -> int:
    return parse_required_int(getattr(op, "id", 0), field="id")


def _is_graph_like(value: Any) -> bool:
    return hasattr(value, "nodes") and hasattr(value, "edges")


def _graph_ready_op_id_set(value: Any, *, field: str) -> set:
    if value is None:
        raise ValidationError(f"图 ready 队列上下文缺少 {field} 集合。", field="graph_ready_context")
    if isinstance(value, (str, bytes)):
        raise ValidationError(f"图 ready 队列上下文 {field} 必须是 op_id 集合。", field="graph_ready_context")
    if _is_graph_like(value):
        raise ValidationError(f"图 ready 队列上下文 {field} 只能传普通 op_id 集合，不能传图对象。", field="graph_ready_context")
    try:
        return {parse_required_int(item, field=field, min_value=1) for item in value}
    except TypeError as exc:
        raise ValidationError(f"图 ready 队列上下文 {field} 必须是 op_id 集合。", field="graph_ready_context") from exc


def _prepare_graph_ready_state(
    graph_ready_context: Optional[Any],
    *,
    ops_by_batch: Dict[str, List[Any]],
) -> Optional[Dict[str, Any]]:
    if graph_ready_context is None:
        return None
    if not isinstance(graph_ready_context, dict) or not graph_ready_context.get("enabled"):
        raise ValidationError("图 ready 队列上下文无效，不能启用图排产候选。", field="graph_ready_context")

    op_by_id: Dict[int, Tuple[str, Any]] = {}
    for batch_id, operations in ops_by_batch.items():
        for op in operations:
            op_id = _op_id(op)
            if op_id in op_by_id:
                raise ValidationError(f"图 ready 队列上下文发现重复 op_id：{op_id}", field="graph_ready_context")
            op_by_id[op_id] = (batch_id, op)

    schedulable_ids = _graph_ready_op_id_set(graph_ready_context.get("schedulable_op_ids"), field="schedulable_op_ids")
    fixed_op_ids = _graph_ready_op_id_set(graph_ready_context.get("fixed_op_ids"), field="fixed_op_ids")
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
    if schedulable_ids != set(op_by_id):
        raise ValidationError("图 ready 队列上下文和本次待排工序不一致。", field="graph_ready_context")
    predecessor_map = graph_ready_context.get("predecessor_op_ids_by_op_id")
    successor_map = graph_ready_context.get("successor_op_ids_by_op_id")
    predecessor_map, successor_map = _validate_graph_ready_links(
        op_ids=set(op_by_id).union(fixed_op_ids),
        predecessor_map=predecessor_map,
        successor_map=successor_map,
    )
    score_enabled = _graph_score_enabled(graph_ready_context.get("score_enabled", False))
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]] = {}
    if score_enabled:
        graph_priority_key_by_op_id = _graph_priority_key_map(
            graph_ready_context.get("graph_priority_key_by_op_id"),
            schedulable_ids=set(op_by_id),
        )
    sort_key_by_op_id = _graph_sort_key_map(
        graph_ready_context.get("sort_key_by_op_id"),
        schedulable_ids=set(op_by_id),
    )
    remaining_predecessor_count_by_op_id, ready_op_ids = _initialize_graph_ready_frontier(
        schedulable_ids=set(op_by_id),
        completed_or_fixed_op_ids=fixed_op_ids,
        predecessor_op_ids_by_op_id=predecessor_map,
    )
    return {
        "op_by_id": op_by_id,
        "completed_or_fixed_op_ids": fixed_op_ids,
        "blocked_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": sort_key_by_op_id,
        "remaining_predecessor_count_by_op_id": remaining_predecessor_count_by_op_id,
        "ready_op_ids": ready_op_ids,
        "score_enabled": score_enabled,
        "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
    }


def _graph_score_enabled(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("图评分开关 score_enabled 必须是 bool。", field="graph_ready_context")
    return bool(value)


def _graph_priority_key_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError("图评分 key 不能包含 NaN 或 Inf。", field="graph_ready_context")
    return number


def _graph_priority_key_map(value: Any, *, schedulable_ids: set) -> Dict[int, Tuple[float, ...]]:
    if not isinstance(value, dict):
        raise ValidationError("图评分上下文缺少 graph_priority_key_by_op_id 映射。", field="graph_ready_context")
    normalized: Dict[int, Tuple[float, ...]] = {}
    for op_id in sorted(schedulable_ids):
        if op_id not in value:
            raise ValidationError(f"图评分上下文缺少待排工序 {op_id} 的评分 key。", field="graph_ready_context")
        raw_key = value[op_id]
        if raw_key is None or isinstance(raw_key, (str, bytes)) or _is_graph_like(raw_key):
            raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context")
        try:
            key = tuple(_graph_priority_key_number(item) for item in raw_key)
        except TypeError as exc:
            raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context") from exc
        if not key:
            raise ValidationError("图评分 key 不能为空。", field="graph_ready_context")
        normalized[op_id] = key
    return normalized


def _graph_sort_key_map(value: Any, *, schedulable_ids: set) -> Dict[int, Tuple[int, int, int]]:
    if not isinstance(value, dict):
        raise ValidationError("图 ready 队列上下文 sort_key_by_op_id 必须是映射。", field="graph_ready_context")
    for raw_op_id in value:
        if isinstance(raw_op_id, bool) or not isinstance(raw_op_id, int) or raw_op_id <= 0:
            raise ValidationError("图 ready 队列上下文 sort_key_by_op_id 的 key 必须是正整数 op_id。", field="graph_ready_context")

    normalized: Dict[int, Tuple[int, int, int]] = {}
    for op_id in sorted(schedulable_ids):
        if op_id not in value:
            raise ValidationError(f"图 ready 队列缺少工序 {op_id} 的排序 key。", field="graph_ready_context")
        raw_key = value[op_id]
        if not isinstance(raw_key, tuple) or len(raw_key) != 3:
            raise ValidationError(f"图 ready 队列工序 {op_id} 的排序 key 必须是三元组。", field="graph_ready_context")
        try:
            normalized[op_id] = (
                parse_required_int(raw_key[0], field=f"sort_key_by_op_id[{op_id}]"),
                parse_required_int(raw_key[1], field=f"sort_key_by_op_id[{op_id}]"),
                parse_required_int(raw_key[2], field=f"sort_key_by_op_id[{op_id}]"),
            )
        except ValidationError as exc:
            raise ValidationError(f"图 ready 队列工序 {op_id} 的排序 key 必须只包含整数。", field="graph_ready_context") from exc
    return normalized


def _normalize_link_map(value: Any, *, field: str) -> Dict[int, set]:
    if not isinstance(value, dict):
        raise ValidationError(f"图 ready 队列上下文缺少 {field} 映射。", field="graph_ready_context")
    normalized: Dict[int, set] = {}
    for raw_op_id, raw_linked_ids in value.items():
        op_id = parse_required_int(raw_op_id, field=field)
        if raw_linked_ids is None or isinstance(raw_linked_ids, (str, bytes)):
            raise ValidationError(f"图 ready 队列上下文 {field} 映射不是集合。", field="graph_ready_context")
        if _is_graph_like(raw_linked_ids):
            raise ValidationError(f"图 ready 队列上下文 {field} 映射不能传图对象。", field="graph_ready_context")
        try:
            normalized[op_id] = {parse_required_int(item, field=field) for item in raw_linked_ids}
        except TypeError as exc:
            raise ValidationError(f"图 ready 队列上下文 {field} 映射不是集合。", field="graph_ready_context") from exc
    return normalized


def _validate_graph_ready_links(*, op_ids: set, predecessor_map: Any, successor_map: Any) -> Tuple[Dict[int, set], Dict[int, set]]:
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
        predecessors.setdefault(op_id, set())
        successors.setdefault(op_id, set())
    for op_id, predecessor_ids in predecessors.items():
        for predecessor_id in predecessor_ids:
            if op_id not in successors.get(predecessor_id, set()):
                raise ValidationError(
                    f"图 ready 队列上下文不一致：工序 {op_id} 记录了前置 {predecessor_id}，但后继映射没有对应关系。",
                    field="graph_ready_context",
                )
    for op_id, successor_ids in successors.items():
        for successor_id in successor_ids:
            if op_id not in predecessors.get(successor_id, set()):
                raise ValidationError(
                    f"图 ready 队列上下文不一致：工序 {op_id} 记录了后继 {successor_id}，但前置映射没有对应关系。",
                    field="graph_ready_context",
                )
    return predecessors, successors


def _validate_link_scope(*, link_map: Dict[int, set], known_op_ids: set, link_label: str) -> None:
    for op_id, linked_ids in link_map.items():
        if op_id not in known_op_ids:
            raise ValidationError(f"图 ready 队列上下文不完整：工序 {op_id} 不在待排或已固定集合里。", field="graph_ready_context")
        for linked_id in linked_ids:
            if linked_id not in known_op_ids:
                raise ValidationError(
                    f"图 ready 队列上下文不完整：工序 {op_id} 的{link_label} {linked_id} 既不是待排也不是固定/已完成。",
                    field="graph_ready_context",
                )


def _initialize_graph_ready_frontier(
    *,
    schedulable_ids: set,
    completed_or_fixed_op_ids: set,
    predecessor_op_ids_by_op_id: Dict[int, set],
) -> Tuple[Dict[int, int], set]:
    remaining_predecessor_count_by_op_id: Dict[int, int] = {}
    ready_op_ids = set()

    for op_id in sorted(schedulable_ids):
        remaining_count = sum(1 for predecessor_id in predecessor_op_ids_by_op_id.get(op_id, set()) if predecessor_id not in completed_or_fixed_op_ids)
        remaining_predecessor_count_by_op_id[op_id] = remaining_count
        if remaining_count == 0 and op_id not in completed_or_fixed_op_ids:
            ready_op_ids.add(op_id)

    return remaining_predecessor_count_by_op_id, ready_op_ids


def _collect_candidates(
    *,
    graph_state: Optional[Dict[str, Any]],
    batch_ids: List[str],
    ops_by_batch: Dict[str, List[Any]],
    next_idx: Dict[str, int],
    blocked_batches: set,
) -> List[Tuple[str, Any]]:
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
    ready_op_ids = sorted(ready_op_ids, key=lambda item: graph_state["sort_key_by_op_id"][item])
    return [graph_state["op_by_id"][op_id] for op_id in ready_op_ids]


def _ensure_graph_ready_complete(*, graph_state: Dict[str, Any], ops_by_batch: Dict[str, List[Any]], blocked_batches: set) -> None:
    expected = set(graph_state["op_by_id"])
    finished = set(graph_state["completed_or_fixed_op_ids"])
    blocked = set(graph_state["blocked_op_ids"])
    for batch_id in blocked_batches:
        blocked.update(_op_id(op) for op in ops_by_batch.get(batch_id, []))
    if expected.issubset(finished.union(blocked)):
        return
    remaining = sorted(expected.difference(finished).difference(blocked))
    raise ValidationError(f"图 ready 队列没有可排工序，但仍有未完成工序：{remaining}", field="graph_ready_context")


def _block_graph_operation(graph_state: Dict[str, Any], op_id: int) -> List[int]:
    blocked = graph_state["blocked_op_ids"]
    successors_by_op_id = graph_state["successor_op_ids_by_op_id"]
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    newly_blocked: List[int] = []
    stack = [op_id]
    while stack:
        current = stack.pop()
        if current in blocked:
            continue
        if current in completed_or_fixed:
            raise ValidationError(
                f"图 ready 队列阻塞状态和固定/已完成工序冲突：{current}",
                field="graph_ready_context",
            )
        blocked.add(current)
        graph_state["ready_op_ids"].discard(current)
        newly_blocked.append(current)
        stack.extend(successors_by_op_id.get(current) or set())
    return newly_blocked


def _mark_graph_operation_completed(graph_state: Dict[str, Any], op_id: int) -> None:
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    if op_id in completed_or_fixed:
        return

    completed_or_fixed.add(op_id)
    graph_state["ready_op_ids"].discard(op_id)
    for successor_id in graph_state["successor_op_ids_by_op_id"].get(op_id, set()):
        if successor_id not in graph_state["op_by_id"]:
            continue
        if successor_id in completed_or_fixed or successor_id in graph_state["blocked_op_ids"]:
            continue
        remaining = int(graph_state["remaining_predecessor_count_by_op_id"][successor_id]) - 1
        graph_state["remaining_predecessor_count_by_op_id"][successor_id] = remaining
        if remaining == 0:
            graph_state["ready_op_ids"].add(successor_id)


def _batch_failed_op_ids(batch_id: str, next_idx: Dict[str, int], ops_by_batch: Dict[str, List[Any]]) -> set:
    operations = ops_by_batch.get(batch_id) or []
    idx0 = int(next_idx.get(batch_id, 0) or 0)
    return {_op_id(op) for op in operations[idx0:]}


def _graph_op_label(graph_state: Dict[str, Any], op_id: int) -> str:
    op_entry = graph_state["op_by_id"].get(op_id)
    if not op_entry:
        return str(op_id)
    _batch_id, op = op_entry
    return str(getattr(op, "op_code", None) or op_id)


def _record_graph_blocked_operations(
    state: Any,
    *,
    graph_state: Dict[str, Any],
    failed_op_id: int,
    newly_blocked_op_ids: List[int],
    already_counted_op_ids: set,
) -> int:
    extra_failed_count = 0
    failed_label = _graph_op_label(graph_state, failed_op_id)
    for blocked_op_id in sorted(set(newly_blocked_op_ids)):
        if blocked_op_id == failed_op_id or blocked_op_id not in graph_state["op_by_id"]:
            continue
        blocked_label = _graph_op_label(graph_state, blocked_op_id)
        state.errors.append(f"工序 {blocked_label}：依赖的前序工序 {failed_label} 排产失败，本次跳过。")
        if blocked_op_id not in already_counted_op_ids:
            extra_failed_count += 1
    return extra_failed_count
