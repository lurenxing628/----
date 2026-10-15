"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

import json

from core.infrastructure.transaction import TransactionManager
from core.models.content import same
from core.models.workbench_run_job import durable_value
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.production_capture import NON_INPUT_TABLES, ProductionFactsCapture, non_input_row
from core.services.workbench.facts.schema_compat import archived_columns, project_facts
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository


def capture_run_facts(conn, capture=None):
    text = _capture_run_facts_text(conn, capture)
    return None, text


def _capture_run_facts_text(conn, capture=None):
    if capture is not None:
        return capture.content()
    with TransactionManager(conn).transaction():
        return ProductionFactsCapture(conn).content()


def _production_facts(value, receipt_columns):
    """Exclude non-input contents only; retain every schema and business fact."""
    tables = {name: [row for row in rows if not non_input_row(name,
                  [row.get(column) for column in archived_columns(value, name)] if type(row) is dict else row, receipt_columns)]
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


def run_execution_projections(conn, settings, *, capture=None, existing=(), service=None):
    if capture is not None:
        identities = {int(row["source_key"]): row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                      if row["kind"] == "operation" and row["active"] == 1}
        selected = {row["entity_key"] for row in capture.table("WorkbenchEntityRefs")
                    if row["kind"] == "batch" and row["active"] == 1 and row["ref"] in settings["batch_refs"]}
        op_ids = {row["id"] for row in capture.table("BatchOperations") if row["batch_id"] in selected}
        versions = [row["version"] for row in capture.table("ScheduleHistory")]
        version = max(versions, default=0)
        op_ids.update(row["op_id"] for row in capture.table("Schedule") if row["version"] <= version)
        if not op_ids <= set(identities):
            raise ValueError("Selected or last-official operation has no permanent identity")
        refs = {identities[key] for key in op_ids}
        result = {projection.operation_ref: projection for projection in existing if projection.operation_ref in refs}
        from core.services.workbench.facts.run_input_codec import validate_projection_dto
        service = service if service is not None else ExecutionLedgerService(conn)
        missing = sorted(refs - set(result))
        for offset in range(0, len(missing), 10000):
            for item in service.project_operations(missing[offset:offset + 10000]):
                validate_projection_dto(item)
                result[item.operation_ref] = item
        if set(result) != refs:
            raise ValueError("ExecutionProjection did not cover the exact admission operation scope")
        return [result[ref] for ref in sorted(refs)]
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
    return sorted(ExecutionLedgerService(conn).project_operations(sorted(identities[key] for key in op_ids)),
                  key=lambda row: row.operation_ref)


def run_baseline(conn, *, capture=None):
    # Permanent official identities only. A new candidate is not registered here.
    if capture is not None:
        version = max((row["version"] for row in capture.table("ScheduleHistory")), default=None)
        if version is None:
            return {"plan_ref": None, "version": None, "rows": []}
        identities = [row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                      if row["kind"] == "official" and row["active"] == 1 and row["version"] == version]
        if len(identities) != 1:
            raise ValueError("Current official baseline identity is missing or ambiguous")
        rows = sorted((row for row in capture.table("Schedule") if row["version"] == version), key=lambda row: row["id"])
        return {"plan_ref": identities[0], "version": version, "rows": [durable_value(row) for row in rows]}
    facts = WorkbenchRunFactsRepository(conn)
    version = facts.latest_history_version()
    if version is None:
        return {"plan_ref": None, "version": None, "rows": []}
    identities = facts.official_plan_refs(version)
    if len(identities) != 1:
        raise ValueError("Current official baseline identity is missing or ambiguous")
    return {"plan_ref": identities[0], "version": version,
            "rows": [durable_value(item) for item in facts.schedule_rows_for_version(version)]}
