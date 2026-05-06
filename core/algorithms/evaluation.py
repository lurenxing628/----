from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.greedy.date_parsers import due_exclusive, parse_date
from core.algorithms.objective_specs import objective_metric_keys
from core.algorithms.priority_constants import PRIORITY_WEIGHT, normalize_priority
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import INTERNAL


def _due_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value or "").strip()


def _parse_due_date_state(value: Any) -> Tuple[Optional[date], bool]:
    if value is None:
        return None, False
    if isinstance(value, date) and not isinstance(value, datetime):
        return value, False
    if isinstance(value, datetime):
        return value.date(), False
    s = str(value or "").strip()
    if not s:
        return None, False
    parsed = parse_date(s)
    return parsed, parsed is None


_parse_due_date = parse_date
_due_exclusive = due_exclusive


@dataclass
class ScheduleMetrics:
    overdue_count: int
    total_tardiness_hours: float
    makespan_hours: float
    changeover_count: int
    # 软指标扩展（V1.2）：更贴近业务的加权拖期 + 利用率/负荷均衡
    weighted_tardiness_hours: float = 0.0
    makespan_internal_hours: float = 0.0
    machine_used_count: int = 0
    operator_used_count: int = 0
    machine_busy_hours_total: float = 0.0
    operator_busy_hours_total: float = 0.0
    machine_util_avg: float = 0.0
    operator_util_avg: float = 0.0
    machine_load_cv: float = 0.0
    operator_load_cv: float = 0.0
    # P2：指标边界语义（向后兼容新增字段）
    internal_horizon_hours: float = 0.0  # internal 利用率的时间窗（=makespan_internal_hours）
    util_defined: bool = False  # horizon>0 才为 True；否则 util_avg 仅为 0.0 占位
    invalid_due_count: int = 0
    unscheduled_batch_count: int = 0
    invalid_due_batch_ids_sample: List[str] = field(default_factory=list)
    unscheduled_batch_ids_sample: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _round_finite(v: Any, ndigits: int) -> float:
            try:
                fv = float(v)
            except Exception:
                return 0.0
            if not math.isfinite(fv):
                return 0.0
            return float(round(fv, ndigits))

        return {
            "overdue_count": int(self.overdue_count),
            "total_tardiness_hours": _round_finite(self.total_tardiness_hours, 4),
            "makespan_hours": _round_finite(self.makespan_hours, 4),
            "changeover_count": int(self.changeover_count),
            "weighted_tardiness_hours": _round_finite(self.weighted_tardiness_hours, 4),
            "makespan_internal_hours": _round_finite(self.makespan_internal_hours, 4),
            "machine_used_count": int(self.machine_used_count),
            "operator_used_count": int(self.operator_used_count),
            "machine_busy_hours_total": _round_finite(self.machine_busy_hours_total, 4),
            "operator_busy_hours_total": _round_finite(self.operator_busy_hours_total, 4),
            "machine_util_avg": _round_finite(self.machine_util_avg, 6),
            "operator_util_avg": _round_finite(self.operator_util_avg, 6),
            "machine_load_cv": _round_finite(self.machine_load_cv, 6),
            "operator_load_cv": _round_finite(self.operator_load_cv, 6),
            "internal_horizon_hours": _round_finite(self.internal_horizon_hours, 4),
            "util_defined": bool(self.util_defined),
            "invalid_due_count": int(self.invalid_due_count),
            "unscheduled_batch_count": int(self.unscheduled_batch_count),
            "invalid_due_batch_ids_sample": [str(x) for x in list(self.invalid_due_batch_ids_sample or [])[:10]],
            "unscheduled_batch_ids_sample": [str(x) for x in list(self.unscheduled_batch_ids_sample or [])[:20]],
        }


@dataclass
class _ResultMetricState:
    finish_by_batch: Dict[str, datetime] = field(default_factory=dict)
    min_start: Optional[datetime] = None
    max_end: Optional[datetime] = None
    by_machine: Dict[str, List[ScheduleResult]] = field(default_factory=dict)
    min_internal_start: Optional[datetime] = None
    max_internal_end: Optional[datetime] = None
    machine_busy: Dict[str, float] = field(default_factory=dict)
    operator_busy: Dict[str, float] = field(default_factory=dict)


@dataclass
class _DueMetricState:
    overdue_count: int = 0
    tardiness_hours: float = 0.0
    weighted_tardiness_hours: float = 0.0
    invalid_due_count: int = 0
    unscheduled_batch_count: int = 0
    invalid_due_batch_ids_sample: List[str] = field(default_factory=list)
    unscheduled_batch_ids_sample: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class _UtilizationMetrics:
    makespan_internal_hours: float
    machine_hours: List[float]
    operator_hours: List[float]
    machine_util_avg: float
    operator_util_avg: float
    util_defined: bool


def compute_metrics(results: List[ScheduleResult], batches: Dict[str, Any]) -> ScheduleMetrics:
    result_state = _collect_result_metric_state(results)
    due_state = _compute_due_metrics(batches, result_state.finish_by_batch)
    utilization = _build_utilization_metrics(result_state)

    return ScheduleMetrics(
        overdue_count=int(due_state.overdue_count),
        total_tardiness_hours=float(due_state.tardiness_hours),
        makespan_hours=float(_hours_between(result_state.min_start, result_state.max_end)),
        changeover_count=int(_count_changeovers(result_state.by_machine)),
        weighted_tardiness_hours=float(due_state.weighted_tardiness_hours),
        makespan_internal_hours=float(utilization.makespan_internal_hours),
        machine_used_count=int(len(utilization.machine_hours)),
        operator_used_count=int(len(utilization.operator_hours)),
        machine_busy_hours_total=float(sum(utilization.machine_hours) if utilization.machine_hours else 0.0),
        operator_busy_hours_total=float(sum(utilization.operator_hours) if utilization.operator_hours else 0.0),
        machine_util_avg=float(utilization.machine_util_avg),
        operator_util_avg=float(utilization.operator_util_avg),
        machine_load_cv=float(_cv(utilization.machine_hours)),
        operator_load_cv=float(_cv(utilization.operator_hours)),
        internal_horizon_hours=float(utilization.makespan_internal_hours),
        util_defined=bool(utilization.util_defined),
        invalid_due_count=int(due_state.invalid_due_count),
        unscheduled_batch_count=int(due_state.unscheduled_batch_count),
        invalid_due_batch_ids_sample=due_state.invalid_due_batch_ids_sample,
        unscheduled_batch_ids_sample=due_state.unscheduled_batch_ids_sample,
    )


def _collect_result_metric_state(results: List[ScheduleResult]) -> _ResultMetricState:
    state = _ResultMetricState()
    for result in results:
        st = getattr(result, "start_time", None)
        et = getattr(result, "end_time", None)
        if not st or not et:
            continue
        bid = str(getattr(result, "batch_id", "") or "").strip()
        if bid:
            _record_batch_finish(state, bid=bid, start_time=st, end_time=et)
        if (getattr(result, "source", "") or "").strip().lower() == INTERNAL:
            _record_internal_result(state, result=result, start_time=st, end_time=et)
    return state


def _record_batch_finish(state: _ResultMetricState, *, bid: str, start_time: datetime, end_time: datetime) -> None:
    if state.min_start is None or start_time < state.min_start:
        state.min_start = start_time
    if state.max_end is None or end_time > state.max_end:
        state.max_end = end_time
    current_finish = state.finish_by_batch.get(bid)
    if current_finish is None or end_time > current_finish:
        state.finish_by_batch[bid] = end_time


def _record_internal_result(
    state: _ResultMetricState,
    *,
    result: ScheduleResult,
    start_time: datetime,
    end_time: datetime,
) -> None:
    if state.min_internal_start is None or start_time < state.min_internal_start:
        state.min_internal_start = start_time
    if state.max_internal_end is None or end_time > state.max_internal_end:
        state.max_internal_end = end_time

    duration_hours = _duration_hours(start_time, end_time)
    machine_id = str(getattr(result, "machine_id", None) or "").strip()
    if machine_id:
        state.by_machine.setdefault(machine_id, []).append(result)
        state.machine_busy[machine_id] = state.machine_busy.get(machine_id, 0.0) + float(duration_hours)
    operator_id = str(getattr(result, "operator_id", None) or "").strip()
    if operator_id:
        state.operator_busy[operator_id] = state.operator_busy.get(operator_id, 0.0) + float(duration_hours)


def _compute_due_metrics(batches: Dict[str, Any], finish_by_batch: Dict[str, datetime]) -> _DueMetricState:
    state = _DueMetricState()
    for bid0, batch in batches.items():
        bid = str(bid0 or "").strip()
        if not bid:
            continue
        _record_batch_due_state(state, bid=bid, batch=batch, finish_time=finish_by_batch.get(bid))
    return state


def _record_batch_due_state(
    state: _DueMetricState,
    *,
    bid: str,
    batch: Any,
    finish_time: Optional[datetime],
) -> None:
    due_raw = getattr(batch, "due_date", None)
    due_date_value, due_invalid = _parse_due_date_state(due_raw)
    if due_invalid:
        state.invalid_due_count += 1
        if len(state.invalid_due_batch_ids_sample) < 10:
            state.invalid_due_batch_ids_sample.append(bid)
    if not finish_time:
        _record_unscheduled_batch(state, bid=bid, due_raw=due_raw)
        return
    if due_date_value:
        _record_tardiness_if_overdue(state, batch=batch, finish_time=finish_time, due_date_value=due_date_value)


def _record_unscheduled_batch(state: _DueMetricState, *, bid: str, due_raw: Any) -> None:
    state.unscheduled_batch_count += 1
    if len(state.unscheduled_batch_ids_sample) >= 20:
        return
    due_text = _due_text(due_raw)
    state.unscheduled_batch_ids_sample.append(f"{bid}({due_text})" if due_text else bid)


def _record_tardiness_if_overdue(
    state: _DueMetricState,
    *,
    batch: Any,
    finish_time: datetime,
    due_date_value: date,
) -> None:
    batch_due_exclusive = due_exclusive(due_date_value)
    if finish_time < batch_due_exclusive:
        return
    state.overdue_count += 1
    delta_hours = (finish_time - batch_due_exclusive).total_seconds() / 3600.0
    state.tardiness_hours += float(delta_hours)
    priority = normalize_priority(getattr(batch, "priority", None), default="normal")
    state.weighted_tardiness_hours += float(delta_hours) * float(PRIORITY_WEIGHT.get(priority, 1.0))


def _count_changeovers(by_machine: Dict[str, List[ScheduleResult]]) -> int:
    changeovers = 0
    for machine_results in by_machine.values():
        machine_results.sort(key=lambda item: (item.start_time or datetime.min, item.end_time or datetime.min, item.op_id))
        changeovers += _count_machine_changeovers(machine_results)
    return int(changeovers)


def _count_machine_changeovers(machine_results: List[ScheduleResult]) -> int:
    changeovers = 0
    previous_type: Optional[str] = None
    for result in machine_results:
        current_type = (result.op_type_name or "").strip()
        if not current_type:
            continue
        if previous_type is not None and current_type != previous_type:
            changeovers += 1
        previous_type = current_type
    return int(changeovers)


def _build_utilization_metrics(state: _ResultMetricState) -> _UtilizationMetrics:
    horizon = float(_hours_between(state.min_internal_start, state.max_internal_end))
    machine_hours = _finite_non_negative(state.machine_busy)
    operator_hours = _finite_non_negative(state.operator_busy)
    return _UtilizationMetrics(
        makespan_internal_hours=float(horizon),
        machine_hours=machine_hours,
        operator_hours=operator_hours,
        machine_util_avg=_util_avg(machine_hours, horizon),
        operator_util_avg=_util_avg(operator_hours, horizon),
        util_defined=bool(horizon > 0),
    )


def _hours_between(start_time: Optional[datetime], end_time: Optional[datetime]) -> float:
    if start_time is None or end_time is None or end_time <= start_time:
        return 0.0
    return (end_time - start_time).total_seconds() / 3600.0


def _duration_hours(start_time: datetime, end_time: datetime) -> float:
    return max((end_time - start_time).total_seconds() / 3600.0, 0.0)


def _finite_non_negative(values: Dict[str, float]) -> List[float]:
    out: List[float] = []
    for value in values.values():
        try:
            float_value = float(value)
        except Exception:
            continue
        if math.isfinite(float_value) and float_value >= 0:
            out.append(float_value)
    return out


def _util_avg(hours: List[float], horizon: float) -> float:
    return float(sum(hours) / (len(hours) * horizon)) if hours and horizon > 0 else 0.0


def _cv(values: List[float]) -> float:
    clean = []
    for value in values:
        try:
            float_value = float(value)
        except Exception:
            continue
        if math.isfinite(float_value) and float_value >= 0:
            clean.append(float_value)
    if len(clean) <= 1:
        return 0.0
    mean_value = statistics.fmean(clean)
    if not math.isfinite(mean_value) or mean_value <= 0:
        return 0.0
    try:
        return float(statistics.pstdev(clean) / mean_value)
    except Exception:
        return 0.0


def objective_score(objective: str, metrics: ScheduleMetrics) -> Tuple[float, ...]:
    return tuple(float(getattr(metrics, key)) for key in objective_metric_keys(objective))
