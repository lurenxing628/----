from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED
from core.models.operation_execution_labels import execution_status_label
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
    duration_minutes as _duration_minutes,
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
    execution_status_cell: str,
) -> Dict[str, Any]:
    return {
        "日期": day.isoformat(),
        "批次号": row.get("batch_id") or "",
        "图号": row.get("part_no") or "",
        "工序": row.get("seq") if row.get("seq") is not None else "",
        "设备": machine_cell,
        "人员": operator_cell,
        "时段": _fmt_day_segment(start, end),
        "现场状态": execution_status_cell,
    }


def _week_plan_execution_status_cell(
    row: Mapping[str, Any],
    execution_facts_by_op_id: Optional[Mapping[int, Any]],
) -> str:
    """行级现场状态（状态属于工序：同工序跨日所有段行同值）。

    facts 为 None = 调用方不提供事实 → "-"（导出同口径）；
    提供后无 fact 的工序按「待开工」（计划行没有事实=尚未开工，
    与甘特详情 _execution_detail_meta 缺省一致，不是数据缺口）。
    """
    if execution_facts_by_op_id is None:
        return "-"
    try:
        op_id = int(row.get("op_id") or 0)
    except (TypeError, ValueError):
        op_id = 0
    fact = execution_facts_by_op_id.get(op_id) if op_id > 0 else None
    status = str(getattr(fact, "actual_status", "") or "").strip() or EXECUTION_STATUS_NOT_STARTED
    return execution_status_label(status)


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


def build_week_plan_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    wr: WeekRange,
    execution_facts_by_op_id: Optional[Mapping[int, Any]] = None,
) -> Tuple[BuildOutcome[List[Dict[str, Any]]], Dict[str, int]]:
    """
    生成周计划行（用于页面预览与导出）。

    字段：日期/批次号/图号/工序/设备/人员/时段/现场状态。
    第二返回值 minutes_by_date 是按日计划分钟数旁路（每日合计的聚合源）——
    段行 dict 自始至终零内部键，聚合数据与公开 rows 物理分离（契约 4.6）。
    """
    collector = DegradationCollector()
    out: List[Dict[str, Any]] = []
    minutes_by_date: Dict[str, int] = {}
    for row in rows:
        interval = _week_plan_interval(row=row, wr=wr, collector=collector)
        if interval is None:
            continue
        # 周计划口径：与甘特图一致。外协/未分配时不硬置为 "-"，而是显示外协提示/供应商。
        machine_cell, operator_cell = _week_plan_resource_cells(row)
        # 现场状态在 _split_by_day 之前按 op_id 取一次（拆分后段行无 op_id）
        execution_status_cell = _week_plan_execution_status_cell(row, execution_facts_by_op_id)
        for d0, a0, b0 in _split_by_day(*interval):
            day_key = d0.isoformat()
            minutes_by_date[day_key] = minutes_by_date.get(day_key, 0) + _duration_minutes(a0, b0)
            out.append(
                _week_plan_segment_row(
                    row,
                    day=d0,
                    start=a0,
                    end=b0,
                    machine_cell=machine_cell,
                    operator_cell=operator_cell,
                    execution_status_cell=execution_status_cell,
                )
            )

    out.sort(key=_week_plan_sort_key)
    outcome = BuildOutcome.from_collector(out, collector, empty_reason=_week_plan_empty_reason(out, collector))
    return outcome, minutes_by_date
