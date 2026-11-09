"""Saved workbench tasks adapt to the same actual-type sequence as evaluation."""

from core.algorithm_contracts.changeover_events import ChangeoverArrangement, project_changeover_events
from core.services.capacity.plan_calendar_intervals import instant


def subject_arrangements(tasks, operation_refs, *, task_intervals):
    """Select the compared work without adding full-sequence predecessors."""
    selected = set(operation_refs)
    result = []
    for task in tasks:
        if task["source"] != "internal" or task["operation_ref"] not in selected:
            continue
        interval = task_intervals[task["row_ref"]]
        if interval is None or interval[0] != interval[1]:
            result.append(task)
    return result


def changeover_projection(tasks, *, start=None, end=None, work_available=True,
                          next_operation_refs=None, task_intervals):
    low = instant(start) if start is not None else None
    high = instant(end) if end is not None else None
    arrangements = []
    if work_available:
        for task in tasks:
            interval = task_intervals[task["row_ref"]]
            machine = task["machine"]
            arrangements.append(ChangeoverArrangement(
                machine_ref=machine["ref"] if machine is not None else None,
                machine_label=machine["label"] if machine is not None else None,
                operation_ref=task["operation_ref"], row_ref=task["row_ref"],
                type_ref=task["process_type_ref"], type_label=task["process_type_label"],
                start=interval[0] if interval is not None else None,
                end=interval[1] if interval is not None else None,
                source=task["source"], point_event=interval is not None and interval[0] == interval[1],
                sort_key=(task["operation_ref"], task["row_ref"])))
    return project_changeover_events(
        arrangements, start=low, end=high, work_available=work_available, next_operation_refs=next_operation_refs)
