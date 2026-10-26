"""Task labels and execution context are projections of the captured generation."""

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.workbench_run_candidate import local_time

from .candidate_projection import scheduled_ids, uses_task_rows
from .candidate_values import corrupt, gap, text
from .zero_duration import PointEventError, point_event_dto
from .zero_duration_evidence import CandidatePointReader, overlaps


def task_resource(facts, kind, key, gaps):
    if key is None or key == "":
        return None
    table = {"machine": "Machines", "operator": "Operators", "supplier": "Suppliers"}[kind]
    row = facts.related(table, key, kind, gaps)
    ref = facts.entity_refs.get((kind, key))
    if ref is None:
        gaps.append(gap(kind + ".ref", "source_missing"))
    return {"ref": ref, "label": text(row.get("name"), kind + ".label", gaps) if row else None}


def operation_labels(facts, ref, payload=None, *, prepared=None):
    if prepared is not None:
        op, gaps = prepared["operation"], list(prepared["operation_gaps"])
    else:
        gaps = []
        op = facts.operation(ref, payload, gaps)
    base = facts.base_operation_labels(ref, op, gaps)
    # Callers extend their own gap list and execution context; the capture's shared base stays unchanged.
    result = {**base, "data_gaps": list(base["data_gaps"])}
    if base["execution_at_generation"] is not None:
        result["execution_at_generation"] = dict(base["execution_at_generation"])
    return result, op


def _expected_task_rows(rows, candidate, scheduled_op_ids):
    if uses_task_rows(candidate["artifact"]):
        ids = scheduled_op_ids
        if ids is None or len(ids) != len(rows):
            corrupt()
        return dict.fromkeys(ids)
    validated = candidate["artifact"].get("validated_payload")
    expected = None
    if validated is not None:
        source = validated.get("schedule_rows")
        if type(source) is not list or any(type(row) is not dict for row in source):
            corrupt()
        expected = {row.get("op_id"): row for row in source}
        if len(expected) != len(source) or len(expected) != len(rows):
            corrupt()
    return expected


def validate_task_payload(payload, *, seen, expected=None):
    if set(payload) != {"op_id", "machine_id", "operator_id", "start_time", "end_time", "source", "locked"}:
        corrupt()
    op = payload.get("op_id")
    if type(op) is not int or op <= 0 or op in seen:
        corrupt()
    seen.add(op)
    if expected is not None:
        if op not in expected or (expected[op] is not None and
                {key: value for key, value in payload.items() if key != "locked"} != expected[op]):
            corrupt()
    try:
        start, end = local_time(payload.get("start_time")), local_time(payload.get("end_time"))
    except (ValueError, TypeError):
        corrupt()
    if (start > end or type(payload.get("source")) is not str or payload["source"] not in OPERATION_SOURCES
            or type(payload.get("locked")) is not bool
            or any(payload[key] is not None and type(payload[key]) is not str for key in ("machine_id", "operator_id"))):
        corrupt()
    return op, start, end


def _task_dto(row, facts, start, end, *, prepared):
    ref, payload = row["operation_ref"], row["payload"]
    task, operation = operation_labels(facts, ref, payload, prepared=prepared)
    gaps = task["data_gaps"]
    task.update(row_ref=row["row_ref"], start=start.isoformat(), end=end.isoformat(),
                source=payload["source"], locked=payload["locked"])
    if start == end:
        task.update(point_event_dto(start, end))
    for kind in ("machine", "operator"):
        task[kind] = task_resource(facts, kind, payload.get(kind + "_id"), gaps)
    task["supplier"] = task_resource(facts, "supplier", operation.get("supplier_id"), gaps)
    return task


def tasks_projection_with_intervals(rows, candidate, facts):
    prepared_tasks = {}
    rows, intervals, ids = validate_saved_tasks(rows, candidate, facts, prepared_tasks=prepared_tasks)
    return project_validated_tasks(rows, candidate, facts, intervals, prepared_tasks=prepared_tasks), intervals, ids


def validate_saved_tasks(rows, candidate, facts, *, prepared_tasks):
    ids = scheduled_ids(candidate)
    expected = _expected_task_rows(rows, candidate, ids)
    intervals, seen, point_reader = {}, set(), None
    for row in rows:
        ref, payload = row["operation_ref"], row["payload"]
        _op, start, end = validate_task_payload(payload, seen=seen, expected=expected)
        operation_gaps = []
        point_work = None
        if start == end:
            try:
                if point_reader is None:
                    point_reader = CandidatePointReader(candidate, facts, ids=ids)
                point_work = point_reader.work(ref, payload)
            except (PointEventError, ValueError, TypeError):
                corrupt()
            operation = point_work["operation"]
        else:
            operation = facts.operation(ref, payload, operation_gaps)
        intervals[row["row_ref"]] = (start, end)
        prepared_tasks[row["row_ref"]] = {"operation": operation, "operation_gaps": operation_gaps,
                                           "interval": (start, end), "point_work": point_work}
    return rows, intervals, ids


def project_validated_tasks(rows, candidate, facts, intervals, *, prepared_tasks=None):
    traces = {row["op_id"]: row for row in candidate["artifact"].get("results", [])}
    result = []
    for row in rows:
        start, end = intervals[row["row_ref"]]
        task = _task_dto(row, facts, start, end,
            prepared=prepared_tasks[row["row_ref"]] if prepared_tasks is not None else None)
        trace = traces.get(row["payload"]["op_id"], {})
        if "op_type_id" in trace:
            task.update(facts.operation_type_labels(trace["op_type_id"]))
        result.append(task)
    return result


def unplanned_projection(disposition, tasks, facts):
    scheduled = {row["operation_ref"] for row in tasks}
    result = []
    for ref, row in disposition.items():
        if ref in scheduled:
            continue
        item, _ = operation_labels(facts, ref)
        skipped = row["status"] == "skipped"
        message = "这个候选方案没有给这道工序排时间。"
        if skipped:
            issues = row.get("issues") or []
            material_wait = any(issue.get("code") in ("material_not_ready", "material_after_window") for issue in issues)
            explanations = [issue["message"] for issue in issues if type(issue.get("message")) is str and issue["message"].strip()]
            message = ("缺料未安排：" if material_wait else "排产时未安排：") + (
                "；".join(explanations) if explanations else "具体原因未记录。")
        item.update(row_ref=None, status="skipped" if skipped else "unscheduled",
                    reason={"code": "input_operation_skipped" if skipped else "candidate_operation_unscheduled",
                            "message": message})
        result.append(item)
    return result


def filter_workspace(tasks, unplanned, scope):
    if scope.batch_ref is not None:
        known = {row["batch_ref"] for row in tasks + unplanned}
        if scope.batch_ref not in known:
            from core.models.workbench_run_candidate import reject
            reject("entity_not_found", "该批次不在候选方案中，请重新选择。", 404)
        tasks = [row for row in tasks if row["batch_ref"] == scope.batch_ref]
        unplanned = [row for row in unplanned if row["batch_ref"] == scope.batch_ref]
    if scope.range_start is not None:
        start, end = local_time(scope.range_start), local_time(scope.range_end)
        tasks = [row for row in tasks if overlaps(local_time(row["start"]), local_time(row["end"]), start, end)]

    def order(row):
        if scope.sort == "sequence":
            return _sequence_order(row)
        return row[scope.sort], row["operation_ref"]

    tasks = sorted(tasks, key=order, reverse=scope.order == "desc")
    unplanned = sorted(unplanned, key=_sequence_order, reverse=scope.order == "desc")
    return tasks, unplanned


def _sequence_order(row):
    """Arranged and unplanned operations share one order: unknown sequences after known ones in
    ascending order (and reversed, so first, in descending order).

    A saved sequence is None when its stored value is missing or damaged, and a string when the
    integer is too large for JSON numbers (candidate_values.number), so it is compared as int.
    """
    sequence = row["sequence"]
    return sequence is None, 0 if sequence is None else int(sequence), row["operation_ref"]


def task_span(tasks):
    return {"start": min(row["start"] for row in tasks), "end": max(row["end"] for row in tasks)} if tasks else None
