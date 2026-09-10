"""Verify captured whole rows and permanent membership before projecting a baseline."""

from types import SimpleNamespace

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .plan_adoption_baseline_values import fail, indexed, raw_rows, require, same, schedule_rows
from .plan_projection import project_tasks, public_time


def verify_capture(baseline, tables):
    version = baseline["version"]
    history = tables["ScheduleHistory"]
    require(all(type(row.get("version")) is int and row["version"] > 0 for row in history), "archived_history_versions")
    require(version == max((row["version"] for row in history), default=None), "archived_official_baseline")
    require(version is None or type(version) is int, "baseline_version_type")
    archived = sorted((row for row in tables["Schedule"] if row["version"] == version), key=lambda row: row["id"])
    require(same(archived, baseline["rows"]), "baseline_matches_archived_schedule")
    if version is None:
        require(baseline["plan_ref"] is None and not baseline["rows"], "empty_baseline")
        return
    if len(archived) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected("query_too_large", "采用时完整基线超过10000条上限，未截断。", 413)
    require(bool(archived), "baseline_complete_row_count")
    _captured_official(baseline, tables)


def _captured_official(baseline, tables):
    official = [row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "official"
                and row["active"] == 1 and row["version"] == baseline["version"]]
    require(len(official) == 1 and official[0]["ref"] == baseline["plan_ref"]
            and official[0]["source_table"] == "schedule" and official[0]["plan_role"] == "adopted",
            "archived_official_reference")


def _live_sources(conn, captured):
    by_ref = indexed(captured, "ref")
    keys, live = list(by_ref), {}
    for start in range(0, len(keys), 400):
        chunk = keys[start:start + 400]
        marks = ",".join("?" for _ in chunk)
        live.update(indexed(raw_rows(conn, "WorkbenchPlanSourceRefs", where="ref IN (" + marks + ")", params=chunk), "ref"))
    if not same(by_ref, live):
        fail("adoption_reference_invalid", "captured_source_instances")


def verify_arranged(conn, plan_ref, version, tables, arranged):
    rows = schedule_rows(conn, version)
    originals, current = indexed(arranged, "op_id"), indexed(rows, "op_id")
    if set(originals) != set(current):
        fail("adoption_plan_drift", "selected_complete_operation_set")
    for op_id, original in originals.items():
        if not _arrangement_matches(current[op_id], original):
            fail("adoption_plan_drift", "selected_saved_arrangement")
    references = WorkbenchPlanIdentityRepository(conn)
    try:
        references.get_task_refs(plan_ref, [dict(row, schedule_id=row["id"]) for row in rows])
        operations = references.get_operation_refs(current)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "selected_complete_task_identity")
    keys = {str(key) for key in current}
    sources = [row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "operation"
               and row["active"] == 1 and row["source_key"] in keys]
    require(len(sources) == len(current), "captured_selected_operations")
    if {int(row["source_key"]): row["ref"] for row in sources} != operations:
        fail("adoption_reference_invalid", "selected_original_operation_instances")
    _live_sources(conn, sources)
    return rows


def _arrangement_matches(row, original):
    expected = {key: original[key] for key in ("machine_id", "operator_id")}
    actual = {key: row[key] for key in expected}
    if not same(expected, actual):
        return False
    for key in ("start_time", "end_time"):
        if type(row[key]) is not str or type(original[key]) is not str or public_time(row[key]) != public_time(original[key]):
            return False
    return True


def baseline_tasks(conn, baseline, tables, facts, *, point_annotator=None):
    ref, version = baseline["plan_ref"], baseline["version"]
    references = WorkbenchPlanIdentityRepository(conn)
    if not conn.execute("SELECT 1 FROM ScheduleHistory WHERE version=?", (version,)).fetchone():
        fail("adoption_baseline_archived", "ScheduleHistory.original_version")
    try:
        locator = references.resolve_plan(ref)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "baseline.plan_ref")
    if locator != WorkbenchPlanLocator(version, "adopted"):
        fail("adoption_reference_invalid", "baseline.official_locator")
    rows = schedule_rows(conn, version)
    facts["observed_baseline_rows"] = rows
    captured = baseline["rows"]
    if not {row["id"] for row in captured} <= {row["id"] for row in rows}:
        fail("adoption_baseline_archived", "Schedule.original_rows")
    if not same(rows, captured):
        fail("adoption_baseline_drift", "Schedule.complete_original_values_and_types")
    task_refs, operations = _task_bindings(conn, baseline, tables, references)
    resources = _resources(conn, captured, tables)
    ops, batches = indexed(tables["BatchOperations"], "id"), indexed(tables["Batches"], "batch_id")
    detail = []
    for row in captured:
        op = ops.get(row["op_id"])
        if op is None or op["batch_id"] not in batches:
            fail(gap="baseline.original_operation_and_batch")
        detail.append({**row, "schedule_id": row["id"], "batch_id": op["batch_id"],
                       "seq": op["seq"], "piece_id": op["piece_id"], "op_type_name": op["op_type_name"], "supplier_id": None})
    # As in RunBaseline, Schedule has no historical supplier/effective-hours field.
    if point_annotator is not None:
        detail = point_annotator(detail)
    return project_tasks(ref, detail, task_refs, operations, resources, conn=conn)


def _captured_tasks(baseline, tables):
    ref, version, rows = baseline["plan_ref"], baseline["version"], baseline["rows"]
    sources = tables["WorkbenchPlanSourceRefs"]
    row_sources = indexed([row for row in sources if row["kind"] == "schedule_row" and row["active"] == 1
                           and row["version"] == version], "source_key")
    tasks = indexed([row for row in tables["WorkbenchTaskRefs"] if row["plan_ref"] == ref], "row_ref")
    op_sources = indexed([row for row in sources if row["kind"] == "operation" and row["active"] == 1], "source_key")
    task_refs, operations, used = {}, {}, []
    require(set(row_sources) == {str(row["id"]) for row in rows}, "baseline.full_row_membership")
    require(set(tasks) == {row["ref"] for row in row_sources.values()}, "baseline.full_task_membership")
    for row in rows:
        source, operation = row_sources[str(row["id"])], op_sources.get(str(row["op_id"]))
        operation = _captured_row_binding(row, source, operation)
        task_refs[row["id"]], operations[row["op_id"]] = tasks[source["ref"]]["ref"], operation["ref"]
        used.extend([source, operation])
    used.append(next(row for row in sources if row["ref"] == ref))
    return tasks, task_refs, operations, used


def _captured_row_binding(row, source, operation):
    if operation is None:
        fail(gap="baseline.task_operation_binding")
    require(source["operation_id"] == row["op_id"]
            and source["operation_ref"] == operation["ref"] and source["source_table"] == "schedule",
            "baseline.task_operation_binding")
    return operation


def _task_bindings(conn, baseline, tables, references):
    ref, rows = baseline["plan_ref"], baseline["rows"]
    tasks, task_refs, operations, used = _captured_tasks(baseline, tables)
    _live_sources(conn, list({row["ref"]: row for row in used}.values()))
    try:
        current_tasks = references.get_task_refs(ref, [dict(row, schedule_id=row["id"]) for row in rows])
        current_ops = references.get_operation_refs(operations)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "baseline.current_task_binding")
    if current_tasks != task_refs or current_ops != operations:
        fail("adoption_reference_invalid", "baseline.original_task_ref")
    current = raw_rows(conn, "WorkbenchTaskRefs", where="plan_ref=?", params=(ref,))
    if not same(indexed(current, "row_ref"), tasks):
        fail("adoption_reference_invalid", "baseline.full_current_task_membership")
    return task_refs, operations


def _resources(conn, rows, tables):
    archived = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    repo, result = WorkbenchIdentityRepository(conn), {"supplier": {}}
    operations = indexed(tables["BatchOperations"], "id")
    for kind in ("machine", "operator", "batch"):
        keys = ({operations[row["op_id"]]["batch_id"] for row in rows} if kind == "batch" else
                {row[kind + "_id"] for row in rows if row[kind + "_id"] is not None})
        require(all(type(key) is str for key in keys), "baseline.resource_storage_type")
        require(all((kind, key) in archived for key in keys), "baseline.captured_resource_identity")
        live = repo.active_map(kind, sorted(keys))
        if any(key not in live or live[key].ref != archived[kind, key] for key in keys):
            fail("adoption_reference_invalid", "baseline.original_" + kind + "_instance")
        result[kind] = {key: SimpleNamespace(ref=archived[kind, key]) for key in keys}
    return result
