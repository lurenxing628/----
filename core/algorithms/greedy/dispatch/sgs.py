from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union, cast

from core.algorithm_contracts.dispatch_rules import (
    DispatchRule,
    DispatchRuleSpec,
    as_dispatch_rule_spec,
)
from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.piece_input import operation_dispatch_state
from core.algorithm_runtime.run_state import ScheduleRunState

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
    SgsCandidateScore,
    _score_external_candidate,
    _score_internal_candidate,
    with_graph_priority_key,
)

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch

    from .sgs_score_cache import SgsScoreCache


@dataclass(frozen=True)
class ScoredCandidate:
    batch_id: str
    op: OpForScheduleAlgo
    score: SgsCandidateScore


def dispatch_sgs(
    ctx: Any,
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
    rule_spec = as_dispatch_rule_spec(dispatch_rule)
    ops_by_batch = _group_sgs_ops(sorted_ops=sorted_ops, batches=batches, state=state)
    batch_ids = sorted(ops_by_batch, key=lambda item: (batch_order.get(item, 999999), item))
    next_idx: Dict[str, int] = {batch_id: 0 for batch_id in batch_ids}
    avg_proc_hours, total_hours_by_op_id = _average_proc_hours(ctx)
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


def _average_proc_hours(ctx: Any) -> Tuple[float, Dict[int, float]]:
    preparation = ctx.native_preparation
    total_hours_by_op_id: Dict[int, float] = preparation.total_hours_by_op_id
    if preparation.average_internal_proc_hours is not None:
        return preparation.average_internal_proc_hours, total_hours_by_op_id
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
    graph_state: Optional[Dict[str, Any]] = None
    if graph_ready_context is not None:
        graph_state = _prepare_graph_ready_state(
            ctx.native_preparation.graph_topology(),
            graph_ready_context,
            ops_by_batch=ops_by_batch,
            skip_initial_frontier=decode_resume is not None,
        )
        # Only a piece graph carries piece_scope.
        if graph_ready_context.get("piece_scope"):
            graph_state["end_time_by_op_id"] = {row.op_id: row.end_time for row in state.results}
            if state.readiness_gate_enabled:
                graph_state["ready_starts_by_batch_id"] = ctx.native_preparation.parsed_ready_starts()
    # Picks completed so far; a resumed decode continues from the checkpoint's count and progress.
    position = 0
    if decode_resume is not None:
        position = resume_graph_progress(decode_resume, graph_state=graph_state, next_idx=next_idx)
    # The scheduler builds one score cache for every SGS decode.
    score_cache: SgsScoreCache = ctx.sgs_score_cache
    pruning = GraphPriorityPruning.for_cache(score_cache, graph_state)
    acceleration = DecodeAcceleration(decode_checkpoints, graph_state, pruning, total_hours_by_op_id,
                                      resume=decode_resume)

    def collect():
        return _collect_candidates(graph_state=graph_state, batch_ids=batch_ids, ops_by_batch=ops_by_batch,
                                   next_idx=next_idx, blocked_batches=state.blocked_batches)

    def score(candidates):
        return _score_candidates(ctx, state, candidates, batches, batch_order, dispatch_rule, end_dt_exclusive,
                                 machine_downtimes, auto_assign_enabled, resource_pool, avg_proc_hours,
                                 total_hours_by_op_id, graph_state, priority_pruning=pruning)

    while True:
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
        selected = min(scored, key=lambda item: item.score.key)
        _dispatch_selected(
            ctx,
            state,
            selected.op,
            selected.batch_id,
            batches,
            next_idx,
            ops_by_batch,
            end_dt_exclusive,
            machine_downtimes,
            auto_assign_enabled,
            resource_pool,
            scored=selected.score,
            graph_state=graph_state,
        )
        position += 1
        if acceleration.record(selected.op.id, position, state=state, next_idx=next_idx, graph=graph_state):
            _ensure_graph_ready_complete(
                graph_state=cast(Dict[str, Any], graph_state),
                ops_by_batch=ops_by_batch,
                blocked_batches=state.blocked_batches,
            )
            return
        score_cache.forget(selected.op)


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
    cache: SgsScoreCache = ctx.sgs_score_cache
    candidates, remainder = (priority_pruning.partition(candidates, graph_state)
                             if priority_pruning is not None else (candidates, []))
    scored: List[ScoredCandidate] = []
    for batch_id, op in candidates:
        def score(batch_id=batch_id, op=op) -> SgsCandidateScore:
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
            )
        candidate_score = cache.resolve(op, batch_id, graph_state, score)
        scored.append(ScoredCandidate(batch_id=batch_id, op=op, score=candidate_score))
    if remainder:
        if any(item.score.key[0] == 0.0 for item in scored):
            cache.graph_candidates_pruned += len(remainder)
        else:
            scored.extend(_score_candidates(
                ctx, state, remainder, batches, batch_order, dispatch_rule, end_dt_exclusive,
                machine_downtimes, auto_assign_enabled, resource_pool,
                avg_proc_hours, total_hours_by_op_id, graph_state))
    return scored


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
) -> SgsCandidateScore:
    state = operation_dispatch_state(state, graph_state, op)
    if op.source == EXTERNAL:
        scored = _score_external_candidate(
            ctx=ctx,
            state=state,
            op=op,
            batch=batch,
            batch_id=batch_id,
            batch_order=batch_order,
            dispatch_rule=dispatch_rule,
            end_dt_exclusive=end_dt_exclusive,
            avg_proc_hours=avg_proc_hours,
        )
    else:
        scored = _score_internal_candidate(
            ctx=ctx,
            state=state,
            op=op,
            batch=ctx.native_preparation.operation_batch(op, batch),
            batch_id=batch_id,
            batch_order=batch_order,
            dispatch_rule=dispatch_rule,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            avg_proc_hours=avg_proc_hours,
            total_hours_by_op_id=total_hours_by_op_id,
        )
    if graph_state is None or not graph_state["score_enabled"]:
        return scored
    return replace(
        scored,
        key=with_graph_priority_key(scored.key, graph_state["graph_priority_key_by_op_id"][op.id]),
    )
