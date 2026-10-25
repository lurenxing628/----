from __future__ import annotations

from typing import Any, Dict, Iterable, List

FREEZE_WINDOW_DEGRADED_MESSAGE = "冻结窗口资料不完整，本次排产未使用冻结窗口。"

_PUBLIC_EVENT_MESSAGES = {
    "config_fallback": "配置里有填写不完整或不正确的内容，本次先按默认值生成摘要。",
    "freeze_seed_unavailable": FREEZE_WINDOW_DEGRADED_MESSAGE,
    "invalid_due_date": "部分交期数据无法使用，本次已按可确认数据继续。",
    "invalid_choice": "部分选项填得不对，本次先按默认值处理。",
    "invalid_number": "部分数字填得不对，本次先按默认值处理。",
    "missing_required": "部分必填内容缺失，本次先按默认值处理。",
    "blank_required": "部分必填内容为空，本次先按默认值处理。",
    "number_below_minimum": "部分数字小于允许范围，本次先按默认值处理。",
    "ortools_warmstart_failed": "系统没能复用上一次的排产结果，本次已从头重新计算。结果仍然有效，但耗时可能更长。",
    "graph_enhancement_degraded": "工序图报告已生成，但图增强排队因循环依赖关闭，本次退回普通排法。",
    "dispatch_failure_details": "部分工序没有形成有效排程，摘要已保留失败和跳过明细。",
    "resource_load_capacity_failed": "部分日期的容量暂时算不了，相关负荷格按「利用率暂时算不了」显示。",
    "bad_time_row_skipped": "有些甘特记录的开始或结束时间写法不对，页面已先过滤。",
    "plugin_bootstrap_db_unavailable": "扩展功能设置暂时读不到，当前按默认开关运行。",
    "plugin_bootstrap_config_read_failed": "扩展功能设置读取失败，当前按默认开关运行。",
    "plugin_bootstrap_load_failed": "插件加载失败，请联系维护人员检查系统运行记录。",
    "plugin_bootstrap_telemetry_failed": "扩展功能启动记录写入失败，请联系维护人员检查系统运行记录。",
}


def public_degradation_event_message(code: object) -> str:
    normalized = str(code or "").strip()
    return _PUBLIC_EVENT_MESSAGES.get(normalized) or "排产摘要里有需要注意的提示。"


def _public_degradation_event_code(code: object) -> str:
    normalized = str(code or "").strip()
    if normalized in _PUBLIC_EVENT_MESSAGES:
        return normalized
    return "scheduler_degradation"


def public_degradation_events(events: Iterable[Any]) -> List[Dict[str, Any]]:
    by_code: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for event in events or ():
        code = str(event.get("code") or "").strip()
        if not code:
            continue
        public_code = _public_degradation_event_code(code)
        count = max(1, int(event.get("count") or 1))
        if public_code not in by_code:
            order.append(public_code)
            by_code[public_code] = {
                "code": public_code,
                "message": public_degradation_event_message(code),
                "count": 0,
            }
        by_code[public_code]["count"] += count
    return [by_code[code] for code in order]


__all__ = [
    "FREEZE_WINDOW_DEGRADED_MESSAGE",
    "public_degradation_events",
    "public_degradation_event_message",
]
