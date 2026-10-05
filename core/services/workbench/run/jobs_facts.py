"""Durable acceptance facts; self-owned run bookkeeping is not a production change."""

import hashlib
import json

from core.models.workbench_command import canonical_json
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution.ledger import ExecutionLedgerService
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository

from .preflight_facts import NON_INPUT_TABLES, non_input_row


def capture_run_facts(conn):
    repo = WorkbenchRunFactsRepository(conn)
    schema, tables = repo.admission_facts(exclude_tables=NON_INPUT_TABLES)
    facts = _production_facts({"schema": schema, "tables": tables}, repo.command_receipt_columns())
    text = canonical_json(durable_value(facts))
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), text


def _production_facts(value, receipt_columns):
    """Exclude non-input contents only; retain every schema and business fact."""
    tables = {name: [row for row in rows if not non_input_row(name, row, receipt_columns)]
              for name, rows in value["tables"].items() if name not in NON_INPUT_TABLES}
    return {**value, "tables": tables}


def run_facts_unchanged(conn, captured_text, captured_hash):
    """Prove archive integrity, then compare production inputs across audit writes.

    Keep the original full archive and SHA unchanged, including older admissions:
    the exclusions apply to both sides only while comparing, so an archive taken
    before they existed still compares on the same terms. OperationLogs and
    SystemJobState hold telemetry and maintenance timing; neither contents nor
    their allocators are scheduling inputs. An 'unchanged' command receipt only records that a command found
    nothing to change. Trial drafts/scenarios and dashboard handling, with their
    receipts, are never read by the run (see NON_INPUT_TABLES); a trial adoption
    still changes the official plan tables. Every other committed or partial
    receipt, all other tables (including unknown extensions), sequence counters,
    and the complete schema remain part of this comparison.
    """
    if type(captured_text) is not str or hashlib.sha256(captured_text.encode("utf-8")).hexdigest() != captured_hash:
        return False
    return production_facts_match(conn, captured_text, captured_hash)


def production_facts_match(conn, captured_text, captured_hash):
    """Compare live inputs after the caller has verified the immutable archive once."""
    current_hash, current_text = capture_run_facts(conn)
    if current_hash == captured_hash:
        return True
    # The schema itself is compared, so the current column order also describes the archive whenever both can match.
    columns = WorkbenchRunFactsRepository(conn).command_receipt_columns()
    return (canonical_json(_production_facts(json.loads(current_text), columns))
            == canonical_json(_production_facts(json.loads(captured_text), columns)))


def run_execution_projections(conn, settings):
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
