"""Task labels and execution context are projections of the captured generation."""

from datetime import date

from core.models.workbench_run_candidate import local_time

from .candidate_projection import scheduled_ids, uses_task_rows
from .candidate_values import corrupt, gap, number, text
from .zero_duration import PointEventError, point_event_dto
from .zero_duration_evidence import CandidatePointReader, overlaps


def _date(value, field, gaps):
    result = text(value, field, gaps)
    if result is not None:
        try:
            if date.fromisoformat(result).isoformat() == result:
                return result
        except ValueError:
            pass
        gaps.append(gap(field, "invalid_stored_value"))
    return None


def task_resource(facts, kind, key, gaps):
    if key is None or key == "":
        return None
    table = {"machine": "Machines", "operator": "Operators", "supplier": "Suppliers"}[kind]
    row = facts.related(table, key, kind, gaps)
    ref = facts.entity_refs.get((kind, key))
    if ref is None:
        gaps.append(gap(kind + ".ref", "source_missing"))
    return {"ref": ref, "label": text(row.get("name"), kind + ".label", gaps) if row else None}


def _execution(facts, ref, gaps):
    row = facts.execution.get(ref)
    if row is None:
        gaps.append(gap("execution_at_generation", "source_missing"))
        return None
    values = {key: number(row.get(key), "execution_at_generation." + key, gaps, integer=True)
              for key in ("target_quantity", "known_completed_quantity", "remaining_quantity")}
    domains = {"execution_state": ("complete", "paused", "exception", "partial", "started", "unreported"),
               "data_quality": ("invalid", "legacy_incomplete", "incomplete", "complete"), "target_basis": ("piece", "batch")}
    for key, allowed in domains.items():
        value = row.get(key)
        values[key] = value if type(value) is str and value in allowed else None
        if values[key] is None:
            gaps.append(gap("execution_at_generation." + key, "invalid_stored_value"))
    return values


def operation_labels(facts, ref, payload=None, *, prepared=None):
    if prepared is not None:
        op = prepared["operation"]
    else:
        gaps = []
        op = facts.operation(ref, payload, gaps)
    if ref not in facts._operation_labels:
        if prepared is not None:
            gaps = list(prepared["operation_gaps"])
        facts._operation_labels[ref] = _base_operation_labels(facts, ref, op, gaps)
    base = facts._operation_labels[ref]
    result = {**base, "data_gaps": [dict(item) for item in base["data_gaps"]]}
    if base["execution_at_generation"] is not None:
        result["execution_at_generation"] = dict(base["execution_at_generation"])
    return result, op


def _base_operation_labels(facts, ref, op, gaps):
    batch = facts.related("Batches", op.get("batch_id"), "batch", gaps)
    part = facts.related("Parts", batch.get("part_no"), "part", gaps)
    batch_key = op.get("batch_id")
    batch_ref = facts.entity_refs.get(("batch", batch_key)) if type(batch_key) is str else None
    if batch_ref is None:
        gaps.append(gap("batch_ref", "source_missing"))
    piece_id = op.get("piece_id")
    if piece_id is not None or "piece_id" not in op:
        piece_id = text(piece_id, "piece_id", gaps)
    execution = _execution(facts, ref, gaps)
    quantity = execution["target_quantity"] if execution is not None else None
    if (any(item["field"] == "piece_id" for item in gaps) or execution is None
            or execution["target_basis"] != ("piece" if piece_id is not None else "batch")):
        quantity = None
        gaps.append(gap("quantity", "source_missing"))
    result = {"operation_ref": ref, "batch_ref": batch_ref,
              "batch_label": text(batch.get("batch_id"), "batch_label", gaps),
              "part_label": text(part.get("part_name"), "part_label", gaps),
              "sequence": number(op.get("seq"), "sequence", gaps, integer=True),
              "process_label": text(op.get("op_type_name"), "process_label", gaps),
              "piece_id": piece_id, "quantity": quantity,
              "batch_quantity": number(batch.get("quantity"), "batch_quantity", gaps, integer=True),
              "due_date": _date(batch.get("due_date"), "due_date", gaps),
              "execution_at_generation": execution, "data_gaps": gaps}
    result.update(operation_type_labels(facts, op.get("op_type_id")))
    return result


def operation_type_labels(facts, type_id):
    ref = facts.entity_refs.get(("op_type", type_id)) if type(type_id) is str else None
    label = facts.tables.get("OpTypes", {}).get(type_id, {}).get("name") if type(type_id) is str else None
    return {"process_type_ref": ref, "process_type_label": label if type(label) is str else None}


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


def validate_task_payload(payload, expected=None, seen=None):
    if set(payload) != {"op_id", "machine_id", "operator_id", "start_time", "end_time", "source", "locked"}:
        corrupt()
    op = payload.get("op_id")
    if type(op) is not int or op <= 0 or (seen is not None and op in seen):
        corrupt()
    if seen is not None:
        seen.add(op)
    if expected is not None:
        if op not in expected or (expected[op] is not None and
                {key: value for key, value in payload.items() if key != "locked"} != expected[op]):
            corrupt()
    try:
        start, end = local_time(payload.get("start_time")), local_time(payload.get("end_time"))
    except (ValueError, TypeError):
        corrupt()
    if (start > end or payload.get("source") not in ("internal", "external")
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


def validate_saved_tasks(rows, candidate, facts, *, prepared_tasks=None):
    ids = scheduled_ids(candidate)
    expected = _expected_task_rows(rows, candidate, ids)
    intervals, seen, point_reader = {}, set(), None
    for row in rows:
        ref, payload = row["operation_ref"], row["payload"]
        _op, start, end = validate_task_payload(payload, expected, seen)
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
        if prepared_tasks is not None:
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
            task.update(operation_type_labels(facts, trace["op_type_id"]))
        result.append(task)
    return result


def unplanned_projection(disposition, tasks, facts):
    if disposition is None:
        return None
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
        known = {row["batch_ref"] for row in tasks + (unplanned or [])}
        if scope.batch_ref not in known:
            from core.models.workbench_run_candidate import reject
            reject("entity_not_found", "该批次不在候选方案中，请重新选择。", 404)
        tasks = [row for row in tasks if row["batch_ref"] == scope.batch_ref]
        if unplanned is not None:
            unplanned = [row for row in unplanned if row["batch_ref"] == scope.batch_ref]
    if scope.range_start is not None:
        start, end = local_time(scope.range_start), local_time(scope.range_end)
        tasks = [row for row in tasks if overlaps(local_time(row["start"]), local_time(row["end"]), start, end)]

    def order(row):
        value = row[scope.sort]
        if scope.sort == "sequence":
            value = -1 if value is None else int(value)
        return value, row["operation_ref"]

    tasks = sorted(tasks, key=order, reverse=scope.order == "desc")
    if unplanned is not None:
        unplanned = sorted(unplanned, key=lambda row: (int(row["sequence"] or 0), row["operation_ref"]),
                           reverse=scope.order == "desc")
    return tasks, unplanned


def task_span(tasks):
    return {"start": min(row["start"] for row in tasks), "end": max(row["end"] for row in tasks)} if tasks else None
