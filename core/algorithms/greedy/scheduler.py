from __future__ import annotations

"""贪心排产算法（Phase 7 / P7-02, P7-06）。

协调内部工序的设备、人员、工作日历与批次前后约束；外部工序按自然日推进，merged 组共享时间块。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.ordering import (
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
from core.algorithm_contracts.sort_strategies import SortStrategy, StrategyFactory
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithm_runtime.algo_stats import ensure_algo_stats, increment_counter, make_algo_stats
from core.algorithm_runtime.checkpoint_calendar import checkpoint_calendar_signature
from core.algorithm_runtime.native_snapshot import make_class_guard
from core.algorithm_runtime.resource_quality import initialize_resource_quality
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import sgs_reuse_scope
from core.infrastructure.errors import ValidationError

from . import internal_operation
from .auto_assign import (
    auto_assign_internal_resources,
    auto_assign_internal_resources_attempt,
    eligible_auto_assign_resources,
    native_auto_assign_unchanged,
)
from .dispatch import dispatch_batch_order, dispatch_sgs
from .dispatch.route import dispatch_run
from .dispatch.sgs_checkpoint import DecodeCheckpoint, DecodeCheckpointRequest, decode_input_signature
from .dispatch.sgs_decode_acceleration import dispatch_certificate, pristine_functions
from .dispatch.sgs_reuse import can_skip_native_sgs_reuse, create_native_sgs_reuse
from .dispatch.sgs_score_cache import AutoAssignProbeContract, attach_sgs_score_cache, sgs_score_cache_stats
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation
from .run_context import ScheduleRunContext
from .run_state_setup import _prepare_run_state, replay_resumed_demand, resume_run_state
from .schedule_params import resolve_schedule_params
from .seed import _identity_int, normalize_seed_results

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
        self._decode_invocations = 0
        self._last_sgs_reuse_stats = {"hits": 0, "misses": 0}
        self._last_sgs_score_cache_stats = sgs_score_cache_stats(None)

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
        readiness_gate_enabled: bool = False,
        strict_mode: bool = False,
        graph_ready_context: Optional[Any] = None,
        decode_resume: Optional[DecodeCheckpoint] = None,
        decode_checkpoints: Optional[DecodeCheckpointRequest] = None,
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        self._decode_invocations += 1
        self._last_sgs_reuse_stats = {"hits": 0, "misses": 0}
        self._last_sgs_score_cache_stats = sgs_score_cache_stats(None)
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
        batch_order = _build_batch_order(
            batches,
            params,
            batch_order_override=batch_order_override,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            strict_mode=bool(strict_mode),
        )
        seed_results, seed_op_ids = _normalize_seed_inputs(seed_results, operations, warnings=warnings, algo_stats=algo_stats)
        sorted_ops = _sorted_unseeded_operations(operations, seed_op_ids=seed_op_ids, batch_order=batch_order, warnings=warnings, algo_stats=algo_stats)
        skip_score_reuse = params.dispatch_mode_key == "sgs" and can_skip_native_sgs_reuse(sorted_ops)
        checkpoint_signature = None
        if decode_resume is not None or decode_checkpoints is not None:
            checkpoint_signature = decode_input_signature(
                operations=sorted_ops, batches=batches, batch_order=batch_order, params=params,
                machine_downtimes=machine_downtimes, resource_pool=resource_pool, seed_results=seed_results,
                graph_ready_context=graph_ready_context, readiness_gate_enabled=bool(readiness_gate_enabled),
                strict_mode=bool(strict_mode), calendar_signature=checkpoint_calendar_signature(self.calendar),
                warnings=warnings)
        if decode_resume is not None:
            # Resumed decode: the checkpoint already holds seeds, readiness progress and the prefix picks.
            state = resume_run_state(decode_resume, signature=checkpoint_signature, warnings=warnings,
                                     dispatch_mode_key=params.dispatch_mode_key, graph_ready_context=graph_ready_context)
        else:
            state = _prepare_run_state(
                self.calendar,
                batches=batches,
                operations=operations,
                seed_results=seed_results,
                params=params,
                warnings=warnings,
                algo_stats=algo_stats,
                readiness_gate_enabled=bool(readiness_gate_enabled),
                strict_mode=bool(strict_mode),
                owned_timelines=not skip_score_reuse,
            )
        ctx = ScheduleRunContext.from_legacy_scheduler(self)
        ctx.algo_stats = algo_stats
        if getattr(decode_checkpoints, "tail_reuse", None) is not None:
            ctx.checkpoint_dispatch_guard = dispatch_certificate(self, ctx, _NATIVE_SGS_SCHEDULER_GUARD, _NATIVE_SGS_CONTEXT_GUARD,
                                                                 internal_operation, _NATIVE_INTERNAL_OPERATION_FUNCTIONS)
        initialize_resource_quality(state, sorted_ops, resource_pool)
        if decode_resume is not None:
            replay_resumed_demand(state)
        if decode_checkpoints is not None:
            decode_checkpoints.arm(signature=checkpoint_signature, warnings=warnings)
        attach_sgs_score_cache(ctx, self, GreedyScheduler, state=state, params=params, resource_pool=resource_pool, probe=_SGS_AUTO_ASSIGN_PROBE)

        self._log_start(batches=batches, sorted_ops=sorted_ops, params=params)
        reuse = (create_native_sgs_reuse(self, ctx, state, sorted_ops, batches,
                                        _NATIVE_SGS_SCHEDULER_GUARD, _NATIVE_SGS_CONTEXT_GUARD)
                 if params.dispatch_mode_key == "sgs" and not skip_score_reuse else None)
        with sgs_reuse_scope(reuse):
            _run_dispatch(
                ctx,
                state=state,
                sorted_ops=sorted_ops,
                batches=batches,
                batch_order=batch_order,
                params=params,
                machine_downtimes=machine_downtimes,
                resource_pool=resource_pool,
                graph_ready_context=graph_ready_context,
                strict_mode=bool(strict_mode),
                decode_resume=decode_resume,
                decode_checkpoints=decode_checkpoints,
            )
        if reuse is not None:
            self._last_sgs_reuse_stats = {"hits": reuse.hits, "misses": reuse.misses}
        self._last_sgs_score_cache_stats = sgs_score_cache_stats(ctx.sgs_score_cache)
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
        extra = f" 派工=sgs({params.dispatch_rule_spec.token})" if params.dispatch_mode_key == "sgs" else ""
        self.logger.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}{extra}")

    def _schedule_external(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
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
            auto_assign_resources=self._auto_assign_internal_resources_attempt,
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

    def _auto_assign_internal_resources_attempt(
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
    ):
        return auto_assign_internal_resources_attempt(
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


def _build_batch_order(
    batches: Dict[str, Any],
    params: Any,
    *,
    batch_order_override: Optional[List[str]],
    readiness_gate_enabled: bool,
    strict_mode: bool,
) -> Dict[str, int]:
    override_order = normalize_batch_order_override(batch_order_override, batches)
    if override_order and len(override_order) == len(batches):
        return {batch_id: index for index, batch_id in enumerate(override_order)}
    batch_for_sort = build_batch_sort_inputs(
        batches,
        strict_mode=bool(strict_mode),
        strategy=params.strategy,
        readiness_gate_enabled=bool(readiness_gate_enabled),
    )
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
        op_id = _operation_op_id(op)
        if op_id and op_id in seed_op_ids:
            dropped += 1
            continue
        filtered.append(op)
    return filtered, dropped


def _operation_op_id(op: Any) -> int:
    raw_id = getattr(op, "id", 0)
    op_id = _identity_int(raw_id)
    if op_id <= 0:
        raise ValidationError(f"待排工序编号不合法：{raw_id!r}", field="operations")
    return op_id


def _run_dispatch(ctx: ScheduleRunContext, *, state: ScheduleRunState, sorted_ops: List[Any], batches: Dict[str, Any], batch_order: Dict[str, int], params: Any, machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]], resource_pool: Optional[Dict[str, Any]], graph_ready_context: Optional[Any], strict_mode: bool, decode_resume: Optional[DecodeCheckpoint] = None, decode_checkpoints: Optional[DecodeCheckpointRequest] = None) -> None:
    dispatch_run(
        ctx, state=state, sorted_ops=sorted_ops, batches=batches, batch_order=batch_order,
        params=params, machine_downtimes=machine_downtimes, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context, strict_mode=strict_mode,
        batch_dispatch=dispatch_batch_order, sgs_dispatch=dispatch_sgs,
        decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
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
        failure_details=list(state.failure_details),
    )


_NATIVE_SGS_SCHEDULER_GUARD = make_class_guard(GreedyScheduler)
_SGS_AUTO_ASSIGN_PROBE = AutoAssignProbeContract(eligible_auto_assign_resources, native_auto_assign_unchanged)
# Freeze the imported context's original methods during module initialization;
# the dispatch child never imports its parent or certifies a caller-supplied type.
_NATIVE_SGS_CONTEXT_GUARD = make_class_guard(ScheduleRunContext)
# 派工见证只在 internal_operation 的函数仍是导入时的同一批对象时才有效；快照由本包持有，dispatch 子包不反向 import。
_NATIVE_INTERNAL_OPERATION_FUNCTIONS = pristine_functions(internal_operation)
