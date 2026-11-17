"""贪心排产算法（Phase 7 / P7-02, P7-06）。

协调内部工序的设备、人员、工作日历与批次前后约束；外部工序按自然日推进，merged 组共享时间块。
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.algorithm_contracts.ordering import (
    clean_resource_id,
    operation_sort_key,
)
from core.algorithm_contracts.resource_occupancy import (
    PreparedSeedApplication,
    ResourceOccupancy,
    project_internal_occupancies,
)
from core.algorithm_contracts.resource_pool import ResourcePool
from core.algorithm_contracts.schedule_point_evidence import point_seed_valid
from core.algorithm_contracts.sort_strategies import StrategyFactory
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult, ScheduleSummary
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.algo_stats import make_algo_stats
from core.algorithm_runtime.resource_quality import initialize_resource_quality
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.seed_results import seed_external_group_keys, seed_resource_segments, seed_result_for_output
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse
from core.models.batch import Batch
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

from .dispatch.route import dispatch_run
from .dispatch.sgs_checkpoint import DecodeCheckpoint, DecodeCheckpointRequest, decode_input_signature
from .dispatch.sgs_graph import prepare_graph_ready_topology
from .dispatch.sgs_score_cache import SgsScoreCache
from .external_groups import rebuild_external_group_cache_from_seeds
from .run_context import ScheduleRunContext
from .run_state_setup import prepare_run_state, replay_resumed_demand, resume_run_state
from .schedule_params import ScheduleParams
from .schedule_preparation import NativeSchedulePreparation

__all__ = ["GreedyScheduler"]

_LOGGER = logging.getLogger(__name__)


class GreedyScheduler:
    """贪心排产算法：服务层注入日历与配置快照，经已准备好的输入解码。"""

    def __init__(self, calendar_service, config_service: ScheduleConfigSnapshot):
        self.calendar = calendar_service
        self.config = config_service
        # 本次解码的降级统计由调度器自己持有；每次解码开头重建，优化器与测试读取这里。
        self.last_algo_stats = make_algo_stats()

    def schedule_prepared(
        self, prepared_inputs: NativeSchedulePreparation, *, params: ScheduleParams, batch_order: Dict[str, int],
        operations: List[OpForScheduleAlgo], resource_pool: ResourcePool, graph_ready_context: Any,
        readiness_gate_enabled: bool, decode_resume: Optional[DecodeCheckpoint],
        decode_checkpoints: Optional[DecodeCheckpointRequest],
    ) -> Tuple[List[ScheduleResult], ScheduleSummary]:
        """Decode already prepared run facts; candidate arguments only supply changes."""
        self.last_algo_stats = algo_stats = make_algo_stats()
        t0 = datetime.now()
        for bucket, values in prepared_inputs.algo_stats.items():
            algo_stats[bucket].update(values)
        warnings = list(prepared_inputs.warnings)
        batches = prepared_inputs.batches
        machine_downtimes = prepared_inputs.normalized_machine_downtimes
        sorted_ops = sorted(operations, key=lambda op: operation_sort_key(op, batch_order))
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
                readiness_gate_enabled=readiness_gate_enabled,
            )
        initialize_resource_quality(state, sorted_ops, resource_pool, preparation=prepared_inputs)
        if decode_resume is not None:
            replay_resumed_demand(state)
        if decode_checkpoints is not None:
            assert checkpoint_signature is not None
            decode_checkpoints.arm(signature=checkpoint_signature, warnings=warnings)
        score_cache = (
            SgsScoreCache.for_preparation(prepared_inputs, state=state) if params.dispatch_mode_key == "sgs" else None
        )
        overlap_reuse = SlotOverlapReuse() if params.dispatch_mode_key == "sgs" else None
        ctx = ScheduleRunContext(
            native_preparation=prepared_inputs,
            algo_stats=algo_stats,
            sgs_score_cache=score_cache,
            overlap_reuse=overlap_reuse,
        )

        self._log_start(batches=batches, sorted_ops=sorted_ops, params=params)
        dispatch_run(
            ctx, state=state, sorted_ops=sorted_ops, batches=batches, batch_order=batch_order,
            params=params, machine_downtimes=machine_downtimes, resource_pool=resource_pool,
            graph_ready_context=graph_ready_context,
            decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
        )
        summary = _build_summary(state=state, warnings=warnings, sorted_ops=sorted_ops, duration=(datetime.now() - t0).total_seconds())
        _LOGGER.info(f"排产结束：成功={summary.scheduled_ops}/{summary.total_ops} 失败={summary.failed_ops} 耗时={summary.duration_seconds:.2f}s")
        return state.results, summary

    def _log_start(self, *, batches: Dict[str, Batch], sorted_ops: List[OpForScheduleAlgo], params: ScheduleParams) -> None:
        sorter = StrategyFactory.create(params.strategy, params.weights)
        extra = f" 派工=sgs({params.dispatch_rule_spec.token})" if params.dispatch_mode_key == "sgs" else ""
        _LOGGER.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}{extra}")


def _normalize_machine_downtimes(machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]]) -> Dict[str, List[Tuple[datetime, datetime]]]:
    if not machine_downtimes:
        return machine_downtimes
    return {
        resource_key: sorted(segments, key=lambda segment: (segment[0], segment[1]))
        for resource_id, segments in machine_downtimes.items()
        for resource_key in (clean_resource_id(resource_id),)
        if resource_key
    }


def prepare_native_schedule_inputs(
    machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]], *, scheduler: GreedyScheduler,
    operations: List[OpForScheduleAlgo], batches: Dict[str, Batch], required_hours_by_op_id: Mapping[int, float],
    seed_results: List[ScheduleResult], resource_pool: ResourcePool, graph_ready_context: Any,
) -> NativeSchedulePreparation:
    """``required_hours_by_op_id`` holds the run's standard hours of every internal operation it schedules.

    ``operations`` are the run's operations to schedule; its seeds are the held and completed operations, which the
    run input keeps apart from them and keys by operation ID, one seed per operation (``prepare_runtime_seeds``).
    """
    calendar = scheduler.calendar
    stats: Dict[str, Any] = make_algo_stats()
    warnings: List[str] = []
    seed_applications: List[PreparedSeedApplication] = []
    seed_occupancies_by_op_id: Dict[int, Tuple[ResourceOccupancy, ...]] = {}
    external_seed_cache = {}
    for seed in seed_results:
        occupies = seed.source == INTERNAL and not point_seed_valid(seed)
        occupancies = (
            project_internal_occupancies(seed, actual_segments=seed_resource_segments(seed) or ())
            if occupies
            else ()
        )
        output_result = seed_result_for_output(seed)
        seed_applications.append(PreparedSeedApplication(output_result, occupancies))
        seed_occupancies_by_op_id[output_result.op_id] = occupancies
    rebuild_external_group_cache_from_seeds(
        seed_results=seed_results, operations=operations, external_group_cache=external_seed_cache,
        warnings=warnings, algo_stats=stats, seed_group_keys=seed_external_group_keys(seed_results),
    )
    # Each decode request brings its own score switch and keys; only the static graph facts are compiled here.
    topology = None if graph_ready_context is None else prepare_graph_ready_topology(graph_ready_context, operations)
    records = list(operations) + list(batches.values())
    preparation = NativeSchedulePreparation(
        normalized_machine_downtimes=_normalize_machine_downtimes(machine_downtimes), calendar=calendar,
        operations=operations, records_by_token={id(value): value for value in records}, batches=batches,
        seed_results=seed_results, seed_applications=tuple(seed_applications),
        seed_occupancies_by_op_id=MappingProxyType(seed_occupancies_by_op_id),
        seed_external_group_cache=external_seed_cache, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context,
        warnings=tuple(warnings), algo_stats=stats, topology=topology,
    )
    grouped: Dict[str, List[OpForScheduleAlgo]] = {}
    for op in operations:
        grouped.setdefault(op.batch_id, []).append(op)
    # The average keeps its batch-then-sequence summation order.
    internal_samples: List[float] = []
    for batch_ops in grouped.values():
        for op in sorted(batch_ops, key=lambda item: (item.seq, item.id)):
            if op.source == INTERNAL:
                hours = required_hours_by_op_id[op.id]
                preparation.total_hours_by_op_id[op.id] = hours
                internal_samples.append(hours)
    if internal_samples:
        preparation.average_internal_proc_hours = sum(internal_samples) / len(internal_samples)
    return preparation


def build_batch_order(
    batches: Dict[str, Batch],
    params: ScheduleParams,
    *,
    batch_order_override: List[str],
    preparation: NativeSchedulePreparation,
) -> Dict[str, int]:
    if batch_order_override and len(batch_order_override) == len(batches):
        return {batch_id: index for index, batch_id in enumerate(batch_order_override)}
    sorted_batch_ids = preparation.batch_order(
        start_dt=params.base_time,
        strategy=params.strategy,
        weights=params.weights,
    )
    if not batch_order_override:
        return {batch_id: index for index, batch_id in enumerate(sorted_batch_ids)}
    # A partial override leads; its own copy is the working list the remaining sorted batches extend.
    override_order = list(batch_order_override)
    seen = set(override_order)
    override_order.extend([batch_id for batch_id in sorted_batch_ids if batch_id not in seen])
    return {batch_id: index for index, batch_id in enumerate(override_order)}


def _build_summary(*, state: ScheduleRunState, warnings: List[str], sorted_ops: List[OpForScheduleAlgo], duration: float) -> ScheduleSummary:
    total_ops = len(sorted_ops) + state.seed_count
    return ScheduleSummary(
        success=(state.failed_count == 0),
        total_ops=total_ops,
        scheduled_ops=state.scheduled_count,
        failed_ops=state.failed_count,
        warnings=warnings,
        errors=[],
        duration_seconds=duration,
        failure_details=list(state.failure_details),
    )
