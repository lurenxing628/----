"""甘特资源×日桶负荷聚合（fusion-gantt-load-strip，契约 4.6 第二个落地实例）。

分子：内部行（source=internal，外协不占内部容量）按 split_by_day 切自然日、
clamp 到 wr 窗口后的重叠小时数累加；分母：capacity_hours_at_noon 单源 helper
（正午采样 shift_hours×efficiency，刻意不调 calculations.capacity_hours——
midnight 采样在跨午夜班次错归属，4.6 红线）。容量≤0 或日历异常时 ratio 置
None 不伪装 0，由 web 装饰层映射 severity=unknown。

输出行仅公开字段（date/resource_id/resource_label/hours/capacity_hours/ratio）；
severity 与跳转 links 属 Web 展示语义，归 web/viewmodels 装饰层——core 不
import web 阈值常量。新文件而非 gantt_service.py：500 行门禁 + 4.6
「新容量逻辑必须落新文件」双约束。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.models.enums import SourceType
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector

from ._sched_display_utils import (
    capacity_hours_at_noon,
    display_machine,
    display_operator,
    parse_dt,
    split_by_day,
)
from .gantt_range import WeekRange

# Top-N 承接老 roadmap item 11「最忙资源摘要」：条带按周内总负荷降序最多 5 行
MAX_STRIP_ROWS = 5


def _row_resource(view: str, row: Mapping[str, Any]) -> Tuple[str, str]:
    if view == "machine":
        rid = str(row.get("machine_id") or "").strip()
        label = display_machine(row.get("machine_id"), row.get("machine_name"), row.get("supplier_name"))
    else:
        rid = str(row.get("operator_id") or "").strip()
        label = display_operator(row.get("operator_id"), row.get("operator_name"))
    return rid, label


def _capacity_or_none(calendar: Any, day: Any, failed_days: Dict[str, str]) -> Optional[float]:
    try:
        return capacity_hours_at_noon(calendar, day)
    except Exception as exc:  # 日历单日异常：当日 ratio 诚实置 None，不让整条带炸掉
        failed_days[day.isoformat()] = exc.__class__.__name__
        return None


def _accumulate_hours(
    view: str,
    rows: Sequence[Mapping[str, Any]],
    wr: WeekRange,
) -> Tuple[Dict[Tuple[str, str], float], Dict[str, str]]:
    """分子累加：内部行 clamp 到窗口、split_by_day 切日桶，按 (resource_id, date) 求和。

    外协/无资源 id 的行跳过（不计数不报错——它们不占内部容量）；坏时间行
    跳过但不登记（同一 rows 已由 build_tasks 计数，避免一行报两次）。
    """
    hours_by_key: Dict[Tuple[str, str], float] = {}
    label_by_resource: Dict[str, str] = {}
    for row in rows or []:
        if str(row.get("source") or "").strip().lower() != SourceType.INTERNAL.value:
            continue
        rid, label = _row_resource(view, row)
        if not rid:
            continue
        st = parse_dt(row.get("start_time"))
        et = parse_dt(row.get("end_time"))
        if not st or not et or not (st < et):
            continue
        st2 = max(st, wr.start_dt)
        et2 = min(et, wr.end_dt_exclusive)
        if not (st2 < et2):
            continue
        label_by_resource[rid] = label
        for day, seg_start, seg_end in split_by_day(st2, et2):
            seconds = (seg_end - seg_start).total_seconds()
            if seconds <= 0:
                continue
            key = (rid, day.isoformat())
            hours_by_key[key] = hours_by_key.get(key, 0.0) + seconds / 3600.0
    return hours_by_key, label_by_resource


def _build_load_rows(
    hours_by_key: Dict[Tuple[str, str], float],
    label_by_resource: Dict[str, str],
    calendar: Any,
    failed_days: Dict[str, str],
) -> List[Dict[str, Any]]:
    capacity_by_date: Dict[str, Optional[float]] = {}
    out: List[Dict[str, Any]] = []
    for (rid, day_key), hours in hours_by_key.items():
        if day_key not in capacity_by_date:
            day = datetime.strptime(day_key, "%Y-%m-%d").date()
            capacity_by_date[day_key] = _capacity_or_none(calendar, day, failed_days)
        capacity = capacity_by_date[day_key]
        ratio = round(hours / capacity, 4) if capacity is not None and capacity > 0 else None
        out.append(
            {
                "date": day_key,
                "resource_id": rid,
                "resource_label": label_by_resource.get(rid, rid),
                "hours": round(hours, 2),
                "capacity_hours": round(capacity, 2) if capacity is not None else None,
                "ratio": ratio,
            }
        )
    total_by_resource: Dict[str, float] = {}
    for item in out:
        total_by_resource[item["resource_id"]] = total_by_resource.get(item["resource_id"], 0.0) + item["hours"]
    out.sort(key=lambda item: (-total_by_resource[item["resource_id"]], item["resource_id"], item["date"]))
    return out


def compute_gantt_resource_day_load(
    *,
    view: str,
    rows: Sequence[Mapping[str, Any]],
    wr: WeekRange,
    calendar: Any,
) -> BuildOutcome[List[Dict[str, Any]]]:
    """按 (resource_id, date) 聚合负荷行，按资源周内总负荷降序、同资源内按日期升序。"""
    collector = DegradationCollector()
    failed_days: Dict[str, str] = {}
    hours_by_key, label_by_resource = _accumulate_hours(view, rows, wr)
    out = _build_load_rows(hours_by_key, label_by_resource, calendar, failed_days)
    if failed_days:
        sample = "、".join(sorted(failed_days)[:3])
        collector.add(
            code="resource_load_capacity_failed",
            scope="gantt.resource_load",
            field="capacity_hours",
            message=f"部分日期的容量暂时算不了（{sample} 等 {len(failed_days)} 天），相关负荷格按「利用率暂时算不了」显示。",
            sample="、".join(sorted(set(failed_days.values()))[:3]),
        )
    return BuildOutcome.from_collector(out, collector)


__all__ = ["MAX_STRIP_ROWS", "compute_gantt_resource_day_load"]
