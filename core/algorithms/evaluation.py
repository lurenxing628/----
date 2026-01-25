from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.greedy import ScheduleResult


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overdue_count": int(self.overdue_count),
            "total_tardiness_hours": float(round(self.total_tardiness_hours, 4)),
            "makespan_hours": float(round(self.makespan_hours, 4)),
            "changeover_count": int(self.changeover_count),
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
            tardiness_hours += (fin - due_end).total_seconds() / 3600.0

    makespan_hours = 0.0
    if min_start is not None and max_end is not None and max_end > min_start:
        makespan_hours = (max_end - min_start).total_seconds() / 3600.0

    # changeovers: per machine consecutive op_type change
    by_machine: Dict[str, List[ScheduleResult]] = {}
    for r in results:
        if not r.start_time or not r.end_time:
            continue
        if (r.source or "").strip() != "internal":
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

    return ScheduleMetrics(
        overdue_count=int(overdue_count),
        total_tardiness_hours=float(tardiness_hours),
        makespan_hours=float(makespan_hours),
        changeover_count=int(changeovers),
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

