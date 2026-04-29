from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

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
    fmt_hhmm as _fmt_hhmm,
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


def build_week_plan_rows(*, rows: Sequence[Mapping[str, Any]], wr: WeekRange) -> BuildOutcome[List[Dict[str, Any]]]:
    """
    生成周计划行（用于页面预览与导出）。

    字段：日期/批次号/图号/工序/设备/人员/时段
    """
    collector = DegradationCollector()
    out: List[Dict[str, Any]] = []
    for row in rows:
        st = _parse_dt(row.get("start_time"))
        et = _parse_dt(row.get("end_time"))
        if not st or not et or not (st < et):
            _record_bad_time_row(collector, scope="week_plan.rows", row=dict(row))
            continue

        st2 = max(st, wr.start_dt)
        et2 = min(et, wr.end_dt_exclusive)
        if not (st2 < et2):
            continue

        machine_disp = _display_machine(row.get("machine_id"), row.get("machine_name"), row.get("supplier_name"))
        operator_disp = _display_operator(row.get("operator_id"), row.get("operator_name"))
        # 周计划口径：与甘特图一致。外协/未分配时不硬置为 "-"，而是显示外协提示/供应商。
        machine_cell = machine_disp
        operator_cell = operator_disp

        parts = _split_by_day(st2, et2)
        for d0, a0, b0 in parts:
            out.append(
                {
                    "日期": d0.isoformat(),
                    "批次号": row.get("batch_id") or "",
                    "图号": row.get("part_no") or "",
                    "工序": row.get("seq") if row.get("seq") is not None else "",
                    "设备": machine_cell,
                    "人员": operator_cell,
                    "时段": f"{_fmt_hhmm(a0)}-{_fmt_hhmm(b0)}",
                }
            )

    out.sort(
        key=lambda item: (
            item.get("日期") or "",
            item.get("设备") or "",
            item.get("人员") or "",
            item.get("批次号") or "",
            item.get("工序") or "",
        )
    )
    empty_reason = None
    if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(out, collector, empty_reason=empty_reason)
