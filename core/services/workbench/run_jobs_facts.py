"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

import hashlib

from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.models.workbench_command import canonical_json
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.preflight_facts import quote


def capture_run_facts(conn):
    schema = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    tables = {}
    for kind, name, _, _ in schema:
        if kind != "table" or name in RUN_TABLES:
            continue
        sql = "SELECT * FROM " + quote(name)
        if name == "WorkbenchCommandReceipts":
            sql += " WHERE action <> 'scheduling.run'"
        tables[name] = [durable_value(tuple(row)) for row in conn.execute(sql + " ORDER BY rowid")]
    facts = {"schema": durable_value(schema), "tables": tables}
    text = canonical_json(facts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), text


def run_execution_projections(conn, settings):
    identities = {int(row[0]): row[1] for row in conn.execute(
        "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
    selected = set(settings["batch_refs"])
    op_ids = {row[0] for row in conn.execute("""SELECT bo.id,r.ref FROM BatchOperations bo
        JOIN WorkbenchEntityRefs r ON r.kind='batch' AND r.entity_key=bo.batch_id AND r.active=1""") if row[1] in selected}
    svc = ScheduleService(conn)
    op_ids.update(_latest_plan_rows(svc, svc.history_repo.get_latest_version()))
    if not op_ids <= set(identities):
        raise ValueError("Selected or last-official operation has no permanent identity")
    return ExecutionLedgerService(conn).project_operations(sorted(identities[key] for key in op_ids))


def run_baseline(conn):
    # Permanent official identities only. A new candidate is not registered here.
    row = conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()
    version = row[0]
    if version is None:
        return {"plan_ref": None, "version": None, "rows": []}
    identities = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND active=1 AND version=?", (version,)).fetchall()
    if len(identities) != 1:
        raise ValueError("Current official baseline identity is missing or ambiguous")
    return {"plan_ref": identities[0][0], "version": version,
            "rows": [durable_value(dict(item)) for item in conn.execute("SELECT * FROM Schedule WHERE version=? ORDER BY id", (version,))]}
