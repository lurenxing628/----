from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import statistics
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.types import ScheduleResult


def _parse_due_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value or "").strip()
    if not s:
        return None
    s = s.replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overdue_count": int(self.overdue_count),
            "total_tardiness_hours": float(round(self.total_tardiness_hours, 4)),
            "makespan_hours": float(round(self.makespan_hours, 4)),
            "changeover_count": int(self.changeover_count),
            "weighted_tardiness_hours": float(round(self.weighted_tardiness_hours, 4)),
            "makespan_internal_hours": float(round(self.makespan_internal_hours, 4)),
            "machine_used_count": int(self.machine_used_count),
            "operator_used_count": int(self.operator_used_count),
            "machine_busy_hours_total": float(round(self.machine_busy_hours_total, 4)),
            "operator_busy_hours_total": float(round(self.operator_busy_hours_total, 4)),
            "machine_util_avg": float(round(self.machine_util_avg, 6)),
            "operator_util_avg": float(round(self.operator_util_avg, 6)),
            "machine_load_cv": float(round(self.machine_load_cv, 6)),
            "operator_load_cv": float(round(self.operator_load_cv, 6)),
        }


def compute_metrics(results: List[ScheduleResult], batches: Dict[str, Any]) -> ScheduleMetrics:
    # finish time per batch
    finish_by_batch: Dict[str, datetime] = {}
    min_start: Optional[datetime] = None
    max_end: Optional[datetime] = None

    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if min_start is None or r.start_time < min_start:
            min_start = r.start_time
        if max_end is None or r.end_time > max_end:
            max_end = r.end_time
        cur = finish_by_batch.get(r.batch_id)
        if cur is None or r.end_time > cur:
            finish_by_batch[r.batch_id] = r.end_time

    overdue_count = 0
    tardiness_hours = 0.0
    weighted_tardiness_hours = 0.0
    priority_weight = {"normal": 1.0, "urgent": 2.0, "critical": 3.0}
    for bid, b in batches.items():
        due_d = _parse_due_date(getattr(b, "due_date", None))
        if not due_d:
            continue
        fin = finish_by_batch.get(bid)
        if not fin:
            continue
        due_end = datetime(due_d.year, due_d.month, due_d.day, 23, 59, 59)
        if fin > due_end:
            overdue_count += 1
            delta_h = (fin - due_end).total_seconds() / 3600.0
            tardiness_hours += delta_h
            pr = str(getattr(b, "priority", "") or "normal").strip().lower() or "normal"
            w = float(priority_weight.get(pr, 1.0))
            weighted_tardiness_hours += (delta_h * w)

    makespan_hours = 0.0
    if min_start is not None and max_end is not None and max_end > min_start:
        makespan_hours = (max_end - min_start).total_seconds() / 3600.0

    # changeovers: per machine consecutive op_type change
    by_machine: Dict[str, List[ScheduleResult]] = {}
    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if (r.source or "").strip().lower() != "internal":
            continue
        mid = (r.machine_id or "").strip()
        if not mid:
            continue
        by_machine.setdefault(mid, []).append(r)

    changeovers = 0
    for mid, lst in by_machine.items():
        lst.sort(key=lambda x: (x.start_time or datetime.min, x.end_time or datetime.min, x.op_id))
        prev = None
        for r in lst:
            cur = (r.op_type_name or "").strip()
            if prev is None:
                prev = cur
                continue
            if cur != prev:
                changeovers += 1
            prev = cur

    # utilization & load balance（internal only）
    min_int: Optional[datetime] = None
    max_int: Optional[datetime] = None
    machine_busy: Dict[str, float] = {}
    operator_busy: Dict[str, float] = {}
    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if (r.source or "").strip().lower() != "internal":
            continue
        st = r.start_time
        et = r.end_time
        if et <= st:
            continue
        if min_int is None or st < min_int:
            min_int = st
        if max_int is None or et > max_int:
            max_int = et
        mid = (r.machine_id or "").strip()
        if mid:
            machine_busy[mid] = machine_busy.get(mid, 0.0) + (et - st).total_seconds() / 3600.0
        oid = (r.operator_id or "").strip()
        if oid:
            operator_busy[oid] = operator_busy.get(oid, 0.0) + (et - st).total_seconds() / 3600.0

    makespan_internal_hours = 0.0
    if min_int is not None and max_int is not None and max_int > min_int:
        makespan_internal_hours = (max_int - min_int).total_seconds() / 3600.0

    def _cv(vals: List[float]) -> float:
        if not vals:
            return 0.0
        m = statistics.fmean(vals)
        if m <= 0:
            return 0.0
        if len(vals) < 2:
            return 0.0
        return float(statistics.pstdev(vals) / m)

    machine_hours = list(machine_busy.values())
    operator_hours = list(operator_busy.values())
    horizon = makespan_internal_hours
    machine_util_avg = float(statistics.fmean([h / horizon for h in machine_hours])) if horizon > 0 and machine_hours else 0.0
    operator_util_avg = float(statistics.fmean([h / horizon for h in operator_hours])) if horizon > 0 and operator_hours else 0.0

    return ScheduleMetrics(
        overdue_count=int(overdue_count),
        total_tardiness_hours=float(tardiness_hours),
        makespan_hours=float(makespan_hours),
        changeover_count=int(changeovers),
        weighted_tardiness_hours=float(weighted_tardiness_hours),
        makespan_internal_hours=float(makespan_internal_hours),
        machine_used_count=int(len(machine_busy)),
        operator_used_count=int(len(operator_busy)),
        machine_busy_hours_total=float(sum(machine_hours) if machine_hours else 0.0),
        operator_busy_hours_total=float(sum(operator_hours) if operator_hours else 0.0),
        machine_util_avg=float(machine_util_avg),
        operator_util_avg=float(operator_util_avg),
        machine_load_cv=float(_cv(machine_hours)),
        operator_load_cv=float(_cv(operator_hours)),
    )


def objective_score(objective: str, metrics: ScheduleMetrics) -> Tuple[float, ...]:
    """
    目标函数（越小越好）。

    objective 取值（V1.1）：
    - min_overdue: 优先最小化超期批次数，其次总拖期小时，再其次 makespan，再其次换型次数
    - min_tardiness: 优先最小化总拖期小时，其次超期批次数，再其次 makespan，再其次换型次数
    - min_changeover: 优先最小化换型次数，其次超期批次数，再其次总拖期小时，再其次 makespan
    """
    obj = (objective or "min_overdue").strip().lower()
    if obj == "min_tardiness":
        return (metrics.total_tardiness_hours, float(metrics.overdue_count), metrics.makespan_hours, float(metrics.changeover_count))
    if obj == "min_changeover":
        return (float(metrics.changeover_count), float(metrics.overdue_count), metrics.total_tardiness_hours, metrics.makespan_hours)
    # default: min_overdue
    return (float(metrics.overdue_count), metrics.total_tardiness_hours, metrics.makespan_hours, float(metrics.changeover_count))

