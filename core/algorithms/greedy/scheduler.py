from __future__ import annotations

"""贪心排产算法（Phase 7 / P7-02, P7-06）。

协调内部工序的设备、人员、工作日历与批次前后约束；外部工序按自然日推进，merged 组共享时间块。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.ordering import (
    build_batch_sort_inputs,
    build_normalized_batches_map,
    normalize_text_id,
    operation_sort_key,
)
from core.algorithm_contracts.sort_strategies import SortStrategy, StrategyFactory
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult, ScheduleSummary
from core.algorithm_runtime.algo_stats import increment_counter, make_algo_stats
from core.algorithm_runtime.resource_quality import initialize_resource_quality
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy.dispatch.batch_order import dispatch_batch_order
from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
from core.models.batch import Batch
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

from .auto_assign import auto_assign_internal_resources_attempt
from .dispatch.route import dispatch_run
from .dispatch.sgs_checkpoint import DecodeCheckpoint, DecodeCheckpointRequest, decode_input_signature
from .dispatch.sgs_score_cache import (
    attach_sgs_score_cache,
    make_sgs_score_cache_factory,
)
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation
from .run_context import ScheduleRunContext
from .run_state_setup import prepare_run_state, replay_resumed_demand, resume_run_state
from .schedule_params import ScheduleParams
from .schedule_preparation import NativeSchedulePreparation
from .seed import normalize_seed_results

__all__ = ["GreedyScheduler"]

_LOGGER = logging.getLogger(__name__)


class GreedyScheduler:
    """贪心排产算法：服务层注入日历与配置快照，经已准备好的输入解码。"""

    # 只在 schedule_prepared 解码期间存在；派工回调读取本次解码的准备结果。
    _active_preparation: NativeSchedulePreparation

    def __init__(self, calendar_service, config_service: ScheduleConfigSnapshot):
        self.calendar = calendar_service
        self.config = config_service
        # 本次解码的降级统计由调度器自己持有；每次解码开头重建，优化器与测试读取这里。
        self.last_algo_stats = make_algo_stats()
        self._decode_invocations = 0

    def schedule_prepared(
        self, prepared_inputs: NativeSchedulePreparation, *, params: ScheduleParams, batch_order: Dict[str, int],
        operations: List[OpForScheduleAlgo], resource_pool: Any, graph_ready_context: Any,
        readiness_gate_enabled: bool, decode_resume: Optional[DecodeCheckpoint],
        decode_checkpoints: Optional[DecodeCheckpointRequest],
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        """Decode already prepared run facts; candidate arguments only supply changes."""
        self._decode_invocations += 1
        self.last_algo_stats = algo_stats = make_algo_stats()
        t0 = datetime.now()
        self._active_preparation = prepared_inputs
        for bucket, values in prepared_inputs.algo_stats.items():
            algo_stats[bucket].update(values)
        warnings = list(params.warnings) + list(prepared_inputs.warnings)
        batches = prepared_inputs.batches
        machine_downtimes = prepared_inputs.normalized_machine_downtimes
        if operations is prepared_inputs.operations:
            unseeded = prepared_inputs.unseeded_operations
        else:
            unseeded, _ = _drop_seeded_operations(operations, prepared_inputs.seed_op_ids)
        sorted_ops = sorted(unseeded, key=lambda op: operation_sort_key(op, batch_order))
        checkpoint_signature = None
        if decode_resume is not None or decode_checkpoints is not None:
            checkpoint_signature = decode_input_signature(
                operations=sorted_ops, batch_order=batch_order, params=params, resource_pool=resource_pool,
                graph_ready_context=graph_ready_context, readiness_gate_enabled=readiness_gate_enabled,
                warnings=warnings, prepared_inputs=prepared_inputs)
        if decode_resume is not None:
            # Resumed decode: the checkpoint already holds seeds, readiness progress and the prefix picks.
            assert checkpoint_signature is not None
            state = resume_run_state(decode_resume, signature=checkpoint_signature, warnings=warnings,
                                     dispatch_mode_key=params.dispatch_mode_key, graph_ready_context=graph_ready_context)
        else:
            state = prepare_run_state(
                prepared_inputs=prepared_inputs,
                params=params,
                warnings=warnings,
                algo_stats=algo_stats,
                readiness_gate_enabled=readiness_gate_enabled,
            )
        ctx = prepared_inputs.run_context
        ctx.sgs_score_cache = None
        ctx.algo_stats = algo_stats
        initialize_resource_quality(state, sorted_ops, resource_pool, preparation=prepared_inputs)
        if decode_resume is not None:
            replay_resumed_demand(state)
        if decode_checkpoints is not None:
            assert checkpoint_signature is not None
            decode_checkpoints.arm(signature=checkpoint_signature, warnings=warnings)
        attach_sgs_score_cache(ctx, state=state, params=params, resource_pool=resource_pool)

        self._log_start(batches=batches, sorted_ops=sorted_ops, params=params)
        dispatch_run(
            ctx, state=state, sorted_ops=sorted_ops, batches=batches, batch_order=batch_order,
            params=params, machine_downtimes=machine_downtimes, resource_pool=resource_pool,
            graph_ready_context=graph_ready_context,
            batch_dispatch=dispatch_batch_order, sgs_dispatch=dispatch_sgs,
            decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
        )
        summary = _build_summary(state=state, warnings=warnings, sorted_ops=sorted_ops, duration=(datetime.now() - t0).total_seconds())
        _LOGGER.info(f"排产结束：成功={summary.scheduled_ops}/{summary.total_ops} 失败={summary.failed_ops} 耗时={summary.duration_seconds:.2f}s")
        return state.results, summary, params.strategy, params.used_params

    def _log_start(self, *, batches: Dict[str, Batch], sorted_ops: List[OpForScheduleAlgo], params: ScheduleParams) -> None:
        sorter = StrategyFactory.create(params.strategy, **params.used_params)
        extra = f" 派工=sgs({params.dispatch_rule_spec.token})" if params.dispatch_mode_key == "sgs" else ""
        _LOGGER.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}{extra}")

    def _schedule_external(
        self,
        op: OpForScheduleAlgo,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
    ) -> Tuple[Optional[ScheduleResult], bool]:
        return schedule_external(
            calendar=self.calendar,
            op=op,
            batch_progress=batch_progress,
            external_group_cache=external_group_cache,
            base_time=base_time,
            errors=errors,
            end_dt_exclusive=end_dt_exclusive,
        )

    def _schedule_internal(
        self,
        op: OpForScheduleAlgo,
        batch: Batch,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]],
        *,
        auto_assign_enabled: bool,
        resource_pool: Optional[Dict[str, Any]],
        last_op_type_by_machine: Dict[str, str],
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
    ) -> Tuple[Optional[ScheduleResult], bool]:
        return schedule_internal_operation(
            calendar=self.calendar,
            algo_stats=self.last_algo_stats,
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
            total_hours_by_op_id=self._active_preparation.total_hours_by_op_id,
        )

    def _auto_assign_internal_resources_attempt(
        self,
        *,
        op: OpForScheduleAlgo,
        batch: Batch,
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
        preparation = self._active_preparation
        return auto_assign_internal_resources_attempt(
            calendar=self.calendar,
            algo_stats=self.last_algo_stats,
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
            resource_preparation=preparation,
        )


def _normalize_machine_downtimes(machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]]) -> Dict[str, List[Tuple[datetime, datetime]]]:
    if not machine_downtimes:
        return machine_downtimes
    return {
        normalize_text_id(resource_id): sorted(segments, key=lambda segment: (segment[0], segment[1]))
        for resource_id, segments in machine_downtimes.items()
        if normalize_text_id(resource_id)
    }


def prepare_native_schedule_inputs(
    machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]], *, scheduler: GreedyScheduler,
    operations: List[OpForScheduleAlgo], batches: Dict[str, Batch], seed_results: List[ScheduleResult],
    resource_pool: Any, graph_ready_context: Any,
) -> NativeSchedulePreparation:
    from .dispatch.sgs_graph import (
        TOPOLOGY_FIELD,
        graph_priority_key_map,
        graph_score_enabled,
        prepare_graph_ready_topology,
    )

    calendar = scheduler.calendar
    stats: Dict[str, Any] = make_algo_stats()
    normalized_batches = build_normalized_batches_map(batches)
    normalized_seeds, seed_op_ids, warnings = normalize_seed_results(seed_results=seed_results, algo_stats=stats)
    unseeded = operations
    if seed_op_ids:
        unseeded, dropped = _drop_seeded_operations(unseeded, seed_op_ids)
        if dropped:
            warnings.append(f"检测到 seed_results 与 operations 重叠：已过滤 {dropped} 道工序避免重复排产。")
            increment_counter(stats, "seed_overlap_filtered_count", dropped)
    from core.algorithm_contracts.schedule_point_evidence import point_seed_valid
    from core.algorithm_contracts.value_domains import INTERNAL

    from .external_groups import rebuild_external_group_cache_from_seeds
    from .seed import seed_external_group_keys, seed_resource_segments, seed_result_for_output

    seed_applications, external_seed_cache = [], {}
    for seed in normalized_seeds:
        occupies = seed.source == INTERNAL and not point_seed_valid(seed)
        seed_applications.append((seed_result_for_output(seed), normalize_text_id(seed.machine_id) if occupies else "",
                                  normalize_text_id(seed.operator_id) if occupies else "",
                                  seed_resource_segments(seed) if occupies else None))
    rebuild_external_group_cache_from_seeds(
        seed_results=normalized_seeds, operations=operations, external_group_cache=external_seed_cache,
        warnings=warnings, algo_stats=stats, seed_group_keys=seed_external_group_keys(normalized_seeds),
    )
    context, topology = graph_ready_context, None
    if context is not None:
        topology = prepare_graph_ready_topology(context, unseeded)
        score_enabled = graph_score_enabled(context.get("score_enabled", False))
        keys = (graph_priority_key_map(context.get("graph_priority_key_by_op_id"), schedulable_ids=set(topology.schedulable_ids))
                if score_enabled else {})
        context = dict(context, score_enabled=score_enabled, graph_priority_key_by_op_id=keys,
                       **{TOPOLOGY_FIELD: topology})
    records = list(operations) + list(normalized_batches.values())
    preparation = NativeSchedulePreparation(
        normalized_machine_downtimes=_normalize_machine_downtimes(machine_downtimes), calendar=calendar,
        operations=operations, records_by_token={id(value): value for value in records}, batches=normalized_batches, seed_results=normalized_seeds, seed_applications=tuple(seed_applications),
        seed_external_group_cache=external_seed_cache, seed_op_ids=seed_op_ids,
        unseeded_operations=unseeded, resource_pool=resource_pool, graph_ready_context=context,
        warnings=tuple(warnings), algo_stats=stats, topology=topology,
    )
    ctx = preparation.run_context = ScheduleRunContext.from_legacy_scheduler(scheduler, preparation)
    preparation.score_cache_factory = make_sgs_score_cache_factory(ctx, preparation=preparation)
    return preparation


def build_batch_order(
    batches: Dict[str, Batch],
    params: ScheduleParams,
    *,
    batch_order_override: List[str],
) -> Dict[str, int]:
    override_order = list(batch_order_override)
    if override_order and len(override_order) == len(batches):
        return {batch_id: index for index, batch_id in enumerate(override_order)}
    batch_for_sort = build_batch_sort_inputs(
        batches,
        strategy=params.strategy,
    )
    sorted_batches = StrategyFactory.create(params.strategy, **params.used_params).sort(batch_for_sort, base_date=params.base_time.date())
    if not override_order:
        return {batch.batch_id: index for index, batch in enumerate(sorted_batches)}
    seen = set(override_order)
    override_order.extend([batch.batch_id for batch in sorted_batches if batch.batch_id not in seen])
    return {batch_id: index for index, batch_id in enumerate(override_order)}


def _drop_seeded_operations(operations: List[OpForScheduleAlgo], seed_op_ids: Set[int]) -> Tuple[List[OpForScheduleAlgo], int]:
    filtered = [op for op in operations if op.id not in seed_op_ids]
    return filtered, len(operations) - len(filtered)


def _build_summary(*, state: ScheduleRunState, warnings: List[str], sorted_ops: List[OpForScheduleAlgo], duration: float) -> ScheduleSummary:
    total_ops = len(sorted_ops) + state.seed_count
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
