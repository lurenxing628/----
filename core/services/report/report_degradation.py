from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.shared.degradation import DegradationCollector, degradation_events_to_dicts

BAD_TIME_MESSAGE = "开始或结束时间写法不对，已过滤。"
MISSING_MACHINE_MESSAGE = "停机记录缺少设备编号，已过滤。"
DOWNTIME_OVERLAP_MESSAGE = "同一设备存在时间重叠的停机记录，停机工时已按合并后时间段计算，不重复计时。"
ZERO_CAPACITY_MESSAGE = "窗口内产能为 0，利用率不适用。"


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


def _safe_missing_machine_sample(row: Mapping[str, Any]) -> Optional[str]:
    parts: List[str] = []
    start_time = _text(row.get("start_time"))
    end_time = _text(row.get("end_time"))
    if start_time or end_time:
        parts.append(f"时间={start_time}~{end_time}")
    reason_code = _text(row.get("reason_code"))
    if reason_code:
        parts.append(f"原因={reason_code}")
    return " / ".join(parts) if parts else None


def record_report_missing_machine_row(
    collector: Optional[DegradationCollector],
    *,
    scope: str,
    row: Mapping[str, Any],
) -> None:
    if collector is None:
        return
    collector.add(
        code="missing_machine_row_skipped",
        scope=scope,
        field="设备编号",
        message=MISSING_MACHINE_MESSAGE,
        sample=_safe_missing_machine_sample(row),
    )


def _fmt_interval(interval: Any) -> str:
    start, end = interval
    return f"{start:%Y-%m-%d %H:%M}~{end:%Y-%m-%d %H:%M}"


def record_report_downtime_overlap_merged(
    collector: Optional[DegradationCollector],
    *,
    scope: str,
    machine_id: str,
    kept: Any,
    merged_in: Any,
) -> None:
    """停机重叠段合并留痕：同机重叠 active 行（并发查后插竞态或库外直写产生）在聚合侧
    按区间归并计时，归并不许静默修数——每合并一处计数一次，样本带设备与重叠区间对。"""
    if collector is None:
        return
    collector.add(
        code="downtime_overlap_merged",
        scope=scope,
        field="时间范围",
        message=DOWNTIME_OVERLAP_MESSAGE,
        sample=f"设备={machine_id} / 重叠区间={_fmt_interval(kept)} 与 {_fmt_interval(merged_in)}",
    )


def record_report_zero_capacity_window(
    collector: Optional[DegradationCollector],
    *,
    scope: str,
    machine_row_count: int,
    operator_row_count: int,
) -> None:
    """零产能窗口留痕：窗口内产能为 0（如整周节假日）时利用率列为 None 是合法语义
    （除零不适用），但不许静默——按受影响资源行数计数，payload/导出摘要给出可读提示。"""
    if collector is None:
        return
    total = int(machine_row_count) + int(operator_row_count)
    if total <= 0:
        return
    collector.add(
        code="zero_capacity_window",
        scope=scope,
        field="利用率",
        message=ZERO_CAPACITY_MESSAGE,
        count=total,
        sample=f"设备行 {int(machine_row_count)} 条 / 人员行 {int(operator_row_count)} 条",
    )


def report_degradation_payload(collector: DegradationCollector) -> Dict[str, Any]:
    counters = collector.to_counters()
    bad_time_count = int(counters.get("bad_time_row_skipped") or 0)
    missing_machine_count = int(counters.get("missing_machine_row_skipped") or 0)
    overlap_merged_count = int(counters.get("downtime_overlap_merged") or 0)
    zero_capacity_count = int(counters.get("zero_capacity_window") or 0)
    unknown_capacity_count = int(counters.get("resource_load_capacity_failed") or 0)
    events = collector.to_list()
    samples = [str(event.sample) for event in events if event.code == "bad_time_row_skipped" and event.sample]
    messages: List[str] = []
    if bad_time_count > 0:
        messages.append(f"已过滤 {bad_time_count} 条开始或结束时间写法不对的记录，下面结果只按可解析记录计算。")
    if missing_machine_count > 0:
        messages.append(f"已过滤 {missing_machine_count} 条缺少设备编号的停机记录。")
    if overlap_merged_count > 0:
        messages.append(f"发现 {overlap_merged_count} 处同设备停机时间重叠，停机工时已按合并后时间段计算，不重复计时。")
    if zero_capacity_count > 0:
        messages.append(f"窗口内产能为 0，共 {zero_capacity_count} 行资源负荷的利用率不适用，利用率列显示为空。")
    if unknown_capacity_count > 0:
        messages.append(f"共 {unknown_capacity_count} 行资源的日历资料不完整，占用率无法计算；具体原因见计算说明。")
    return {
        "report_degraded": bool(collector),
        "report_degradation_events": degradation_events_to_dicts(events),
        "report_degradation_counters": counters,
        "report_degradation_samples": samples[:3],
        "report_degradation_message": "".join(messages),
        "report_bad_time_skipped_count": bad_time_count,
        "report_missing_machine_skipped_count": missing_machine_count,
        "report_downtime_overlap_merged_count": overlap_merged_count,
        "report_zero_capacity_row_count": zero_capacity_count,
    }
