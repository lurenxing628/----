from __future__ import annotations

from typing import Any, Iterable

DOWNTIME_LOAD_FAILED_MESSAGE = "停机区间加载失败，本次排产已降级为忽略停机约束。"
DOWNTIME_EXTEND_FAILED_MESSAGE = "停机区间扩展加载失败，候选设备可能未覆盖停机约束。"
FREEZE_WINDOW_DEGRADED_MESSAGE = "冻结窗口约束已降级，本次排产未应用冻结窗口种子。"
FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE = "冻结窗口约束已降级，本次排产已应用可确认的冻结窗口种子，部分工序未冻结。"
RESOURCE_POOL_BUILD_FAILED_MESSAGE = "自动分配资源池构建失败，本次排产已降级为不自动分配资源。"
SCHEDULE_OPERATION_FAILED_MESSAGE = "工序排产异常，请查看系统日志。"

_PUBLIC_EVENT_MESSAGES = {
    "config_fallback": "配置快照存在兼容回退，摘要已按标准化配置生成。",
    "input_fallback": "输入构建存在兼容回退，摘要已按标准化输入生成。",
    "freeze_seed_unavailable": FREEZE_WINDOW_DEGRADED_MESSAGE,
    "freeze_window_degraded": FREEZE_WINDOW_DEGRADED_MESSAGE,
    "freeze_window_partially_applied": FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
    "downtime_avoid_degraded": DOWNTIME_LOAD_FAILED_MESSAGE,
    "resource_pool_degraded": RESOURCE_POOL_BUILD_FAILED_MESSAGE,
    "summary_merge_failed": "摘要告警合并已降级。",
    "invalid_due_date": "交期数据已降级。",
    "invalid_choice": "配置字段已按兼容值标准化。",
    "invalid_number": "数值字段已按兼容值标准化。",
    "missing_required": "缺失字段已按兼容值标准化。",
    "blank_required": "空白字段已按兼容值标准化。",
    "number_below_minimum": "数值字段低于下限，已按兼容值标准化。",
    "legacy_external_days_defaulted": "历史外协周期已按兼容默认值处理。",
    "template_missing": "组合合同模板上下文已降级。",
    "external_group_missing": "组合并外部组上下文已降级。",
    "merge_context_degraded": "组合并语义已降级。",
    "ortools_warmstart_failed": "预热已降级。",
    "calendar_load_failed": "工作日历加载失败，当前不显示假期/停工背景标注。",
    "bad_time_row_skipped": "存在时间不合法的甘特记录，已过滤。",
    "critical_chain_unavailable": "关键链暂不可用，当前不显示关键链控制前驱箭头与外框高亮。",
    "plugin_bootstrap_db_unavailable": "插件配置数据库不可用，当前按默认开关运行。",
    "plugin_bootstrap_config_reader_failed": "插件配置读取器初始化失败，当前按默认开关运行。",
    "plugin_bootstrap_config_read_failed": "插件配置读取失败，当前按默认开关运行。",
    "plugin_bootstrap_status_snapshot_failed": "插件状态读取失败，当前仅展示可用的插件状态。",
    "plugin_bootstrap_telemetry_failed": "插件启动留痕写入失败，请查看系统日志。",
}

_PUBLIC_WARNING_MESSAGES = {
    "冻结窗口存在跳批风险",
    "停机区间加载失败，已按默认能力继续",
    "存在 1 个批次未命中首选技能",
    "资源池已降级",
}

_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}


def public_degradation_event_message(code: object) -> str:
    normalized = str(code or "").strip()
    return _PUBLIC_EVENT_MESSAGES.get(normalized) or "排产摘要存在可见退化。"


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


def public_summary_warning_messages(value: Any) -> list[str]:
    if value is None:
        raw_items: list[Any] = []
    elif isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = [value]

    out: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if not text or text not in _PUBLIC_WARNING_MESSAGES or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def public_summary_merge_error_code(value: Any) -> str | None:
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


def public_degradation_events(events: Iterable[Any]) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    order: list[str] = []
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
