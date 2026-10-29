"""Verify captured whole rows and permanent membership before projecting a baseline."""

from core.models.content import same
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.services.workbench.facts.adoption_baseline_values import (
    fail,
    indexed,
    require,
    schedule_rows,
)
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .projection import project_tasks, public_time


def verify_capture(baseline, tables, *, admission_proof=None):
    version = baseline["version"]
    if (version is not None and admission_proof is not None
            and admission_proof.baseline is baseline and admission_proof.tables is tables):
        require(bool(baseline["rows"]), "baseline_complete_row_count")
        _captured_official(baseline, tables)
        return
    history = tables["ScheduleHistory"]
    require(all(type(row.get("version")) is int and row["version"] > 0 for row in history), "archived_history_versions")
    require(version == max((row["version"] for row in history), default=None), "archived_official_baseline")
    require(version is None or type(version) is int, "baseline_version_type")
    if version is None:
        require(baseline["plan_ref"] is None and not baseline["rows"], "empty_baseline")
        return
    require(bool(baseline["rows"]), "baseline_complete_row_count")
    _captured_official(baseline, tables)


def _captured_official(baseline, tables):
    official = [row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "official"
                and row["active"] == 1 and row["version"] == baseline["version"]]
    require(len(official) == 1 and official[0]["ref"] == baseline["plan_ref"]
            and official[0]["source_table"] == "schedule" and official[0]["plan_role"] == "adopted",
            "archived_official_reference")


def _live_sources(conn, captured, *, context):
    by_ref = indexed(captured, "ref")
    keys, live = list(by_ref), {}
    if context is not None:
        live = indexed(context.source_identities(keys), "ref")
    else:
        repo = WorkbenchPlanBaselineRepository(conn)
        for start in range(0, len(keys), 400):
            chunk = keys[start:start + 400]
            live.update(indexed(repo.source_refs_by_refs(chunk), "ref"))
    if not same(by_ref, live):
        fail("adoption_reference_invalid", "captured_source_instances")


def verify_arranged(conn, plan_ref, version, tables, arranged, *, context,
                    arranged_times=None, indexed_tables=None, verified_out=None):
    rows = context.source_rows(version=version) if context is not None else schedule_rows(conn, version)
    originals, current = indexed(arranged, "op_id"), indexed(rows, "op_id")
    if set(originals) != set(current):
        fail("adoption_plan_drift", "selected_complete_operation_set")
    intervals = context.peek_source_intervals(version=version) if context is not None else None
    if intervals is not None and not {row["id"] for row in rows} <= set(intervals):
        intervals = None
    for op_id, original in originals.items():
        row = current[op_id]
        known_times = intervals[row["id"]] if intervals is not None else None
        original_times = arranged_times.get(op_id) if arranged_times is not None else None
        if not _arrangement_matches(row, original, known_times=known_times, original_times=original_times):
            fail("adoption_plan_drift", "selected_saved_arrangement")
    references = context.references if context is not None else WorkbenchPlanIdentityRepository(conn)
    try:
        task_refs = references.get_task_refs(plan_ref, ((row["id"], row["op_id"], row["version"]) for row in rows))
        operations = references.get_operation_refs(current)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "selected_complete_task_identity")
    keys = {str(key) for key in current}
    if indexed_tables is not None and indexed_tables.get("source_refs_id") == id(tables["WorkbenchPlanSourceRefs"]):
        op_sources = indexed_tables["operation_sources"]
        sources = [op_sources[key] for key in keys if key in op_sources]
    else:
        sources = [row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "operation"
                   and row["active"] == 1 and row["source_key"] in keys]
    require(len(sources) == len(current), "captured_selected_operations")
    if {int(row["source_key"]): row["ref"] for row in sources} != operations:
        fail("adoption_reference_invalid", "selected_original_operation_instances")
    _live_sources(conn, sources, context=context)
    if verified_out is not None:
        verified_out["selected_task_refs"] = task_refs
        verified_out["verified_operation_keys"] = frozenset(keys)
    return rows


def _resources_match(row, original):
    actual = row["machine_id"], row["operator_id"]
    expected = original["machine_id"], original["operator_id"]
    # These common SQLite values have an exact type/value JSON spelling. Keep
    # complex storage values on the existing whole-dictionary canonical path.
    if all(type(value) in (str, bool, type(None)) or type(value) is int and -(1 << 63) <= value < (1 << 63)
           for value in actual + expected):
        return all(type(left) is type(right) and left == right for left, right in zip(expected, actual))
    return same({"machine_id": expected[0], "operator_id": expected[1]},
                {"machine_id": actual[0], "operator_id": actual[1]})


def _arrangement_matches(row, original, *, known_times=None, original_times=None):
    if not _resources_match(row, original):
        return False
    for index, key in enumerate(("start_time", "end_time")):
        if type(row[key]) is not str or type(original[key]) is not str:
            return False
        if original_times is not None and (
            row[key] == original[key]
            or row[key] == original_times[index]
            or (len(row[key]) == len(original_times[index]) and row[key].replace(" ", "T", 1) == original_times[index])
        ):
            continue
        current = known_times[index].replace(" ", "T") if known_times is not None else public_time(row[key])
        if known_times is not None and row[key] == original[key]:
            continue
        expected = original_times[index] if original_times is not None else public_time(original[key])
        if current != expected:
            return False
    return True


def baseline_tasks(conn, baseline, tables, facts, *, point_annotator, context):
    from core.services.workbench.facts.adoption_baseline_sources import read_adoption_operation_facts

    ref, version = baseline["plan_ref"], baseline["version"]
    if context.history(version) is None:
        fail("adoption_baseline_archived", "ScheduleHistory.original_version")
    try:
        locator = context.references.resolve_plan(ref)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "baseline.plan_ref")
    if locator != WorkbenchPlanLocator(version, "adopted"):
        fail("adoption_reference_invalid", "baseline.official_locator")
    rows = context.source_rows(version=version)
    facts["observed_baseline_rows"] = rows
    captured = baseline["rows"]
    if not {row["id"] for row in captured} <= {row["id"] for row in rows}:
        fail("adoption_baseline_archived", "Schedule.original_rows")
    if not same(rows, captured):
        fail("adoption_baseline_drift", "Schedule.complete_original_values_and_types")
    task_refs, operations = _task_bindings(conn, baseline, tables, context=context)
    resources = _resources(captured, tables, context=context)
    origins = read_adoption_operation_facts(conn, context.adopted_source(ref))
    ops, batches = indexed(tables["BatchOperations"], "id"), indexed(tables["Batches"], "batch_id")
    detail = []
    for row in captured:
        op = ops.get(row["op_id"])
        if op is None or op["batch_id"] not in batches:
            fail(gap="baseline.original_operation_and_batch")
        origin = origins.get(row["op_id"])
        if origin is None or any(item["field"] in ("source", "supplier", "supplier.ref") for item in origin["data_gaps"]):
            fail("adoption_evidence_missing", "baseline.original_source_and_supplier")
        supplier = next((item for item in origin["resource_directory"] if item["kind"] == "supplier"), None)
        detail.append({**row, "schedule_id": row["id"], "batch_id": op["batch_id"],
                       "seq": op["seq"], "piece_id": op["piece_id"], "op_type_name": op["op_type_name"],
                       "supplier_id": supplier["business_code"] if supplier is not None else None})
    detail = point_annotator(detail)
    return project_tasks(ref, detail, task_refs, operations, resources, facts=facts, context=context)


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


def _task_bindings(conn, baseline, tables, *, context):
    ref, rows = baseline["plan_ref"], baseline["rows"]
    tasks, task_refs, operations, used = _captured_tasks(baseline, tables)
    _live_sources(conn, list({row["ref"]: row for row in used}.values()), context=context)
    try:
        current_tasks = context.references.get_task_refs(ref, ((row["id"], row["op_id"], row["version"]) for row in rows))
        current_ops = context.references.get_operation_refs(operations)
    except WorkbenchPlanReferenceError:
        fail("adoption_reference_invalid", "baseline.current_task_binding")
    if current_tasks != task_refs or current_ops != operations:
        fail("adoption_reference_invalid", "baseline.original_task_ref")
    current = context.task_identities(ref)
    if not same(indexed(current, "row_ref"), tasks):
        fail("adoption_reference_invalid", "baseline.full_current_task_membership")
    return task_refs, operations


def _resources(rows, tables, *, context):
    """Every captured machine, operator and batch must still be its archived identity; return the machine and operator maps."""
    archived = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    verified = {}
    operations = indexed(tables["BatchOperations"], "id")
    for kind in ("machine", "operator", "batch"):
        keys = ({operations[row["op_id"]]["batch_id"] for row in rows} if kind == "batch" else
                {row[kind + "_id"] for row in rows if row[kind + "_id"] is not None})
        require(all(type(key) is str for key in keys), "baseline.resource_storage_type")
        require(all((kind, key) in archived for key in keys), "baseline.captured_resource_identity")
        live = context.active_map(kind, sorted(keys))
        if any(key not in live or live[key].ref != archived[kind, key] for key in keys):
            fail("adoption_reference_invalid", "baseline.original_" + kind + "_instance")
        verified[kind] = live
    # project_tasks resolves only machine and operator refs; suppliers come from the adopted origins.
    return {"machine": verified["machine"], "operator": verified["operator"]}
