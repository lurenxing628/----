"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import dump, fingerprint
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.run_jobs_facts import run_baseline
from data.repositories.workbench_trial_raw_repo import read_raw_table

_BOOKKEEPING = set(TRIAL_TABLES + RUN_TABLES) | {"WorkbenchCommandReceipts", "OperationLogs", "sqlite_sequence"}


def capture_facts(conn):
    schema = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
              if row[2] not in _BOOKKEEPING]
    tables, columns = {}, {}
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        columns[name], tables[name] = read_raw_table(conn, name)
    result = {"schema": schema, "columns": columns, "tables": tables}
    dump(result)
    return result, fingerprint(result)


def execution_facts(conn, tables, selected_refs):
    ids = {int(row["source_key"]): row["ref"] for row in tables["WorkbenchPlanSourceRefs"]
           if row["kind"] == "operation" and row["active"] == 1}
    refs = set(selected_refs)
    refs.update(ids[row["op_id"]] for row in tables["Schedule"] if row["op_id"] in ids)
    for row in tables.get("WorkbenchProductionReports", []):
        refs.add(row["operation_ref"])
    for row in tables.get("WorkbenchExecutionLegacyFacts", []):
        if row["operation_ref"] is not None:
            refs.add(row["operation_ref"])
    if len(refs) > MAX_TRIAL_TASKS:
        reject("query_too_large", "试调及真实执行保护范围超过10000道工序，未遗漏范围外占用。", 413)
    svc = ExecutionLedgerService(conn)
    values = svc.project_operations(sorted(refs))
    return {row.operation_ref: row.to_dict() for row in values}


def live_context(conn, selected_refs):
    facts, digest = capture_facts(conn)
    projections = execution_facts(conn, facts["tables"], selected_refs)
    return {"facts": facts, "facts_hash": digest, "execution": projections, "baseline": run_baseline(conn)}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
