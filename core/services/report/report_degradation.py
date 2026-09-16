from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts

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
    samples = [str(event.sample) for event in collector.to_list() if event.code == "bad_time_row_skipped" and event.sample]
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
        "report_degradation_events": degradation_events_to_dicts(collector.to_list()),
        "report_degradation_counters": counters,
        "report_degradation_samples": samples[:3],
        "report_degradation_message": "".join(messages),
        "report_bad_time_skipped_count": bad_time_count,
        "report_missing_machine_skipped_count": missing_machine_count,
        "report_downtime_overlap_merged_count": overlap_merged_count,
        "report_zero_capacity_row_count": zero_capacity_count,
    }


def report_degradation_summary_rows(degradation: Optional[Mapping[str, Any]]) -> List[List[Any]]:
    data = dict(degradation or {})
    bad_time_count = _summary_count(data, "report_bad_time_skipped_count")
    invalid_due_count = _summary_count(data, "report_invalid_due_count")
    missing_machine_count = _summary_count(data, "report_missing_machine_skipped_count")
    overlap_merged_count = _summary_count(data, "report_downtime_overlap_merged_count")
    zero_capacity_count = _summary_count(data, "report_zero_capacity_row_count")
    # 任意一类降级都要在导出摘要里诚实出现，不能只看坏完工时间数。
    # 否则“仅坏交期、无坏完工时间”时页面有提示而 Excel 摘要静默为空（两条链路口径不一致）。
    degraded = (
        bool(data.get("report_degraded"))
        or bad_time_count > 0
        or invalid_due_count > 0
        or missing_machine_count > 0
        or overlap_merged_count > 0
        or zero_capacity_count > 0
    )
    if not degraded:
        return []
    rows: List[List[Any]] = [["数据不完整", "是"]]
    rows.extend(_bad_time_summary_rows(data, bad_time_count))
    if invalid_due_count > 0:
        rows.append(["交期写法异常批次数", invalid_due_count])
    if missing_machine_count > 0:
        rows.append(["缺少设备编号的停机记录数", missing_machine_count])
    if overlap_merged_count > 0:
        rows.append(["同设备停机时间重叠处数", overlap_merged_count])
    if zero_capacity_count > 0:
        rows.append(["产能为 0 利用率不适用的资源行数", zero_capacity_count])
    rows.append(["处理提示", data.get("report_degradation_message") or ""])
    return rows


def _summary_count(data: Mapping[str, Any], key: str) -> int:
    return int(data.get(key) or 0)


def _bad_time_summary_rows(data: Mapping[str, Any], bad_time_count: int) -> List[List[Any]]:
    if bad_time_count <= 0:
        return []
    count_label = _text(data.get("report_degradation_count_label")) or "开始或结束时间写法不对，已过滤的记录数"
    sample_label = _text(data.get("report_degradation_sample_label")) or "已过滤记录样例"
    samples_text = "；".join(str(item) for item in data.get("report_degradation_samples") or [])
    return [[count_label, bad_time_count], [sample_label, samples_text]]
