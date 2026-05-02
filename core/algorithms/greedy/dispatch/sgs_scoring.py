from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms.dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key
from core.algorithms.value_domains import MERGED
from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import is_blank_input, parse_optional_date, parse_required_float, parse_required_int

from ..date_parsers import parse_date
from ..internal_slot import (
    estimate_internal_slot,
    raise_strict_internal_hours_validation,
    validate_internal_hours_for_mode,
)
from ..run_state import ScheduleRunState


def _parse_due_date(value: Any, *, strict_mode: bool = False) -> Optional[date]:
    return parse_optional_date(value, field="due_date") if strict_mode else parse_date(value)


def _dispatch_key(
    *,
    dispatch_key_builder: Callable[[DispatchInputs], Tuple[float, ...]] = build_dispatch_key,
    dispatch_rule: DispatchRule,
    priority: Any,
    due_date: Optional[date],
    est_start: datetime,
    est_end: datetime,
    proc_hours: float,
    avg_proc_hours: float,
    changeover_penalty: int,
    batch_order: Dict[str, int],
    batch_id: str,
    seq: int,
    op_id: int,
    score_penalty: float,
) -> Tuple[float, ...]:
    base_key = dispatch_key_builder(
        DispatchInputs(
            rule=dispatch_rule,
            priority=str(priority or "normal"),
            due_date=due_date,
            est_start=est_start,
            est_end=est_end,
            proc_hours=float(proc_hours),
            avg_proc_hours=float(avg_proc_hours),
            changeover_penalty=int(changeover_penalty),
            batch_order=int(batch_order.get(batch_id, 999999)),
            batch_id=batch_id,
            seq=int(seq),
            op_id=int(op_id),
        )
    )
    return (float(score_penalty),) + tuple(base_key)


def _collect_sgs_candidates(
    *,
    batch_ids_in_order: List[str],
    ops_by_batch: Dict[str, List[Any]],
    next_idx: Dict[str, int],
    blocked_batches: set,
) -> List[Tuple[str, Any]]:
    candidates: List[Tuple[str, Any]] = []
    for batch_id in batch_ids_in_order:
        idx = int(next_idx.get(batch_id, 0) or 0)
        operations = ops_by_batch.get(batch_id) or []
        if batch_id not in blocked_batches and idx < len(operations):
            candidates.append((batch_id, operations[idx]))
    return candidates


def _score_external_candidate(
    *,
    ctx: Any,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    end_dt_exclusive: Optional[datetime],
    avg_proc_hours: float,
    strict_mode: bool,
    dispatch_key_builder: Callable[[DispatchInputs], Tuple[float, ...]] = build_dispatch_key,
) -> Tuple[float, ...]:
    meta = _candidate_meta(op=op, batch=batch, batch_id=batch_id, state=state, strict_mode=strict_mode)
    window = _external_candidate_window(ctx, state, op=op, batch_id=batch_id, prev_end=meta["prev_end"], strict_mode=strict_mode)
    est_start, est_end = window
    proc_hours = max((est_end - est_start).total_seconds() / 3600.0, 0.0)
    return _dispatch_key(
        dispatch_key_builder=dispatch_key_builder,
        dispatch_rule=dispatch_rule,
        priority=meta["priority"],
        due_date=meta["due_date"],
        est_start=est_start,
        est_end=est_end,
        proc_hours=proc_hours,
        avg_proc_hours=avg_proc_hours,
        changeover_penalty=0,
        batch_order=batch_order,
        batch_id=batch_id,
        seq=meta["seq"],
        op_id=meta["op_id"],
        score_penalty=(1.0 if end_dt_exclusive is not None and est_end >= end_dt_exclusive else 0.0),
    )


def _score_internal_candidate(
    *,
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
    avg_proc_hours: float,
    strict_mode: bool,
    estimate_slot: Callable[..., Any] = estimate_internal_slot,
    dispatch_key_builder: Callable[[DispatchInputs], Tuple[float, ...]] = build_dispatch_key,
) -> Tuple[float, ...]:
    meta = _candidate_meta(op=op, batch=batch, batch_id=batch_id, state=state, strict_mode=strict_mode)
    total_hours = _scoring_total_hours(ctx, op=op, batch=batch, strict_mode=strict_mode)
    machine_id, operator_id = _scoring_resources(
        ctx,
        state=state,
        op=op,
        batch=batch,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
    )
    if not machine_id or not operator_id:
        raise ValidationError(f"智能派工计算时发现自制工序缺少设备或人员：工序编号={meta['op_id']!r}", field="resource")
    estimate = _estimate_scoring_slot(ctx, state, op, batch, meta, machine_id, operator_id, end_dt_exclusive, machine_downtimes, total_hours, estimate_slot=estimate_slot)
    return _dispatch_key(
        dispatch_key_builder=dispatch_key_builder,
        dispatch_rule=dispatch_rule,
        priority=meta["priority"],
        due_date=meta["due_date"],
        est_start=estimate.start_time,
        est_end=estimate.end_time,
        proc_hours=estimate.total_hours,
        avg_proc_hours=avg_proc_hours,
        changeover_penalty=estimate.changeover_penalty,
        batch_order=batch_order,
        batch_id=batch_id,
        seq=meta["seq"],
        op_id=meta["op_id"],
        score_penalty=(1.0 if estimate.blocked_by_window else 0.0),
    )


def _candidate_meta(*, op: Any, batch: Any, batch_id: str, state: ScheduleRunState, strict_mode: bool) -> Dict[str, Any]:
    return {
        "priority": getattr(batch, "priority", None),
        "due_date": _parse_due_date(getattr(batch, "due_date", None), strict_mode=bool(strict_mode)),
        "seq": parse_required_int(getattr(op, "seq", 0), field="seq"),
        "op_id": parse_required_int(getattr(op, "id", 0), field="id"),
        "batch_id": batch_id,
        "prev_end": state.prev_end(batch_id),
    }


def _external_candidate_window(
    ctx: Any,
    state: ScheduleRunState,
    *,
    op: Any,
    batch_id: str,
    prev_end: datetime,
    strict_mode: bool,
) -> Tuple[datetime, datetime]:
    merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()
    if merge_mode == MERGED and ext_group_id:
        cached = state.external_group_cache.get((batch_id, ext_group_id))
        if cached:
            return cached
        total_days = _parse_external_days(
            getattr(op, "ext_group_total_days", None),
            field="ext_group_total_days",
            strict_mode=strict_mode,
        )
        return prev_end, ctx.calendar.add_calendar_days(prev_end, total_days)
    ext_days = _parse_external_days(
        getattr(op, "ext_days", None),
        field="ext_days",
        strict_mode=strict_mode,
        default_days=1.0,
    )
    return prev_end, ctx.calendar.add_calendar_days(prev_end, ext_days)


def _parse_external_days(value: Any, *, field: str, strict_mode: bool, default_days: Optional[float] = None) -> float:
    if not strict_mode and is_blank_input(value) and default_days is not None:
        return float(default_days)
    return parse_required_float(value, field=field, min_value=0.0, min_inclusive=False)


def _scoring_total_hours(ctx: Any, *, op: Any, batch: Any, strict_mode: bool) -> float:
    try:
        return validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)
    except ValueError as exc:
        raise_strict_internal_hours_validation(op, batch, exc)


def _scoring_resources(
    ctx: Any,
    *,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    machine_id = str(getattr(op, "machine_id", None) or "").strip()
    operator_id = str(getattr(op, "operator_id", None) or "").strip()
    if machine_id and operator_id:
        return machine_id, operator_id
    if not auto_assign_enabled or resource_pool is None:
        return "", ""
    chosen = ctx.auto_assign_internal_resources(
        op=op,
        batch=batch,
        batch_progress=state.batch_progress,
        machine_timeline=state.machine_timeline,
        operator_timeline=state.operator_timeline,
        base_time=state.base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=(resource_pool if isinstance(resource_pool, dict) else {}),
        last_op_type_by_machine=state.last_op_type_by_machine,
        machine_busy_hours=state.machine_busy_hours,
        operator_busy_hours=state.operator_busy_hours,
        probe_only=True,
    )
    if chosen is None:
        return "", ""
    if not isinstance(chosen, (list, tuple)) or len(chosen) < 2:
        raise TypeError("auto_assign probe result is not a pair")
    return str(chosen[0] or "").strip(), str(chosen[1] or "").strip()


def _estimate_scoring_slot(
    ctx: Any,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    meta: Dict[str, Any],
    machine_id: str,
    operator_id: str,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    total_hours: float,
    estimate_slot: Callable[..., Any] = estimate_internal_slot,
):
    estimate = estimate_slot(
        calendar=ctx.calendar,
        op=op,
        batch=batch,
        machine_id=machine_id,
        operator_id=operator_id,
        base_time=state.base_time,
        prev_end=meta["prev_end"],
        machine_timeline=state.machine_timeline.get(machine_id) or [],
        operator_timeline=state.operator_timeline.get(operator_id) or [],
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
        last_op_type_by_machine=state.last_op_type_by_machine,
        abort_after=None,
        total_hours_base=total_hours,
    )
    if estimate.abort_after_hit:
        raise RuntimeError("SGS 评分不应命中 abort_after 早停")
    return estimate
