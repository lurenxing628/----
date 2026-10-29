from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithm_contracts.date_parsers import parse_date
from core.algorithm_contracts.priority_constants import PRIORITY_WEIGHT, normalize_priority
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.algorithm_runtime.piece_input import operation_batch
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BASELINE_ORDERING_FIELD,
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
)

from .v2_capacity import (
    FixedResourceBlockingFacts,
    bottleneck_on,
    non_negative_float,
    residual_capacity_for_operation,
    residual_capacity_window_end,
    seed_results_by_resource_id,
)
from .workload import batch_ordering_workload_signals, build_work_buckets, operation_workload_signals

_NO_DUE_DEADLINE_HOURS = 1_000_000_000.0
_NO_DUE_CRITICAL_RATIO = 1_000_000_000.0
_NO_DUE_SACRIFICE_PENALTY = 2.0

# 真零工时自制工序（total==0：setup=unit=0，或 quantity=0 且 setup=0）在系统口径下合法
# （见 _operation_hours 内注释），但 duration 类特征有两条恒>0 的承重合同：
# 1) _critical_ratio/_saveability 依赖 remaining_hours>0 做除零安全（见 _critical_ratio 注释）；
# 2) 下游公式层 optimizer_graph_ready_candidates._required_positive_metric 要求
#    remaining_due_burden_hours 恒>0（既有合同测试锁死）。
# 取舍：在「从 duration 聚合剔除」与「按文档化最小 epsilon 计入」里选后者——剔除会让全零批次的
# remaining_hours==0，既打破除零安全承重合同又被下游 >0 合同拒绝；epsilon 计入则保住
# remaining_hours >= epsilon > 0 的不变量。除零安全论证：critical_ratio=due_budget/remaining
# <= due_budget/epsilon，due_budget 为有限墙钟/日历窗口小时数，比值恒为有限 float；
# 无交期路径走占位常量不做除法。epsilon=1e-6 小时（3.6 毫秒）远低于任何真实工时录入粒度，
# 不会翻转非零工序间的任何特征排序。计入时按 op 留痕（_duration_by_op_id_with_zero_total_trace）。
_ZERO_TOTAL_DURATION_EPSILON_HOURS = 1e-6

_LOGGER = logging.getLogger(__name__)


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
) -> Optional[Dict[int, Dict[str, Any]]]:
    if clock() >= deadline:
        return None
    inputs = dict(batches=batches, start_dt=start_dt, calendar_service=calendar_service,
                  seed_results=seed_results, resource_pool=resource_pool,
                  graph_ready_context=graph_ready_context)
    inputs["prepared"] = _prepare_common_features(
        metrics_by_op_id, operations=operations, batches=batches, start_dt=start_dt,
        seed_results=seed_results, downtime_map=downtime_map)
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


def _prepare_common_features(metrics, *, operations, batches, start_dt, seed_results, downtime_map):
    op_by_id = {op.id: op for op in operations}
    if set(metrics).difference(op_by_id):
        raise ValidationError("GraphReady v2 特征缺少对应工序。", field="graph_ready_v2_features")
    durations = _duration_by_op_id_with_zero_total_trace(op_by_id, batches=batches)
    durations = {op_id: durations[op_id] for op_id in metrics}
    batch_by_op_id = {op_id: _batch_for_operation(op_by_id[op_id], batches=batches) for op_id in metrics}
    due_exclusive_by_batch: Dict[int, Optional[datetime]] = {}
    due_hours_by_batch: Dict[int, float] = {}
    priority_weight_by_batch: Dict[int, float] = {}
    for batch in batch_by_op_id.values():
        batch_key = id(batch)
        if batch_key not in due_exclusive_by_batch:
            due = _due_exclusive_datetime(batch)
            due_exclusive_by_batch[batch_key] = due
            due_hours_by_batch[batch_key] = (
                _NO_DUE_DEADLINE_HOURS if due is None else _deadline_hours(start_dt=start_dt, due_exclusive=due)
            )
            priority_weight_by_batch[batch_key] = PRIORITY_WEIGHT[normalize_priority(batch.priority)]
    family_ids = sorted({op_by_id[op_id].op_type_id for op_id in metrics})
    family_ranks = {type_id: index for index, type_id in enumerate(family_ids)}
    processing_ranks = _processing_time_ranks(durations)
    base_row_by_op_id: Dict[int, Dict[str, Any]] = {}
    for op_id, metric in metrics.items():
        op = op_by_id[op_id]
        batch_key = id(batch_by_op_id[op_id])
        priority_weight = priority_weight_by_batch[batch_key]
        base_row = dict(metric)
        base_row.update(
            {
                "due_deadline_hours": float(due_hours_by_batch[batch_key]),
                "weighted_processing_hours": float(durations[op_id] / priority_weight),
                "changeover_family_rank": family_ranks[op.op_type_id],
                "processing_time_rank": float(processing_ranks[op_id]),
            }
        )
        base_row_by_op_id[op_id] = base_row
    resource_seeds = seed_results_by_resource_id(seed_results)
    return {
        "operations": op_by_id,
        "metrics": metrics,
        "durations": durations,
        "batch_by_op_id": batch_by_op_id,
        "priority_weight_by_op_id": {
            op_id: priority_weight_by_batch[id(batch)]
            for op_id, batch in batch_by_op_id.items()
        },
        "bottleneck_score_by_op_id": {
            op_id: _required_non_negative(metric, field="bottleneck_machine_score") for op_id, metric in metrics.items()
        },
        "due_exclusive_by_op_id": {
            op_id: due_exclusive_by_batch[id(batch)]
            for op_id, batch in batch_by_op_id.items()
        },
        "base_row_by_op_id": base_row_by_op_id,
        "resource_blocking": FixedResourceBlockingFacts(
            downtime_map=downtime_map, seed_results_by_resource_id=resource_seeds),
        "capacity_by_window": {},
        "work_buckets": build_work_buckets(op_by_id, durations),
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
        work_buckets=prepared["work_buckets"], deadline=deadline, clock=clock)
    if signals is None:
        return None
    remaining_by_op_id, ready_offset_hours_by_op_id = signals
    base_row_by_op_id = prepared["base_row_by_op_id"]
    capacity_by_window = prepared["capacity_by_window"]
    for op_id in metrics_by_op_id:
        if clock() >= deadline:
            return None
        op = op_by_id[op_id]
        batch = prepared["batch_by_op_id"][op_id]
        remaining_hours = remaining_by_op_id[op_id]
        priority_weight = prepared["priority_weight_by_op_id"][op_id]
        bottleneck_score = prepared["bottleneck_score_by_op_id"][op_id]
        capacity_start_dt = start_dt + timedelta(hours=float(ready_offset_hours_by_op_id[op_id]))
        parsed_due_exclusive = prepared["due_exclusive_by_op_id"][op_id]
        capacity_window_end = residual_capacity_window_end(
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
            capacity_window_end,
        )
        if window_key not in capacity_by_window:
            capacity_by_window[window_key] = residual_capacity_for_operation(
                op,
                batch=batch,
                start_dt=capacity_start_dt,
                due_exclusive=capacity_window_end,
                calendar_service=calendar_service,
                resource_pool=resource_pool,
                prepared=prepared["resource_blocking"],
            )
        capacity = capacity_by_window[window_key]
        due_unavailable = parsed_due_exclusive is None
        if due_unavailable:
            due_budget_hours = _NO_DUE_DEADLINE_HOURS
            slack_hours = float(_NO_DUE_DEADLINE_HOURS - remaining_hours)
            due_pressure = 0.0
            saveability = 0.0
            sacrifice_penalty = _NO_DUE_SACRIFICE_PENALTY
            critical_ratio = _NO_DUE_CRITICAL_RATIO
        else:
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
                "residual_capacity_hours": float(capacity["residual_capacity_hours"]),
                "residual_capacity_window_hours": float(capacity["residual_capacity_window_hours"]),
                "residual_capacity_blocked_hours": float(capacity["residual_capacity_blocked_hours"]),
                "residual_capacity_start_offset_hours": float(ready_offset_hours_by_op_id[op_id]),
                "bottleneck_due_gate": float(bottleneck_score_with_capacity * due_pressure * saveability),
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


def _duration_by_op_id_with_zero_total_trace(
    op_by_id: Dict[int, Any],
    *,
    batches: Dict[str, Any],
) -> Dict[int, float]:
    duration_by_op_id: Dict[int, float] = {}
    zero_total_op_ids: List[int] = []
    for op_id, op in op_by_id.items():
        total = non_negative_float(_operation_hours(op, batches=batches), field="operation.total_hours")
        if total <= 0.0:
            # 真零工时工序：按文档化 epsilon 计入并留痕，取舍与除零安全论证见
            # _ZERO_TOTAL_DURATION_EPSILON_HOURS 常量注释。
            zero_total_op_ids.append(int(op_id))
            total = _ZERO_TOTAL_DURATION_EPSILON_HOURS
        duration_by_op_id[op_id] = float(total)
    if zero_total_op_ids:
        _LOGGER.warning(
            "GraphReady v2 特征遇到 %d 个总工时为 0 的自制工序，按最小 epsilon=%.0e 小时计入 duration 特征"
            "（zero_total_op_ids 样本=%s）。",
            len(zero_total_op_ids),
            _ZERO_TOTAL_DURATION_EPSILON_HOURS,
            sorted(zero_total_op_ids)[:20],
        )
    return duration_by_op_id


def _operation_hours(op: Any, *, batches: Dict[str, Any]) -> float:
    batch = operation_batch(op, _batch_for_operation(op, batches=batches))
    if op.source == EXTERNAL:
        return float(_external_operation_hours(op))
    # 单一真相源：total=setup+unit*quantity 与 core/algorithm_runtime/internal_slot.validate_internal_hours
    # 同口径——quantity==0 合法（总量=setup）、总工时 0 合法，不复辟 quantity>0 / total>0 硬闸
    # （系统口径见 schedule_input_runtime_support._ensure_internal_runtime_hours 护栏注释与回归测试
    # test_ensure_internal_runtime_hours_allows_zero_quantity）。缺失/非数字/非有限/负数已由 validate_internal_hours
    # 按坏输入报错（对 None 同样报错，不补 0）；这里逐字段检查只为给出带字段名的
    # graph_ready_v2_features 错误。total==0 的处理见 _duration_by_op_id_with_zero_total_trace。
    quantity = non_negative_float(batch.quantity, field="batch.quantity")
    setup = non_negative_float(op.setup_hours, field="operation.setup_hours")
    unit = non_negative_float(op.unit_hours, field="operation.unit_hours")
    return float(setup + unit * quantity)


def _external_operation_hours(op: OpForScheduleAlgo) -> float:
    # 排产输入构建保证合并外协组必带组身份。
    if op.ext_merge_mode == MERGED:
        return _positive_float(op.ext_group_total_days, field="operation.ext_group_total_days") * 24.0
    return _positive_float(op.ext_days, field="operation.ext_days") * 24.0


def _batch_for_operation(op: OpForScheduleAlgo, *, batches: Dict[str, Any]) -> Any:
    if op.batch_id not in batches:
        raise ValidationError("GraphReady v2 特征找不到工序批次。", field="graph_ready_v2_features")
    return batches[op.batch_id]


def _due_exclusive_datetime(batch: Any) -> Optional[datetime]:
    due_day = _parse_due_day(batch.due_date)
    if due_day is None:
        return None
    return datetime.combine(due_day + timedelta(days=1), time.min)


def _deadline_hours(*, start_dt: datetime, due_exclusive: datetime) -> float:
    return float((due_exclusive - start_dt).total_seconds() / 3600.0)


def _parse_due_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is None:
        raise ValidationError(
            "GraphReady v2 特征要求批次交期格式必须是 YYYY-MM-DD。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_v2_bad_due_date"},
        )
    return parsed


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
    return max(0.0, min(1.0, due_hours / remaining_hours))


def _critical_ratio(*, due_hours: float, remaining_hours: float) -> float:
    # remaining_hours 由 _duration_by_op_id_with_zero_total_trace 汇总:正常工序 duration>0,
    # 真零工时工序按 _ZERO_TOTAL_DURATION_EPSILON_HOURS(>0)计入,且每批至少含自身工序,
    # 故恒为正有限值,无需再防 0。
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


def _positive_float(value: Any, *, field: str) -> float:
    number = non_negative_float(value, field=field)
    if number <= 0.0:
        raise ValidationError(f"{field} 必须大于 0。", field="graph_ready_v2_features")
    return number


def _required_non_negative(metric: Dict[str, Any], *, field: str) -> float:
    if field not in metric:
        raise ValidationError(f"GraphReady v2 特征缺少 {field}。", field="graph_ready_v2_features")
    return non_negative_float(metric.get(field), field=field)


__all__ = ["enrich_graph_ready_v2_metrics"]
