"""
排产调度模块（Scheduler）。

Phase 6 范围：
- 批次（Batches）与批次工序（BatchOperations）
- 工作日历（WorkCalendar）
- 排产策略配置（ScheduleConfig）

说明：
- 服务层只依赖 repositories，不在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "BatchService": ".batch_service",
    "CalendarService": ".calendar_service",
    "ConfigService": ".config.config_service",
    "GanttService": ".gantt_service",
    "ResourceDispatchService": ".resource_dispatch_service",
    "ScheduleService": ".schedule_service",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value

__all__ = [
    "BatchService",
    "CalendarService",
    "ConfigService",
    "GanttService",
    "ResourceDispatchService",
    "ScheduleService",
]
