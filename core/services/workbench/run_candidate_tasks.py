"""Task labels and execution context are projections of the captured generation."""

from datetime import date

from core.models.workbench_run_candidate import local_time

from .run_candidate_values import corrupt, gap, number, text
from .zero_duration import point_event_dto
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


def _resource(facts, kind, key, gaps):
    if key is None or key == "":
        return None
    table = {"machine": "Machines", "operator": "Operators", "supplier": "Suppliers"}[kind]
    row = facts.related(table, key, kind, gaps)
    if not row:
        return None
    ref = facts.entity_refs.get((kind, key))
    if ref is None:
        gaps.append(gap(kind + ".ref", "source_missing"))
    return {"ref": ref, "label": text(row.get("name"), kind + ".label", gaps)}


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


def operation_labels(facts, ref, payload=None):
    gaps = []
    op = facts.operation(ref, payload, gaps)
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
    return result, op


def _expected_task_rows(rows, candidate):
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


def _check_task_payload(payload, expected, seen):
    op = payload.get("op_id")
    if type(op) is not int or op <= 0 or op in seen:
        corrupt()
    seen.add(op)
    if expected is not None and {key: value for key, value in payload.items() if key != "locked"} != expected.get(op):
        corrupt()


def _task_dto(row, facts, start, end):
    ref, payload = row["operation_ref"], row["payload"]
    task, operation = operation_labels(facts, ref, payload)
    gaps = task["data_gaps"]
    task.update(row_ref=row["row_ref"], start=start.isoformat(), end=end.isoformat(),
                source=payload["source"], locked=payload["locked"])
    if start == end:
        task.update(point_event_dto(start, end))
    for kind in ("machine", "operator"):
        task[kind] = _resource(facts, kind, payload.get(kind + "_id"), gaps)
    task["supplier"] = _resource(facts, "supplier", operation.get("supplier_id"), gaps)
    return task


def tasks_projection(rows, candidate, facts):
    expected = _expected_task_rows(rows, candidate)
    result, seen, point_reader = [], set(), None
    for row in rows:
        ref, payload = row["operation_ref"], row["payload"]
        _check_task_payload(payload, expected, seen)
        try:
            start, end = local_time(payload.get("start_time")), local_time(payload.get("end_time"))
            if start > end or payload.get("source") not in ("internal", "external") or type(payload.get("locked")) is not bool:
                corrupt()
            if start == end:
                if point_reader is None:
                    point_reader = CandidatePointReader(candidate, facts)
                point_reader.work(ref, payload)
        except (ValueError, TypeError):
            corrupt()
        result.append(_task_dto(row, facts, start, end))
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
        item.update(row_ref=None, status="skipped" if skipped else "unscheduled",
                    reason={"code": "input_operation_skipped" if skipped else "candidate_operation_unscheduled",
                            "message": "排产时这道工序被排除在外，这里照样列出来。" if skipped else "这个候选方案没有给这道工序排时间。"})
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
