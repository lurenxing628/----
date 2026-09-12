from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.date_parsers import parse_date
from core.algorithm_contracts.priority_constants import PRIORITY_WEIGHT, normalize_priority
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithms.value_domains import EXTERNAL, MERGED
from core.infrastructure.errors import ValidationError
from core.models.objective import normalize_objective_name

from .optimizer_graph_ready_feature_basis import BASELINE_ORDERING_FIELD, BATCH_WORKLOAD_BASIS, SUCCESSOR_WORKLOAD_BASIS
from .optimizer_graph_ready_v2_capacity import (
    bottleneck_on,
    residual_capacity_for_operation,
    seed_results_by_resource_id,
)
from .optimizer_graph_ready_workload import batch_ordering_workload_signals, operation_workload_signals

_NO_DUE_DEADLINE_HOURS = 1_000_000_000.0
_NO_DUE_CRITICAL_RATIO = 1_000_000_000.0
_NO_DUE_SACRIFICE_PENALTY = 2.0
_NO_DUE_CAPACITY_WINDOW_DAYS = 30

# 真零工时自制工序（total==0：setup=unit=0，或 quantity=0 且 setup=0）在系统口径下合法
# （见 _operation_hours 内注释），但 duration 类特征有两条恒>0 的承重合同：
# 1) _critical_ratio/_saveability 依赖 remaining_hours>0 做除零安全（见 _critical_ratio 注释）；
# 2) 下游公式层 optimizer_graph_ready_candidates._required_positive_metric 要求
#    remaining_work_hours / remaining_due_burden_hours 恒>0（既有合同测试锁死）。
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
    operations: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    calendar_service: Optional[Any] = None,
    downtime_map: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    seed_results: Optional[List[Any]] = None,
    resource_pool: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
    objective_name: str = "min_overdue",
    graph_ready_context: Optional[Dict[str, Any]] = None,
    include_baseline_ordering: bool = True,
) -> Dict[int, Dict[str, Any]]:
    inputs = dict(operations=operations, batches=batches, start_dt=start_dt, calendar_service=calendar_service,
                  downtime_map=downtime_map, seed_results=seed_results, resource_pool=resource_pool,
                  strict_mode=strict_mode, objective_name=objective_name, graph_ready_context=graph_ready_context)
    out = _enrich_feature_basis(metrics_by_op_id, feature_basis=SUCCESSOR_WORKLOAD_BASIS, **inputs)
    if include_baseline_ordering:
        baseline = _enrich_feature_basis(metrics_by_op_id, feature_basis=BATCH_WORKLOAD_BASIS, **inputs)
        for op_id, row in out.items():
            row[BASELINE_ORDERING_FIELD] = baseline[op_id]
    return out


def _enrich_feature_basis(metrics_by_op_id, *, operations, batches, start_dt, calendar_service,
                          downtime_map, seed_results, resource_pool, strict_mode, objective_name,
                          graph_ready_context, feature_basis):
    op_by_id = {_positive_int(getattr(op, "id", None), field="operation.id"): op for op in list(operations or [])}
    metrics_by_op_id = _normalize_metrics_by_op_id(metrics_by_op_id)
    metric_op_ids = set(metrics_by_op_id)
    missing_op_ids = sorted(metric_op_ids.difference(op_by_id))
    if missing_op_ids:
        raise ValidationError("GraphReady v2 特征缺少对应工序。", field="graph_ready_v2_features")
    out: Dict[int, Dict[str, Any]] = {}
    duration_by_op_id = _duration_by_op_id_with_zero_total_trace(op_by_id, batches=batches)
    schedulable_duration_by_op_id = {op_id: duration_by_op_id[op_id] for op_id in metric_op_ids}
    remaining_by_op_id, ready_offset_hours_by_op_id = _workload_signals(
        feature_basis, op_by_id, schedulable_duration_by_op_id, batches=batches, start_dt=start_dt,
        graph_ready_context=graph_ready_context, seed_results=list(seed_results or []), calendar_service=calendar_service)
    family_names = sorted({str(getattr(op_by_id[key], "op_type_name", "") or "").strip() for key in metric_op_ids})
    family_ranks = {name: index for index, name in enumerate(family_names)}
    processing_ranks = _processing_time_ranks(schedulable_duration_by_op_id)
    seed_results_by_resource = seed_results_by_resource_id(seed_results or [])
    for op_id, metric in metrics_by_op_id.items():
        op = op_by_id[op_id]
        batch = _batch_for_operation(op, batches=batches)
        remaining_hours = remaining_by_op_id[op_id]
        priority_weight = PRIORITY_WEIGHT[normalize_priority(getattr(batch, "priority", None))]
        bottleneck_score = _required_non_negative(metric, field="bottleneck_machine_score")
        capacity_start_dt = start_dt + timedelta(hours=float(ready_offset_hours_by_op_id[op_id]))
        parsed_due_exclusive, due_date_state = _due_exclusive_datetime(batch, strict_mode=bool(strict_mode))
        capacity_due_exclusive = parsed_due_exclusive or (
            capacity_start_dt + timedelta(days=_NO_DUE_CAPACITY_WINDOW_DAYS)
        )
        capacity = residual_capacity_for_operation(
            op,
            batch=batch,
            start_dt=capacity_start_dt,
            due_exclusive=capacity_due_exclusive,
            calendar_service=calendar_service,
            downtime_map=downtime_map or {},
            seed_results_by_resource_id=seed_results_by_resource,
            resource_pool=resource_pool,
        )
        due_unavailable = parsed_due_exclusive is None
        if due_unavailable:
            due_hours = _NO_DUE_DEADLINE_HOURS
            due_budget_hours = _NO_DUE_DEADLINE_HOURS
            slack_hours = float(_NO_DUE_DEADLINE_HOURS - remaining_hours)
            due_pressure = 0.0
            saveability = 0.0
            sacrifice_penalty = _NO_DUE_SACRIFICE_PENALTY
            critical_ratio = _NO_DUE_CRITICAL_RATIO
            due_budget_basis = "no_due_placeholder"
        else:
            due_hours = _deadline_hours(start_dt=start_dt, due_exclusive=parsed_due_exclusive)
            due_budget_hours = _deadline_budget_hours(
                op,
                calendar_service=calendar_service,
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
            due_budget_basis = _due_budget_basis(
                op,
                calendar_service=calendar_service,
                capacity=capacity,
            )
        bottleneck_score_with_capacity = bottleneck_on(
            bottleneck_score=bottleneck_score,
            residual_capacity_pressure=capacity["residual_capacity_pressure"],
            machine_count=int(capacity["bottleneck_machine_count"]),
        )
        row = dict(metric)
        row.update(
            {
                "due_deadline_hours": float(due_hours),
                "due_budget_hours": float(due_budget_hours),
                "due_budget_basis": due_budget_basis,
                "due_pressure": float(due_pressure),
                "slack_hours": float(slack_hours),
                "remaining_work_hours": float(remaining_hours),
                "remaining_due_burden_hours": float(remaining_hours),
                "graph_ready_objective_name": normalize_objective_name(objective_name),
                "weighted_processing_hours": float(schedulable_duration_by_op_id[op_id] / priority_weight),
                "weighted_due_pressure": float(due_pressure * priority_weight),
                "changeover_family_rank": family_ranks[str(getattr(op, "op_type_name", "") or "").strip()],
                "saveability": float(saveability),
                "processing_time_rank": float(processing_ranks[op_id]),
                "sacrifice_penalty": float(sacrifice_penalty),
                "critical_ratio": float(critical_ratio),
                "residual_capacity_hours": float(capacity["residual_capacity_hours"]),
                "residual_capacity_window_hours": float(capacity["residual_capacity_window_hours"]),
                "residual_capacity_blocked_hours": float(capacity["residual_capacity_blocked_hours"]),
                "residual_capacity_ratio": float(capacity["residual_capacity_ratio"]),
                "residual_capacity_pressure": float(capacity["residual_capacity_pressure"]),
                "residual_capacity_start_offset_hours": float(ready_offset_hours_by_op_id[op_id]),
                "candidate_machine_count": int(capacity["candidate_machine_count"]),
                "effective_candidate_machine_count": int(capacity["effective_candidate_machine_count"]),
                "resource_candidate_machine_count": int(capacity["resource_candidate_machine_count"]),
                "bottleneck_machine_count": int(capacity["bottleneck_machine_count"]),
                "bottleneck_on": float(bottleneck_score_with_capacity),
                "bottleneck_release": float(bottleneck_score_with_capacity * saveability),
                "bottleneck_due_gate": float(bottleneck_score_with_capacity * due_pressure * saveability),
                "graph_ready_v2_feature_version": "graph_ready_v2_objective_features_v2",
            }
        )
        row.update(_basis_metadata(feature_basis))
        out[int(op_id)] = row
    return out


def _basis_metadata(basis):
    return {
        "remaining_due_burden_basis": "whole_batch_ordering_work" if basis == BATCH_WORKLOAD_BASIS else "unique_current_and_successor_work",
        "graph_ready_workload_version": basis,
        "ready_offset_basis": "batch_sequence_work_sum" if basis == BATCH_WORKLOAD_BASIS else "gross_precedence_calendar_estimate",
    }


def _ordering_deadline_hours(basis, start_dt, capacity_start_dt, due_exclusive):
    return _deadline_hours(start_dt=start_dt if basis == BATCH_WORKLOAD_BASIS else capacity_start_dt,
                           due_exclusive=due_exclusive)


def _workload_signals(basis, operations, durations, **kwargs):
    if basis == BATCH_WORKLOAD_BASIS:
        return batch_ordering_workload_signals(operations, durations)
    if basis != SUCCESSOR_WORKLOAD_BASIS:
        raise ValidationError("GraphReady 候选特征语义不支持。", field="graph_ready_v2_features")
    return operation_workload_signals(operations, durations, **kwargs)


def _duration_by_op_id_with_zero_total_trace(
    op_by_id: Dict[int, Any],
    *,
    batches: Dict[str, Any],
) -> Dict[int, float]:
    duration_by_op_id: Dict[int, float] = {}
    zero_total_op_ids: List[int] = []
    for op_id, op in op_by_id.items():
        total = _non_negative_float(_operation_hours(op, batches=batches), field="operation.total_hours")
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
    if _operation_source(op) == EXTERNAL:
        total = _external_operation_hours(op)
        # 与内部分支不对称是有意的：ext_days/ext_group_total_days 的录入与输入构建全链要求 >0，
        # 不存在“外协 0 天”的合法语义，total<=0 只可能是坏数据，保持 fail-loud。
        if total <= 0.0:
            raise ValidationError("GraphReady v2 特征要求外协工时必须大于 0。", field="graph_ready_v2_features")
        return float(total)
    # 单一真相源：total=setup+unit*quantity 与 core/algorithm_runtime/internal_slot.validate_internal_hours
    # 同口径——quantity==0 合法（总量=setup）、总工时 0 合法，不复辟 quantity>0 / total>0 硬闸
    # （系统口径见 schedule_input_runtime_support._ensure_internal_runtime_hours 护栏注释与回归测试
    # test_ensure_internal_runtime_hours_allows_zero_quantity）。v2 特征层仍保留逐字段存在性/有限性/
    # 非负的 fail-loud 前置检查（比 legacy「缺失补 0」更严）：进入 optimizer 的工序/批次字段必须齐全，
    # 缺字段是坏输入而非合法降级。total==0 的处理见 _duration_by_op_id_with_zero_total_trace。
    quantity = _non_negative_float(_required_attr(batch, "quantity", field="batch.quantity"), field="batch.quantity")
    setup = _non_negative_float(_required_attr(op, "setup_hours", field="operation.setup_hours"), field="operation.setup_hours")
    unit = _non_negative_float(_required_attr(op, "unit_hours", field="operation.unit_hours"), field="operation.unit_hours")
    return float(setup + unit * quantity)


def _external_operation_hours(op: Any) -> float:
    if _is_merged_external(op):
        total_days = _required_attr(op, "ext_group_total_days", field="operation.ext_group_total_days")
        return _positive_float(total_days, field="operation.ext_group_total_days") * 24.0
    return _positive_float(_required_attr(op, "ext_days", field="operation.ext_days"), field="operation.ext_days") * 24.0


def _is_merged_external(op: Any) -> bool:
    merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()
    return _operation_source(op) == EXTERNAL and merge_mode == MERGED and bool(ext_group_id)


def _operation_source(op: Any) -> str:
    return str(getattr(op, "source", "internal") or "internal").strip().lower()


def _batch_for_operation(op: Any, *, batches: Dict[str, Any]) -> Any:
    batch_id = _batch_id_for_operation(op)
    if not batch_id:
        raise ValidationError("GraphReady v2 特征要求工序必须有批次。", field="graph_ready_v2_features")
    if batch_id not in batches:
        raise ValidationError("GraphReady v2 特征找不到工序批次。", field="graph_ready_v2_features")
    return batches[batch_id]


def _batch_id_for_operation(op: Any) -> str:
    return str(_required_attr(op, "batch_id", field="operation.batch_id") or "").strip()


def _required_attr(obj: Any, name: str, *, field: str) -> Any:
    if not hasattr(obj, name):
        raise ValidationError(f"GraphReady v2 特征缺少 {field}。", field="graph_ready_v2_features")
    return getattr(obj, name)


def _due_exclusive_datetime(batch: Any, *, strict_mode: bool) -> Tuple[Optional[datetime], str]:
    raw_due = getattr(batch, "due_date", None)
    due_day, due_date_state = _parse_due_day(raw_due, strict_mode=bool(strict_mode))
    if due_day is None:
        return None, due_date_state
    return datetime.combine(due_day + timedelta(days=1), time.min), due_date_state


def _deadline_hours(*, start_dt: datetime, due_exclusive: datetime) -> float:
    return float((due_exclusive - start_dt).total_seconds() / 3600.0)


def _parse_due_day(value: Any, *, strict_mode: bool) -> Tuple[Optional[date], str]:
    if isinstance(value, datetime):
        return value.date(), "valid"
    if isinstance(value, date):
        return value, "valid"
    text = str(value or "").strip()
    if not text:
        return None, "missing"
    parsed = parse_date(text)
    if parsed is None:
        raise ValidationError(
            "GraphReady v2 特征要求批次交期格式必须是 YYYY-MM-DD。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_v2_bad_due_date"},
        )
    return parsed, "valid"


def _deadline_budget_hours(
    op: Any,
    *,
    calendar_service: Optional[Any],
    due_wall_hours: float,
    capacity: Dict[str, Any],
) -> float:
    if due_wall_hours <= 0.0:
        return float(due_wall_hours)
    if _operation_source(op) == EXTERNAL:
        return float(due_wall_hours)
    if _uses_calendar_capacity_budget(calendar_service=calendar_service, capacity=capacity):
        return float(capacity["residual_capacity_window_hours"])
    return float(due_wall_hours)


def _due_budget_basis(
    op: Any,
    *,
    calendar_service: Optional[Any],
    capacity: Dict[str, Any],
) -> str:
    if _operation_source(op) == EXTERNAL:
        return "wall_clock_hours"
    if _uses_calendar_capacity_budget(calendar_service=calendar_service, capacity=capacity):
        return "calendar_capacity_hours"
    return "wall_clock_hours"


def _uses_calendar_capacity_budget(*, calendar_service: Optional[Any], capacity: Dict[str, Any]) -> bool:
    policy_for_datetime = getattr(calendar_service, "policy_for_datetime", None)
    return callable(policy_for_datetime) and int(capacity.get("candidate_machine_count") or 0) > 0


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


def _normalize_metrics_by_op_id(metrics_by_op_id: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for raw_op_id, metric in metrics_by_op_id.items():
        op_id = _positive_int(raw_op_id, field="node_metrics_by_op_id")
        if op_id in out:
            raise ValidationError("GraphReady v2 特征发现重复 node_metrics_by_op_id。", field="graph_ready_v2_features")
        out[op_id] = metric
    return out


def _positive_int(value: Any, *, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} 必须是正整数。", field="graph_ready_v2_features") from exc
    if number <= 0:
        raise ValidationError(f"{field} 必须是正整数。", field="graph_ready_v2_features")
    return number


def _positive_float(value: Any, *, field: str) -> float:
    number = _non_negative_float(value, field=field)
    if number <= 0.0:
        raise ValidationError(f"{field} 必须大于 0。", field="graph_ready_v2_features")
    return number


def _non_negative_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} 必须是数字。", field="graph_ready_v2_features")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} 必须是数字。", field="graph_ready_v2_features") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{field} 必须是有限数字。", field="graph_ready_v2_features")
    if number < 0.0:
        raise ValidationError(f"{field} 必须是非负数。", field="graph_ready_v2_features")
    return number


def _required_non_negative(metric: Dict[str, Any], *, field: str) -> float:
    if field not in metric:
        raise ValidationError(f"GraphReady v2 特征缺少 {field}。", field="graph_ready_v2_features")
    return _non_negative_float(metric.get(field), field=field)


__all__ = ["enrich_graph_ready_v2_metrics"]
