"""守护停机影响报表重叠段归并契约（B13 聚合侧）：同机重叠 active 停机行必须按标准区间归并后计时——
downtime_hours / schedule_overlap_hours 只计并集不双计，downtime_count 仍按原始记录数计；
检测到重叠必须降级留痕（downtime_overlap_merged 计数进 collector、payload 置 report_degraded
并给出可读提示、导出摘要逐项出现）；不重叠/仅首尾相接的行为保持原样零留痕；不传 collector 不炸。"""

from __future__ import annotations

from datetime import datetime

from core.services.common.degradation import DegradationCollector
from core.services.report.downtime_impact import compute_downtime_impact
from core.services.report.report_degradation import (
    report_degradation_payload,
    report_degradation_summary_rows,
)


def _row(machine_id: str, start: str, end: str) -> dict:
    return {
        "machine_id": machine_id,
        "machine_name": f"设备{machine_id}",
        "start_time": start,
        "end_time": end,
        "reason_code": "maintenance",
        "reason_detail": "",
    }


def _schedule_row(machine_id: str, start: str, end: str) -> dict:
    return {
        "machine_id": machine_id,
        "start_time": start,
        "end_time": end,
        "source": "internal",
    }


def test_overlapping_downtime_rows_counted_once_with_degradation_trace() -> None:
    collector = DegradationCollector()
    items = compute_downtime_impact(
        downtime_rows=[
            _row("M1", "2026-07-01 08:00:00", "2026-07-01 12:00:00"),
            _row("M1", "2026-07-01 10:00:00", "2026-07-01 14:00:00"),
        ],
        schedule_rows=[_schedule_row("M1", "2026-07-01 09:00:00", "2026-07-01 13:00:00")],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        degradation_collector=collector,
    )

    assert len(items) == 1
    item = items[0]
    # 并集 08:00~14:00 = 6h，而不是 4h+4h=8h 的重叠双计。
    assert item["downtime_hours"] == 6.0
    # 排产 09:00~13:00 与并集重叠 4h，而不是 3h+3h=6h。
    assert item["schedule_overlap_hours"] == 4.0
    assert item["schedule_overlap_count"] == 1
    # 停机记录数仍按原始行数计，归并只改时间口径。
    assert item["downtime_count"] == 2

    counters = collector.to_counters()
    assert counters.get("downtime_overlap_merged") == 1, "重叠归并必须计数留痕"

    payload = report_degradation_payload(collector)
    assert payload["report_degraded"] is True
    assert payload["report_downtime_overlap_merged_count"] == 1
    assert "停机时间重叠" in payload["report_degradation_message"]

    events = [e for e in collector.to_list() if e.code == "downtime_overlap_merged"]
    assert events and "设备=M1" in str(events[0].sample), "样本必须带设备与重叠区间对"

    summary_rows = report_degradation_summary_rows(payload)
    assert ["同设备停机时间重叠处数", 1] in summary_rows, "导出摘要必须逐项出现该降级"


def test_downtime_hours_capped_by_window_even_with_many_overlaps() -> None:
    collector = DegradationCollector()
    items = compute_downtime_impact(
        downtime_rows=[
            _row("M1", "2026-07-01 00:00:00", "2026-07-02 00:00:00"),
            _row("M1", "2026-07-01 06:00:00", "2026-07-01 18:00:00"),
            _row("M1", "2026-07-01 08:00:00", "2026-07-01 20:00:00"),
        ],
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        degradation_collector=collector,
    )
    # 归并后不可能超过窗口总长 24h（修复前 = 24+12+12 = 48h）。
    assert items[0]["downtime_hours"] == 24.0
    assert items[0]["downtime_count"] == 3
    assert collector.to_counters().get("downtime_overlap_merged") == 2


def test_disjoint_and_touching_rows_keep_behavior_without_trace() -> None:
    collector = DegradationCollector()
    items = compute_downtime_impact(
        downtime_rows=[
            _row("M1", "2026-07-01 08:00:00", "2026-07-01 10:00:00"),
            # 首尾相接不算重叠，不留痕。
            _row("M1", "2026-07-01 10:00:00", "2026-07-01 12:00:00"),
            _row("M2", "2026-07-01 09:00:00", "2026-07-01 11:00:00"),
        ],
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        degradation_collector=collector,
    )
    by_machine = {x["machine_id"]: x for x in items}
    assert by_machine["M1"]["downtime_hours"] == 4.0
    assert by_machine["M1"]["downtime_count"] == 2
    assert by_machine["M2"]["downtime_hours"] == 2.0
    assert not collector, "无重叠不许留痕"

    payload = report_degradation_payload(collector)
    assert payload["report_degraded"] is False
    assert payload["report_downtime_overlap_merged_count"] == 0


def test_overlapping_rows_without_collector_do_not_raise() -> None:
    items = compute_downtime_impact(
        downtime_rows=[
            _row("M1", "2026-07-01 08:00:00", "2026-07-01 12:00:00"),
            _row("M1", "2026-07-01 10:00:00", "2026-07-01 14:00:00"),
        ],
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
    )
    assert items[0]["downtime_hours"] == 6.0
