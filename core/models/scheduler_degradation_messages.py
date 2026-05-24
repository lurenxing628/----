from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

DOWNTIME_LOAD_FAILED_MESSAGE = "停机区间加载失败，本次排产先不使用停机约束。"
DOWNTIME_EXTEND_FAILED_MESSAGE = "停机区间扩展加载失败，部分自动安排设备可能还没有避开停机时间。"
FREEZE_WINDOW_DEGRADED_MESSAGE = "冻结窗口资料不完整，本次排产未使用冻结窗口。"
FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE = "冻结窗口资料不完整，本次只保留能确认的冻结工序。"
RESOURCE_POOL_BUILD_FAILED_MESSAGE = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
AUTO_ASSIGN_RESOURCE_MISSING_MESSAGE = "自动分配已启用，但可用设备或人员资料缺失，自制工序无法自动分配设备或人员。"
SCHEDULE_OPERATION_FAILED_MESSAGE = "工序排产异常，请联系维护人员检查系统运行记录。"

_PUBLIC_EVENT_MESSAGES = {
    "config_fallback": "配置里有填写不完整或不正确的内容，本次先按默认值生成摘要。",
    "input_fallback": "排产输入里有填写不完整或不正确的数据，本次先按可确认的数据生成摘要。",
    "freeze_seed_unavailable": FREEZE_WINDOW_DEGRADED_MESSAGE,
    "freeze_window_degraded": FREEZE_WINDOW_DEGRADED_MESSAGE,
    "freeze_window_partially_applied": FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
    "downtime_avoid_degraded": DOWNTIME_LOAD_FAILED_MESSAGE,
    "resource_pool_degraded": RESOURCE_POOL_BUILD_FAILED_MESSAGE,
    "summary_merge_failed": "排产完成了，但部分提示没有整理好。请到系统管理里的排产历史查看这次排产的详细提醒。",
    "invalid_due_date": "部分交期数据无法使用，本次已按可确认数据继续。",
    "invalid_choice": "部分选项填得不对，本次先按默认值处理。",
    "invalid_number": "部分数字填得不对，本次先按默认值处理。",
    "missing_required": "部分必填内容缺失，本次先按默认值处理。",
    "blank_required": "部分必填内容为空，本次先按默认值处理。",
    "number_below_minimum": "部分数字小于允许范围，本次先按默认值处理。",
    "legacy_external_days_defaulted": "部分外协周期缺失或填写不对，本次先按 1 天计算。",
    "template_missing": "组合合同模板资料不完整，本次未使用这项资料。",
    "external_group_missing": "组合并外协组资料不完整，本次未使用这项资料。",
    "merge_context_degraded": "组合并资料不完整，本次按可确认内容继续。",
    "ortools_warmstart_failed": "系统没能复用上一次的排产结果，本次已从头重新计算。结果仍然有效，但耗时可能更长。",
    "calendar_load_failed": "工作日历加载失败，当前不显示假期/停工背景标注。",
    "bad_time_row_skipped": "有些甘特记录的开始或结束时间写法不对，页面已先过滤。",
    "critical_chain_unavailable": "关键工序关系暂时算不出来，所以甘特图不会显示关键工序的箭头和高亮框。排产结果本身仍可查看。",
    "plugin_bootstrap_db_unavailable": "扩展功能设置暂时读不到，当前按默认开关运行。",
    "plugin_bootstrap_config_reader_failed": "扩展功能设置读取器初始化失败，当前按默认开关运行。",
    "plugin_bootstrap_config_read_failed": "扩展功能设置读取失败，当前按默认开关运行。",
    "plugin_bootstrap_load_failed": "插件加载失败，请联系维护人员检查系统运行记录。",
    "plugin_bootstrap_status_snapshot_failed": "扩展功能状态读取失败，当前仅展示可用的状态。",
    "plugin_bootstrap_telemetry_failed": "扩展功能启动记录写入失败，请联系维护人员检查系统运行记录。",
}

_PUBLIC_RESOURCE_POOL_WARNING_MESSAGE = RESOURCE_POOL_BUILD_FAILED_MESSAGE

_PUBLIC_WARNING_MESSAGES = {
    "冻结窗口存在跳批风险",
    "停机区间加载失败，本次先按常规能力继续",
    "存在 1 个批次未命中首选技能",
    "开始时间无法解析，本次已改用当前时间。",
    "截止日期无法解析，本次已忽略这个截止日期。",
    AUTO_ASSIGN_RESOURCE_MISSING_MESSAGE,
    _PUBLIC_RESOURCE_POOL_WARNING_MESSAGE,
}

_PUBLIC_NORMALIZED_START_TIME_WARNING_RE = re.compile(
    r"^开始时间已规范化为：\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
)
_PUBLIC_UNSCHEDULED_BATCH_WARNING_RE = re.compile(
    r"^存在 \d+ 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。$"
)

_PUBLIC_FIELD_WARNING_LABELS = {
    "运行期配置快照",
    "开始时间",
    "截止日期",
    "排序策略",
    "派工方式",
    "派工规则",
    "策略参数",
    "优先级权重",
    "交期权重",
    "就绪权重",
    "自动分配",
}

_PUBLIC_FIELD_WARNING_MESSAGES = {
    _PUBLIC_EVENT_MESSAGES["invalid_choice"],
    _PUBLIC_EVENT_MESSAGES["invalid_number"],
    _PUBLIC_EVENT_MESSAGES["missing_required"],
    _PUBLIC_EVENT_MESSAGES["blank_required"],
    _PUBLIC_EVENT_MESSAGES["number_below_minimum"],
}

_PUBLIC_WARNING_MESSAGE_ALIASES = {
    RESOURCE_POOL_BUILD_FAILED_MESSAGE: _PUBLIC_RESOURCE_POOL_WARNING_MESSAGE,
    "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员（请查看日志）。": _PUBLIC_RESOURCE_POOL_WARNING_MESSAGE,
}

_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}


def public_degradation_event_message(code: object) -> str:
    normalized = str(code or "").strip()
    return _PUBLIC_EVENT_MESSAGES.get(normalized) or "排产摘要里有需要注意的提示。"


def _public_degradation_event_code(code: object) -> str:
    normalized = str(code or "").strip()
    if normalized in _PUBLIC_EVENT_MESSAGES:
        return normalized
    return "scheduler_degradation"


def is_public_freeze_degradation_message(message: object) -> bool:
    return str(message or "").strip() in {
        FREEZE_WINDOW_DEGRADED_MESSAGE,
        FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
    }


def _is_public_summary_warning_message(text: str) -> bool:
    return (
        text in _PUBLIC_WARNING_MESSAGES
        or _PUBLIC_NORMALIZED_START_TIME_WARNING_RE.fullmatch(text) is not None
        or _PUBLIC_UNSCHEDULED_BATCH_WARNING_RE.fullmatch(text) is not None
        or _is_public_field_warning_message(text)
    )


def _is_public_field_warning_message(text: str) -> bool:
    field_label, sep, message = str(text or "").partition("：")
    if sep != "：":
        return False
    return field_label in _PUBLIC_FIELD_WARNING_LABELS and message in _PUBLIC_FIELD_WARNING_MESSAGES


def public_summary_warning_messages(value: Any) -> List[str]:
    if value is None:
        raw_items: List[Any] = []
    elif isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = [value]

    out: List[str] = []
    seen = set()
    for item in raw_items:
        text = str(item or "").strip()
        public_text = _PUBLIC_WARNING_MESSAGE_ALIASES.get(text, text)
        if (
            not public_text
            or not _is_public_summary_warning_message(public_text)
            or public_text in seen
        ):
            continue
        seen.add(public_text)
        out.append(public_text)
    return out


def public_summary_merge_error_code(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text in _SUMMARY_MERGE_ERROR_CODES:
        return text
    return "summary_warnings_assignment_failed"


def _event_value(event: Any, key: str) -> Any:
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key, None)


def public_degradation_events(events: Iterable[Any]) -> List[Dict[str, Any]]:
    by_code: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for event in list(events or []):
        code = str(_event_value(event, "code") or "").strip()
        if not code:
            continue
        public_code = _public_degradation_event_code(code)
        try:
            count = max(1, int(_event_value(event, "count") or 1))
        except Exception:
            count = 1
        if public_code not in by_code:
            order.append(public_code)
            by_code[public_code] = {
                "code": public_code,
                "message": public_degradation_event_message(code),
                "count": 0,
            }
        by_code[public_code]["count"] = int(by_code[public_code].get("count") or 0) + count
    return [by_code[code] for code in order]


__all__ = [
    "DOWNTIME_EXTEND_FAILED_MESSAGE",
    "DOWNTIME_LOAD_FAILED_MESSAGE",
    "FREEZE_WINDOW_DEGRADED_MESSAGE",
    "FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE",
    "SCHEDULE_OPERATION_FAILED_MESSAGE",
    "RESOURCE_POOL_BUILD_FAILED_MESSAGE",
    "is_public_freeze_degradation_message",
    "public_degradation_events",
    "public_degradation_event_message",
    "public_summary_merge_error_code",
    "public_summary_warning_messages",
]
