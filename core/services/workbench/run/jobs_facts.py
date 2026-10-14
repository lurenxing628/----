"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

import json

from core.models.content import content_text, same
from core.models.workbench_run_job import durable_value
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.schema_compat import archived_columns, project_facts
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository

from .preflight_facts import NON_INPUT_TABLES, non_input_row


def capture_run_facts(conn):
    text = _capture_run_facts_text(conn)
    return None, text


def _capture_run_facts_text(conn):
    repo = WorkbenchRunFactsRepository(conn)
    schema, tables = repo.admission_facts(exclude_tables=NON_INPUT_TABLES)
    facts = _production_facts({"schema": schema, "tables": tables}, repo.command_receipt_columns())
    return content_text(facts)


def _production_facts(value, receipt_columns):
    """Exclude non-input contents only; retain every schema and business fact."""
    tables = {name: [row for row in rows if not non_input_row(name, row, receipt_columns)]
              for name, rows in value["tables"].items() if name not in NON_INPUT_TABLES}
    return {**value, "tables": tables}


def run_facts_unchanged(conn, captured_text, captured_hash):
    """Compare the original production archive; old digest values remain metadata."""
    if type(captured_text) is not str:
        return False
    return production_facts_match(conn, captured_text)


def production_facts_match(conn, captured_text):
    """Compare live inputs after the caller has verified the immutable archive once."""
    current_text = _capture_run_facts_text(conn)
    if current_text == captured_text:
        return True
    current, captured = json.loads(current_text), json.loads(captured_text)
    current = _production_facts(current, archived_columns(current, "WorkbenchCommandReceipts"))
    captured = _production_facts(captured, archived_columns(captured, "WorkbenchCommandReceipts"))
    return same(project_facts(current), project_facts(captured))


def run_execution_projections(conn, settings):
    from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
    from core.services.scheduler.schedule_service import ScheduleService

    facts = WorkbenchRunFactsRepository(conn)
    identities = {int(row[0]): row[1] for row in facts.operation_identity_refs()}
    selected = set(settings["batch_refs"])
    op_ids = {row[0] for row in facts.batch_operation_batch_refs() if row[1] in selected}
    svc = ScheduleService(conn)
    op_ids.update(_latest_plan_rows(svc, svc.history_repo.get_latest_version()))
    if not op_ids <= set(identities):
        raise ValueError("Selected or last-official operation has no permanent identity")
    return ExecutionLedgerService(conn).project_operations(sorted(identities[key] for key in op_ids))


def run_baseline(conn):
    # Permanent official identities only. A new candidate is not registered here.
    facts = WorkbenchRunFactsRepository(conn)
    version = facts.latest_history_version()
    if version is None:
        return {"plan_ref": None, "version": None, "rows": []}
    identities = facts.official_plan_refs(version)
    if len(identities) != 1:
        raise ValueError("Current official baseline identity is missing or ambiguous")
    return {"plan_ref": identities[0], "version": version,
            "rows": [durable_value(item) for item in facts.schedule_rows_for_version(version)]}
