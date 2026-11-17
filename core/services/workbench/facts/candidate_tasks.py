"""Task labels and execution context are projections of the captured generation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Set, Tuple

from core.models.workbench_run_candidate import local_time

from .candidate_facts import RESOURCE_TABLES, require_arranged_type
from .candidate_projection import scheduled_ids
from .candidate_values import corrupt, text
from .zero_duration import overlaps, point_event_dto


def task_resource(facts, kind, key, gaps):
    if key is None or key == "":
        return None
    row = facts.related(RESOURCE_TABLES[kind], key)
    return {"ref": facts.entity_ref(kind, key), "label": text(row["name"], kind + ".label", gaps)}


def operation_labels(facts, ref, op_id=None, *, operation=None):
    """An archived operation's labels and the operation; ``operation`` is the row already read for ``ref``."""
    if operation is None:
        operation = facts.operation(ref, op_id)
    base = facts.base_operation_labels(ref, operation)
    # The base is the capture's labels cache (architecture-invariants「可变容器所有权」): callers extend their own
    # gap list and execution context, so both are copied here, at the rewrite point.
    result = {**base, "data_gaps": [dict(item) for item in base["data_gaps"]]}
    if base["execution_at_generation"] is not None:
        result["execution_at_generation"] = dict(base["execution_at_generation"])
    return result, operation


def _task_dto(row, facts, start, end, *, operation):
    task, operation = operation_labels(facts, row["operation_ref"], row["op_id"], operation=operation)
    gaps = task["data_gaps"]
    task.update(row_ref=row["row_ref"], start=start.isoformat(), end=end.isoformat(),
                source=row["source"], locked=row["locked"])
    if start == end:
        task.update(point_event_dto(start, end))
    for kind in ("machine", "operator"):
        task[kind] = task_resource(facts, kind, row[kind + "_id"], gaps)
    task["supplier"] = task_resource(facts, "supplier", operation["supplier_id"], gaps)
    return task


@dataclass(frozen=True)
class ValidatedCandidateTasks:
    """One candidate's saved task rows bound to its scheduled operations; ``prepared_tasks`` holds each row's
    archived operation, read once, by row ref."""

    raw_tasks: List[Dict[str, Any]]
    task_intervals: Dict[str, Tuple[datetime, datetime]]
    scheduled_op_ids: Set[int]
    prepared_tasks: Dict[str, Dict[str, Any]]


def validate_candidate_tasks(store, candidate, facts) -> ValidatedCandidateTasks:
    """Read a candidate's saved tasks once and bind them to its scheduled operations and their archived operations.

    ``CandidateStore.tasks`` reads exactly ``task_count`` rows and the store's candidate record holds
    ``task_count`` equal to the scheduled operations, so the rows and the scheduled operations correspond one to one.
    Each row's ``op_id`` is one of them, once, and the one its ``operation_ref`` was archived for, an operation with
    a type (``require_arranged_type``; one missing from the archive is corrupt); time order, the point flag and
    value domains are the store boundary's. Point events were proven zero-duration when generated
    (``zero_duration.candidate_point_validator``) and their facts are immutable since.
    """
    rows = store.tasks(candidate["candidate_ref"])
    ids = scheduled_ids(candidate)
    intervals: Dict[str, Tuple[datetime, datetime]] = {}
    prepared_tasks: Dict[str, Dict[str, Any]] = {}
    seen: Set[int] = set()
    for row in rows:
        op_id = row["op_id"]
        if op_id in seen or op_id not in ids:
            corrupt()
        seen.add(op_id)
        operation = facts.operation(row["operation_ref"], op_id)
        require_arranged_type(operation)
        prepared_tasks[row["row_ref"]] = operation
        intervals[row["row_ref"]] = (row["start_time"], row["end_time"])
    return ValidatedCandidateTasks(rows, intervals, ids, prepared_tasks)


def project_validated_tasks(rows, facts, intervals, *, prepared_tasks=None):
    result = []
    for row in rows:
        start, end = intervals[row["row_ref"]]
        result.append(_task_dto(row, facts, start, end,
            operation=prepared_tasks[row["row_ref"]] if prepared_tasks is not None else None))
    return result


def unplanned_reason(row: Mapping[str, Any]) -> Dict[str, Any]:
    skipped = row["status"] == "skipped"
    message = "这个候选方案没有给这道工序排时间。"
    if skipped:
        issues = row.get("issues") or []
        material_wait = any(issue.get("code") in ("material_not_ready", "material_after_window") for issue in issues)
        explanations = [issue["message"] for issue in issues if type(issue.get("message")) is str and issue["message"].strip()]
        message = ("缺料未安排：" if material_wait else "排产时未安排：") + (
            "；".join(explanations) if explanations else "具体原因未记录。")
    return {"code": "input_operation_skipped" if skipped else "candidate_operation_unscheduled",
            "message": message}


def unplanned_projection(disposition, tasks, facts):
    scheduled = {row["operation_ref"] for row in tasks}
    result = []
    for ref, row in disposition.items():
        if ref in scheduled:
            continue
        item, _ = operation_labels(facts, ref)
        item.update(row_ref=None, status="skipped" if row["status"] == "skipped" else "unscheduled",
                    reason=unplanned_reason(row))
        result.append(item)
    return result


def scope_workspace_tasks(source, scope):
    facts = source.facts
    raw_tasks = source.raw_tasks
    scheduled_refs = {row["operation_ref"] for row in raw_tasks}
    unplanned_disposition = {ref: row for ref, row in source.disposition.items() if ref not in scheduled_refs}
    if scope.batch_ref is not None:
        known = (
            {facts.operation_batch_ref(row["operation_ref"]) for row in raw_tasks}
            | {facts.operation_batch_ref(ref) for ref in unplanned_disposition}
        )
        if scope.batch_ref not in known:
            from core.models.workbench_run_candidate import reject
            reject("entity_not_found", "该批次不在候选方案中，请重新选择。", 404)
        raw_tasks = [row for row in raw_tasks if facts.operation_batch_ref(row["operation_ref"]) == scope.batch_ref]
        unplanned_disposition = {
            ref: row for ref, row in unplanned_disposition.items()
            if facts.operation_batch_ref(ref) == scope.batch_ref
        }
    if scope.range_start is not None:
        start, end = local_time(scope.range_start), local_time(scope.range_end)
        raw_tasks = [
            row
            for row in raw_tasks
            for low, high in (source.task_intervals[row["row_ref"]],)
            if overlaps(low, high, start, end)
        ]
    tasks = (
        source.tasks
        if len(raw_tasks) == len(source.raw_tasks)
        else source.project_tasks(raw_tasks)
    )
    unplanned = (
        source.unplanned
        if scope.batch_ref is None
        else source.project_unplanned(unplanned_disposition)
    )

    def order(row):
        if scope.sort == "sequence":
            return operation_sequence_order(row)
        return row[scope.sort], row["operation_ref"]

    tasks = sorted(tasks, key=order, reverse=scope.order == "desc")
    unplanned = sorted(unplanned, key=operation_sequence_order, reverse=scope.order == "desc")
    return tasks, unplanned


def operation_sequence_value(value):
    return None if value is None else int(value)


def operation_sequence_order(row):
    """Arranged and unplanned operations share one order: unknown sequences after known ones in
    ascending order (and reversed, so first, in descending order).

    A saved sequence is None when its stored value is missing or damaged, and a string when the
    integer is too large for JSON numbers (candidate_values.number), so it is compared as int.
    """
    sequence = operation_sequence_value(row["sequence"])
    return sequence is None, 0 if sequence is None else sequence, row["operation_ref"]


def interval_span(intervals):
    if not intervals:
        return None
    values = intervals.values()
    return {
        "start": min(start for start, _ in values).isoformat(),
        "end": max(end for _, end in values).isoformat(),
    }


def task_span(tasks):
    return {"start": min(row["start"] for row in tasks), "end": max(row["end"] for row in tasks)} if tasks else None
