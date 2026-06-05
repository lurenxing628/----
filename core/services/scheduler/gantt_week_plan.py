from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector

from ._sched_display_utils import (
    BAD_TIME_EMPTY_REASON as _BAD_TIME_EMPTY_REASON,
)
from ._sched_display_utils import (
    display_machine as _display_machine,
)
from ._sched_display_utils import (
    display_operator as _display_operator,
)
from ._sched_display_utils import (
    fmt_day_segment as _fmt_day_segment,
)
from ._sched_display_utils import (
    parse_dt as _parse_dt,
)
from ._sched_display_utils import (
    record_bad_time_row as _record_bad_time_row,
)
from ._sched_display_utils import (
    split_by_day as _split_by_day,
)
from .gantt_range import WeekRange


def _week_plan_interval(
    *,
    row: Mapping[str, Any],
    wr: WeekRange,
    collector: DegradationCollector,
) -> Optional[Tuple[Any, Any]]:
    start = _parse_dt(row.get("start_time"))
    end = _parse_dt(row.get("end_time"))
    if not start or not end or not (start < end):
        _record_bad_time_row(collector, scope="week_plan.rows", row=dict(row))
        return None
    clipped_start = max(start, wr.start_dt)
    clipped_end = min(end, wr.end_dt_exclusive)
    if not (clipped_start < clipped_end):
        return None
    return clipped_start, clipped_end


def _week_plan_resource_cells(row: Mapping[str, Any]) -> Tuple[str, str]:
    machine_cell = _display_machine(row.get("machine_id"), row.get("machine_name"), row.get("supplier_name"))
    operator_cell = _display_operator(row.get("operator_id"), row.get("operator_name"))
    return machine_cell, operator_cell


def _week_plan_segment_row(
    row: Mapping[str, Any],
    *,
    day: Any,
    start: Any,
    end: Any,
    machine_cell: str,
    operator_cell: str,
) -> Dict[str, Any]:
    return {
        "日期": day.isoformat(),
        "批次号": row.get("batch_id") or "",
        "图号": row.get("part_no") or "",
        "工序": row.get("seq") if row.get("seq") is not None else "",
        "设备": machine_cell,
        "人员": operator_cell,
        "时段": _fmt_day_segment(start, end),
    }


def _week_plan_sort_key(item: Mapping[str, Any]) -> Tuple[Any, Any, Any, Any, Any]:
    return (
        item.get("日期") or "",
        item.get("设备") or "",
        item.get("人员") or "",
        item.get("批次号") or "",
        item.get("工序") or "",
    )


def _week_plan_empty_reason(out: Sequence[Mapping[str, Any]], collector: DegradationCollector) -> Optional[str]:
    if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        return _BAD_TIME_EMPTY_REASON
    return None


def build_week_plan_rows(*, rows: Sequence[Mapping[str, Any]], wr: WeekRange) -> BuildOutcome[List[Dict[str, Any]]]:
    """
    生成周计划行（用于页面预览与导出）。

    字段：日期/批次号/图号/工序/设备/人员/时段
    """
    collector = DegradationCollector()
    out: List[Dict[str, Any]] = []
    for row in rows:
        interval = _week_plan_interval(row=row, wr=wr, collector=collector)
        if interval is None:
            continue
        # 周计划口径：与甘特图一致。外协/未分配时不硬置为 "-"，而是显示外协提示/供应商。
        machine_cell, operator_cell = _week_plan_resource_cells(row)
        for d0, a0, b0 in _split_by_day(*interval):
            out.append(
                _week_plan_segment_row(
                    row,
                    day=d0,
                    start=a0,
                    end=b0,
                    machine_cell=machine_cell,
                    operator_cell=operator_cell,
                )
            )

    out.sort(key=_week_plan_sort_key)
    return BuildOutcome.from_collector(out, collector, empty_reason=_week_plan_empty_reason(out, collector))
