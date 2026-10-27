from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from core.algorithm_contracts.dispatch_rules import (
    DispatchRule,
    DispatchRuleSpec,
    as_dispatch_rule_spec,
    build_dispatch_key,
)
from core.algorithm_contracts.value_domains import EXTERNAL, INTERNAL
from core.algorithm_runtime.internal_slot import estimate_internal_slot, require_internal_hours
from core.algorithm_runtime.piece_input import operation_dispatch_state
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import sgs_handoff_scope
from core.algorithm_runtime.slot_overlap_reuse import sgs_overlap_reuse
from core.errors import ValidationError

from .sgs_checkpoint import (
    DecodeCheckpoint,
    DecodeCheckpointRequest,
    resume_graph_progress,
)
from .sgs_decode_acceleration import DecodeAcceleration
from .sgs_dispatch_step import _dispatch_selected
from .sgs_graph import (
    _collect_candidates,
    _ensure_graph_ready_complete,
    _prepare_graph_ready_state,
)
from .sgs_priority_frontier import score_next_ready
from .sgs_priority_pruning import GraphPriorityPruning
from .sgs_scoring import (
    _score_external_candidate,
    with_graph_priority_key,
)
from .sgs_scoring import (
    _score_internal_candidate as _score_internal_candidate_impl,
)

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch

ScoredCandidate = Tuple[Tuple[float, ...], str, "OpForScheduleAlgo"]


def _score_internal_candidate(**kwargs: Any) -> Tuple[float, ...]:
    return _score_internal_candidate_impl(
        **kwargs,
        estimate_slot=estimate_internal_slot,
        dispatch_key_builder=build_dispatch_key,
    )


def _pick_best_candidate(scored_candidates: List[ScoredCandidate]) -> Tuple[str, OpForScheduleAlgo]:
    if not scored_candidates:
        raise RuntimeError("SGS 评分阶段未产生任何候选")
    _best_key, best_batch_id, best_op = min(scored_candidates, key=lambda item: item[0])
    return best_batch_id, best_op


def dispatch_sgs(
    context: Any,
    *,
    sorted_ops: List[OpForScheduleAlgo],
    batches: Dict[str, Batch],
    batch_order: Dict[str, int],
    dispatch_rule: Union[DispatchRule, DispatchRuleSpec],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    state: ScheduleRunState,
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    graph_ready_context: Optional[Any] = None,
    decode_resume: Optional[DecodeCheckpoint] = None,
    decode_checkpoints: Optional[DecodeCheckpointRequest] = None,
) -> None:
    ctx = context
    rule_spec = as_dispatch_rule_spec(dispatch_rule)
    ops_by_batch = _group_sgs_ops(sorted_ops=sorted_ops, batches=batches, state=state)
    batch_ids = sorted(ops_by_batch, key=lambda item: (batch_order.get(item, 999999), item))
    next_idx: Dict[str, int] = {batch_id: 0 for batch_id in batch_ids}
    avg_proc_hours, total_hours_by_op_id = _average_proc_hours(ctx, ops_by_batch=ops_by_batch, batches=batches)
    with sgs_overlap_reuse(state.machine_timeline, expected_operations=len(sorted_ops) + len(state.results)):
        _run_sgs_loop(
            ctx,
            state,
            ops_by_batch,
            batch_ids,
            next_idx,
            batches,
            batch_order,
            rule_spec,
            end_dt_exclusive,
            machine_downtimes,
            auto_assign_enabled,
            resource_pool,
            avg_proc_hours,
            total_hours_by_op_id,
            graph_ready_context,
            decode_resume=decode_resume,
            decode_checkpoints=decode_checkpoints,
        )


def _group_sgs_ops(
    *, sorted_ops: List[OpForScheduleAlgo], batches: Dict[str, Batch], state: ScheduleRunState,
) -> Dict[str, List[OpForScheduleAlgo]]:
    """Group the operation_sort_key order supplied by the native scheduler."""
    grouped: Dict[str, List[OpForScheduleAlgo]] = {}
    for op in sorted_ops:
        batch_id = op.batch_id
        if batch_id not in batches:
            state.record_missing_batch(op, batch_id)
            continue
        grouped.setdefault(batch_id, []).append(op)
    return grouped


def _average_proc_hours(
    ctx: Any,
    *,
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    batches: Dict[str, Batch],
) -> Tuple[float, Dict[int, float]]:
    samples: List[float] = []
    total_hours_by_op_id: Dict[int, float] = ctx.native_preparation.total_hours_by_op_id
    # _group_sgs_ops only keeps batches that exist, so every grouped batch id resolves.
    for batch_id, operations in ops_by_batch.items():
        batch = batches[batch_id]
        for op in operations:
            if op.source == INTERNAL:
                if op.id not in total_hours_by_op_id:
                    total_hours_by_op_id[op.id] = require_internal_hours(op, resolve_operation_batch(ctx, op, batch))
                samples.append(total_hours_by_op_id[op.id])
    if samples:
        return sum(samples) / len(samples), total_hours_by_op_id
    ctx.increment("dispatch_key_avg_proc_hours_fallback_count")
    return 1.0, total_hours_by_op_id


def _run_sgs_loop(
    ctx: Any,
    state: ScheduleRunState,
    ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
    batch_ids: List[str],
    next_idx: Dict[str, int],
    batches: Dict[str, Batch],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRuleSpec,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
    graph_ready_context: Optional[Any],
    *,
    decode_resume: Optional[DecodeCheckpoint] = None,
    decode_checkpoints: Optional[DecodeCheckpointRequest] = None,
) -> None:
    graph_state = _prepare_graph_ready_state(
        graph_ready_context,
        ops_by_batch=ops_by_batch,
        skip_initial_frontier=decode_resume is not None,
    )
    if graph_state is not None and isinstance(graph_ready_context, dict) and graph_ready_context.get("piece_scope"):
        graph_state["end_time_by_op_id"] = {row.op_id: row.end_time for row in state.results}
    # Picks completed so far; a resumed decode continues from the checkpoint's count and progress.
    position = 0
    if decode_resume is not None:
        position = resume_graph_progress(decode_resume, graph_state=graph_state, next_idx=next_idx)
    score_cache = ctx.sgs_score_cache
    if score_cache is not None and score_cache.state is not state:
        raise RuntimeError("SGS 评分缓存绑定的运行状态与本次派工不一致")
    pruning = GraphPriorityPruning.for_cache(score_cache, graph_state, batches, total_hours_by_op_id)
    acceleration = DecodeAcceleration(decode_checkpoints, graph_state, pruning, total_hours_by_op_id,
                                      resume=decode_resume)

    def collect():
        return _collect_candidates(graph_state=graph_state, batch_ids=batch_ids, ops_by_batch=ops_by_batch,
                                   next_idx=next_idx, blocked_batches=state.blocked_batches)

    def score(candidates):
        return _score_candidates(ctx, state, candidates, batches, batch_order, dispatch_rule, end_dt_exclusive,
                                 machine_downtimes, auto_assign_enabled, resource_pool, avg_proc_hours,
                                 total_hours_by_op_id, graph_state, priority_pruning=pruning)

    with sgs_handoff_scope(score_cache):
        while True:
            if score_cache is not None:
                score_cache.next_round()
            scored = score_next_ready(acceleration.frontier, collect=collect, score=score,
                                      blocked_batches=state.blocked_batches, cache=score_cache)
            if not scored:
                if graph_state is not None:
                    _ensure_graph_ready_complete(
                        graph_state=graph_state,
                        ops_by_batch=ops_by_batch,
                        blocked_batches=state.blocked_batches,
                    )
                return
            batch_id, op = _pick_best_candidate(scored)
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
                graph_state=graph_state,
            )
            position += 1
            if acceleration.record(op.id, position, state=state, next_idx=next_idx, graph=graph_state):
                _complete_reused_tail(graph_state, ops_by_batch=ops_by_batch, blocked_batches=state.blocked_batches)
                return
            if score_cache is not None:
                score_cache.forget(op)


def _complete_reused_tail(graph_state: Optional[Dict[str, Any]], *, ops_by_batch: Dict[str, List[OpForScheduleAlgo]],
                          blocked_batches: set) -> None:
    """A reused tail only exists in graph-mode decoding, so a missing graph state means the guard chain broke."""
    if graph_state is None:
        raise RuntimeError("尾段复用只在图模式派工中成立，图状态不能为空")
    _ensure_graph_ready_complete(graph_state=graph_state, ops_by_batch=ops_by_batch, blocked_batches=blocked_batches)


def _prepare_scoring_round(ctx, priority_pruning):
    cache = ctx.sgs_score_cache
    if cache is not None:
        cache.begin_round()
    if cache is None or cache._timing is None:
        priority_pruning = None
    return cache, priority_pruning


def _score_candidates(
    ctx: Any,
    state: ScheduleRunState,
    candidates: List[Tuple[str, OpForScheduleAlgo]],
    batches: Dict[str, Batch],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRuleSpec,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
    graph_state: Optional[Dict[str, Any]],
    *,
    priority_pruning: Optional[GraphPriorityPruning] = None,
) -> List[ScoredCandidate]:
    cache, priority_pruning = _prepare_scoring_round(ctx, priority_pruning)
    candidates, remainder = (priority_pruning.partition(candidates, graph_state)
                             if priority_pruning is not None else (candidates, []))
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
                avg_proc_hours,
                total_hours_by_op_id,
                graph_state,
                attempt_sink=attempt_sink,
            )
        key = cache.resolve(op, batches[batch_id], batch_id, graph_state, score) if cache is not None else score()
        scored.append((key, batch_id, op))
    if remainder:
        if any(item[0][0] == 0.0 for item in scored):
            if cache is None:
                raise RuntimeError("图优先剪枝只在评分缓存在位时启用，评分缓存不能为空")
            cache.graph_candidates_pruned += len(remainder)
        else:
            scored.extend(_score_candidates(
                ctx, state, remainder, batches, batch_order, dispatch_rule, end_dt_exclusive,
                machine_downtimes, auto_assign_enabled, resource_pool,
                avg_proc_hours, total_hours_by_op_id, graph_state))
    return scored


def resolve_operation_batch(ctx: Any, op: OpForScheduleAlgo, batch: Batch) -> Batch:
    return ctx.native_preparation.operation_batch(op, batch)


def _score_candidate(
    ctx: Any,
    state: ScheduleRunState,
    op: OpForScheduleAlgo,
    batch: Batch,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRuleSpec,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    avg_proc_hours: float,
    total_hours_by_op_id: Dict[int, float],
    graph_state: Optional[Dict[str, Any]] = None,
    attempt_sink: Optional[Any] = None,
) -> Tuple[float, ...]:
    state = operation_dispatch_state(state, graph_state, op, batch)
    batch = resolve_operation_batch(ctx, op, batch)
    def score() -> Tuple[float, ...]:
        if op.source == EXTERNAL:
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
            attempt_sink=attempt_sink,
        )

    base_key = score()
    if graph_state is None or not graph_state["score_enabled"]:
        return base_key
    op_id = op.id
    graph_key = graph_state["graph_priority_key_by_op_id"].get(op_id)
    if graph_key is None:
        raise ValidationError(f"图评分上下文缺少待排工序 {op_id} 的评分 key。", field="graph_ready_context")
    return with_graph_priority_key(base_key, graph_key)
