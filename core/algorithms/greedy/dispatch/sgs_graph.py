from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_runtime.graph_cycle import kahn_unreachable_op_ids
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
    predecessor_map = graph_ready_context.get("predecessor_op_ids_by_op_id")
    successor_map = graph_ready_context.get("successor_op_ids_by_op_id")
    predecessor_map, successor_map = _validate_graph_ready_links(
        op_ids=set(op_by_id).union(fixed_op_ids),
        predecessor_map=predecessor_map,
        successor_map=successor_map,
    )
    _detect_graph_ready_cycle(
        schedulable_ids=set(op_by_id),
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
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, label="图评分 key")
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


def _detect_graph_ready_cycle(*, schedulable_ids: set, predecessor_map: Dict[int, set], successor_map: Dict[int, set]) -> None:
    # 标准 Kahn 拓扑检测：借助上游 _validate_graph_ready_links 已校验双向一致的
    # successor_map 做 O(V+E) 后继释放，替代旧实现每弹出一个节点全表扫描 remaining
    # 的 O(V²) 写法（审计 D13；实测 V=2000 单次 55ms、V=5000 单次 345ms）。
    # 算法本体收敛到 core/algorithm_runtime/graph_cycle.py 的共享实现
    # （审计 A09：optimizer 侧第二份拷贝曾漏修，双拷贝已发生一次语义漂移）。
    if kahn_unreachable_op_ids(
        schedulable_ids=set(schedulable_ids),
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
    # The pick itself is order-free (every dispatch key ends with the op_id), but scoring stops at the
    # first candidate that raises, so the sort keeps *which* invalid operation surfaces deterministic.
    # Measured at 0.2% of a 300-operation graph decode; keyed on the map's own lookup, no lambda.
    if len(ready_op_ids) > 1:
        ready_op_ids.sort(key=graph_state["sort_key_by_op_id"].__getitem__)
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


def _block_graph_operation(graph_state: Dict[str, Any], op_id: int) -> Tuple[List[int], List[int]]:
    """阻塞失败工序及其尚未完成的待排后继，返回 (newly_blocked, fixed_conflicts)。

    - newly_blocked：本次新阻塞的待排工序（含失败工序自身）。
    - fixed_conflicts：传播撞到的"输入即固定"后继——即后道已报工（PROCESSING/
      PAUSED 进固定集）但前道排产失败的现场乱序报工形态（审计 A02）。这是
      可发生的生产输入，不再整趟 ValidationError 中止：固定工序现实中已执行，
      无需阻塞也不经它继续传播，由调用方按批失败留痕降级处理。
    - 传播撞到"本趟运行内已完成"的待排工序仍是内部不变量破坏（ready 队列要求
      前驱先完成，失败工序的后继不可能已完成），保持 fail-loud。
    """
    blocked = graph_state["blocked_op_ids"]
    successors_by_op_id = graph_state["successor_op_ids_by_op_id"]
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    input_fixed_op_ids = graph_state["input_fixed_op_ids"]
    newly_blocked: List[int] = []
    fixed_conflicts: List[int] = []
    stack = [op_id]
    while stack:
        current = stack.pop()
        if current in blocked:
            continue
        if current in completed_or_fixed:
            if current in input_fixed_op_ids:
                fixed_conflicts.append(current)
                continue
            raise ValidationError(
                f"图 ready 队列阻塞状态和固定/已完成工序冲突：{current}",
                field="graph_ready_context",
            )
        blocked.add(current)
        graph_state["ready_op_ids"].discard(current)
        newly_blocked.append(current)
        stack.extend(successors_by_op_id.get(current) or set())
    return newly_blocked, sorted(set(fixed_conflicts))


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


def _graph_batch_unreachable_ops(graph_state: Dict[str, Any], batch_id: str, ops_by_batch: Dict[str, List[Any]]) -> List[Any]:
    """图模式失败簿记（审计 A04）：按图状态推导该批内"尚未完成且不再可达"的待排工序。

    替代旧的按列表位置切片（operations[idx0:]）——批内列表按 (seq,id) 排、图链按
    (seq,op_code,node_id) 排，同批同 seq（多 piece 合法形态）时两套 tie-break 错位
    会造成失败工序双记、已成功工序被记跳过、真被阻塞工序零留痕（scheduled+failed
    可超 total）。必须在 _block_graph_operation 之后调用：失败工序与图传播新阻塞的
    工序都已进入 blocked_op_ids，这里只补"图传播覆盖不到、但因批级阻塞不再可达"
    的剩余工序（例如固定后继下游的待排工序）。
    """
    completed_or_fixed = graph_state["completed_or_fixed_op_ids"]
    blocked_op_ids = graph_state["blocked_op_ids"]
    remaining: List[Any] = []
    for op in ops_by_batch.get(batch_id) or []:
        op_id = _op_id(op)
        if op_id in completed_or_fixed or op_id in blocked_op_ids:
            continue
        remaining.append(op)
    return remaining


def _apply_graph_failure_bookkeeping(
    state: Any,
    *,
    graph_state: Dict[str, Any],
    batch_id: str,
    failed_op_id: int,
    ops_by_batch: Dict[str, List[Any]],
) -> Tuple[List[Any], int]:
    """派工失败后的图侧记账：阻塞传播 + 图状态推导被牵连集合 + 结构化留痕。

    返回 (skipped_ops, extra_failed_count)：
    - skipped_ops：批级阻塞后不再可达的剩余工序，由调用方按
      skipped_after_batch_failure 记明细并计数；
    - extra_failed_count：图传播新阻塞工序（graph_blocked_after_failure 明细）的
      追加失败计数。失败工序自身由调用方计 1，不在两者之内，保证
      scheduled + failed <= total 且明细与真实一致（审计 A04）。
    """
    newly_blocked_op_ids, fixed_conflict_op_ids = _block_graph_operation(graph_state, failed_op_id)
    skipped_ops = _graph_batch_unreachable_ops(graph_state, batch_id, ops_by_batch)
    extra_failed_count = _record_graph_blocked_operations(
        state,
        graph_state=graph_state,
        failed_op_id=failed_op_id,
        newly_blocked_op_ids=newly_blocked_op_ids,
        already_counted_op_ids={failed_op_id}.union(_op_id(op) for op in skipped_ops),
    )
    if fixed_conflict_op_ids:
        _record_graph_fixed_order_conflict(
            state,
            graph_state=graph_state,
            batch_id=batch_id,
            failed_op_id=failed_op_id,
            fixed_conflict_op_ids=fixed_conflict_op_ids,
        )
    return skipped_ops, extra_failed_count


def _record_graph_fixed_order_conflict(
    state: Any,
    *,
    graph_state: Dict[str, Any],
    batch_id: str,
    failed_op_id: int,
    fixed_conflict_op_ids: List[int],
) -> None:
    # 审计 A02：后道工序已报工/冻结（输入即固定）但前道排产失败——数据顺序异常。
    # 按批失败留痕（不中止整趟）：给失败工序追加一条结构化明细并写清冲突的固定
    # 后继 op_id，业务侧据此核对报工顺序；渲染文案见
    # core/models/scheduler_public_errors._structured_failure_message。
    _failed_batch_id, failed_op = graph_state["op_by_id"].get(failed_op_id, ("", None))
    if failed_op is None or not hasattr(state, "record_graph_fixed_order_conflict"):
        return
    state.record_graph_fixed_order_conflict(
        failed_op,
        batch_id,
        fixed_successor_op_ids=list(fixed_conflict_op_ids),
    )


def _record_graph_blocked_operations(
    state: Any,
    *,
    graph_state: Dict[str, Any],
    failed_op_id: int,
    newly_blocked_op_ids: List[int],
    already_counted_op_ids: set,
) -> int:
    extra_failed_count = 0
    for blocked_op_id in sorted(set(newly_blocked_op_ids)):
        if blocked_op_id == failed_op_id or blocked_op_id not in graph_state["op_by_id"]:
            continue
        blocked_batch_id, blocked_op = graph_state["op_by_id"][blocked_op_id]
        _failed_batch_id, failed_op = graph_state["op_by_id"].get(failed_op_id, ("", None))
        # 只走结构化 record_graph_blocked_after_failure；不再 append 原始串到 state.errors，
        # 否则会回落成 generic_scheduler_error 与具体文案双发（与 missing_batch/异常路径同源问题）。
        if blocked_op_id in already_counted_op_ids:
            continue
        if hasattr(state, "record_graph_blocked_after_failure"):
            state.record_graph_blocked_after_failure(blocked_op, blocked_batch_id, failed_op=failed_op)
        extra_failed_count += 1
    return extra_failed_count
