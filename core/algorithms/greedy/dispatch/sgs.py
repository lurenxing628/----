from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.dispatch_rules import DispatchRule, build_dispatch_key
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import EXTERNAL, INTERNAL
from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int

from ..internal_slot import estimate_internal_slot, validate_internal_hours_for_mode
from ..run_context import ensure_run_context
from ..run_state import ScheduleRunState
from .batch_order import _coerce_state, _schedule_op
from .ready_queue import ReadyQueueContractError, get_ready_operation_ids
from .sgs_scoring import (
    _collect_sgs_candidates,
    _positive_op_id,
    _score_external_candidate,
)
from .sgs_scoring import (
    _score_internal_candidate as _score_internal_candidate_impl,
)

_SCHEDULE_OPERATION_FAILED_MESSAGE = "排产异常，请查看系统日志。"


def _score_internal_candidate(**kwargs: Any) -> Tuple[float, ...]:
    return _score_internal_candidate_impl(
        **kwargs,
        estimate_slot=estimate_internal_slot,
        dispatch_key_builder=build_dispatch_key,
    )


def _pick_best_candidate(scored_candidates: List[Tuple[Tuple[float, ...], str, Any]]) -> Tuple[str, Any]:
    if not scored_candidates:
        raise RuntimeError("SGS 评分阶段未产生任何候选")
    _best_key, best_batch_id, best_op = min(scored_candidates, key=lambda item: item[0])
    return best_batch_id, best_op


def dispatch_sgs(
    context: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: Optional[ScheduleRunState] = None,
    batch_progress: Optional[Dict[str, datetime]] = None,
    external_group_cache: Optional[Dict[Tuple[str, str], Tuple[datetime, datetime]]] = None,
    machine_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    operator_timeline: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    machine_busy_hours: Optional[Dict[str, float]] = None,
    operator_busy_hours: Optional[Dict[str, float]] = None,
    last_op_type_by_machine: Optional[Dict[str, str]] = None,
    last_end_by_machine: Optional[Dict[str, datetime]] = None,
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    graph_ready_context: Optional[Any] = None,
    results: Optional[List[ScheduleResult]] = None,
    errors: Optional[List[str]] = None,
    blocked_batches: Optional[set] = None,
    scheduled_count: int = 0,
    failed_count: int = 0,
    strict_mode: bool = False,
) -> Tuple[int, int]:
    ctx = ensure_run_context(context)
    run_state = _coerce_state(
        state=state,
        base_time=base_time,
        batch_progress=batch_progress,
        external_group_cache=external_group_cache,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        last_op_type_by_machine=last_op_type_by_machine,
        last_end_by_machine=last_end_by_machine,
        results=results,
        errors=errors,
        blocked_batches=blocked_batches,
        scheduled_count=scheduled_count,
        failed_count=failed_count,
    )
    ops_by_batch = _group_sgs_ops(sorted_ops=sorted_ops, batches=batches, state=run_state)
    batch_ids = sorted(list(ops_by_batch.keys()), key=lambda item: (batch_order.get(item, 999999), item))
    next_idx: Dict[str, int] = {batch_id: 0 for batch_id in batch_ids}
    avg_proc_hours, total_hours_by_op_id = _average_proc_hours(
        ctx,
        ops_by_batch=ops_by_batch,
        batches=batches,
        strict_mode=bool(strict_mode),
    )
    _run_sgs_loop(
        ctx,
        run_state,
        ops_by_batch,
        batch_ids,
        next_idx,
        batches,
        batch_order,
        dispatch_rule,
        end_dt_exclusive,
        machine_downtimes,
        auto_assign_enabled,
        resource_pool,
        bool(strict_mode),
        avg_proc_hours,
        total_hours_by_op_id,
        graph_ready_context,
    )
    _ = scheduled_count
    return run_state.scheduled_count, run_state.failed_count


def _group_sgs_ops(*, sorted_ops: List[Any], batches: Dict[str, Any], state: ScheduleRunState) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for op in sorted_ops:
        batch_id = str(getattr(op, "batch_id", "") or "").strip()
        if batch_id not in batches:
            state.failed_count += 1
            state.errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {batch_id}")
            continue
        grouped.setdefault(batch_id, []).append(op)
    for operations in grouped.values():
        operations.sort(
            key=lambda item: (
                parse_required_int(getattr(item, "seq", 0), field="seq"),
                parse_required_int(getattr(item, "id", 0), field="id"),
            )
        )
    return grouped


def _average_proc_hours(
    ctx: Any,
    *,
    ops_by_batch: Dict[str, List[Any]],
    batches: Dict[str, Any],
    strict_mode: bool,
) -> Tuple[float, Dict[int, float]]:
    samples: List[float] = []
    total_hours_by_op_id: Dict[int, float] = {}
    for batch_id, operations in ops_by_batch.items():
        batch = batches.get(batch_id)
        for op in operations:
            if batch and (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == INTERNAL:
                sample = _append_proc_sample(samples, op=op, batch=batch, strict_mode=strict_mode)
                if sample is not None:
                    cache_key = _positive_op_id(getattr(op, "id", 0))
                    if cache_key is not None:
                        total_hours_by_op_id[cache_key] = float(sample)
    if samples:
        return sum(samples) / float(len(samples)), total_hours_by_op_id
    ctx.increment("dispatch_key_avg_proc_hours_fallback_count")
    return 1.0, total_hours_by_op_id


def _append_proc_sample(samples: List[float], *, op: Any, batch: Any, strict_mode: bool) -> Optional[float]:
    try:
        sample = validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)
    except ValueError:
        return None
    samples.append(sample)
    return float(sample)


def _run_sgs_loop(
    ctx: Any,
    state: ScheduleRunState,
    ops_by_batch: Dict[str, List[Any]],
    batch_ids: List[str],
    next_idx: Dict[str, int],
    batches: Dict[str, Any],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
    graph_ready_context: Optional[Any],
) -> None:
    graph_state = _prepare_graph_ready_state(graph_ready_context, ops_by_batch=ops_by_batch)
    while True:
        candidates = _collect_candidates(
            graph_state=graph_state,
            batch_ids=batch_ids,
            ops_by_batch=ops_by_batch,
            next_idx=next_idx,
            blocked_batches=state.blocked_batches,
        )
        if not candidates:
            if graph_state is not None:
                _ensure_graph_ready_complete(graph_state=graph_state, ops_by_batch=ops_by_batch)
            return
        batch_id, op = _pick_best_candidate(
            _score_candidates(
                ctx,
                state,
                candidates,
                batches,
                batch_order,
                dispatch_rule,
                end_dt_exclusive,
                machine_downtimes,
                auto_assign_enabled,
                resource_pool,
                strict_mode,
                avg_proc_hours,
                total_hours_by_op_id,
            )
        )
        _dispatch_selected(
            ctx,
            state,
            op,
            batch_id,
            batches,
            next_idx,
            ops_by_batch,
            end_dt_exclusive,
            machine_downtimes,
            auto_assign_enabled,
            resource_pool,
            strict_mode,
            graph_state=graph_state,
        )


def _score_candidates(
    ctx: Any,
    state: ScheduleRunState,
    candidates: List[Tuple[str, Any]],
    batches: Dict[str, Any],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
) -> List[Tuple[Tuple[float, ...], str, Any]]:
    return [
        (
            _score_candidate(
                ctx,
                state,
                op,
                batches[batch_id],
                batch_id,
                batch_order,
                dispatch_rule,
                end_dt_exclusive,
                machine_downtimes,
                auto_assign_enabled,
                resource_pool,
                strict_mode,
                avg_proc_hours,
                total_hours_by_op_id,
            ),
            batch_id,
            op,
        )
        for batch_id, op in candidates
    ]


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
        return {parse_required_int(item, field=field) for item in value}
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
    if schedulable_ids != set(op_by_id):
        raise ValidationError("图 ready 队列上下文和本次待排工序不一致。", field="graph_ready_context")
    predecessor_map = graph_ready_context.get("predecessor_op_ids_by_op_id")
    successor_map = graph_ready_context.get("successor_op_ids_by_op_id")
    predecessor_map, successor_map = _validate_graph_ready_links(
        op_ids=set(op_by_id).union(fixed_op_ids),
        predecessor_map=predecessor_map,
        successor_map=successor_map,
    )
    return {
        "op_by_id": op_by_id,
        "completed_or_fixed_op_ids": fixed_op_ids,
        "blocked_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": graph_ready_context.get("sort_key_by_op_id"),
    }


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
    blocked_op_ids = set(graph_state["blocked_op_ids"])
    for op_id, (batch_id, _op) in graph_state["op_by_id"].items():
        if batch_id in blocked_batches:
            blocked_op_ids.add(op_id)
    try:
        ready_op_ids = get_ready_operation_ids(
            schedulable_op_ids=set(graph_state["op_by_id"]),
            completed_or_fixed_op_ids=graph_state["completed_or_fixed_op_ids"],
            blocked_op_ids=blocked_op_ids,
            predecessor_op_ids_by_op_id=graph_state["predecessor_op_ids_by_op_id"],
            sort_key_by_op_id=graph_state["sort_key_by_op_id"],
        )
    except ReadyQueueContractError as exc:
        raise ValidationError(f"图 ready 队列上下文无效：{exc}", field="graph_ready_context") from exc
    return [graph_state["op_by_id"][op_id] for op_id in ready_op_ids]


def _ensure_graph_ready_complete(*, graph_state: Dict[str, Any], ops_by_batch: Dict[str, List[Any]]) -> None:
    expected = set(graph_state["op_by_id"])
    finished = set(graph_state["completed_or_fixed_op_ids"])
    blocked = set(graph_state["blocked_op_ids"])
    if expected.issubset(finished.union(blocked)):
        return
    remaining = sorted(expected.difference(finished).difference(blocked))
    raise ValidationError(f"图 ready 队列没有可排工序，但仍有未完成工序：{remaining}", field="graph_ready_context")


def _block_graph_operation(graph_state: Dict[str, Any], op_id: int) -> List[int]:
    blocked = graph_state["blocked_op_ids"]
    successors_by_op_id = graph_state["successor_op_ids_by_op_id"]
    newly_blocked: List[int] = []
    stack = [op_id]
    while stack:
        current = stack.pop()
        if current in blocked:
            continue
        blocked.add(current)
        newly_blocked.append(current)
        stack.extend(successors_by_op_id.get(current) or set())
    return newly_blocked


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
    state: ScheduleRunState,
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


def _score_candidate(
    ctx: Any,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
) -> Tuple[float, ...]:
    def score() -> Tuple[float, ...]:
        if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == EXTERNAL:
            return _score_external_candidate(
                ctx=ctx,
                state=state,
                op=op,
                batch=batch,
                batch_id=batch_id,
                batch_order=batch_order,
                dispatch_rule=dispatch_rule,
                end_dt_exclusive=end_dt_exclusive,
                avg_proc_hours=avg_proc_hours,
                strict_mode=strict_mode,
                dispatch_key_builder=build_dispatch_key,
            )
        return _score_internal_candidate(
            ctx=ctx,
            state=state,
            op=op,
            batch=batch,
            batch_id=batch_id,
            batch_order=batch_order,
            dispatch_rule=dispatch_rule,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            avg_proc_hours=avg_proc_hours,
            total_hours_by_op_id=total_hours_by_op_id,
            strict_mode=strict_mode,
        )

    return score()


def _dispatch_selected(
    ctx: Any,
    state: ScheduleRunState,
    op: Any,
    batch_id: str,
    batches: Dict[str, Any],
    next_idx: Dict[str, int],
    ops_by_batch: Dict[str, List[Any]],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
    graph_state: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        result, _blocked = _schedule_op(
            ctx,
            op=op,
            batch=batches[batch_id],
            state=state,
            base_time=state.base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            strict_mode=strict_mode,
        )
        if result and result.start_time and result.end_time:
            state.record_dispatch_success(result)
            next_idx[batch_id] = int(next_idx.get(batch_id, 0) or 0) + 1
            if graph_state is not None:
                graph_state["completed_or_fixed_op_ids"].add(_op_id(op))
        else:
            extra_failed_count = 0
            if graph_state is not None:
                failed_op_id = _op_id(op)
                newly_blocked_op_ids = _block_graph_operation(graph_state, failed_op_id)
                extra_failed_count = _record_graph_blocked_operations(
                    state,
                    graph_state=graph_state,
                    failed_op_id=failed_op_id,
                    newly_blocked_op_ids=newly_blocked_op_ids,
                    already_counted_op_ids=_batch_failed_op_ids(batch_id, next_idx, ops_by_batch),
                )
            state.record_dispatch_failure(
                batch_id,
                block=True,
                remaining_failed=_remaining_failed(batch_id, next_idx, ops_by_batch) + extra_failed_count,
            )
    except ValidationError:
        raise
    except Exception:
        extra_failed_count = 0
        state.errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'} {_SCHEDULE_OPERATION_FAILED_MESSAGE}")
        if graph_state is not None:
            failed_op_id = _op_id(op)
            newly_blocked_op_ids = _block_graph_operation(graph_state, failed_op_id)
            extra_failed_count = _record_graph_blocked_operations(
                state,
                graph_state=graph_state,
                failed_op_id=failed_op_id,
                newly_blocked_op_ids=newly_blocked_op_ids,
                already_counted_op_ids=_batch_failed_op_ids(batch_id, next_idx, ops_by_batch),
            )
        state.failed_count += 1 + _remaining_failed(batch_id, next_idx, ops_by_batch) + extra_failed_count
        ctx.log_exception(f"工序 {getattr(op, 'op_code', '-') or '-'} 排产异常")
        state.blocked_batches.add(batch_id)


def _remaining_failed(batch_id: str, next_idx: Dict[str, int], ops_by_batch: Dict[str, List[Any]]) -> int:
    idx0 = int(next_idx.get(batch_id, 0) or 0)
    return max(int(len(ops_by_batch.get(batch_id) or [])) - (idx0 + 1), 0)
