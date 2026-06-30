from __future__ import annotations

import math
from collections.abc import Mapping as MappingABC
from datetime import datetime, time, timedelta
from inspect import Parameter, signature
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.algorithms.value_domains import INTERNAL
from core.infrastructure.errors import ValidationError

_RESIDUAL_CAPACITY_MAX_WINDOW_DAYS = 30


def residual_capacity_for_operation(
    op: Any,
    *,
    batch: Any,
    start_dt: datetime,
    due_exclusive: datetime,
    calendar_service: Optional[Any],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results_by_resource_id: Dict[str, Dict[str, List[Any]]],
    resource_pool: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    machine_ids = _candidate_machine_ids(op, resource_pool=resource_pool)
    if not machine_ids or due_exclusive <= start_dt:
        return _capacity_payload(
            0.0,
            0.0,
            0.0,
            candidate_machine_count=0,
            resource_candidate_machine_count=len(machine_ids),
            bottleneck_machine_count=1 if machine_ids else 0,
        )

    window_end = _residual_capacity_window_end(start_dt=start_dt, due_exclusive=due_exclusive)
    priority = getattr(batch, "priority", None)
    requires_auto_operator = _requires_auto_operator(op, resource_pool=resource_pool)
    candidates = []
    effective_candidate_machine_count = 0
    for machine_id in machine_ids:
        operator_ids = _candidate_operator_ids(op, machine_id=machine_id, resource_pool=resource_pool)
        if requires_auto_operator and not operator_ids:
            continue
        effective_candidate_machine_count += 1
        candidates.append(
            _machine_residual_capacity(
                machine_id=machine_id,
                operator_ids=operator_ids,
                start_dt=start_dt,
                due_exclusive=window_end,
                priority=priority,
                calendar_service=calendar_service,
                downtime_map=downtime_map,
                seed_results_by_resource_id=seed_results_by_resource_id,
            )
        )
    if not candidates:
        return _capacity_payload(
            0.0,
            0.0,
            0.0,
            candidate_machine_count=0,
            resource_candidate_machine_count=len(machine_ids),
            bottleneck_machine_count=1 if machine_ids else 0,
        )
    window_hours, blocked_hours, residual_hours = max(candidates, key=_capacity_rank)
    return _capacity_payload(
        window_hours,
        blocked_hours,
        residual_hours,
        candidate_machine_count=effective_candidate_machine_count,
        resource_candidate_machine_count=len(machine_ids),
        bottleneck_machine_count=effective_candidate_machine_count,
    )


def seed_results_by_resource_id(seed_results: Iterable[Any]) -> Dict[str, Dict[str, List[Any]]]:
    out: Dict[str, Dict[str, List[Any]]] = {"machine": {}, "operator": {}}
    for result in list(seed_results or []):
        if str(getattr(result, "source", INTERNAL) or "").strip().lower() != INTERNAL:
            continue
        machine_id = _text(getattr(result, "machine_id", None))
        if machine_id:
            out["machine"].setdefault(machine_id, []).append(result)
        operator_id = _text(getattr(result, "operator_id", None))
        if operator_id:
            out["operator"].setdefault(operator_id, []).append(result)
    return out


def _residual_capacity_window_end(*, start_dt: datetime, due_exclusive: datetime) -> datetime:
    max_end = start_dt + timedelta(days=_RESIDUAL_CAPACITY_MAX_WINDOW_DAYS)
    return min(due_exclusive, max_end)


def seed_results_by_machine_id(seed_results: Iterable[Any]) -> Dict[str, List[Any]]:
    return seed_results_by_resource_id(seed_results).get("machine", {})


def bottleneck_on(*, bottleneck_score: float, residual_capacity_pressure: float, machine_count: int) -> float:
    if int(machine_count) <= 0:
        return float(bottleneck_score)
    residual_bonus = float(residual_capacity_pressure) / math.sqrt(float(machine_count))
    return float(bottleneck_score + residual_bonus)


def _machine_residual_capacity(
    *,
    machine_id: str,
    operator_ids: Tuple[str, ...],
    start_dt: datetime,
    due_exclusive: datetime,
    priority: Any,
    calendar_service: Optional[Any],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results_by_resource_id: Dict[str, Dict[str, List[Any]]],
) -> Tuple[float, float, float]:
    operator_payloads = [
        _machine_operator_residual_capacity(
            machine_id=machine_id,
            operator_id=operator_id,
            start_dt=start_dt,
            due_exclusive=due_exclusive,
            priority=priority,
            calendar_service=calendar_service,
            downtime_map=downtime_map,
            seed_results_by_resource_id=seed_results_by_resource_id,
        )
        for operator_id in (operator_ids or (None,))
    ]
    return max(operator_payloads, key=_capacity_rank)


def _machine_operator_residual_capacity(
    *,
    machine_id: str,
    operator_id: Optional[str],
    start_dt: datetime,
    due_exclusive: datetime,
    priority: Any,
    calendar_service: Optional[Any],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results_by_resource_id: Dict[str, Dict[str, List[Any]]],
) -> Tuple[float, float, float]:
    window_hours = _calendar_capacity_hours(
        calendar_service,
        start_dt,
        due_exclusive,
        priority=priority,
        operator_id=operator_id,
    )
    machine_seed_results = seed_results_by_resource_id.get("machine", {}).get(machine_id) or []
    operator_seed_results = seed_results_by_resource_id.get("operator", {}).get(operator_id or "") or []
    blocked_segments = _merge_segments(
        list(downtime_map.get(machine_id) or [])
        + _seed_segments(machine_seed_results)
        + _seed_segments(operator_seed_results)
    )
    blocked_hours = _blocked_capacity_hours(
        calendar_service,
        start_dt,
        due_exclusive,
        blocked_segments,
        priority=priority,
        operator_id=operator_id,
    )
    residual_hours = max(0.0, float(window_hours) - float(blocked_hours))
    return float(window_hours), float(blocked_hours), float(residual_hours)


def _capacity_payload(
    window_hours: float,
    blocked_hours: float,
    residual_hours: float,
    *,
    candidate_machine_count: int,
    resource_candidate_machine_count: int,
    bottleneck_machine_count: int,
) -> Dict[str, float]:
    if window_hours <= 0.0:
        pressure = 1.0 if int(resource_candidate_machine_count) > 0 else 0.0
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, float(residual_hours) / float(window_hours)))
        pressure = max(0.0, min(1.0, 1.0 - ratio))
    return {
        "residual_capacity_window_hours": float(window_hours),
        "residual_capacity_blocked_hours": float(blocked_hours),
        "residual_capacity_hours": float(residual_hours),
        "residual_capacity_ratio": float(ratio),
        "residual_capacity_pressure": float(pressure),
        "candidate_machine_count": int(candidate_machine_count),
        "effective_candidate_machine_count": int(candidate_machine_count),
        "resource_candidate_machine_count": int(resource_candidate_machine_count),
        "bottleneck_machine_count": int(bottleneck_machine_count),
    }


def _capacity_rank(item: Tuple[float, float, float]) -> Tuple[float, float, float, float]:
    window_hours, blocked_hours, residual_hours = item
    ratio = float(residual_hours) / float(window_hours) if float(window_hours) > 0.0 else 0.0
    return (ratio, float(residual_hours), float(window_hours), -float(blocked_hours))


def _requires_auto_operator(op: Any, *, resource_pool: Optional[Dict[str, Any]]) -> bool:
    if _text(getattr(op, "operator_id", None)):
        return False
    if _text(getattr(op, "machine_id", None)):
        return True
    op_type_id = _text(getattr(op, "op_type_id", None))
    pool = _ResourcePoolView(resource_pool)
    return bool(op_type_id and op_type_id in pool.machines_by_op_type)


def _candidate_machine_ids(op: Any, *, resource_pool: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    fixed_machine = _text(getattr(op, "machine_id", None))
    fixed_operator = _text(getattr(op, "operator_id", None))
    op_type_id = _text(getattr(op, "op_type_id", None))
    pool = _ResourcePoolView(resource_pool)
    if fixed_machine:
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, pool=pool)
    elif op_type_id and op_type_id in pool.machines_by_op_type:
        candidates = _text_list(pool.machines_by_op_type.get(op_type_id))
    else:
        candidates = []
    if op_type_id and op_type_id in pool.machines_by_op_type:
        allowed = set(_text_list(pool.machines_by_op_type.get(op_type_id)))
        candidates = [machine_id for machine_id in candidates if machine_id in allowed]
    return _unique_text_tuple(candidates)


def _candidate_operator_ids(op: Any, *, machine_id: str, resource_pool: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    fixed_operator = _text(getattr(op, "operator_id", None))
    if fixed_operator:
        return (fixed_operator,)
    pool = _ResourcePoolView(resource_pool)
    return _unique_text_tuple(_text_list(pool.operators_by_machine.get(machine_id)))

class _ResourcePoolView:
    def __init__(self, resource_pool: Optional[Dict[str, Any]]) -> None:
        self.machines_by_op_type = _mapping_part(resource_pool, "machines_by_op_type")
        self.operators_by_machine = _mapping_part(resource_pool, "operators_by_machine")
        self.machines_by_operator = _mapping_part(resource_pool, "machines_by_operator")


def _mapping_part(source: Optional[Dict[str, Any]], key: str) -> MappingABC:
    if not isinstance(source, dict):
        return {}
    value = source.get(key)
    return value if isinstance(value, MappingABC) else {}


def _machines_for_fixed_operator(fixed_operator: str, *, pool: _ResourcePoolView) -> List[str]:
    candidates = _text_list(pool.machines_by_operator.get(fixed_operator))
    if candidates:
        return candidates
    found: List[str] = []
    for machine_id, operator_ids in pool.operators_by_machine.items():
        machine_text = _text(machine_id)
        if machine_text and fixed_operator in _text_list(operator_ids):
            found.append(machine_text)
    return found


def _seed_segments(seed_results: Iterable[Any]) -> List[Tuple[datetime, datetime]]:
    segments: List[Tuple[datetime, datetime]] = []
    for result in list(seed_results or []):
        start = getattr(result, "start_time", None)
        end = getattr(result, "end_time", None)
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start:
            segments.append((start, end))
    return segments


def _merge_segments(segments: Iterable[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    normalized = [
        (start, end)
        for start, end in list(segments or [])
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start
    ]
    normalized.sort(key=lambda item: item[0])
    merged: List[Tuple[datetime, datetime]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if end > prev_end:
            merged[-1] = (prev_start, end)
    return merged


def _blocked_capacity_hours(
    calendar_service: Optional[Any],
    start_dt: datetime,
    end_dt: datetime,
    segments: Iterable[Tuple[datetime, datetime]],
    *,
    priority: Any,
    operator_id: Optional[str],
) -> float:
    total = 0.0
    for block_start, block_end in list(segments or []):
        if not isinstance(block_start, datetime) or not isinstance(block_end, datetime):
            continue
        overlap_start = max(start_dt, block_start)
        overlap_end = min(end_dt, block_end)
        if overlap_end <= overlap_start:
            continue
        total += _calendar_capacity_hours(
            calendar_service,
            overlap_start,
            overlap_end,
            priority=priority,
            operator_id=operator_id,
        )
    return float(total)


def _calendar_capacity_hours(
    calendar_service: Optional[Any],
    start_dt: datetime,
    end_dt: datetime,
    *,
    priority: Any,
    operator_id: Optional[str],
) -> float:
    if end_dt <= start_dt:
        return 0.0
    policy_for_datetime = getattr(calendar_service, "policy_for_datetime", None)
    if not callable(policy_for_datetime):
        return _wall_hours(start_dt, end_dt)
    supports_operator_id = _policy_for_datetime_supports_operator_id(policy_for_datetime)
    cursor = start_dt
    total = 0.0
    guard = 0
    while cursor < end_dt:
        guard += 1
        if guard > 4000:
            raise ValidationError("GraphReady v2 残余容量计算超过安全循环上限。", field="graph_ready_v2_features")
        if supports_operator_id is False:
            policy = policy_for_datetime(cursor)
        else:
            try:
                policy = policy_for_datetime(cursor, operator_id=operator_id)
            except TypeError as exc:
                if supports_operator_id is True or not _is_unexpected_operator_id_type_error(exc):
                    raise
                policy = policy_for_datetime(cursor)
        window_start, window_end = policy.work_window()
        if not _policy_allows(policy, priority) or _policy_efficiency(policy) <= 0.0:
            cursor = _next_calendar_day(cursor, end_dt)
            continue
        if cursor < window_start:
            cursor = min(window_start, end_dt)
            continue
        if window_end <= cursor:
            cursor = _next_calendar_day(cursor, end_dt)
            continue
        segment_end = min(end_dt, window_end)
        total += _wall_hours(cursor, segment_end) * _policy_efficiency(policy)
        cursor = segment_end
    return float(total)


def _policy_for_datetime_supports_operator_id(policy_for_datetime: Any) -> Optional[bool]:
    try:
        parameters = signature(policy_for_datetime).parameters.values()
    except (TypeError, ValueError):
        return None
    for parameter in parameters:
        if parameter.kind == Parameter.VAR_KEYWORD:
            return True
        if parameter.name == "operator_id" and parameter.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        ):
            return True
    return False


def _is_unexpected_operator_id_type_error(exc: TypeError) -> bool:
    message = str(exc)
    return "operator_id" in message and "unexpected keyword" in message


def _next_calendar_day(cursor: datetime, end_dt: datetime) -> datetime:
    next_day = datetime.combine(cursor.date() + timedelta(days=1), time.min)
    if next_day <= cursor:
        next_day = cursor + timedelta(days=1)
    return min(end_dt, next_day)


def _policy_allows(policy: Any, priority: Any) -> bool:
    allowed = getattr(policy, "is_priority_allowed", None)
    if callable(allowed):
        return bool(allowed(priority))
    return True


def _policy_efficiency(policy: Any) -> float:
    return max(0.0, _non_negative_float(getattr(policy, "efficiency", 1.0), field="calendar.efficiency"))


def _wall_hours(start_dt: datetime, end_dt: datetime) -> float:
    return max(0.0, float((end_dt - start_dt).total_seconds() / 3600.0))


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = _text(values)
        return [text] if text else []
    return [text for text in (_text(value) for value in list(values or [])) if text]


def _unique_text_tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


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


__all__ = [
    "bottleneck_on",
    "residual_capacity_for_operation",
    "seed_results_by_machine_id",
    "seed_results_by_resource_id",
]
