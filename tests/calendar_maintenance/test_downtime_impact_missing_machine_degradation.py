"""守护停机影响报表留痕契约：machine_id 为空的停机行（仅库外直写可产生）被丢弃时必须与坏时间行同款
降级留痕——missing_machine_row_skipped 计数进 collector、payload 置 report_degraded 并给出可读提示、
导出摘要逐项出现；不传 collector 时保持不炸。"""

from __future__ import annotations

from datetime import datetime

from core.services.common.degradation import DegradationCollector
from core.services.report.downtime_impact import compute_downtime_impact
from core.services.report.report_degradation import (
    report_degradation_payload,
    report_degradation_summary_rows,
)


def _rows():
    return [
        {
            "machine_id": "M1",
            "machine_name": "车床一",
            "start_time": "2026-07-01 08:00:00",
            "end_time": "2026-07-01 10:00:00",
            "reason_code": "maintenance",
            "reason_detail": "",
        },
        {
            "machine_id": "  ",
            "machine_name": "",
            "start_time": "2026-07-01 09:00:00",
            "end_time": "2026-07-01 11:00:00",
            "reason_code": "fault",
            "reason_detail": "",
        },
        {
            "machine_id": "M2",
            "machine_name": "铣床一",
            "start_time": "不是时间",
            "end_time": "2026-07-01 12:00:00",
            "reason_code": "fault",
            "reason_detail": "",
        },
    ]


def test_missing_machine_downtime_row_is_dropped_with_degradation_trace() -> None:
    collector = DegradationCollector()
    items = compute_downtime_impact(
        downtime_rows=_rows(),
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        degradation_collector=collector,
    )

    assert [x["machine_id"] for x in items] == ["M1"], "空设备编号行与坏时间行都不该进结果"

    counters = collector.to_counters()
    assert counters.get("missing_machine_row_skipped") == 1, "空设备编号行必须计数留痕"
    assert counters.get("bad_time_row_skipped") == 1, "坏时间行留痕行为不许被本合同改动"

    payload = report_degradation_payload(collector)
    assert payload["report_degraded"] is True
    assert payload["report_missing_machine_skipped_count"] == 1
    assert "缺少设备编号" in payload["report_degradation_message"]

    summary_rows = report_degradation_summary_rows(payload)
    assert ["缺少设备编号的停机记录数", 1] in summary_rows, "导出摘要必须逐项出现该降级"


def test_missing_machine_row_without_collector_does_not_raise() -> None:
    items = compute_downtime_impact(
        downtime_rows=_rows(),
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
    )
    assert [x["machine_id"] for x in items] == ["M1"]
