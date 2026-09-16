from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union

from core.algorithm_contracts.date_parsers import parse_date
from core.algorithm_contracts.dispatch_rules import (
    DispatchInputs,
    DispatchRule,
    DispatchRuleSpec,
    as_dispatch_rule_spec,
    build_dispatch_key,
)
from core.algorithm_contracts.value_domains import MERGED
from core.algorithm_runtime.auto_assign_contract import (
    AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
    auto_assign_attempt_from_result,
)
from core.algorithm_runtime.internal_slot import (
    estimate_internal_slot,
    raise_strict_internal_hours_validation,
    validate_internal_hours_for_mode,
)
from core.algorithm_runtime.piece_input import external_group_key
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_handoff, current_sgs_reuse, remember_sgs_estimate
from core.algorithm_runtime.slot_overlap_reuse import overlap_reuse_for
from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import is_blank_input, parse_optional_date, parse_required_float, parse_required_int

from .resource_validation import (
    RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE,
    RESOURCE_REASON_FIXED,
    RESOURCE_REASON_MANUAL_MISSING,
    internal_resource_validation_message,
)


class _ScoringResources(NamedTuple):
    machine_id: str
    operator_id: str
    reason: str
    auto_assign_reason: str


_NATIVE_PARSE_DATE = parse_date
_NATIVE_PARSE_OPTIONAL_DATE = parse_optional_date
_DUE_TEXT_CACHE: Dict[Tuple[bool, str], Optional[date]] = {}


def _parse_native_due_text(value: str, *, strict_mode: bool) -> Optional[date]:
    key = strict_mode, value
    if key in _DUE_TEXT_CACHE:
        return _DUE_TEXT_CACHE[key]
    result = parse_optional_date(value, field="due_date") if strict_mode else parse_date(value)
    # Invalid non-strict dates also return None: retain their original parse path.
    if result is not None or not value.strip():
        if len(_DUE_TEXT_CACHE) >= 4096:
            _DUE_TEXT_CACHE.pop(next(iter(_DUE_TEXT_CACHE)))
        _DUE_TEXT_CACHE[key] = result
    return result


def _parse_due_date(value: Any, *, strict_mode: bool = False) -> Optional[date]:
    if strict_mode:
        if value is None or type(value) is date:
            return value
        if type(value) is str and parse_optional_date is _NATIVE_PARSE_OPTIONAL_DATE:
            return _parse_native_due_text(value, strict_mode=True)
        return parse_optional_date(value, field="due_date")
    if type(value) is str and parse_date is _NATIVE_PARSE_DATE:
        return _parse_native_due_text(value, strict_mode=False)
    return parse_date(value)


def _dispatch_key(
    *,
    dispatch_key_builder: Callable[[DispatchInputs], Tuple[float, ...]] = build_dispatch_key,
    dispatch_rule: Union[DispatchRule, DispatchRuleSpec],
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
    # Internal callers may still hand over the bare enum; both are explicit contract values.
    spec = as_dispatch_rule_spec(dispatch_rule)
    base_key = dispatch_key_builder(
        DispatchInputs(
            rule=spec.rule,
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
            atc_k=spec.atc_k,
        )
    )
    return (float(score_penalty),) + tuple(base_key)


def with_graph_priority_key(base_key: Tuple[float, ...], graph_key: Tuple[float, ...]) -> Tuple[float, ...]:
    return tuple(base_key[:1]) + tuple(graph_key) + tuple(base_key[1:])


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


def _positive_op_id(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        op_id = int(value or 0)
    except (TypeError, ValueError):
        return None
    return op_id if op_id > 0 else None


def _score_external_candidate(
    *,
    ctx: Any,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: Union[DispatchRule, DispatchRuleSpec],
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
    dispatch_rule: Union[DispatchRule, DispatchRuleSpec],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    avg_proc_hours: float,
    strict_mode: bool,
    total_hours_by_op_id: Optional[Dict[int, float]] = None,
    estimate_slot: Callable[..., Any] = estimate_internal_slot,
    dispatch_key_builder: Callable[[DispatchInputs], Tuple[float, ...]] = build_dispatch_key,
    attempt_sink: Optional[Callable[[Any], None]] = None,
) -> Tuple[float, ...]:
    meta = _candidate_meta(op=op, batch=batch, batch_id=batch_id, state=state, strict_mode=strict_mode)
    total_hours = _scoring_total_hours(
        ctx,
        op=op,
        batch=batch,
        strict_mode=strict_mode,
        total_hours_by_op_id=total_hours_by_op_id,
        op_id=int(meta["op_id"]),
    )
    resources = _scoring_resources(
        ctx,
        state=state,
        op=op,
        batch=batch,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
        attempt_sink=attempt_sink,
    )
    if not resources.machine_id or not resources.operator_id:
        if resources.auto_assign_reason == AUTO_ASSIGN_REASON_WINDOW_BLOCKED:
            # 窗口截止导致的自动派工不可放置：与固定资源 blocked_by_window 走同一条降级路径。
            # 不抛 ValidationError（否则评分阶段中止整个排产 run），改为返回 score_penalty=1.0
            # 的垫底排序 key——可行候选（penalty=0）永远优先；该候选真被选中时会在放置层
            # （internal_operation._resolve_internal_resources）按 WINDOW_BLOCKED 记单批失败
            # 并留下截止日期文案，其余批次继续。
            return _dispatch_key(
                dispatch_key_builder=dispatch_key_builder,
                dispatch_rule=dispatch_rule,
                priority=meta["priority"],
                due_date=meta["due_date"],
                est_start=meta["prev_end"],
                est_end=meta["prev_end"],
                proc_hours=total_hours,
                avg_proc_hours=avg_proc_hours,
                changeover_penalty=0,
                batch_order=batch_order,
                batch_id=batch_id,
                seq=meta["seq"],
                op_id=meta["op_id"],
                score_penalty=1.0,
            )
        message, details = internal_resource_validation_message(
            batch=batch,
            op=op,
            meta=meta,
            machine_id=resources.machine_id,
            operator_id=resources.operator_id,
            reason=resources.reason,
            auto_assign_reason=resources.auto_assign_reason,
        )
        raise ValidationError(message, field="resource", details=details)
    estimate = _estimate_scoring_slot(
        ctx,
        state,
        op,
        batch,
        meta,
        resources.machine_id,
        resources.operator_id,
        end_dt_exclusive,
        machine_downtimes,
        total_hours,
        estimate_slot=estimate_slot,
    )
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
        cached = state.external_group_cache.get(external_group_key(op))
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


def _scoring_total_hours(
    ctx: Any,
    *,
    op: Any,
    batch: Any,
    strict_mode: bool,
    total_hours_by_op_id: Optional[Dict[int, float]] = None,
    op_id: Optional[int] = None,
) -> float:
    cache_key = _positive_op_id(op_id if op_id is not None else getattr(op, "id", 0))
    if total_hours_by_op_id is not None and cache_key is not None:
        if cache_key in total_hours_by_op_id:
            return float(total_hours_by_op_id[cache_key])
    try:
        total_hours = validate_internal_hours_for_mode(op, batch, strict_mode=strict_mode)
    except ValueError as exc:
        raise_strict_internal_hours_validation(op, batch, exc)
    if total_hours_by_op_id is not None and cache_key is not None:
        total_hours_by_op_id[cache_key] = float(total_hours)
    return float(total_hours)


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
    attempt_sink: Optional[Callable[[Any], None]] = None,
) -> _ScoringResources:
    machine_id = str(getattr(op, "machine_id", None) or "").strip()
    operator_id = str(getattr(op, "operator_id", None) or "").strip()
    if machine_id and operator_id:
        return _ScoringResources(machine_id, operator_id, RESOURCE_REASON_FIXED, "")
    if not auto_assign_enabled or resource_pool is None:
        return _ScoringResources("", "", RESOURCE_REASON_MANUAL_MISSING, "")
    attempt = _auto_assign_attempt_for_scoring(
        ctx,
        state=state,
        op=op,
        batch=batch,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
    )
    if attempt_sink is not None:
        attempt_sink(attempt)
    if not attempt.machine_id or not attempt.operator_id:
        return _ScoringResources("", "", RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE, attempt.reason)
    return _ScoringResources(attempt.machine_id, attempt.operator_id, RESOURCE_REASON_FIXED, "")


def _auto_assign_attempt_for_scoring(
    ctx: Any,
    *,
    state: ScheduleRunState,
    op: Any,
    batch: Any,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    resource_pool: Optional[Dict[str, Any]],
):
    kwargs = {
        "op": op,
        "batch": batch,
        "batch_progress": state.batch_progress,
        "machine_timeline": state.machine_timeline,
        "operator_timeline": state.operator_timeline,
        "base_time": state.base_time,
        "end_dt_exclusive": end_dt_exclusive,
        "machine_downtimes": machine_downtimes,
        "resource_pool": (resource_pool if isinstance(resource_pool, dict) else {}),
        "last_op_type_by_machine": state.last_op_type_by_machine,
        "machine_busy_hours": state.machine_busy_hours,
        "operator_busy_hours": state.operator_busy_hours,
        "probe_only": True,
    }
    callback = getattr(ctx, "auto_assign_internal_resources_attempt", None)
    if callable(callback):
        return auto_assign_attempt_from_result(callback(**kwargs))
    return auto_assign_attempt_from_result(ctx.auto_assign_internal_resources(**kwargs))


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
    def estimate_selected():
        return estimate_slot(
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
            overlap_reuse=overlap_reuse_for(state.machine_timeline),
        )

    handoff = current_sgs_handoff()
    estimate = None
    compute = estimate_selected
    if handoff is not None and estimate_slot is estimate_internal_slot:
        if handoff._timing is not None:
            def shared_selected():
                return handoff.shared_slot_estimate(
                    calendar=ctx.calendar, op=op, batch=batch, machine_id=machine_id, operator_id=operator_id,
                    prev_end=meta["prev_end"], total_hours=total_hours, end_dt_exclusive=end_dt_exclusive,
                    machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes else [],
                    compute=estimate_selected)

            compute = shared_selected
        estimate = handoff.pair_estimate(
            op=op, machine_id=machine_id, operator_id=operator_id, prev_end=meta["prev_end"],
            machine_timeline=state.machine_timeline, operator_timeline=state.operator_timeline, compute=compute,
        )
    if estimate is None:
        estimate = compute()
    if estimate.abort_after_hit:
        raise RuntimeError("SGS 评分不应命中 abort_after 早停")
    reuse = current_sgs_reuse()
    if (reuse is not None and reuse.scoring_op is op) or current_sgs_handoff() is not None:
        remember_sgs_estimate(
            estimate, calendar=ctx.calendar, op=op, batch=batch,
            machine_id=machine_id, operator_id=operator_id, base_time=state.base_time, prev_end=meta["prev_end"],
            machine_timeline=state.machine_timeline.get(machine_id) or [],
            operator_timeline=state.operator_timeline.get(operator_id) or [],
            machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
            end_dt_exclusive=end_dt_exclusive, last_op_type_by_machine=state.last_op_type_by_machine,
            total_hours_base=total_hours,
        )
    return estimate


_NATIVE_SCORING_HELPERS = {name: globals()[name] for name in (
    "_candidate_meta", "_scoring_total_hours", "_scoring_resources", "_estimate_scoring_slot", "_dispatch_key",
    "_parse_due_date", "parse_optional_date", "parse_date", "_score_internal_candidate", "_score_external_candidate",
)}


def native_scoring_unchanged():
    return all(globals()[name] is original for name, original in _NATIVE_SCORING_HELPERS.items())
