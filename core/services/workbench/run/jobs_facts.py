"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

from core.models.workbench_run_job import durable_value


def run_execution_projections(settings, *, capture, ledger, existing=(), facts=None, latest_plan_rows=None):
    identities = (
        facts.operation_refs
        if facts is not None
        else {
            int(row["source_key"]): row["ref"]
            for row in capture.table("WorkbenchPlanSourceRefs")
            if row["kind"] == "operation" and row["active"] == 1
        }
    )
    if latest_plan_rows is None:
        versions = [row["version"] for row in capture.table("ScheduleHistory")]
        version = max(versions, default=0)
        latest_plan_rows = capture.latest_plan_rows(version)
    batch_refs = set(settings["batch_refs"])
    selected = {
        row["entity_key"]
        for row in capture.table("WorkbenchEntityRefs")
        if row["kind"] == "batch" and row["active"] == 1 and row["ref"] in batch_refs
    }
    op_ids = {row["id"] for row in capture.table("BatchOperations") if row["batch_id"] in selected}
    op_ids.update(latest_plan_rows)
    if not op_ids <= set(identities):
        raise ValueError("Selected or last-official operation has no permanent identity")
    refs = {identities[key] for key in op_ids}
    result = {projection.operation_ref: projection for projection in existing if projection.operation_ref in refs}
    for item in ledger.reader.project_operations(ledger, sorted(refs - set(result))):
        result[item.operation_ref] = item
    return [result[ref] for ref in sorted(refs)]


def run_baseline(*, capture):
    histories = capture.table("ScheduleHistory")
    if not histories:
        return {"plan_ref": None, "version": None, "rows": []}
    latest = max(histories, key=lambda row: row["version"])
    version = latest["version"]
    rows = sorted((row for row in capture.table("Schedule") if row["version"] == version), key=lambda row: row["id"])
    return {"plan_ref": latest["plan_ref"], "version": version, "rows": [durable_value(row) for row in rows]}
