from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithm_contracts.priority_constants import PRIORITY_WEIGHT, normalize_priority
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
)

from .v2_capacity import (
    FixedResourceBlockingFacts,
    bottleneck_on,
    residual_capacity_for_operation,
    residual_capacity_window_end,
    seed_results_by_resource_id,
)
from .workload import batch_ordering_workload_signals, build_work_buckets, operation_workload_signals

if TYPE_CHECKING:
    from core.algorithms.greedy.schedule_preparation import NativeSchedulePreparation

_NO_DUE_DEADLINE_HOURS = 1_000_000_000.0
_NO_DUE_CRITICAL_RATIO = math.inf
_NO_DUE_SACRIFICE_PENALTY = 2.0


def enrich_graph_ready_v2_metrics(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    operations: List[OpForScheduleAlgo],
    batches: Dict[str, Any],
    start_dt: datetime,
    calendar_service: Any,
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results: List[Any],
    resource_pool: Optional[Dict[str, Any]] = None,
    graph_ready_context: Dict[str, Any],
    deadline: float,
    clock: Callable[[], float],
    native_preparation: NativeSchedulePreparation,
) -> Optional[Dict[int, Dict[str, Any]]]:
    if clock() >= deadline:
        return None
    inputs = dict(batches=batches, start_dt=start_dt, calendar_service=calendar_service,
                  seed_results=seed_results, resource_pool=resource_pool,
                  graph_ready_context=graph_ready_context)
    inputs["prepared"] = _prepare_common_features(
        metrics_by_op_id, operations=operations, batches=batches, start_dt=start_dt,
        downtime_map=downtime_map, native_preparation=native_preparation)
    out = _enrich_feature_basis(
        feature_basis=SUCCESSOR_WORKLOAD_BASIS, deadline=deadline, clock=clock, **inputs
    )
    if out is None:
        return None
    baseline = _enrich_feature_basis(
        feature_basis=BATCH_WORKLOAD_BASIS, deadline=deadline, clock=clock, **inputs
    )
    if baseline is None:
        return None
    for op_id, row in out.items():
        row[BASELINE_ORDERING_FIELD] = baseline[op_id]
    return out


def _prepare_common_features(metrics, *, operations, batches, start_dt, downtime_map,
                             native_preparation: NativeSchedulePreparation):
    op_by_id = {op.id: op for op in operations}
    batch_by_op_id = {op_id: batches[op_by_id[op_id].batch_id] for op_id in metrics}
    durations = {
        op_id: _operation_hours(op_by_id[op_id], total_hours_by_op_id=native_preparation.total_hours_by_op_id)
        for op_id in metrics
    }
    due_dates = native_preparation.parsed_due_dates()
    ready_starts = native_preparation.parsed_ready_starts()
    due_exclusive_by_batch: Dict[str, Optional[datetime]] = {}
    due_hours_by_batch: Dict[str, float] = {}
    priority_weight_by_batch: Dict[str, float] = {}
    for op_id, batch in batch_by_op_id.items():
        batch_id = op_by_id[op_id].batch_id
        if batch_id not in due_exclusive_by_batch:
            due_day = due_dates[batch_id]
            due = None if due_day is None else due_exclusive(due_day)
            due_exclusive_by_batch[batch_id] = due
            due_hours_by_batch[batch_id] = (
                _NO_DUE_DEADLINE_HOURS if due is None else _deadline_hours(start_dt=start_dt, due_exclusive=due)
            )
            priority_weight_by_batch[batch_id] = PRIORITY_WEIGHT[normalize_priority(batch.priority)]
    family_ids = sorted({op_by_id[op_id].op_type_id for op_id in metrics})
    family_ranks = {type_id: index for index, type_id in enumerate(family_ids)}
    processing_ranks = _processing_time_ranks(durations)
    base_row_by_op_id: Dict[int, Dict[str, Any]] = {}
    for op_id, metric in metrics.items():
        op = op_by_id[op_id]
        batch_id = op.batch_id
        priority_weight = priority_weight_by_batch[batch_id]
        base_row = dict(metric)
        base_row.update(
            {
                "priority_weight": float(priority_weight),
                "due_deadline_hours": float(due_hours_by_batch[batch_id]),
                "weighted_processing_hours": float(durations[op_id] / priority_weight),
                "changeover_family_rank": family_ranks[op.op_type_id],
                "processing_time_rank": float(processing_ranks[op_id]),
            }
        )
        base_row_by_op_id[op_id] = base_row
    resource_seeds = seed_results_by_resource_id(native_preparation.seed_applications)
    return {
        "operations": op_by_id,
        "metrics": metrics,
        "durations": durations,
        "batch_by_op_id": batch_by_op_id,
        "priority_weight_by_op_id": {
            op_id: priority_weight_by_batch[op_by_id[op_id].batch_id]
            for op_id in batch_by_op_id
        },
        "bottleneck_score_by_op_id": {
            op_id: float(metric["bottleneck_machine_score"]) for op_id, metric in metrics.items()
        },
        "due_exclusive_by_op_id": {
            op_id: due_exclusive_by_batch[op_by_id[op_id].batch_id]
            for op_id in batch_by_op_id
        },
        "base_row_by_op_id": base_row_by_op_id,
        "resource_blocking": FixedResourceBlockingFacts(
            downtime_map=downtime_map, seed_results_by_resource_id=resource_seeds),
        "capacity_by_window": {},
        "work_buckets": build_work_buckets(op_by_id, durations),
        "ready_starts": ready_starts,
    }


def _enrich_feature_basis(*, batches, start_dt, calendar_service,
                          seed_results, resource_pool,
                          graph_ready_context, feature_basis, prepared,
                          deadline: float,
                          clock: Callable[[], float]):
    if clock() >= deadline:
        return None
    op_by_id, metrics_by_op_id, duration_by_op_id = prepared["operations"], prepared["metrics"], prepared["durations"]
    out: Dict[int, Dict[str, Any]] = {}
    signals = _workload_signals(
        feature_basis, op_by_id, duration_by_op_id, batches=batches, start_dt=start_dt,
        graph_ready_context=graph_ready_context, seed_results=seed_results, calendar_service=calendar_service,
        work_buckets=prepared["work_buckets"], ready_starts=prepared["ready_starts"],
        deadline=deadline, clock=clock)
    if signals is None:
        return None
    remaining_by_op_id, ready_offset_hours_by_op_id = signals
    base_row_by_op_id = prepared["base_row_by_op_id"]
    capacity_by_window = prepared["capacity_by_window"]
    for op_id in metrics_by_op_id:
        if clock() >= deadline:
            return None
        remaining_hours = remaining_by_op_id[op_id]
        priority_weight = prepared["priority_weight_by_op_id"][op_id]
        parsed_due_exclusive = prepared["due_exclusive_by_op_id"][op_id]
        if parsed_due_exclusive is None:
            due_budget_hours = _NO_DUE_DEADLINE_HOURS
            slack_hours = float(_NO_DUE_DEADLINE_HOURS - remaining_hours)
            due_pressure = 0.0
            saveability = 0.0
            sacrifice_penalty = _NO_DUE_SACRIFICE_PENALTY
            critical_ratio = _NO_DUE_CRITICAL_RATIO
            bottleneck_due_gate = 0.0
        else:
            op = op_by_id[op_id]
            batch = prepared["batch_by_op_id"][op_id]
            bottleneck_score = prepared["bottleneck_score_by_op_id"][op_id]
            capacity_start_dt = start_dt + timedelta(hours=float(ready_offset_hours_by_op_id[op_id]))
            window_end = residual_capacity_window_end(
                start_dt=capacity_start_dt,
                due_exclusive=parsed_due_exclusive,
            )
            window_key = (
                op.source,
                op.machine_id,
                op.operator_id,
                op.op_type_id,
                batch.priority,
                capacity_start_dt,
                window_end,
            )
            if window_key not in capacity_by_window:
                capacity_by_window[window_key] = residual_capacity_for_operation(
                    op,
                    batch=batch,
                    start_dt=capacity_start_dt,
                    window_end=window_end,
                    calendar_service=calendar_service,
                    resource_pool=resource_pool,
                    prepared=prepared["resource_blocking"],
                )
            capacity = capacity_by_window[window_key]
            due_budget_hours = _deadline_budget_hours(
                op,
                due_wall_hours=_ordering_deadline_hours(feature_basis, start_dt, capacity_start_dt, parsed_due_exclusive),
                capacity=capacity,
            )
            slack_hours = float(due_budget_hours - remaining_hours)
            due_pressure = _due_pressure(due_hours=due_budget_hours, remaining_hours=remaining_hours)
            saveability = _saveability(due_hours=due_budget_hours, remaining_hours=remaining_hours)
            sacrifice_penalty = _sacrifice_penalty(
                due_hours=due_budget_hours,
                remaining_hours=remaining_hours,
                saveability=saveability,
            )
            critical_ratio = _critical_ratio(due_hours=due_budget_hours, remaining_hours=remaining_hours)
            bottleneck_score_with_capacity = bottleneck_on(
                bottleneck_score=bottleneck_score,
                residual_capacity_pressure=capacity["residual_capacity_pressure"],
                machine_count=int(capacity["bottleneck_machine_count"]),
            )
            bottleneck_due_gate = float(bottleneck_score_with_capacity * due_pressure * saveability)
        row = dict(base_row_by_op_id[op_id])
        row.update(
            {
                "due_budget_hours": float(due_budget_hours),
                "due_pressure": float(due_pressure),
                "slack_hours": float(slack_hours),
                "remaining_due_burden_hours": float(remaining_hours),
                "weighted_due_pressure": float(due_pressure * priority_weight),
                "saveability": float(saveability),
                "sacrifice_penalty": float(sacrifice_penalty),
                "critical_ratio": float(critical_ratio),
                "bottleneck_due_gate": float(bottleneck_due_gate),
                "graph_ready_workload_version": feature_basis,
            }
        )
        out[int(op_id)] = row
    return out


def _ordering_deadline_hours(basis, start_dt, capacity_start_dt, due_exclusive):
    return _deadline_hours(start_dt=start_dt if basis == BATCH_WORKLOAD_BASIS else capacity_start_dt,
                           due_exclusive=due_exclusive)


def _workload_signals(
    basis, operations, durations, *, work_buckets,
    deadline: float, clock: Callable[[], float], **kwargs,
):
    if clock() >= deadline:
        return None
    if basis == BATCH_WORKLOAD_BASIS:
        return batch_ordering_workload_signals(operations, durations, work_buckets=work_buckets)
    if basis != SUCCESSOR_WORKLOAD_BASIS:
        raise ValidationError("GraphReady 候选特征语义不支持。", field="graph_ready_v2_features")
    return operation_workload_signals(
        operations, work_buckets=work_buckets, deadline=deadline, clock=clock, **kwargs
    )


def _operation_hours(op: OpForScheduleAlgo, *, total_hours_by_op_id: Dict[int, float]) -> float:
    if op.source == EXTERNAL:
        return _external_operation_hours(op)
    # 单一真相源：自制工序总工时由本次排产的原生准备（prepare_native_schedule_inputs）按
    # internal_slot.require_internal_hours 为每道未落位自制工序算好一次（分件工序按件数量），
    # 已保证有限且非负——quantity==0 合法（总量=setup）、总工时 0 合法，坏工时在那里按字段报错。
    return total_hours_by_op_id[op.id]


def _external_operation_hours(op: OpForScheduleAlgo) -> float:
    # 排产输入构建已保证外协周期为正有限数，合并外协组必带组身份。
    if op.ext_merge_mode == MERGED:
        return float(cast(float, op.ext_group_total_days)) * 24.0
    return float(cast(float, op.ext_days)) * 24.0


def _deadline_hours(*, start_dt: datetime, due_exclusive: datetime) -> float:
    return float((due_exclusive - start_dt).total_seconds() / 3600.0)


def _deadline_budget_hours(
    op: Any,
    *,
    due_wall_hours: float,
    capacity: Dict[str, Any],
) -> float:
    if due_wall_hours <= 0.0:
        return float(due_wall_hours)
    if op.source == EXTERNAL:
        return float(due_wall_hours)
    # The production calendar is always present (scheduler.calendar), so a candidate machine decides the budget.
    if int(capacity["candidate_machine_count"]) > 0:
        return float(capacity["residual_capacity_window_hours"])
    return float(due_wall_hours)


def _due_pressure(*, due_hours: float, remaining_hours: float) -> float:
    # due_hours<=0 表示已过交期:按逾期小时折算成天(/24.0)给递增压力,封顶 +10.0,避免极端逾期吞没其它特征。
    if due_hours <= 0.0:
        return 1.0 + min(abs(due_hours) / 24.0, 10.0)
    return max(0.0, min(1.0, remaining_hours / due_hours))


def _saveability(*, due_hours: float, remaining_hours: float) -> float:
    if due_hours <= 0.0:
        return 0.0
    if remaining_hours <= 0.0:
        return 1.0
    return min(1.0, due_hours / remaining_hours)


def _critical_ratio(*, due_hours: float, remaining_hours: float) -> float:
    if remaining_hours <= 0.0:
        if due_hours < 0.0:
            return -math.inf
        if due_hours == 0.0:
            return 0.0
        return sys.float_info.max
    return due_hours / remaining_hours


def _sacrifice_penalty(*, due_hours: float, remaining_hours: float, saveability: float) -> float:
    if due_hours <= 0.0:
        return 1.0
    # 长尾启发阈值:剩余工时达交期窗口 70% 以上视为难救长尾,叠加一档牺牲惩罚;0.70 为经验值,可随基准调参。
    long_tail_penalty = 1.0 if remaining_hours >= due_hours * 0.70 else 0.0
    return float(long_tail_penalty + max(0.0, 1.0 - saveability))


def _processing_time_ranks(duration_by_op_id: Dict[int, float]) -> Dict[int, int]:
    ordered = sorted(duration_by_op_id.items(), key=lambda item: (item[1], item[0]))
    return {op_id: index for index, (op_id, _hours) in enumerate(ordered)}


__all__ = ["enrich_graph_ready_v2_metrics"]
