"""Workbench write contexts; execution aggregation has one neutral owner."""

from dataclasses import replace

from core.services.execution.projection import project_execution as project_execution
from core.services.execution.projection import report_dto as report_dto


def attach_context(projection, factory, snapshot):
    writable = bool(projection.current_task_ref and projection.plan_identity and
                    projection.plan_identity["capabilities"]["report_actual"] and projection.data_quality != "invalid")
    if factory is None or not writable:
        return projection
    reports = [replace(report, write_context=factory(report.report_ref, ["supplement", "correct"], snapshot))
               for report in projection.reports]
    return replace(projection, reports=reports, write_context=factory(projection.current_task_ref, ["create"], snapshot))
