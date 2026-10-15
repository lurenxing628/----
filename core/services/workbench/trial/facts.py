"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from core.models.content import same
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import dump_document
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.schema_compat import project_facts
from core.services.workbench.run.jobs_facts import run_baseline
from data.repositories.workbench_trial_query_repo import BOOKKEEPING_TABLES


def capture_facts(conn, capture=None):
    facts, legacy_hash = (capture if capture is not None else ProductionFactsCapture(conn)).captured()
    dump_document(facts)
    return facts, legacy_hash


def facts_unchanged(admission, live):
    """Compare saved production content; preserve original historical metadata."""

    def inputs(value):
        return {**value, "schema": [row for row in value["schema"] if row[2] not in BOOKKEEPING_TABLES],
                "columns": {name: columns for name, columns in value["columns"].items() if name not in BOOKKEEPING_TABLES},
                "tables": {name: rows for name, rows in value["tables"].items() if name not in BOOKKEEPING_TABLES}}

    original, current = admission["facts"], live["facts"]
    if original.get("version") != "production-facts-v2":
        original, current = inputs(original), inputs(current)
    return same(project_facts(original), project_facts(current))


def execution_facts(conn, tables, selected_refs, *, prepared=None):
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
    if prepared is not None:
        from core.services.workbench.facts.run_input_codec import validate_projection_dto
        for projection in values:
            validate_projection_dto(projection)
        prepared.extend(values)
    return {row.operation_ref: row.to_dict() for row in values}


def live_context(conn, selected_refs, capture=None, *, prepared_execution=None):
    capture = capture if capture is not None else ProductionFactsCapture(conn)
    facts, legacy_hash = capture_facts(conn, capture)
    projections = execution_facts(conn, facts["tables"], selected_refs, prepared=prepared_execution)
    return {"facts": facts, "facts_hash": legacy_hash, "execution": projections,
            "baseline": run_baseline(conn, capture=capture)}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
