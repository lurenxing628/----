from __future__ import annotations

from typing import Any, Dict

from core.shared.degradation import DegradationCollector

BAD_TIME_MESSAGE = "开始或结束时间写法不对，已过滤。"
MISSING_MACHINE_MESSAGE = "停机记录缺少设备编号，已过滤。"


def record_report_bad_time_row(
    collector: DegradationCollector,
    *,
    scope: str,
) -> None:
    collector.add(
        code="bad_time_row_skipped",
        scope=scope,
        field="时间范围",
        message=BAD_TIME_MESSAGE,
    )


def record_report_missing_machine_row(
    collector: DegradationCollector,
    *,
    scope: str,
) -> None:
    collector.add(
        code="missing_machine_row_skipped",
        scope=scope,
        field="设备编号",
        message=MISSING_MACHINE_MESSAGE,
    )


def report_degradation_payload(collector: DegradationCollector) -> Dict[str, Any]:
    counters = collector.to_counters()
    bad_time_count = counters.get("bad_time_row_skipped", 0)
    missing_machine_count = counters.get("missing_machine_row_skipped", 0)
    unknown_capacity_count = counters.get("resource_load_capacity_failed", 0)
    return {
        "report_degraded": bool(bad_time_count or missing_machine_count or unknown_capacity_count),
    }
