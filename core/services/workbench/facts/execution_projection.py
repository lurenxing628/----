"""Workbench write contexts; execution aggregation has one neutral owner."""

from dataclasses import replace

from core.services.execution.projection import project_execution as project_execution
from core.services.execution.projection import report_dto as report_dto

# 报工状态、完成依据与资料完整性的用户显示值只有这一份，导出和下载都从这里取。
# 词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md。
EXECUTION_STATE_TEXT = {"unreported": "待报工", "started": "已开工", "partial": "部分完成",
                        "paused": "已暂停", "exception": "异常", "complete": "已完工"}
COMPLETION_BASIS_TEXT = {"complete_reports": "完整逐次报工", "legacy_finish_event": "历史完工记录"}
DATA_QUALITY_TEXT = {"complete": "完整", "incomplete": "不完整", "legacy_incomplete": "历史资料不完整", "invalid": "需复核"}


def attach_context(projection, factory, snapshot):
    writable = bool(projection.current_task_ref and projection.plan_identity and
                    projection.plan_identity["capabilities"]["report_actual"] and projection.data_quality != "invalid")
    if factory is None or not writable:
        return projection
    reports = [replace(report, write_context=factory(report.report_ref, ["supplement", "correct", "report_void"], snapshot))
               for report in projection.reports]
    return replace(projection, reports=reports, write_context=factory(projection.current_task_ref, ["create"], snapshot))
