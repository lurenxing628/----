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
from .sgs_scoring import (
    _collect_sgs_candidates,
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
    avg_proc_hours = _average_proc_hours(ctx, ops_by_batch=ops_by_batch, batches=batches, strict_mode=bool(strict_mode))
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


def _average_proc_hours(ctx: Any, *, ops_by_batch: Dict[str, List[Any]], batches: Dict[str, Any], strict_mode: bool) -> float:
    samples: List[float] = []
    for batch_id, operations in ops_by_batch.items():
        batch = batches.get(batch_id)
        for op in operations:
            if batch and (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == INTERNAL:
                _append_proc_sample(samples, op=op, batch=batch, strict_mode=strict_mode)
    if samples:
        return sum(samples) / float(len(samples))
    ctx.increment("dispatch_key_avg_proc_hours_fallback_count")
    return 1.0


def _append_proc_sample(samples: List[float], *, op: Any, batch: Any, strict_mode: bool) -> None:
    try:
        samples.append(validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode))
    except ValueError:
        return


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
) -> None:
    while True:
        candidates = _collect_sgs_candidates(
            batch_ids_in_order=batch_ids,
            ops_by_batch=ops_by_batch,
            next_idx=next_idx,
            blocked_batches=state.blocked_batches,
        )
        if not candidates:
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
            ),
            batch_id,
            op,
        )
        for batch_id, op in candidates
    ]


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
        else:
            state.record_dispatch_failure(batch_id, block=True, remaining_failed=_remaining_failed(batch_id, next_idx, ops_by_batch))
    except ValidationError:
        raise
    except Exception:
        state.failed_count += 1 + _remaining_failed(batch_id, next_idx, ops_by_batch)
        state.errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'} {_SCHEDULE_OPERATION_FAILED_MESSAGE}")
        ctx.log_exception(f"工序 {getattr(op, 'op_code', '-') or '-'} 排产异常")
        state.blocked_batches.add(batch_id)


def _remaining_failed(batch_id: str, next_idx: Dict[str, int], ops_by_batch: Dict[str, List[Any]]) -> int:
    idx0 = int(next_idx.get(batch_id, 0) or 0)
    return max(int(len(ops_by_batch.get(batch_id) or [])) - (idx0 + 1), 0)
