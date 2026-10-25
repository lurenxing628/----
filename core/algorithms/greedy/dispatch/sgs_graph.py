from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, AbstractSet, Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from core.algorithm_runtime.graph_cycle import kahn_unreachable_op_ids
from core.errors import ValidationError
from core.shared.strict_parse import parse_required_int

from .sgs_priority_keys import ValidatedGraphPriorityKeys
from .sgs_scoring import _collect_sgs_candidates

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo

TOPOLOGY_FIELD = "_prepared_graph_ready_topology"


@dataclass(frozen=True)
class PreparedGraphReadyTopology:
    """Decode-independent facts; progress and priority belong to each decode."""

    schedulable_ids: FrozenSet[int]
    fixed_ids: FrozenSet[int]
    predecessors: Mapping[int, FrozenSet[int]]
    successors: Mapping[int, FrozenSet[int]]
    sort_keys: Mapping[int, Tuple[int, int, int]]



def prepare_graph_ready_topology(context, operations: List[OpForScheduleAlgo]) -> PreparedGraphReadyTopology:
    raw = dict(context)
    raw.pop(TOPOLOGY_FIELD, None)
    raw["score_enabled"] = False
    grouped: Dict[str, List[OpForScheduleAlgo]] = {}
    for op in operations:
        grouped.setdefault(op.batch_id, []).append(op)
    state = _prepare_graph_ready_state(raw, ops_by_batch=grouped)
    if state is None:
        raise ValidationError("图 ready 队列上下文无效，不能启用图排产候选。", field="graph_ready_context")
    return PreparedGraphReadyTopology(
        frozenset(state["op_by_id"]), state["input_fixed_op_ids"],
        MappingProxyType({key: frozenset(value) for key, value in state["predecessor_op_ids_by_op_id"].items()}),
        MappingProxyType({key: frozenset(value) for key, value in state["successor_op_ids_by_op_id"].items()}),
        MappingProxyType(dict(state["sort_key_by_op_id"])),
    )


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
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    skip_initial_frontier: bool = False,
) -> Optional[Dict[str, Any]]:
    if graph_ready_context is None:
        return None
    if not isinstance(graph_ready_context, dict) or not graph_ready_context.get("enabled"):
        raise ValidationError("图 ready 队列上下文无效，不能启用图排产候选。", field="graph_ready_context")

    op_by_id: Dict[int, Tuple[str, OpForScheduleAlgo]] = {}
    for batch_id, operations in ops_by_batch.items():
        for op in operations:
            op_id = op.id
            if op_id in op_by_id:
                raise ValidationError(f"图 ready 队列上下文发现重复 op_id：{op_id}", field="graph_ready_context")
            op_by_id[op_id] = (batch_id, op)

    topology: Any = graph_ready_context.get(TOPOLOGY_FIELD)
    prepared: Optional[PreparedGraphReadyTopology] = (
        cast(PreparedGraphReadyTopology, topology)
        if type(topology) is PreparedGraphReadyTopology else None
    )
    if prepared is not None:
        schedulable_ids, fixed_op_ids = set(prepared.schedulable_ids), set(prepared.fixed_ids)
    else:
        schedulable_ids = _graph_ready_op_id_set(graph_ready_context.get("schedulable_op_ids"), field="schedulable_op_ids")
        fixed_op_ids = _graph_ready_op_id_set(graph_ready_context.get("fixed_op_ids"), field="fixed_op_ids")
        _validate_fixed_op_sources(graph_ready_context.get("fixed_op_sources_by_op_id"), fixed_op_ids=fixed_op_ids)
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
    if prepared is not None:
        predecessor_map, successor_map = prepared.predecessors, prepared.successors
    else:
        predecessor_map, successor_map = _validate_graph_ready_links(
            op_ids=set(op_by_id).union(fixed_op_ids),
            predecessor_map=graph_ready_context.get("predecessor_op_ids_by_op_id"),
            successor_map=graph_ready_context.get("successor_op_ids_by_op_id"),
        )
        _detect_graph_ready_cycle(schedulable_ids=set(op_by_id), predecessor_map=predecessor_map, successor_map=successor_map)
    score_enabled = graph_score_enabled(graph_ready_context.get("score_enabled", False))
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]] = {}
    if score_enabled:
        graph_priority_key_by_op_id = (graph_ready_context["graph_priority_key_by_op_id"] if prepared is not None
            else graph_priority_key_map(graph_ready_context.get("graph_priority_key_by_op_id"),
                                         schedulable_ids=set(op_by_id)))
    sort_key_by_op_id = prepared.sort_keys if prepared is not None else _graph_sort_key_map(
        graph_ready_context.get("sort_key_by_op_id"),
        schedulable_ids=set(op_by_id),
    )
    if skip_initial_frontier:
        remaining_predecessor_count_by_op_id: Dict[int, int] = {}
        ready_op_ids: Set[int] = set()
    else:
        remaining_predecessor_count_by_op_id, ready_op_ids = _initialize_graph_ready_frontier(
            schedulable_ids=set(op_by_id),
            completed_or_fixed_op_ids=fixed_op_ids,
            predecessor_op_ids_by_op_id=predecessor_map,
        )
    return {
        "op_by_id": op_by_id,
        "completed_or_fixed_op_ids": fixed_op_ids,
        # completed_or_fixed_op_ids 会随本趟排产成功不断并入新完成工序；
        # 这里冻结一份"输入即固定"（冻结窗/执行报工 seed）的快照，供失败阻塞
        # 传播区分"撞到已报工的固定后继（现场乱序报工，按批降级）"和
        # "撞到本趟已完成工序（内部不变量破坏，fail-loud）"（审计 A02）。
        "input_fixed_op_ids": frozenset(fixed_op_ids),
        "blocked_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": sort_key_by_op_id,
        "remaining_predecessor_count_by_op_id": remaining_predecessor_count_by_op_id,
        "ready_op_ids": ready_op_ids,
        "score_enabled": score_enabled,
        "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
    }


def graph_score_enabled(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("图评分开关 score_enabled 必须是 bool。", field="graph_ready_context")
    return value


def _graph_priority_key_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("图评分 key 必须是数字 tuple。", field="graph_ready_context")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError("图评分 key 不能包含 NaN 或 Inf。", field="graph_ready_context")
    return number


def graph_priority_key_map(value: Any, *, schedulable_ids: set) -> Dict[int, Tuple[float, ...]]:
    if not isinstance(value, dict):
        raise ValidationError("图评分上下文缺少 graph_priority_key_by_op_id 映射。", field="graph_ready_context")
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, label="图评分 key")
    normalized: Dict[int, Tuple[float, ...]] = ValidatedGraphPriorityKeys()
    for op_id in sorted(schedulable_ids):
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
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, label="图 ready 队列上下文 sort_key_by_op_id")
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


def _validate_exact_key_set(value: Dict[Any, Any], *, schedulable_ids: set, label: str) -> None:
    actual_ids = set()
    for raw_op_id in value:
        try:
            actual_ids.add(parse_required_int(raw_op_id, field="graph_ready_context", min_value=1))
        except ValidationError as exc:
            raise ValidationError(f"{label} 的 key 必须是正整数 op_id。", field="graph_ready_context") from exc
    if actual_ids != set(schedulable_ids):
        raise ValidationError(f"{label} 的 key 必须和待排工序完全一致。", field="graph_ready_context")


def _validate_fixed_op_sources(value: Any, *, fixed_op_ids: set) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError("图 ready 队列上下文 fixed_op_sources_by_op_id 必须是映射。", field="graph_ready_context")
    source_ids = {
        parse_required_int(raw_op_id, field="fixed_op_sources_by_op_id", min_value=1)
        for raw_op_id in value
    }
    if source_ids != set(fixed_op_ids):
        raise ValidationError("图 ready 队列上下文 fixed_op_sources_by_op_id 和 fixed_op_ids 不一致。", field="graph_ready_context")


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
            if op_id not in successors[predecessor_id]:
                raise ValidationError(
                    f"图 ready 队列上下文不一致：工序 {op_id} 记录了前置 {predecessor_id}，但后继映射没有对应关系。",
                    field="graph_ready_context",
                )
    for op_id, successor_ids in successors.items():
        for successor_id in successor_ids:
            if op_id not in predecessors[successor_id]:
                raise ValidationError(
                    f"图 ready 队列上下文不一致：工序 {op_id} 记录了后继 {successor_id}，但前置映射没有对应关系。",
                    field="graph_ready_context",
                )
    return predecessors, successors


def _detect_graph_ready_cycle(*, schedulable_ids: set, predecessor_map: Dict[int, set], successor_map: Dict[int, set]) -> None:
    # 标准 Kahn 拓扑检测：借助上游 _validate_graph_ready_links 已校验双向一致的
    # successor_map 做 O(V+E) 后继释放，替代旧实现每弹出一个节点全表扫描 remaining
    # 的 O(V²) 写法（审计 D13；实测 V=2000 单次 55ms、V=5000 单次 345ms）。
    # 算法本体收敛到 core/algorithm_runtime/graph_cycle.py 的共享实现
    # （审计 A09：optimizer 侧第二份拷贝曾漏修，双拷贝已发生一次语义漂移）。
    if kahn_unreachable_op_ids(
        schedulable_ids=schedulable_ids,
        predecessor_map=predecessor_map,
        successor_map=successor_map,
    ):
        raise ValidationError("图 ready 队列上下文包含环形前后置关系。", field="graph_ready_context")


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
    predecessor_op_ids_by_op_id: Mapping[int, AbstractSet[int]],
) -> Tuple[Dict[int, int], set]:
    remaining_predecessor_count_by_op_id: Dict[int, int] = {}
    ready_op_ids = set()

    for op_id in sorted(schedulable_ids):
        remaining_count = sum(1 for predecessor_id in predecessor_op_ids_by_op_id[op_id] if predecessor_id not in completed_or_fixed_op_ids)
        remaining_predecessor_count_by_op_id[op_id] = remaining_count
        if remaining_count == 0 and op_id not in completed_or_fixed_op_ids:
            ready_op_ids.add(op_id)

    return remaining_predecessor_count_by_op_id, ready_op_ids


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
    if op_id in completed_or_fixed:
        return

    completed_or_fixed.add(op_id)
    graph_state["ready_op_ids"].discard(op_id)
    for successor_id in graph_state["successor_op_ids_by_op_id"].get(op_id, set()):
        if successor_id not in graph_state["op_by_id"]:
            continue
        if successor_id in completed_or_fixed or successor_id in graph_state["blocked_op_ids"]:
            continue
        remaining = graph_state["remaining_predecessor_count_by_op_id"][successor_id] - 1
        graph_state["remaining_predecessor_count_by_op_id"][successor_id] = remaining
        if remaining == 0:
            graph_state["ready_op_ids"].add(successor_id)
