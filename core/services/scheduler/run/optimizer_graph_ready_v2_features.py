from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Tuple

from core.algorithms.greedy.date_parsers import parse_date
from core.infrastructure.errors import ValidationError


def enrich_graph_ready_v2_metrics(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    operations: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
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
        batch_id_by_op_id=batch_id_by_op_id,
        duration_by_op_id=schedulable_duration_by_op_id,
    )
    processing_ranks = _processing_time_ranks(schedulable_duration_by_op_id)
    for op_id, metric in metrics_by_op_id.items():
        op = op_by_id[op_id]
        batch = _batch_for_operation(op, batches=batches)
        due_hours = _due_deadline_hours(batch, start_dt=start_dt)
        remaining_hours = remaining_hours_by_batch_id[batch_id_by_op_id[op_id]]
        slack_hours = float(due_hours - remaining_hours)
        due_pressure = _due_pressure(due_hours=due_hours, remaining_hours=remaining_hours)
        saveability = _saveability(due_hours=due_hours, remaining_hours=remaining_hours)
        sacrifice_penalty = _sacrifice_penalty(due_hours=due_hours, remaining_hours=remaining_hours, saveability=saveability)
        bottleneck_score = _required_non_negative(metric, field="bottleneck_machine_score")
        row = dict(metric)
        row.update(
            {
                "due_deadline_hours": float(due_hours),
                "due_pressure": float(due_pressure),
                "slack_hours": float(slack_hours),
                "remaining_work_hours": float(remaining_hours),
                "saveability": float(saveability),
                "processing_time_rank": float(processing_ranks[op_id]),
                "sacrifice_penalty": float(sacrifice_penalty),
                "critical_ratio": float(_critical_ratio(due_hours=due_hours, remaining_hours=remaining_hours)),
                "bottleneck_on": float(bottleneck_score),
                "bottleneck_release": float(bottleneck_score * saveability),
                "bottleneck_due_gate": float(bottleneck_score * due_pressure * saveability),
                "graph_ready_v2_feature_version": "graph_ready_v2_objective_features_v2",
            }
        )
        out[int(op_id)] = row
    return out


def _operation_hours(op: Any, *, batches: Dict[str, Any]) -> float:
    batch = _batch_for_operation(op, batches=batches)
    quantity = _positive_float(_required_attr(batch, "quantity", field="batch.quantity"), field="batch.quantity")
    setup = _non_negative_float(
        _required_attr(op, "setup_hours", field="operation.setup_hours"),
        field="operation.setup_hours",
    )
    unit = _non_negative_float(
        _required_attr(op, "unit_hours", field="operation.unit_hours"),
        field="operation.unit_hours",
    )
    total = float(setup + unit * quantity)
    if total <= 0.0:
        raise ValidationError("GraphReady v2 特征要求工序工时必须大于 0。", field="graph_ready_v2_features")
    return total


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
    batch_id_by_op_id: Dict[int, str],
    duration_by_op_id: Dict[int, float],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for op_id in sorted(duration_by_op_id):
        batch_id = batch_id_by_op_id[op_id]
        out[batch_id] = out.get(batch_id, 0.0) + float(duration_by_op_id[op_id])
    return out


def _due_deadline_hours(batch: Any, *, start_dt: datetime) -> float:
    raw_due = getattr(batch, "due_date", None)
    due_day = _parse_due_day(raw_due)
    due_exclusive = datetime.combine(due_day + timedelta(days=1), time.min)
    return float((due_exclusive - start_dt).total_seconds() / 3600.0)


def _parse_due_day(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value or "").strip())
    if parsed is None:
        raise ValidationError("GraphReady v2 特征要求批次必须有可解析交期。", field="graph_ready_v2_features")
    return parsed


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
