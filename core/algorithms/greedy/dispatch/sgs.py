from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import EXTERNAL, INTERNAL, MERGED
from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector
from core.services.common.field_parse import parse_field_float
from core.services.common.strict_parse import parse_optional_date

from ..algo_stats import increment_counter
from ..date_parsers import parse_date
from ..downtime import find_earliest_available_start
from ..internal_slot import estimate_internal_slot, validate_internal_hours
from .runtime_state import accumulate_busy_hours, update_machine_last_state

_SCHEDULE_OPERATION_FAILED_MESSAGE = "排产异常，请查看系统日志。"


def _parse_due_date(value: Any, *, strict_mode: bool = False) -> Optional[date]:
    if strict_mode:
        return parse_optional_date(value, field="due_date")
    return parse_date(value)


def _safe_seq(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return 0


def _raise_strict_internal_hours_validation(op: Any, batch: Any, exc: ValueError) -> None:
    for field, raw_value in (
        ("setup_hours", getattr(op, "setup_hours", None)),
        ("unit_hours", getattr(op, "unit_hours", None)),
        ("quantity", getattr(batch, "quantity", None)),
    ):
        if raw_value is True:
            continue
        try:
            if not raw_value:
                continue
        except Exception:
            raise
        try:
            parsed = float(raw_value)
        except Exception as parse_exc:
            raise ValidationError(f"“{field}”必须是数字", field=field) from parse_exc
        if not math.isfinite(parsed):
            raise ValidationError(f"“{field}”必须是有限数字", field=field)
        if parsed < 0:
            raise ValidationError(f"“{field}”必须大于等于 0", field=field)
    raise ValidationError(str(exc), field="setup_hours")


def _dispatch_key(
    *,
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
    base_key = build_dispatch_key(
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


def _build_unscorable_dispatch_key(
    *,
    scheduler: Any,
    dispatch_rule: DispatchRule,
    priority: Any,
    due_date: Optional[date],
    avg_proc_hours: float,
    batch_order: Dict[str, int],
    batch_id: str,
    seq: int,
    op_id: int,
    est_start: datetime,
    machine_id: str = "",
    operator_id: str = "",
    machine_timeline: Optional[List[Tuple[datetime, datetime]]] = None,
    operator_timeline: Optional[List[Tuple[datetime, datetime]]] = None,
    machine_downtimes: Optional[List[Tuple[datetime, datetime]]] = None,
) -> Tuple[float, ...]:
    increment_counter(scheduler, "dispatch_key_proc_hours_fallback_count")
    try:
        proc_hours = max(float(avg_proc_hours), 1e-6)
    except Exception:
        proc_hours = 1.0

    estimate_start = est_start
    if machine_id and operator_id:
        estimate_start = find_earliest_available_start(machine_timeline or [], estimate_start, proc_hours)
        estimate_start = find_earliest_available_start(operator_timeline or [], estimate_start, proc_hours)
        estimate_start = find_earliest_available_start(machine_downtimes or [], estimate_start, proc_hours)
        estimate_start = scheduler.calendar.adjust_to_working_time(
            estimate_start,
            priority=priority,
            operator_id=operator_id,
        )

    return _dispatch_key(
        dispatch_rule=dispatch_rule,
        priority=priority,
        due_date=due_date,
        est_start=estimate_start,
        est_end=estimate_start,
        proc_hours=proc_hours,
        avg_proc_hours=avg_proc_hours,
        changeover_penalty=1,
        batch_order=batch_order,
        batch_id=batch_id,
        seq=seq,
        op_id=op_id,
        score_penalty=1.0,
    )


def _collect_sgs_candidates(
    *,
    batch_ids_in_order: List[str],
    ops_by_batch: Dict[str, List[Any]],
    next_idx: Dict[str, int],
    blocked_batches: set,
) -> List[Tuple[str, Any]]:
    candidates: List[Tuple[str, Any]] = []
    for batch_id in batch_ids_in_order:
        if batch_id in blocked_batches:
            continue
        idx = int(next_idx.get(batch_id, 0) or 0)
        operations = ops_by_batch.get(batch_id) or []
        if idx >= len(operations):
            continue
        candidates.append((batch_id, operations[idx]))
    return candidates


def _record_external_compat_counters(scheduler: Any, collector: DegradationCollector) -> None:
    counters = collector.to_counters()
    legacy_defaulted = int(counters.get("legacy_external_days_defaulted") or 0) + int(counters.get("blank_required") or 0)
    if legacy_defaulted > 0:
        increment_counter(scheduler, "legacy_external_days_defaulted_count", legacy_defaulted)


def _score_external_candidate(
    *,
    scheduler: Any,
    op: Any,
    batch: Any,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
    avg_proc_hours: float,
    strict_mode: bool,
) -> Tuple[float, ...]:
    priority = getattr(batch, "priority", None)
    due_date = _parse_due_date(getattr(batch, "due_date", None), strict_mode=bool(strict_mode))
    seq = _safe_seq(getattr(op, "seq", 0))
    op_id = _safe_seq(getattr(op, "id", 0))
    prev_end = batch_progress.get(batch_id, base_time)
    merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()

    if merge_mode == MERGED and ext_group_id:
        cached = external_group_cache.get((batch_id, ext_group_id))
        if cached:
            est_start, est_end = cached
        else:
            collector = DegradationCollector()
            total_days_raw = getattr(op, "ext_group_total_days", None)
            try:
                total_days = float(
                    parse_field_float(
                        total_days_raw,
                        field="ext_group_total_days",
                        strict_mode=bool(strict_mode),
                        scope="greedy.dispatch.sgs",
                        fallback=0.0,
                        collector=collector,
                        min_value=0.0,
                        min_inclusive=False,
                        min_violation_fallback=0.0,
                    )
                )
            except Exception:
                if strict_mode:
                    raise
                increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")
                return _build_unscorable_dispatch_key(
                    scheduler=scheduler,
                    dispatch_rule=dispatch_rule,
                    priority=priority,
                    due_date=due_date,
                    avg_proc_hours=avg_proc_hours,
                    batch_order=batch_order,
                    batch_id=batch_id,
                    seq=seq,
                    op_id=op_id,
                    est_start=prev_end,
                )
            _record_external_compat_counters(scheduler, collector)
            if total_days <= 0:
                increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")
                return _build_unscorable_dispatch_key(
                    scheduler=scheduler,
                    dispatch_rule=dispatch_rule,
                    priority=priority,
                    due_date=due_date,
                    avg_proc_hours=avg_proc_hours,
                    batch_order=batch_order,
                    batch_id=batch_id,
                    seq=seq,
                    op_id=op_id,
                    est_start=prev_end,
                )
            est_start = prev_end
            est_end = scheduler.calendar.add_calendar_days(est_start, total_days)
    else:
        collector = DegradationCollector()
        ext_days_raw = getattr(op, "ext_days", None)
        try:
            ext_days = float(
                parse_field_float(
                    ext_days_raw,
                    field="ext_days",
                    strict_mode=bool(strict_mode),
                    scope="greedy.dispatch.sgs",
                    fallback=1.0,
                    collector=collector,
                    min_value=0.0,
                    min_inclusive=False,
                    min_violation_fallback=0.0,
                )
            )
        except Exception:
            if strict_mode:
                raise
            increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")
            return _build_unscorable_dispatch_key(
                scheduler=scheduler,
                dispatch_rule=dispatch_rule,
                priority=priority,
                due_date=due_date,
                avg_proc_hours=avg_proc_hours,
                batch_order=batch_order,
                batch_id=batch_id,
                seq=seq,
                op_id=op_id,
                est_start=prev_end,
            )
        _record_external_compat_counters(scheduler, collector)
        if ext_days <= 0:
            increment_counter(scheduler, "dispatch_sgs_external_duration_unscorable_count")
            return _build_unscorable_dispatch_key(
                scheduler=scheduler,
                dispatch_rule=dispatch_rule,
                priority=priority,
                due_date=due_date,
                avg_proc_hours=avg_proc_hours,
                batch_order=batch_order,
                batch_id=batch_id,
                seq=seq,
                op_id=op_id,
                est_start=prev_end,
            )
        est_start = prev_end
        est_end = scheduler.calendar.add_calendar_days(est_start, ext_days)

    proc_hours = max((est_end - est_start).total_seconds() / 3600.0, 0.0)
    score_penalty = 0.0
    if end_dt_exclusive is not None and est_end >= end_dt_exclusive:
        score_penalty = 1.0

    return _dispatch_key(
        dispatch_rule=dispatch_rule,
        priority=priority,
        due_date=due_date,
        est_start=est_start,
        est_end=est_end,
        proc_hours=proc_hours,
        avg_proc_hours=avg_proc_hours,
        changeover_penalty=0,
        batch_order=batch_order,
        batch_id=batch_id,
        seq=seq,
        op_id=op_id,
        score_penalty=score_penalty,
    )


def _score_internal_candidate(
    *,
    scheduler: Any,
    op: Any,
    batch: Any,
    batch_id: str,
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    last_op_type_by_machine: Dict[str, str],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    avg_proc_hours: float,
    strict_mode: bool,
) -> Tuple[float, ...]:
    priority = getattr(batch, "priority", None)
    due_date = _parse_due_date(getattr(batch, "due_date", None), strict_mode=bool(strict_mode))
    seq = _safe_seq(getattr(op, "seq", 0))
    op_id = _safe_seq(getattr(op, "id", 0))
    prev_end = batch_progress.get(batch_id, base_time)

    try:
        total_hours_base = validate_internal_hours(op, batch)
    except ValueError as exc:
        if strict_mode:
            _raise_strict_internal_hours_validation(op, batch, exc)
        increment_counter(scheduler, "dispatch_sgs_total_hours_unscorable_count")
        return _build_unscorable_dispatch_key(
            scheduler=scheduler,
            dispatch_rule=dispatch_rule,
            priority=priority,
            due_date=due_date,
            avg_proc_hours=avg_proc_hours,
            batch_order=batch_order,
            batch_id=batch_id,
            seq=seq,
            op_id=op_id,
            est_start=prev_end,
        )

    machine_id = str(getattr(op, "machine_id", None) or "").strip()
    operator_id = str(getattr(op, "operator_id", None) or "").strip()
    if (not machine_id or not operator_id) and auto_assign_enabled and resource_pool is not None:
        chooser = getattr(scheduler, "_auto_assign_internal_resources", None)
        if not callable(chooser):
            raise TypeError("scheduler._auto_assign_internal_resources 不可调用")
        chosen = chooser(
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            resource_pool=(resource_pool if isinstance(resource_pool, dict) else {}),
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            probe_only=True,
        )
        if chosen is not None:
            if not isinstance(chosen, (list, tuple)) or len(chosen) < 2:
                raise TypeError("auto_assign probe result is not a pair")
            machine_id = str(chosen[0] or "").strip()
            operator_id = str(chosen[1] or "").strip()

    if not machine_id or not operator_id:
        increment_counter(scheduler, "dispatch_sgs_missing_resource_unscorable_count")
        return _build_unscorable_dispatch_key(
            scheduler=scheduler,
            dispatch_rule=dispatch_rule,
            priority=priority,
            due_date=due_date,
            avg_proc_hours=avg_proc_hours,
            batch_order=batch_order,
            batch_id=batch_id,
            seq=seq,
            op_id=op_id,
            est_start=prev_end,
        )

    estimate = estimate_internal_slot(
        calendar=scheduler.calendar,
        op=op,
        batch=batch,
        machine_id=machine_id,
        operator_id=operator_id,
        base_time=base_time,
        prev_end=prev_end,
        machine_timeline=machine_timeline.get(machine_id) or [],
        operator_timeline=operator_timeline.get(operator_id) or [],
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
        last_op_type_by_machine=last_op_type_by_machine,
        abort_after=None,
        total_hours_base=total_hours_base,
    )
    if estimate.abort_after_hit:
        raise RuntimeError("SGS 评分不应命中 abort_after 早停")

    return _dispatch_key(
        dispatch_rule=dispatch_rule,
        priority=priority,
        due_date=due_date,
        est_start=estimate.start_time,
        est_end=estimate.end_time,
        proc_hours=estimate.total_hours,
        avg_proc_hours=avg_proc_hours,
        changeover_penalty=estimate.changeover_penalty,
        batch_order=batch_order,
        batch_id=batch_id,
        seq=seq,
        op_id=op_id,
        score_penalty=(1.0 if estimate.blocked_by_window else 0.0),
    )


def _pick_best_candidate(scored_candidates: List[Tuple[Tuple[float, ...], str, Any]]) -> Tuple[str, Any]:
    if not scored_candidates:
        raise RuntimeError("SGS 评分阶段未产生任何候选")
    best_key, best_batch_id, best_op = min(scored_candidates, key=lambda item: item[0])
    _ = best_key
    return best_batch_id, best_op


def dispatch_sgs(
    scheduler: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    last_op_type_by_machine: Dict[str, str],
    last_end_by_machine: Dict[str, datetime],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    results: List[ScheduleResult],
    errors: List[str],
    blocked_batches: set,
    scheduled_count: int,
    failed_count: int,
    strict_mode: bool = False,
) -> Tuple[int, int]:
    """
    Serial SGS（eligible set）派工：每个批次只暴露“下一道”可排工序，动态选择最优候选。

    注意：保持与原 GreedyScheduler.schedule 内 sgs 分支的行为一致：
    - 无效 batch_id：计 failed + errors
    - 任一工序失败：阻断该批次，并将“剩余工序”一次性计入 failed（保证 summary 口径一致）
    """
    ops_by_batch: Dict[str, List[Any]] = {}
    for op in sorted_ops:
        batch_id = str(getattr(op, "batch_id", "") or "").strip()
        if batch_id not in batches:
            failed_count += 1
            errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {batch_id}")
            continue
        ops_by_batch.setdefault(batch_id, []).append(op)
    for operations in ops_by_batch.values():
        operations.sort(key=lambda item: (_safe_seq(getattr(item, "seq", 0)), _safe_seq(getattr(item, "id", 0))))

    batch_ids_in_order = sorted(list(ops_by_batch.keys()), key=lambda item: (batch_order.get(item, 999999), item))
    next_idx: Dict[str, int] = {batch_id: 0 for batch_id in batch_ids_in_order}

    proc_samples: List[float] = []
    for batch_id, operations in ops_by_batch.items():
        batch = batches.get(batch_id)
        if not batch:
            continue
        for op in operations:
            if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() != INTERNAL:
                continue
            try:
                proc_samples.append(validate_internal_hours(op, batch))
            except ValueError as exc:
                if strict_mode:
                    _raise_strict_internal_hours_validation(op, batch, exc)
                continue
    avg_proc_hours = (sum(proc_samples) / float(len(proc_samples))) if proc_samples else 1.0
    if not proc_samples:
        increment_counter(scheduler, "dispatch_key_avg_proc_hours_fallback_count")

    while True:
        candidates = _collect_sgs_candidates(
            batch_ids_in_order=batch_ids_in_order,
            ops_by_batch=ops_by_batch,
            next_idx=next_idx,
            blocked_batches=blocked_batches,
        )
        if not candidates:
            break

        scored_candidates: List[Tuple[Tuple[float, ...], str, Any]] = []
        for batch_id, op in candidates:
            batch = batches[batch_id]
            if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == EXTERNAL:
                score_key = _score_external_candidate(
                    scheduler=scheduler,
                    op=op,
                    batch=batch,
                    batch_id=batch_id,
                    batch_order=batch_order,
                    dispatch_rule=dispatch_rule,
                    base_time=base_time,
                    end_dt_exclusive=end_dt_exclusive,
                    batch_progress=batch_progress,
                    external_group_cache=external_group_cache,
                    avg_proc_hours=avg_proc_hours,
                    strict_mode=bool(strict_mode),
                )
            else:
                score_key = _score_internal_candidate(
                    scheduler=scheduler,
                    op=op,
                    batch=batch,
                    batch_id=batch_id,
                    batch_order=batch_order,
                    dispatch_rule=dispatch_rule,
                    base_time=base_time,
                    end_dt_exclusive=end_dt_exclusive,
                    machine_downtimes=machine_downtimes,
                    batch_progress=batch_progress,
                    machine_timeline=machine_timeline,
                    operator_timeline=operator_timeline,
                    machine_busy_hours=machine_busy_hours,
                    operator_busy_hours=operator_busy_hours,
                    last_op_type_by_machine=last_op_type_by_machine,
                    auto_assign_enabled=auto_assign_enabled,
                    resource_pool=resource_pool,
                    avg_proc_hours=avg_proc_hours,
                    strict_mode=bool(strict_mode),
                )
            scored_candidates.append((score_key, batch_id, op))

        batch_id, op = _pick_best_candidate(scored_candidates)
        try:
            batch = batches[batch_id]
            if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == EXTERNAL:
                result, _blocked = scheduler._schedule_external(  # type: ignore[attr-defined]
                    op,
                    batch,
                    batch_progress,
                    external_group_cache,
                    base_time,
                    errors,
                    end_dt_exclusive,
                    strict_mode=bool(strict_mode),
                )
            else:
                result, _blocked = scheduler._schedule_internal(  # type: ignore[attr-defined]
                    op,
                    batch,
                    batch_progress,
                    machine_timeline,
                    operator_timeline,
                    base_time,
                    errors,
                    end_dt_exclusive,
                    machine_downtimes,
                    auto_assign_enabled=auto_assign_enabled,
                    resource_pool=resource_pool,
                    last_op_type_by_machine=last_op_type_by_machine,
                    machine_busy_hours=machine_busy_hours,
                    operator_busy_hours=operator_busy_hours,
                )

            if result and result.start_time and result.end_time:
                if (result.source or "").strip().lower() == INTERNAL and result.machine_id:
                    accumulate_busy_hours(
                        machine_busy_hours=machine_busy_hours,
                        operator_busy_hours=operator_busy_hours,
                        machine_id=str(result.machine_id or "").strip(),
                        operator_id=str(result.operator_id or "").strip(),
                        start_time=result.start_time,
                        end_time=result.end_time,
                    )
                    update_machine_last_state(
                        last_end_by_machine=last_end_by_machine,
                        last_op_type_by_machine=last_op_type_by_machine,
                        machine_id=str(result.machine_id or "").strip(),
                        end_time=result.end_time,
                        op_type_name=result.op_type_name,
                        seed_mode=False,
                    )
                results.append(result)
                batch_progress[batch_id] = max(batch_progress.get(batch_id, base_time), result.end_time)
                scheduled_count += 1
                next_idx[batch_id] = int(next_idx.get(batch_id, 0) or 0) + 1
            else:
                failed_count += 1
                blocked_batches.add(batch_id)
                idx0 = int(next_idx.get(batch_id, 0) or 0)
                operations = ops_by_batch.get(batch_id) or []
                rest = max(int(len(operations)) - (idx0 + 1), 0)
                failed_count += int(rest)
        except Exception:
            failed_count += 1
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"工序 {op_code} {_SCHEDULE_OPERATION_FAILED_MESSAGE}")
            try:
                scheduler.logger.exception(f"工序 {op_code} 排产异常")  # type: ignore[attr-defined]
            except Exception:
                pass
            blocked_batches.add(batch_id)
            try:
                idx0 = int(next_idx.get(batch_id, 0) or 0)
                operations = ops_by_batch.get(batch_id) or []
                rest = max(int(len(operations)) - (idx0 + 1), 0)
                failed_count += int(rest)
            except Exception:
                pass

    return scheduled_count, failed_count
