"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

from core.models.content import same
from core.models.workbench_run_job import durable_value
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.facts.production_capture import NON_INPUT_TABLES, ProductionFactsCapture, non_input_row
from core.services.workbench.facts.schema_compat import archived_columns, project_facts


def _production_facts(value, receipt_columns):
    """Exclude non-input contents only; retain every schema and business fact."""
    tables = {name: [row for row in rows if not non_input_row(name,
                  [row.get(column) for column in archived_columns(value, name)] if type(row) is dict else row, receipt_columns)]
              for name, rows in value["tables"].items() if name not in NON_INPUT_TABLES}
    return {**value, "tables": tables}


def production_facts_match(conn, captured_text, *, capture=None):
    """Compare live inputs after the caller has verified the immutable archive once."""
    if capture is None:
        capture = ProductionFactsCapture(conn)
    current_text = capture.content()
    if current_text == captured_text:
        return True
    current = capture.archive()
    captured = stored_json(captured_text)
    captured = _production_facts(captured, archived_columns(captured, "WorkbenchCommandReceipts"))
    return same(project_facts(current), project_facts(captured))


def run_execution_projections(conn, settings, *, capture, existing=(), service=None):
    identities = {int(row["source_key"]): row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                  if row["kind"] == "operation" and row["active"] == 1}
    batch_refs = set(settings["batch_refs"])
    selected = {row["entity_key"] for row in capture.table("WorkbenchEntityRefs")
                if row["kind"] == "batch" and row["active"] == 1 and row["ref"] in batch_refs}
    op_ids = {row["id"] for row in capture.table("BatchOperations") if row["batch_id"] in selected}
    versions = [row["version"] for row in capture.table("ScheduleHistory")]
    version = max(versions, default=0)
    op_ids.update(capture.latest_plan_rows(version))
    if not op_ids <= set(identities):
        raise ValueError("Selected or last-official operation has no permanent identity")
    refs = {identities[key] for key in op_ids}
    result = {projection.operation_ref: projection for projection in existing if projection.operation_ref in refs}
    service = service if service is not None else ExecutionLedgerService(conn)
    missing = sorted(refs - set(result))
    for offset in range(0, len(missing), 10000):
        for item in service.project_operations(missing[offset:offset + 10000]):
            result[item.operation_ref] = item
    if set(result) != refs:
        raise ValueError("ExecutionProjection did not cover the exact admission operation scope")
    return [result[ref] for ref in sorted(refs)]


def run_baseline(*, capture):
    # Permanent official identities only. A new candidate is not registered here.
    version = max((row["version"] for row in capture.table("ScheduleHistory")), default=None)
    if version is None:
        return {"plan_ref": None, "version": None, "rows": []}
    identities = [row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                  if row["kind"] == "official" and row["active"] == 1 and row["version"] == version]
    if len(identities) != 1:
        raise ValueError("Current official baseline identity is missing or ambiguous")
    rows = sorted((row for row in capture.table("Schedule") if row["version"] == version), key=lambda row: row["id"])
    return {"plan_ref": identities[0], "version": version, "rows": [durable_value(row) for row in rows]}
