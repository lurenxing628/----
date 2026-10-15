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
from core.errors import ValidationError

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
from .dispatch.sgs_score_cache import (
    AutoAssignProbeContract,
    attach_sgs_score_cache,
    make_sgs_score_cache_factory,
    sgs_score_cache_stats,
)
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation
from .run_context import ScheduleRunContext
from .run_state_setup import _prepare_run_state, replay_resumed_demand, resume_run_state
from .schedule_params import resolve_schedule_params
from .schedule_preparation import NativeSchedulePreparation
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
        self._begin_native_decode()
        params = resolve_schedule_params(
            config=self.config, strategy=strategy, strategy_params=strategy_params, start_dt=start_dt, end_date=end_date,
            dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule, resource_pool=resource_pool,
            strict_mode=bool(strict_mode), algo_stats=self._last_algo_stats,
        )
        preparation = prepare_native_schedule_inputs(
            machine_downtimes, scheduler=self, operations=operations, batches=batches,
            seed_results=seed_results, resource_pool=resource_pool, graph_ready_context=graph_ready_context,
        )
        batch_order = _build_batch_order(
            preparation.batches, params,
            batch_order_override=normalize_batch_order_override(batch_order_override, preparation.batches),
            readiness_gate_enabled=bool(readiness_gate_enabled), strict_mode=bool(strict_mode),
        )
        return self._decode_prepared(
            preparation, params=params, batch_order=batch_order, readiness_gate_enabled=readiness_gate_enabled,
            strict_mode=strict_mode, decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
        )

    def _begin_native_decode(self) -> None:
        self._decode_invocations += 1
        self._last_sgs_score_cache_stats = sgs_score_cache_stats(None)
        self._reset_algo_stats()
        self._decode_started_at = datetime.now()

    def schedule_prepared(self, prepared_inputs: NativeSchedulePreparation, **changes: Any) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        self._begin_native_decode()
        return self._decode_prepared(prepared_inputs, **changes)

    def _decode_prepared(
        self, prepared_inputs: NativeSchedulePreparation, *, params: Any, batch_order: Dict[str, int],
        operations: Any = None, resource_pool: Any = None, graph_ready_context: Any = None,
        readiness_gate_enabled: bool = False, strict_mode: bool = False, graph_enabled: bool = True,
        decode_resume: Optional[DecodeCheckpoint] = None,
        decode_checkpoints: Optional[DecodeCheckpointRequest] = None,
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        """Decode already prepared run facts; candidate arguments only supply changes."""
        t0 = self._decode_started_at
        algo_stats = ensure_algo_stats(self)
        self._active_preparation = prepared_inputs
        algo_stats["param_fallbacks"].update(params.param_fallbacks)
        for bucket, values in prepared_inputs.algo_stats.items():
            algo_stats[bucket].update(values)
        warnings = list(params.warnings) + list(prepared_inputs.warnings)
        batches, seed_results = prepared_inputs.batches, prepared_inputs.seed_results
        operations = prepared_inputs.operations if operations is None else operations
        resource_pool = prepared_inputs.resource_pool if resource_pool is None else resource_pool
        if not graph_enabled:
            graph_ready_context = None
        elif graph_ready_context is None:
            graph_ready_context = prepared_inputs.graph_ready_context
        machine_downtimes = prepared_inputs.normalized_machine_downtimes
        if operations is prepared_inputs.operations:
            unseeded = prepared_inputs.unseeded_operations
        else:
            unseeded, _ = _drop_seeded_operations(operations, prepared_inputs.seed_op_ids)
        sorted_ops = sorted(unseeded, key=lambda op: operation_sort_key(op, batch_order))
        checkpoint_signature = None
        if decode_resume is not None or decode_checkpoints is not None:
            if prepared_inputs.calendar is not None:
                calendar_signature = None
                prepared_calendar_signature = prepared_inputs.checkpoint_calendar_component()
            else:
                calendar_signature = checkpoint_calendar_signature(self.calendar)
                prepared_calendar_signature = None
            checkpoint_signature = decode_input_signature(
                operations=sorted_ops, batches=batches, batch_order=batch_order, params=params,
                machine_downtimes=machine_downtimes, resource_pool=resource_pool, seed_results=seed_results,
                graph_ready_context=graph_ready_context, readiness_gate_enabled=bool(readiness_gate_enabled),
                strict_mode=bool(strict_mode), calendar_signature=calendar_signature,
                prepared_calendar_signature=prepared_calendar_signature,
                warnings=warnings, prepared_inputs=prepared_inputs)
        if decode_resume is not None:
            # Resumed decode: the checkpoint already holds seeds, readiness progress and the prefix picks.
            if checkpoint_signature is None:
                raise RuntimeError("断点续排缺少解码输入签名")
            state = resume_run_state(decode_resume, signature=checkpoint_signature, warnings=warnings,
                                     dispatch_mode_key=params.dispatch_mode_key, graph_ready_context=graph_ready_context)
        else:
            state = _prepare_run_state(
                prepared_inputs=prepared_inputs,
                params=params,
                warnings=warnings,
                algo_stats=algo_stats,
                readiness_gate_enabled=bool(readiness_gate_enabled),
                strict_mode=bool(strict_mode),
            )
        ctx = prepared_inputs.run_context
        ctx.sgs_score_cache = None
        ctx.algo_stats = algo_stats
        ctx.native_preparation = prepared_inputs
        initialize_resource_quality(state, sorted_ops, resource_pool, preparation=prepared_inputs)
        if decode_resume is not None:
            replay_resumed_demand(state)
        if decode_checkpoints is not None:
            if checkpoint_signature is None:
                raise RuntimeError("解码断点缺少解码输入签名")
            decode_checkpoints.arm(signature=checkpoint_signature, warnings=warnings)
        attach_sgs_score_cache(ctx, state=state, params=params, resource_pool=resource_pool)

        self._log_start(batches=batches, sorted_ops=sorted_ops, params=params)
        _run_dispatch(
            ctx, state=state, sorted_ops=sorted_ops, batches=batches, batch_order=batch_order,
            params=params, machine_downtimes=machine_downtimes, resource_pool=resource_pool,
            graph_ready_context=graph_ready_context, strict_mode=bool(strict_mode),
            decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
        )
        self._last_sgs_score_cache_stats = sgs_score_cache_stats(ctx.sgs_score_cache)
        summary = _build_summary(state=state, warnings=warnings, sorted_ops=sorted_ops, duration=(datetime.now() - t0).total_seconds())
        self.logger.info(f"排产结束：成功={summary.scheduled_ops}/{summary.total_ops} 失败={summary.failed_ops} 耗时={summary.duration_seconds:.2f}s")
        return state.results, summary, params.strategy, params.used_params

    def _reset_algo_stats(self) -> Dict[str, Any]:
        self._last_algo_stats = make_algo_stats()
        return ensure_algo_stats(self._last_algo_stats)

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
            total_hours_by_op_id=getattr(getattr(self, "_active_preparation", None), "total_hours_by_op_id", None),
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
            resource_preparation=getattr(self, "_active_preparation", None),
            total_hours_by_op_id=getattr(getattr(self, "_active_preparation", None), "total_hours_by_op_id", None),
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
            resource_preparation=getattr(self, "_active_preparation", None),
            total_hours_by_op_id=getattr(getattr(self, "_active_preparation", None), "total_hours_by_op_id", None),
        )


def _normalize_machine_downtimes(machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]]) -> Optional[Dict[str, List[Tuple[datetime, datetime]]]]:
    if not machine_downtimes:
        return machine_downtimes
    return {
        normalize_text_id(resource_id): sorted(list(segments or []), key=lambda segment: (segment[0], segment[1]))
        for resource_id, segments in machine_downtimes.items()
        if normalize_text_id(resource_id)
    }


def prepare_native_schedule_inputs(
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]], *, scheduler: Any,
    operations: Any, batches: Any, seed_results: Any = None,
    resource_pool: Any = None, graph_ready_context: Any = None,
) -> NativeSchedulePreparation:
    from .dispatch.sgs_graph import (
        _TOPOLOGY_FIELD,
        _graph_priority_key_map,
        _graph_score_enabled,
        prepare_graph_ready_topology,
    )
    from .dispatch.sgs_score_cache import plain_record_class

    calendar = scheduler.calendar
    stats, warnings = make_algo_stats(), []
    normalized_batches = build_normalized_batches_map(batches, warnings=warnings)
    normalized_seeds, seed_op_ids = _normalize_seed_inputs(seed_results, operations, warnings=warnings, algo_stats=stats)
    unseeded = operations
    if seed_op_ids:
        unseeded, dropped = _drop_seeded_operations(unseeded, seed_op_ids)
        if dropped:
            warnings.append(f"检测到 seed_results 与 operations 重叠：已过滤 {dropped} 道工序避免重复排产。")
            increment_counter(stats, "seed_overlap_filtered_count", dropped)
    from core.algorithm_contracts.schedule_point_evidence import point_seed_valid
    from core.algorithm_contracts.value_domains import INTERNAL

    from .external_groups import rebuild_external_group_cache_from_seeds
    from .seed import seed_external_group_keys, seed_result_for_output

    seed_applications, external_seed_cache = [], {}
    for seed in normalized_seeds or ():
        occupies = str(seed.source or "").strip().lower() == INTERNAL and not point_seed_valid(seed)
        seed_applications.append((seed_result_for_output(seed), normalize_text_id(seed.machine_id) if occupies else "",
                                  normalize_text_id(seed.operator_id) if occupies else ""))
    rebuild_external_group_cache_from_seeds(
        seed_results=normalized_seeds or [], operations=operations, external_group_cache=external_seed_cache,
        warnings=warnings, algo_stats=stats, seed_group_keys=seed_external_group_keys(normalized_seeds or []),
    )
    context, topology = graph_ready_context, None
    if context is not None:
        topology = prepare_graph_ready_topology(context, unseeded)
        score_enabled = _graph_score_enabled(context.get("score_enabled", False))
        keys = (_graph_priority_key_map(context.get("graph_priority_key_by_op_id"), schedulable_ids=set(topology.schedulable_ids))
                if score_enabled else {})
        context = dict(context, score_enabled=score_enabled, graph_priority_key_by_op_id=keys,
                       **{_TOPOLOGY_FIELD: topology})
    records = list(operations) + list(normalized_batches.values())
    plain_classes = {kind: plain_record_class(kind) for kind in {type(value) for value in records}}
    from .dispatch.sgs_priority_pruning import prepare_pruning_record
    pruning_records = ({id(value): prepare_pruning_record(value, plain_classes) for value in records}
                       if context is not None else {})
    preparation = NativeSchedulePreparation(
        normalized_machine_downtimes=_normalize_machine_downtimes(machine_downtimes), calendar=calendar,
        run_context=ScheduleRunContext.from_legacy_scheduler(scheduler),
        operations=operations, records_by_token={id(value): value for value in records}, batches=normalized_batches, seed_results=normalized_seeds, seed_applications=tuple(seed_applications),
        seed_external_group_cache=external_seed_cache, seed_op_ids=seed_op_ids,
        unseeded_operations=unseeded, resource_pool=(dict(resource_pool, pair_rank=(dict(resource_pool["pair_rank"])
                                                                                         if isinstance(resource_pool.get("pair_rank"), dict)
                                                                                         else resource_pool.get("pair_rank", {})))
                                                   if isinstance(resource_pool, dict) else resource_pool), graph_ready_context=context,
        warnings=tuple(warnings), algo_stats=stats, topology=topology,
        plain_classes=plain_classes, pruning_records=pruning_records,
    )
    ctx = preparation.run_context
    from .dispatch.sgs import _native_score_functions_unchanged
    ctx.native_scoring = _native_score_functions_unchanged()
    native_dispatch = dispatch_certificate(scheduler, ctx, _NATIVE_SGS_SCHEDULER_GUARD, _NATIVE_SGS_CONTEXT_GUARD,
                                           internal_operation, _NATIVE_INTERNAL_OPERATION_FUNCTIONS)()
    ctx.checkpoint_dispatch_guard = lambda: native_dispatch
    preparation.score_cache_factory = make_sgs_score_cache_factory(
        ctx, scheduler, GreedyScheduler, preparation=preparation, probe=_SGS_AUTO_ASSIGN_PROBE,
    )
    return preparation


def _build_batch_order(
    batches: Dict[str, Any],
    params: Any,
    *,
    batch_order_override: Optional[List[str]],
    readiness_gate_enabled: bool,
    strict_mode: bool,
) -> Dict[str, int]:
    override_order = list(batch_order_override or [])
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
