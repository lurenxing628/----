from __future__ import annotations

from typing import Any, Dict, NoReturn, Optional, cast

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import finite_number


def graph_node_metrics_by_op_id(
    graph_ready_context: Dict[str, Any], *, schedulable_ids: set,
) -> Dict[int, Dict[str, Any]]:
    value = graph_ready_context.get("node_metrics_by_op_id")
    if not isinstance(value, dict):
        _raise("图 ready 候选缺少 node_metrics_by_op_id，无法按多组图权重重新评分。", "graph_ready_missing_node_metrics")
    out: Dict[int, Dict[str, Any]] = {}
    for op_id in sorted(schedulable_ids):
        metric = value.get(op_id)
        if not isinstance(metric, dict):
            _raise(f"图 ready 候选缺少待排工序 {op_id} 的图指标。", "graph_ready_missing_node_metrics")
        out[op_id] = cast(Dict[str, Any], metric)
    return out


def bool_metric(metric: Dict[str, Any], field: str) -> bool:
    value = metric.get(field)
    if not isinstance(value, bool):
        _raise(f"图指标 {field} 必须是 bool。", "graph_ready_bad_node_metrics")
    return bool(value)


def non_negative_number(value: Any, *, field: str) -> float:
    number = finite_number(value, field=field)
    if number < 0:
        _raise(f"图指标 {field} 必须是非负数。", "graph_ready_bad_node_metrics")
    return float(number)


def required_non_negative_number(metric: Dict[str, Any], *, field: str) -> float:
    if field not in metric:
        _raise(f"图指标缺少 {field}。", "graph_ready_missing_node_metrics")
    return non_negative_number(metric.get(field), field=field)


def optional_non_negative_number(value: Any, *, field: str) -> Optional[float]:
    if value is None:
        return None
    return non_negative_number(value, field=field)


def _raise(message: str, reason: str) -> NoReturn:
    raise ValidationError(message, field="graph_ready_context", details={"reason": reason})
