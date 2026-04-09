from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.greedy.date_parsers import due_exclusive, parse_date
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


def compute_metrics(results: List[ScheduleResult], batches: Dict[str, Any]) -> ScheduleMetrics:
    # finish time per batch
    finish_by_batch: Dict[str, datetime] = {}
    min_start: Optional[datetime] = None
    max_end: Optional[datetime] = None

    for r in results:
        if not r.start_time or not r.end_time:
            continue
        bid = str(getattr(r, "batch_id", "") or "").strip()
        if not bid:
            continue
        if min_start is None or r.start_time < min_start:
            min_start = r.start_time
        if max_end is None or r.end_time > max_end:
            max_end = r.end_time
        cur = finish_by_batch.get(bid)
        if cur is None or r.end_time > cur:
            finish_by_batch[bid] = r.end_time

    overdue_count = 0
    tardiness_hours = 0.0
    weighted_tardiness_hours = 0.0
    invalid_due_count = 0
    unscheduled_batch_count = 0
    invalid_due_batch_ids_sample: List[str] = []
    unscheduled_batch_ids_sample: List[str] = []
    for bid0, b in batches.items():
        bid = str(bid0 or "").strip()
        if not bid:
            continue
        due_raw = getattr(b, "due_date", None)
        due_d, due_invalid = _parse_due_date_state(due_raw)
        if due_invalid:
            invalid_due_count += 1
            if len(invalid_due_batch_ids_sample) < 10:
                invalid_due_batch_ids_sample.append(bid)
        fin = finish_by_batch.get(bid)
        if not fin:
            unscheduled_batch_count += 1
            if len(unscheduled_batch_ids_sample) < 20:
                due_text = _due_text(due_raw)
                if due_text:
                    unscheduled_batch_ids_sample.append(f"{bid}({due_text})")
                else:
                    unscheduled_batch_ids_sample.append(bid)
            continue
        if not due_d:
            continue
        batch_due_exclusive = due_exclusive(due_d)
        if fin >= batch_due_exclusive:
            overdue_count += 1
            delta_h = (fin - batch_due_exclusive).total_seconds() / 3600.0
            tardiness_hours += delta_h
            pr = normalize_priority(getattr(b, "priority", None), default="normal")
            w = float(PRIORITY_WEIGHT.get(pr, 1.0))
            weighted_tardiness_hours += (delta_h * w)

    makespan_hours = 0.0
    if min_start is not None and max_end is not None and max_end > min_start:
        makespan_hours = (max_end - min_start).total_seconds() / 3600.0

    # changeovers: per machine consecutive op_type change
    by_machine: Dict[str, List[ScheduleResult]] = {}
    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if (r.source or "").strip().lower() != INTERNAL:
            continue
        mid = str(getattr(r, "machine_id", None) or "").strip()
        if not mid:
            continue
        by_machine.setdefault(mid, []).append(r)

    changeovers = 0
    for _mid, lst in by_machine.items():
        lst.sort(key=lambda x: (x.start_time or datetime.min, x.end_time or datetime.min, x.op_id))
        prev_type: Optional[str] = None
        for r in lst:
            cur_type = (r.op_type_name or "").strip()
            if not cur_type:
                # op_type_name 缺失：不应制造“假换型”，也不应打断上一道有效类型
                continue
            if prev_type is None:
                prev_type = cur_type
                continue
            if cur_type != prev_type:
                changeovers += 1
            prev_type = cur_type

    # utilization & load balance（internal only）
    min_int: Optional[datetime] = None
    max_int: Optional[datetime] = None
    machine_busy: Dict[str, float] = {}
    operator_busy: Dict[str, float] = {}
    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if (r.source or "").strip().lower() != INTERNAL:
            continue
        st = r.start_time
        et = r.end_time
        if min_int is None or st < min_int:
            min_int = st
        if max_int is None or et > max_int:
            max_int = et
        dur_h = max((et - st).total_seconds() / 3600.0, 0.0)
        mid = str(getattr(r, "machine_id", None) or "").strip()
        if mid:
            machine_busy[mid] = machine_busy.get(mid, 0.0) + float(dur_h)
        oid = str(getattr(r, "operator_id", None) or "").strip()
        if oid:
            operator_busy[oid] = operator_busy.get(oid, 0.0) + float(dur_h)

    makespan_internal_hours = 0.0
    if min_int is not None and max_int is not None and max_int > min_int:
        makespan_internal_hours = (max_int - min_int).total_seconds() / 3600.0

    def _cv(vals: List[float]) -> float:
        clean = []
        for v in vals:
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isfinite(fv) and fv >= 0:
                clean.append(fv)
        if not clean:
            return 0.0
        if len(clean) <= 1:
            return 0.0
        m = statistics.fmean(clean)
        if not math.isfinite(m) or m <= 0:
            return 0.0
        try:
            return float(statistics.pstdev(clean) / m)
        except Exception:
            return 0.0

    def _finite_non_negative(values: Dict[str, float]) -> List[float]:
        out: List[float] = []
        for v in values.values():
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isfinite(fv) and fv >= 0:
                out.append(fv)
        return out

    machine_hours = _finite_non_negative(machine_busy)
    operator_hours = _finite_non_negative(operator_busy)
    horizon = float(makespan_internal_hours)
    machine_util_avg = (sum(machine_hours) / (len(machine_hours) * horizon)) if machine_hours and horizon > 0 else 0.0
    operator_util_avg = (sum(operator_hours) / (len(operator_hours) * horizon)) if operator_hours and horizon > 0 else 0.0
    util_defined = bool(horizon > 0)

    return ScheduleMetrics(
        overdue_count=int(overdue_count),
        total_tardiness_hours=float(tardiness_hours),
        makespan_hours=float(makespan_hours),
        changeover_count=int(changeovers),
        weighted_tardiness_hours=float(weighted_tardiness_hours),
        makespan_internal_hours=float(makespan_internal_hours),
        machine_used_count=int(len(machine_hours)),
        operator_used_count=int(len(operator_hours)),
        machine_busy_hours_total=float(sum(machine_hours) if machine_hours else 0.0),
        operator_busy_hours_total=float(sum(operator_hours) if operator_hours else 0.0),
        machine_util_avg=float(machine_util_avg),
        operator_util_avg=float(operator_util_avg),
        machine_load_cv=float(_cv(machine_hours)),
        operator_load_cv=float(_cv(operator_hours)),
        internal_horizon_hours=float(horizon),
        util_defined=util_defined,
        invalid_due_count=int(invalid_due_count),
        unscheduled_batch_count=int(unscheduled_batch_count),
        invalid_due_batch_ids_sample=invalid_due_batch_ids_sample,
        unscheduled_batch_ids_sample=unscheduled_batch_ids_sample,
    )


def objective_score(objective: str, metrics: ScheduleMetrics) -> Tuple[float, ...]:
    obj = str(objective or "min_overdue").strip().lower()
    if obj == "min_weighted_tardiness":
        return (
            float(metrics.weighted_tardiness_hours),
            float(metrics.total_tardiness_hours),
            float(metrics.makespan_hours),
            float(metrics.changeover_count),
        )
    if obj == "min_makespan":
        return (
            float(metrics.makespan_hours),
            float(metrics.overdue_count),
            float(metrics.total_tardiness_hours),
            float(metrics.changeover_count),
        )
    if obj == "balance_load":
        return (
            float(metrics.machine_load_cv),
            float(metrics.operator_load_cv),
            float(metrics.overdue_count),
            float(metrics.weighted_tardiness_hours),
            float(metrics.makespan_hours),
            float(metrics.changeover_count),
        )
    return (
        float(metrics.overdue_count),
        float(metrics.weighted_tardiness_hours),
        float(metrics.total_tardiness_hours),
        float(metrics.makespan_hours),
        float(metrics.changeover_count),
    )
