"""Permanent-operation task intervals, counted and queried without daily rescans."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

from core.services.capacity.plan_calendar_intervals import instant, segments, union

KINDS = ("machine", "operator")


def task_interval(task):
    if task.get("interval_comparable") is False:
        return None
    try:
        start, end = instant(task.get("start")), instant(task.get("end"))
    except (ValueError, TypeError, OverflowError):
        return None
    if start == end:
        return (start, end) if task.get("event_kind") == "point" and task.get("occupies_resources") is False else None
    return (start, end) if start < end else None


def resource_cohort(task_pools, *, task_intervals=None):
    """Saved resource identities involved across every compared object's tasks."""
    resources = {}
    for source_index, tasks in enumerate(task_pools):
        for task in tasks:
            interval = task_interval(task) if task_intervals is None else task_intervals[source_index][task["row_ref"]]
            if task.get("source") == "external" or interval is not None and interval[0] == interval[1]:
                continue
            for kind in KINDS:
                value = task.get(kind)
                if value is not None and value.get("ref") is not None:
                    key = (kind, value["ref"])
                    resources.setdefault(key, {"ref": value["ref"], "kind": kind, "label": value.get("label")})
    return [resources[key] for key in sorted(resources)]


class _OverlapNode:
    """Balanced interval tree enumerates only rows intersecting a requested day."""

    def __init__(self, rows):
        middle = len(rows) // 2
        self.row = rows[middle]
        self.left = _OverlapNode(rows[:middle]) if middle else None
        self.right = _OverlapNode(rows[middle + 1:]) if middle + 1 < len(rows) else None
        self.low = rows[0][0]
        self.high = max(self.row[1], self.left.high if self.left else self.row[1],
                        self.right.high if self.right else self.row[1])

    def query(self, start, end, result):
        if self.high <= start or self.low >= end:
            return
        if self.left:
            self.left.query(start, end, result)
        if self.row[0] < end and self.row[1] > start:
            result.append(self.row)
        if self.right:
            self.right.query(start, end, result)


class ResourceIntervals:
    """One resource's valid rows and independent operation demand segments."""

    def __init__(self, rows: List[Tuple[datetime, datetime, Dict[str, Any]]], unknown: List[Dict[str, Any]]):
        self.rows = sorted(rows, key=lambda row: (row[0], row[1], row[2].get("row_ref") or ""))
        self.unknown = unknown
        self.starts = [row[0] for row in self.rows]
        self.ends = sorted(row[1] for row in self.rows)
        grouped = defaultdict(list)
        for start, end, task in rows:
            grouped[task["operation_ref"]].append((start, end))
        self.operations = {ref: union(values) for ref, values in grouped.items()}
        self.intervals = [item for values in self.operations.values() for item in values]
        self._tree = None
        self._swept = None

    @property
    def swept(self):
        if self._swept is None:
            self._swept = segments(self.intervals)
        return self._swept

    def counts(self, start, end):
        if start == end:
            return 0, 0
        tasks = bisect_left(self.starts, end) - bisect_right(self.ends, start)
        operations = len({row[2]["operation_ref"] for row in self.overlapping(start, end)})
        return tasks, operations

    def overlapping(self, start, end):
        if not self.rows or start == end:
            return []
        if self._tree is None:
            self._tree = _OverlapNode(self.rows)
        result = []
        self._tree.query(start, end, result)
        return result


def details(rows, unknown, start, end):
    """Sweep actual active rows; conflicts count distinct permanent operations."""
    events = defaultdict(list)
    for index, (low, high, task) in enumerate(rows):
        events[max(start, low)].append((True, index, task))
        events[min(end, high)].append((False, index, task))
    active, previous, conflicts = {}, None, []
    for at in sorted(events):
        operations = sorted({task["operation_ref"] for task in active.values()})
        if previous is not None and previous < at and len(operations) > 1:
            row_refs = sorted({task["row_ref"] for task in active.values()})
            value = {"start": previous.isoformat(), "end": at.isoformat(),
                     "operation_refs": operations, "row_refs": row_refs}
            if conflicts and conflicts[-1]["end"] == value["start"] and all(
                conflicts[-1][key] == value[key] for key in ("operation_refs", "row_refs")
            ):
                conflicts[-1]["end"] = value["end"]
            else:
                conflicts.append(value)
        for adding, index, task in events[at]:
            if adding:
                active[index] = task
            else:
                active.pop(index, None)
        previous = at
    fields = ("row_ref", "operation_ref", "batch_ref", "batch_label", "process_label", "start", "end")
    tasks = [{key: task.get(key) for key in fields} for _, _, task in rows]
    tasks.extend({key: task.get(key) for key in fields} for task in unknown)
    return {"conflicts": conflicts, "tasks": tasks}
