from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts

BAD_TIME_MESSAGE = "开始或结束时间写法不对，已过滤。"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_bad_time_sample(row: Mapping[str, Any]) -> Optional[str]:
    parts: List[str] = []
    batch_id = _text(row.get("batch_id"))
    if batch_id:
        parts.append(f"批次号={batch_id}")
    machine_id = _text(row.get("machine_id"))
    if machine_id:
        parts.append(f"设备={machine_id}")
    operator_id = _text(row.get("operator_id"))
    if operator_id:
        parts.append(f"人员={operator_id}")
    return " / ".join(parts) if parts else None


def record_report_bad_time_row(
    collector: Optional[DegradationCollector],
    *,
    scope: str,
    row: Mapping[str, Any],
) -> None:
    if collector is None:
        return
    collector.add(
        code="bad_time_row_skipped",
        scope=scope,
        field="时间范围",
        message=BAD_TIME_MESSAGE,
        sample=_safe_bad_time_sample(row),
    )


def report_degradation_payload(collector: DegradationCollector) -> Dict[str, Any]:
    counters = collector.to_counters()
    bad_time_count = int(counters.get("bad_time_row_skipped") or 0)
    samples = [str(event.sample) for event in collector.to_list() if event.code == "bad_time_row_skipped" and event.sample]
    message = ""
    if bad_time_count > 0:
        message = f"已过滤 {bad_time_count} 条开始或结束时间写法不对的记录，下面结果只按可解析记录计算。"
    return {
        "report_degraded": bool(collector),
        "report_degradation_events": degradation_events_to_dicts(collector.to_list()),
        "report_degradation_counters": counters,
        "report_degradation_samples": samples[:3],
        "report_degradation_message": message,
        "report_bad_time_skipped_count": bad_time_count,
    }


def report_degradation_summary_rows(degradation: Optional[Mapping[str, Any]]) -> List[List[Any]]:
    data = dict(degradation or {})
    bad_time_count = int(data.get("report_bad_time_skipped_count") or 0)
    if bad_time_count <= 0:
        return []
    count_label = _text(data.get("report_degradation_count_label")) or "开始或结束时间写法不对，已过滤的记录数"
    sample_label = _text(data.get("report_degradation_sample_label")) or "已过滤记录样例"
    return [
        ["数据不完整", "是"],
        [count_label, bad_time_count],
        [sample_label, "；".join(str(item) for item in data.get("report_degradation_samples") or [])],
        ["处理提示", data.get("report_degradation_message") or ""],
    ]
