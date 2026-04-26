from __future__ import annotations

"""
贪心排产算法（Phase 7 / P7-02, P7-06）。

要点（对齐开发文档.md）：
- 内部工序：设备 + 人员 双重资源约束
- 外部工序：不占内部资源，仅按自然日（天）推进
- 前后约束：同一批次按工序顺序串行推进
- 工作日历：使用 CalendarService 的 adjust_to_working_time / add_working_hours / get_efficiency / add_calendar_days
- 外部组合并周期（merged）：整组作为一个时间块，组内每道外部工序落同一 start/end
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.ordering import (
    _parse_created_at_for_sort,
    _parse_due_date_for_sort,
    _parse_ready_date_for_sort,
    build_batch_sort_inputs,
    build_normalized_batches_map,
    normalize_batch_order_override,
    normalize_text_id,
    operation_sort_key,
    parse_ready_date_for_sort,
    resolve_batch_sort_batch_id,
)
from core.algorithms.value_domains import INTERNAL

from ..sort_strategies import SortStrategy, StrategyFactory
from ..types import ScheduleResult, ScheduleSummary
from .algo_stats import ensure_algo_stats, increment_counter, make_algo_stats
from .auto_assign import auto_assign_internal_resources
from .dispatch import dispatch_batch_order, dispatch_sgs
from .downtime import occupy_resource
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation
from .run_context import ScheduleRunContext
from .run_state import ScheduleRunState
from .schedule_params import resolve_schedule_params
from .seed import normalize_seed_results

__all__ = [
    "GreedyScheduler",
    "_parse_created_at_for_sort",
    "_parse_due_date_for_sort",
    "_parse_ready_date_for_sort",
    "build_batch_sort_inputs",
    "build_normalized_batches_map",
    "normalize_batch_order_override",
    "normalize_text_id",
    "operation_sort_key",
    "parse_ready_date_for_sort",
    "resolve_batch_sort_batch_id",
]


class GreedyScheduler:
    """贪心排产算法（可由服务层注入日历与配置）。"""

    def __init__(self, calendar_service, config_service=None, logger: Optional[logging.Logger] = None):
        self.calendar = calendar_service
        self.config = config_service
        self.logger = logger or logging.getLogger(__name__)
        self._last_algo_stats = make_algo_stats()

    def schedule(
        self,
        operations: List[Any],
        batches: Dict[str, Any],
        strategy: Optional[SortStrategy] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        start_dt: Any = None,
        end_date: Any = None,
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        batch_order_override: Optional[List[str]] = None,
        seed_results: Optional[List[ScheduleResult]] = None,
        dispatch_mode: Optional[str] = None,
        dispatch_rule: Optional[str] = None,
        resource_pool: Optional[Dict[str, Any]] = None,
        strict_mode: bool = False,
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        t0 = datetime.now()
        algo_stats = self._reset_algo_stats()
        warnings: List[str] = []
        params = self._resolve_params(
            strategy=strategy,
            strategy_params=strategy_params,
            start_dt=start_dt,
            end_date=end_date,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            resource_pool=resource_pool,
            strict_mode=bool(strict_mode),
            warnings=warnings,
            algo_stats=algo_stats,
        )
        batches = build_normalized_batches_map(batches, warnings=warnings)
        machine_downtimes = _normalize_machine_downtimes(machine_downtimes)
        batch_order = _build_batch_order(batches, params, batch_order_override=batch_order_override, strict_mode=bool(strict_mode))
        seed_results, seed_op_ids = _normalize_seed_inputs(seed_results, operations, warnings=warnings, algo_stats=algo_stats)
        sorted_ops = _sorted_unseeded_operations(operations, seed_op_ids=seed_op_ids, batch_order=batch_order, warnings=warnings, algo_stats=algo_stats)
        state = _prepare_run_state(self.calendar, batches=batches, seed_results=seed_results, params=params, warnings=warnings, algo_stats=algo_stats, strict_mode=bool(strict_mode))
        ctx = ScheduleRunContext.from_legacy_scheduler(self)
        ctx.algo_stats = algo_stats

        self._log_start(batches=batches, sorted_ops=sorted_ops, params=params)
        _run_dispatch(
            ctx,
            state=state,
            sorted_ops=sorted_ops,
            batches=batches,
            batch_order=batch_order,
            params=params,
            machine_downtimes=machine_downtimes,
            resource_pool=resource_pool,
            strict_mode=bool(strict_mode),
        )
        summary = _build_summary(state=state, warnings=warnings, sorted_ops=sorted_ops, duration=(datetime.now() - t0).total_seconds())
        self.logger.info(f"排产结束：成功={summary.scheduled_ops}/{summary.total_ops} 失败={summary.failed_ops} 耗时={summary.duration_seconds:.2f}s")
        return state.results, summary, params.strategy, params.used_params

    def _reset_algo_stats(self) -> Dict[str, Any]:
        self._last_algo_stats = make_algo_stats()
        return ensure_algo_stats(self._last_algo_stats)

    def _resolve_params(self, *, warnings: List[str], algo_stats: Dict[str, Any], **kwargs: Any):
        params = resolve_schedule_params(config=self.config, algo_stats=algo_stats, **kwargs)
        warnings.extend(params.warnings)
        return params

    def _log_start(self, *, batches: Dict[str, Any], sorted_ops: List[Any], params: Any) -> None:
        sorter = StrategyFactory.create(params.strategy, **params.used_params)
        extra = f" 派工=sgs({params.dispatch_rule_enum.value})" if params.dispatch_mode_key == "sgs" else ""
        self.logger.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}{extra}")

    def _schedule_external(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        strict_mode: bool = False,
    ) -> Tuple[Optional[ScheduleResult], bool]:
        return schedule_external(
            self,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            external_group_cache=external_group_cache,
            base_time=base_time,
            errors=errors,
            end_dt_exclusive=end_dt_exclusive,
            strict_mode=bool(strict_mode),
        )

    def _schedule_internal(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        *,
        auto_assign_enabled: bool = False,
        resource_pool: Optional[Dict[str, Any]] = None,
        last_op_type_by_machine: Optional[Dict[str, str]] = None,
        machine_busy_hours: Optional[Dict[str, float]] = None,
        operator_busy_hours: Optional[Dict[str, float]] = None,
        strict_mode: bool = False,
    ) -> Tuple[Optional[ScheduleResult], bool]:
        return schedule_internal_operation(
            calendar=self.calendar,
            algo_stats=self._last_algo_stats,
            auto_assign_resources=self._auto_assign_internal_resources,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            errors=errors,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            strict_mode=bool(strict_mode),
        )

    def _auto_assign_internal_resources(
        self,
        *,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
        resource_pool: Dict[str, Any],
        last_op_type_by_machine: Dict[str, str],
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        probe_only: bool = False,
    ) -> Optional[Tuple[str, str]]:
        return auto_assign_internal_resources(
            calendar=self.calendar,
            algo_stats=self._last_algo_stats,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            resource_pool=resource_pool,
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            probe_only=probe_only,
        )


def _normalize_machine_downtimes(machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]]) -> Optional[Dict[str, List[Tuple[datetime, datetime]]]]:
    if not machine_downtimes:
        return machine_downtimes
    return {
        normalize_text_id(resource_id): sorted(list(segments or []), key=lambda segment: (segment[0], segment[1]))
        for resource_id, segments in machine_downtimes.items()
        if normalize_text_id(resource_id)
    }


def _build_batch_order(batches: Dict[str, Any], params: Any, *, batch_order_override: Optional[List[str]], strict_mode: bool) -> Dict[str, int]:
    override_order = normalize_batch_order_override(batch_order_override, batches)
    if override_order and len(override_order) == len(batches):
        return {batch_id: index for index, batch_id in enumerate(override_order)}
    batch_for_sort = build_batch_sort_inputs(batches, strict_mode=bool(strict_mode), strategy=params.strategy)
    sorted_batches = StrategyFactory.create(params.strategy, **params.used_params).sort(batch_for_sort, base_date=params.base_time.date())
    if not override_order:
        return {batch.batch_id: index for index, batch in enumerate(sorted_batches)}
    seen = set(override_order)
    override_order.extend([batch.batch_id for batch in sorted_batches if batch.batch_id not in seen])
    return {batch_id: index for index, batch_id in enumerate(override_order)}


def _normalize_seed_inputs(seed_results: Optional[List[ScheduleResult]], operations: List[Any], *, warnings: List[str], algo_stats: Dict[str, Any]) -> Tuple[Optional[List[ScheduleResult]], set]:
    if not seed_results:
        return seed_results, set()
    normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_results=seed_results, operations=operations, algo_stats=algo_stats)
    warnings.extend(seed_warnings)
    return normalized_seed, seed_op_ids


def _sorted_unseeded_operations(operations: List[Any], *, seed_op_ids: set, batch_order: Dict[str, int], warnings: List[str], algo_stats: Dict[str, Any]) -> List[Any]:
    ops_for_sort = operations
    if seed_op_ids:
        ops_for_sort, dropped = _drop_seeded_operations(operations, seed_op_ids)
        if dropped:
            warnings.append(f"检测到 seed_results 与 operations 重叠：已过滤 {dropped} 道工序避免重复排产。")
            increment_counter(algo_stats, "seed_overlap_filtered_count", dropped)
    return sorted(ops_for_sort, key=lambda op: operation_sort_key(op, batch_order))


def _drop_seeded_operations(operations: List[Any], seed_op_ids: set) -> Tuple[List[Any], int]:
    filtered = []
    dropped = 0
    for op in operations:
        op_id = _safe_op_id(op)
        if op_id and op_id in seed_op_ids:
            dropped += 1
            continue
        filtered.append(op)
    return filtered, dropped


def _safe_op_id(op: Any) -> int:
    try:
        return int(getattr(op, "id", 0) or 0)
    except Exception:
        return 0


def _prepare_run_state(calendar: Any, *, batches: Dict[str, Any], seed_results: Optional[List[ScheduleResult]], params: Any, warnings: List[str], algo_stats: Dict[str, Any], strict_mode: bool) -> ScheduleRunState:
    state = ScheduleRunState(base_time=params.base_time)
    _initialize_ready_progress(calendar, state=state, batches=batches, strict_mode=strict_mode)
    if seed_results:
        _apply_seed_results(state=state, seed_results=seed_results)
        warnings.extend(state.seed_resource_warnings())
        increment_counter(algo_stats, "seed_missing_machine_id_count", state.missing_seed_machine_count)
        increment_counter(algo_stats, "seed_missing_operator_id_count", state.missing_seed_operator_count)
    return state


def _initialize_ready_progress(calendar: Any, *, state: ScheduleRunState, batches: Dict[str, Any], strict_mode: bool) -> None:
    for batch_id, batch in batches.items():
        ready_date = parse_ready_date_for_sort(getattr(batch, "ready_date", None), strict_mode=bool(strict_mode))
        if batch_id and ready_date is not None:
            ready_start = datetime(ready_date.year, ready_date.month, ready_date.day, 0, 0, 0)
            state.advance_batch(batch_id, calendar.adjust_to_working_time(ready_start, priority=getattr(batch, "priority", None)))


def _apply_seed_results(*, state: ScheduleRunState, seed_results: List[ScheduleResult]) -> None:
    for result in seed_results:
        if _valid_seed_result(result):
            _freeze_seed_resources(state, result)
            state.record_seed_result(result)


def _valid_seed_result(result: ScheduleResult) -> bool:
    if not result or not isinstance(result.start_time, datetime) or not isinstance(result.end_time, datetime):
        return False
    try:
        return int(getattr(result, "op_id", 0) or 0) > 0
    except Exception:
        return False


def _freeze_seed_resources(state: ScheduleRunState, result: ScheduleResult) -> None:
    if (result.source or "").strip().lower() != INTERNAL:
        return
    if not isinstance(result.start_time, datetime) or not isinstance(result.end_time, datetime):
        return
    machine_id = normalize_text_id(result.machine_id)
    operator_id = normalize_text_id(result.operator_id)
    if machine_id:
        occupy_resource(state.machine_timeline, machine_id, result.start_time, result.end_time)
    if operator_id:
        occupy_resource(state.operator_timeline, operator_id, result.start_time, result.end_time)


def _run_dispatch(ctx: ScheduleRunContext, *, state: ScheduleRunState, sorted_ops: List[Any], batches: Dict[str, Any], batch_order: Dict[str, int], params: Any, machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]], resource_pool: Optional[Dict[str, Any]], strict_mode: bool) -> None:
    if params.dispatch_mode_key != "sgs":
        dispatch_batch_order(
            ctx,
            sorted_ops=sorted_ops,
            batches=batches,
            base_time=params.base_time,
            end_dt_exclusive=params.end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            state=state,
            auto_assign_enabled=params.auto_assign_enabled,
            resource_pool=resource_pool,
            strict_mode=strict_mode,
        )
        return
    dispatch_sgs(
        ctx,
        sorted_ops=sorted_ops,
        batches=batches,
        batch_order=batch_order,
        dispatch_rule=params.dispatch_rule_enum,
        base_time=params.base_time,
        end_dt_exclusive=params.end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        state=state,
        auto_assign_enabled=params.auto_assign_enabled,
        resource_pool=resource_pool,
        strict_mode=strict_mode,
    )


def _build_summary(*, state: ScheduleRunState, warnings: List[str], sorted_ops: List[Any], duration: float) -> ScheduleSummary:
    total_ops = int(len(sorted_ops) + state.seed_count)
    return ScheduleSummary(
        success=(state.failed_count == 0),
        total_ops=total_ops,
        scheduled_ops=state.scheduled_count,
        failed_ops=state.failed_count,
        warnings=warnings,
        errors=state.errors,
        duration_seconds=duration,
    )
