"""现场事实公开展示标签单源（契约 4.10）。

把 ExecutionFact 映射成中文展示标签字典——所有「现场实际」展示（甘特详情面板、
批次详情排程去向卡等）都消费这里，禁各处重复实现标签映射造成口径分叉。raw 状态码与
内部计划身份字段只在服务端消费、绝不进输出。输出以公开 *_label / has_execution_record
为主；另含两个裸 actual_start_time/actual_end_time 格式化字符串，仅为甘特 tooltip 旧合同
保留（见下方返回处注释），新消费方只取 *_label 白名单、不消费这两个裸键。

由 fusion-batch-detail-schedule-card 从 gantt_tasks._execution_detail_meta
抽取并去前缀公开（只搬不改行为）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED
from core.models.operation_execution_labels import execution_status_label

from ._sched_display_utils import fmt_dt, parse_dt


def _fmt_fact_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return fmt_dt(value)
    parsed = parse_dt(value)
    return fmt_dt(parsed) if parsed else ""


def _fact_has_site_record(fact: Any) -> bool:
    if fact is None:
        return False
    if getattr(fact, "actual_start_time", None) is not None:
        return True
    if getattr(fact, "actual_end_time", None) is not None:
        return True
    status = str(getattr(fact, "actual_status", "") or "").strip()
    return bool(status and status != EXECUTION_STATUS_NOT_STARTED)


def execution_detail_meta(fact: Any) -> Dict[str, Any]:
    status = str(getattr(fact, "actual_status", "") or "").strip() or EXECUTION_STATUS_NOT_STARTED
    status_label = execution_status_label(status)
    actual_start = _fmt_fact_dt(getattr(fact, "actual_start_time", None))
    actual_end = _fmt_fact_dt(getattr(fact, "actual_end_time", None))
    has_record = _fact_has_site_record(fact)
    if not has_record:
        summary = "暂未记录现场实际"
    else:
        parts = [f"现场状态：{status_label}"]
        if actual_start:
            parts.append(f"实际开工：{actual_start}")
        if actual_end:
            parts.append(f"实际完工：{actual_end}")
        if not actual_start and not actual_end:
            parts.append("暂未填写实际开工和完工")
        summary = "；".join(parts)
    return {
        "execution_status_label": status_label,
        # 裸 actual_start_time/actual_end_time 是甘特 tooltip 旧合同所需；新消费方（如批次卡）
        # 只取下面的 *_label/has_execution_record 白名单，不外显裸时间。
        "actual_start_time": actual_start,
        "actual_end_time": actual_end,
        "actual_start_time_label": actual_start or "暂无实际开工",
        "actual_end_time_label": actual_end or "暂无实际完工",
        "actual_summary_label": summary,
        "has_execution_record": has_record,
    }
