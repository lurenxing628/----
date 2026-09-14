from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.dispatch_rules import DispatchRule, build_dispatch_key
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import EXTERNAL, INTERNAL
from core.algorithm_runtime.dispatch_context import DispatchContextContractError, ensure_dispatch_context
from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours_for_mode
from core.algorithm_runtime.piece_input import operation_batch, operation_dispatch_state
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_reuse, sgs_handoff_scope
from core.algorithm_runtime.slot_overlap_reuse import sgs_overlap_reuse
from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int

from .batch_order import _coerce_state, _schedule_op
from .sgs_graph import (
    _apply_graph_failure_bookkeeping,
    _collect_candidates,
    _ensure_graph_ready_complete,
    _mark_graph_operation_completed,
    _op_id,
    _prepare_graph_ready_state,
)
from .sgs_scoring import (
    _positive_op_id,
    _score_external_candidate,
    native_scoring_unchanged,
    with_graph_priority_key,
)
from .sgs_scoring import (
    _score_internal_candidate as _score_internal_candidate_impl,
)


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
    external_group_cache: Optional[Dict[Tuple[str, ...], Tuple[datetime, datetime]]] = None,
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
    ctx = ensure_dispatch_context(context)
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
    with sgs_overlap_reuse(run_state.machine_timeline):
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
            state.record_missing_batch(op, batch_id)
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
                sample = _append_proc_sample(ctx, samples, op=op, batch=batch, strict_mode=strict_mode)
                if sample is not None:
                    cache_key = _positive_op_id(getattr(op, "id", 0))
                    if cache_key is not None:
                        total_hours_by_op_id[cache_key] = float(sample)
    if samples:
        return sum(samples) / float(len(samples)), total_hours_by_op_id
    ctx.increment("dispatch_key_avg_proc_hours_fallback_count")
    return 1.0, total_hours_by_op_id


def _append_proc_sample(ctx: Any, samples: List[float], *, op: Any, batch: Any, strict_mode: bool) -> Optional[float]:
    try:
        sample = validate_internal_hours_for_mode(op, operation_batch(op, batch), strict_mode=strict_mode)
    except ValueError:
        # 非 strict 预扫跳过坏工时样本会让均值悄悄偏移，必须计数留痕（不许零留痕静默跳过）。
        ctx.increment("dispatch_key_avg_proc_hours_sample_skipped_count")
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
    if graph_state is not None and isinstance(graph_ready_context, dict) and graph_ready_context.get("piece_scope"):
        graph_state["end_time_by_op_id"] = {row.op_id: row.end_time for row in state.results}
    score_cache = getattr(ctx, "sgs_score_cache", None)
    if score_cache is not None and score_cache.state is not state:
        raise RuntimeError("SGS 评分缓存绑定的运行状态与本次派工不一致")
    with sgs_handoff_scope(score_cache):
        while True:
            if score_cache is not None:
                score_cache.next_round()
            candidates = _collect_candidates(
                graph_state=graph_state,
                batch_ids=batch_ids,
                ops_by_batch=ops_by_batch,
                next_idx=next_idx,
                blocked_batches=state.blocked_batches,
            )
            if not candidates:
                if graph_state is not None:
                    _ensure_graph_ready_complete(
                        graph_state=graph_state,
                        ops_by_batch=ops_by_batch,
                        blocked_batches=state.blocked_batches,
                    )
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
                    graph_state,
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
            if score_cache is not None:
                score_cache.forget(op)


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
    graph_state: Optional[Dict[str, Any]],
) -> List[Tuple[Tuple[float, ...], str, Any]]:
    natives_intact = _native_score_functions_unchanged()
    reuse = current_sgs_reuse()
    if reuse is not None and (reuse.state is not state or not natives_intact):
        reuse = None
    if reuse is not None and not reuse.begin_round(candidates):
        reuse = None
    cache = getattr(ctx, "sgs_score_cache", None) if natives_intact else None
    if cache is not None and not cache.begin_round():
        cache = None
    attempt_sink = cache.record_attempt if cache is not None else None
    scored = []
    for batch_id, op in candidates:
        def score(batch_id=batch_id, op=op):
            return _score_candidate(
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
                graph_state,
                attempt_sink=attempt_sink,
            )
        def cached(batch_id=batch_id, op=op, score=score):
            return cache.resolve(op, batches[batch_id], batch_id, graph_state, score)
        if reuse is not None:
            key = reuse.score(score, dict(
                op=op, batch=batches[batch_id], batch_id=batch_id, batch_order=batch_order,
                graph_state=graph_state, end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=machine_downtimes, dispatch_rule=dispatch_rule,
                strict_mode=strict_mode, avg_proc_hours=avg_proc_hours, total_hours_by_op_id=total_hours_by_op_id,
            ), fallback=cached if cache is not None else None)
        else:
            key = cached() if cache is not None else score()
        scored.append((key, batch_id, op))
    return scored


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
    graph_state: Optional[Dict[str, Any]] = None,
    attempt_sink: Optional[Any] = None,
) -> Tuple[float, ...]:
    state = operation_dispatch_state(state, graph_state, op, batch)
    batch = operation_batch(op, batch)
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
            attempt_sink=attempt_sink,
        )

    base_key = score()
    if graph_state is None or not bool(graph_state.get("score_enabled")):
        return base_key
    op_id = _op_id(op)
    graph_key = (graph_state.get("graph_priority_key_by_op_id") or {}).get(op_id)
    if graph_key is None:
        raise ValidationError(f"图评分上下文缺少待排工序 {op_id} 的评分 key。", field="graph_ready_context")
    return with_graph_priority_key(base_key, graph_key)


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
            batch=operation_batch(op, batches[batch_id]),
            state=operation_dispatch_state(state, graph_state, op, batches[batch_id]),
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
                if "end_time_by_op_id" in graph_state:
                    graph_state["end_time_by_op_id"][_op_id(op)] = result.end_time
                _mark_graph_operation_completed(graph_state, _op_id(op))
        else:
            extra_failed_count = 0
            if graph_state is None:
                # 非图模式：批内派工顺序就是列表顺序，按位置切片仍是正确口径（A04 保持不变）。
                skipped_ops = _remaining_ops_after(batch_id, next_idx, ops_by_batch)
            else:
                # 图模式：派工顺序跟随图链而非列表位置，被牵连集合按图状态推导（审计 A04）。
                skipped_ops, extra_failed_count = _apply_graph_failure_bookkeeping(
                    state,
                    graph_state=graph_state,
                    batch_id=batch_id,
                    failed_op_id=_op_id(op),
                    ops_by_batch=ops_by_batch,
                )
            state.record_dispatch_failure(
                batch_id,
                block=True,
                remaining_failed=len(skipped_ops) + extra_failed_count,
                failed_op=op,
                skipped_ops=skipped_ops,
            )
    except (ValidationError, DispatchContextContractError):
        raise
    except Exception:
        extra_failed_count = 0
        state.record_dispatch_exception(op, batch_id, dispatch_mode="sgs")
        if graph_state is None:
            skipped_ops = _remaining_ops_after(batch_id, next_idx, ops_by_batch)
        else:
            skipped_ops, extra_failed_count = _apply_graph_failure_bookkeeping(
                state,
                graph_state=graph_state,
                batch_id=batch_id,
                failed_op_id=_op_id(op),
                ops_by_batch=ops_by_batch,
            )
        for skipped_op in skipped_ops:
            state.record_skipped_after_batch_failure(skipped_op, batch_id)
        state.failed_count += extra_failed_count
        op_code = state._safe_text_attr(op, "op_code", "-") or "-"
        ctx.log_exception(f"工序 {op_code} 排产异常")
        state.blocked_batches.add(batch_id)


def _remaining_ops_after(batch_id: str, next_idx: Dict[str, int], ops_by_batch: Dict[str, List[Any]]) -> List[Any]:
    operations = list(ops_by_batch.get(batch_id) or [])
    idx0 = int(next_idx.get(batch_id, 0) or 0)
    return operations[idx0 + 1 :]


_NATIVE_SCORE_FUNCTIONS = {name: globals()[name] for name in (
    "_score_candidate", "_score_internal_candidate", "_score_internal_candidate_impl", "_score_external_candidate",
    "estimate_internal_slot", "build_dispatch_key", "operation_batch", "operation_dispatch_state",
)}


def _native_score_functions_unchanged():
    return native_scoring_unchanged() and all(globals()[name] is original for name, original in _NATIVE_SCORE_FUNCTIONS.items())
