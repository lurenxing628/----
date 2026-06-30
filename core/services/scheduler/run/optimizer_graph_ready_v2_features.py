from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.greedy.date_parsers import parse_date
from core.algorithms.value_domains import EXTERNAL, MERGED
from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_v2_capacity import (
    bottleneck_on,
    residual_capacity_for_operation,
    seed_results_by_resource_id,
)

_NO_DUE_DEADLINE_HOURS = 1_000_000_000.0
_NO_DUE_CRITICAL_RATIO = 1_000_000_000.0
_NO_DUE_SACRIFICE_PENALTY = 2.0
_NO_DUE_CAPACITY_WINDOW_DAYS = 30


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
) -> Dict[int, Dict[str, Any]]:
    op_by_id = {_positive_int(getattr(op, "id", None), field="operation.id"): op for op in list(operations or [])}
    metrics_by_op_id = _normalize_metrics_by_op_id(metrics_by_op_id)
    metric_op_ids = set(metrics_by_op_id)
    missing_op_ids = sorted(metric_op_ids.difference(op_by_id))
    if missing_op_ids:
        raise ValidationError("GraphReady v2 特征缺少对应工序。", field="graph_ready_v2_features")
    out: Dict[int, Dict[str, Any]] = {}
    duration_by_op_id = {op_id: _operation_hours(op, batches=batches) for op_id, op in op_by_id.items()}
    batch_id_by_op_id = {op_id: _batch_id_for_operation(op) for op_id, op in op_by_id.items()}
    schedulable_duration_by_op_id = {op_id: duration_by_op_id[op_id] for op_id in metric_op_ids}
    remaining_hours_by_batch_id = _remaining_hours_by_batch(
        operations_by_op_id=op_by_id,
        batch_id_by_op_id=batch_id_by_op_id,
        duration_by_op_id=schedulable_duration_by_op_id,
    )
    ready_offset_hours_by_op_id = _ready_offset_hours_by_op_id(
        operations_by_op_id=op_by_id,
        batch_id_by_op_id=batch_id_by_op_id,
        duration_by_op_id=schedulable_duration_by_op_id,
    )
    processing_ranks = _processing_time_ranks(schedulable_duration_by_op_id)
    seed_results_by_resource = seed_results_by_resource_id(seed_results or [])
    for op_id, metric in metrics_by_op_id.items():
        op = op_by_id[op_id]
        batch = _batch_for_operation(op, batches=batches)
        remaining_hours = remaining_hours_by_batch_id[batch_id_by_op_id[op_id]]
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
                due_wall_hours=due_hours,
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
        out[int(op_id)] = row
    return out


def _operation_hours(op: Any, *, batches: Dict[str, Any]) -> float:
    batch = _batch_for_operation(op, batches=batches)
    if _operation_source(op) == EXTERNAL:
        total = _external_operation_hours(op)
        if total <= 0.0:
            raise ValidationError("GraphReady v2 特征要求外协工时必须大于 0。", field="graph_ready_v2_features")
        return float(total)
    quantity = _positive_float(_required_attr(batch, "quantity", field="batch.quantity"), field="batch.quantity")
    setup = _non_negative_float(_required_attr(op, "setup_hours", field="operation.setup_hours"), field="operation.setup_hours")
    unit = _non_negative_float(_required_attr(op, "unit_hours", field="operation.unit_hours"), field="operation.unit_hours")
    total = float(setup + unit * quantity)
    if total <= 0.0:
        raise ValidationError("GraphReady v2 特征要求工序工时必须大于 0。", field="graph_ready_v2_features")
    return total


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


def _remaining_hours_by_batch(
    *,
    operations_by_op_id: Dict[int, Any],
    batch_id_by_op_id: Dict[int, str],
    duration_by_op_id: Dict[int, float],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    counted_duration_keys: set = set()
    for op_id in sorted(duration_by_op_id):
        batch_id = batch_id_by_op_id[op_id]
        duration_key = _duration_bucket_key(operations_by_op_id[op_id], batch_id=batch_id, op_id=op_id)
        if duration_key in counted_duration_keys:
            continue
        counted_duration_keys.add(duration_key)
        out[batch_id] = out.get(batch_id, 0.0) + float(duration_by_op_id[op_id])
    return out


def _ready_offset_hours_by_op_id(
    *,
    operations_by_op_id: Dict[int, Any],
    batch_id_by_op_id: Dict[int, str],
    duration_by_op_id: Dict[int, float],
) -> Dict[int, float]:
    by_batch: Dict[str, List[int]] = {}
    for op_id in duration_by_op_id:
        by_batch.setdefault(batch_id_by_op_id[op_id], []).append(op_id)
    out: Dict[int, float] = {}
    for op_ids in by_batch.values():
        elapsed = 0.0
        offset_by_duration_key: Dict[Tuple[str, str, str], float] = {}
        for op_id in sorted(op_ids, key=lambda item: _operation_sequence_key(operations_by_op_id[item], op_id=item)):
            duration_key = _duration_bucket_key(operations_by_op_id[op_id], batch_id=batch_id_by_op_id[op_id], op_id=op_id)
            if duration_key in offset_by_duration_key:
                out[op_id] = offset_by_duration_key[duration_key]
                continue
            offset_by_duration_key[duration_key] = float(elapsed)
            out[op_id] = float(elapsed)
            elapsed += float(duration_by_op_id[op_id])
    return out


def _duration_bucket_key(op: Any, *, batch_id: str, op_id: int) -> Tuple[str, str, str]:
    if _is_merged_external(op):
        return "merged_external", str(batch_id), str(getattr(op, "ext_group_id", "") or "").strip()
    return "operation", str(batch_id), str(int(op_id))


def _operation_sequence_key(op: Any, *, op_id: int) -> Tuple[int, int]:
    raw_seq = getattr(op, "seq", None)
    if raw_seq is None:
        seq = int(op_id)
    else:
        try:
            seq = int(raw_seq)
        except (TypeError, ValueError):
            seq = int(op_id)
    return int(seq), int(op_id)


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
    # remaining_hours 由 _operation_hours(恒 >0)汇总,且每批至少含自身工序,故恒为正有限值,无需再防 0。
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
