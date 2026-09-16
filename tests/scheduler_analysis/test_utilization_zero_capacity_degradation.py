"""守护利用率报表零产能窗口留痕契约（B10）：窗口内产能为 0（如整周节假日）时利用率整列 None
是合法语义（除零不适用），但不许静默空白——必须按受影响资源行数计数进 collector、payload 置
report_degraded 并给出可读提示、导出摘要逐项出现；不许把 None 改成 0 之类的错数；
正常产能窗口与空结果窗口不受影响；不传 collector 不炸。"""

from __future__ import annotations

from datetime import datetime

from core.services.common.degradation import DegradationCollector
from core.services.report.report_degradation import (
    report_degradation_payload,
    report_degradation_summary_rows,
)
from core.services.report.utilization import compute_utilization


def _schedule_rows():
    return [
        {
            "machine_id": "M1",
            "machine_name": "车床一",
            "operator_id": "P1",
            "operator_name": "张三",
            "start_time": "2026-07-01 08:00:00",
            "end_time": "2026-07-01 10:00:00",
            "source": "internal",
        }
    ]



def _calendars(working):
    calendar = {"state": "available", "issues": [], "windows": [{"start": "2026-07-01T08:00:00",
        "end": "2026-07-01T16:00:00", "allow_normal": True, "allow_urgent": True}] if working else []}
    return {("machine", "M1"): calendar, ("operator", "P1"): calendar}


def test_zero_capacity_window_keeps_none_and_leaves_trace() -> None:
    collector = DegradationCollector()
    machine_rows, operator_rows = compute_utilization(
        schedule_rows=_schedule_rows(),
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        calendars=_calendars(False),
        degradation_collector=collector,
    )

    # None 语义保留：除零不适用，不许改成 0 之类的错数。
    assert machine_rows[0]["utilization"] is None
    assert operator_rows[0]["utilization"] is None
    assert machine_rows[0]["hours"] == 0.0
    assert machine_rows[0]["outside_calendar_hours"] == 2.0

    counters = collector.to_counters()
    assert counters.get("zero_capacity_window") == 2, "设备行+人员行各 1 行都要计数留痕"

    payload = report_degradation_payload(collector)
    assert payload["report_degraded"] is True
    assert payload["report_zero_capacity_row_count"] == 2
    assert "产能为 0" in payload["report_degradation_message"]
    assert "利用率不适用" in payload["report_degradation_message"]

    summary_rows = report_degradation_summary_rows(payload)
    assert ["产能为 0 利用率不适用的资源行数", 2] in summary_rows, "导出摘要必须逐项出现该降级"


def test_positive_capacity_window_unaffected() -> None:
    collector = DegradationCollector()
    machine_rows, operator_rows = compute_utilization(
        schedule_rows=_schedule_rows(),
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        calendars=_calendars(True),
        degradation_collector=collector,
    )
    assert machine_rows[0]["utilization"] == 0.25
    assert operator_rows[0]["utilization"] == 0.25
    assert not collector, "正常产能窗口不许留痕"

    payload = report_degradation_payload(collector)
    assert payload["report_degraded"] is False
    assert payload["report_zero_capacity_row_count"] == 0
    assert report_degradation_summary_rows(payload) == []


def test_zero_capacity_window_without_rows_leaves_no_trace() -> None:
    collector = DegradationCollector()
    machine_rows, operator_rows = compute_utilization(
        schedule_rows=[],
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        calendars=_calendars(False),
        degradation_collector=collector,
    )
    assert machine_rows == [] and operator_rows == []
    assert not collector, "没有受影响行就没有降级事实，不许虚报"


def test_zero_capacity_window_without_collector_does_not_raise() -> None:
    machine_rows, _operator_rows = compute_utilization(
        schedule_rows=_schedule_rows(),
        start_dt=datetime(2026, 7, 1),
        end_dt_excl=datetime(2026, 7, 2),
        calendars=_calendars(False),
    )
    assert machine_rows[0]["utilization"] is None
