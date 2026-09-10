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
    "GanttAdjustmentDraftService": ".gantt_adjustment_draft_service",
    "GanttAdjustmentScenarioService": ".gantt_adjustment_scenario_service",
    "GanttAdjustmentPublishService": ".gantt_adjustment_publish_service",
    "GanttAdjustmentValidationService": ".gantt_adjustment_validation_service",
    "GanttService": ".gantt_service",
    "OperationExecutionFeedbackService": ".operation_execution_feedback_service",
    "ResourceDispatchActualRecordService": ".resource_dispatch_actual_record_service",
    "ResourceDispatchExecutionService": ".resource_dispatch_execution_service",
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
    "GanttAdjustmentDraftService",
    "GanttAdjustmentScenarioService",
    "GanttAdjustmentPublishService",
    "GanttAdjustmentValidationService",
    "GanttService",
    "OperationExecutionFeedbackService",
    "ResourceDispatchActualRecordService",
    "ResourceDispatchExecutionService",
    "ResourceDispatchService",
    "ScheduleService",
]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .batch_service import BatchService
    from .calendar_service import CalendarService
    from .config.config_service import ConfigService
    from .gantt_adjustment_draft_service import GanttAdjustmentDraftService
    from .gantt_adjustment_publish_service import GanttAdjustmentPublishService
    from .gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
    from .gantt_adjustment_validation_service import GanttAdjustmentValidationService
    from .gantt_service import GanttService
    from .operation_execution_feedback_service import OperationExecutionFeedbackService
    from .resource_dispatch_actual_record_service import ResourceDispatchActualRecordService
    from .resource_dispatch_execution_service import ResourceDispatchExecutionService
    from .resource_dispatch_service import ResourceDispatchService
    from .schedule_service import ScheduleService
