"""Saved workbench tasks adapt to the same actual-type sequence as evaluation."""

from core.algorithm_contracts.changeover_events import ChangeoverArrangement, project_changeover_events
from core.services.capacity.plan_calendar_intervals import instant

from .resource_intervals import task_interval


def changeover_projection(tasks, *, start=None, end=None, work_available=True,
                          machine_ref=None, next_operation_refs=None, task_intervals=None):
    arrangements = []
    for task in tasks:
        interval = task_interval(task) if task_intervals is None else task_intervals[task["row_ref"]]
        machine = task.get("machine") or {}
        arrangements.append(ChangeoverArrangement(
            machine_ref=machine.get("ref"), machine_label=machine.get("label"),
            operation_ref=task.get("operation_ref"), row_ref=task.get("row_ref"),
            type_ref=task.get("process_type_ref"), type_label=task.get("process_type_label"),
            start=interval[0] if interval is not None else None,
            end=interval[1] if interval is not None else None,
            source=task.get("source"), point_event=interval is not None and interval[0] == interval[1],
            sort_key=(task.get("operation_ref") or "", task.get("row_ref") or "")))
    return project_changeover_events(
        arrangements, start=instant(start) if start is not None else None, end=instant(end) if end is not None else None,
        work_available=work_available, machine_ref=machine_ref, next_operation_refs=next_operation_refs)
