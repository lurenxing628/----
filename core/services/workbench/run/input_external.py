"""Bind scheduling to the batch contexts used by preflight and batch detail."""

from types import SimpleNamespace

from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_actual_group_intervals,
    merged_external_group_identity,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.run_input_codec import restore_execution_projections
from core.services.workbench.facts.run_input_rows import fail
from data.repositories.schedule_execution_facts_repo import ScheduleExecutionFactsRepository


def prime_template_cache(svc, tables, batches, operations):
    contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
    members = member_index(contexts, tables.get("BatchOperations", []))
    for op in operations:
        if op.source != "external":
            continue
        problem = context_problem(contexts.get(op.id), operation_id=op.id,
                                  part_no=batches[op.batch_id].part_no, sequence=op.seq)
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
        row = contexts[op.id]
        problem = merged_supplier_problem(row, op.supplier_id,
            members.get((op.batch_id, context_group_key(row), getattr(op, "piece_id", None))))
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
    svc._aps_schedule_input_cache = {"batch": dict(batches), "external_contexts": contexts,
                                     "external_members": members, "external_contexts_bound": True}


def external_execution_cycles(tables, batches, operations, seeds, actual_ids):
    """Use proven actual periods with valid immutable batch/group/piece bindings."""
    contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
    groups = {}
    for op in operations:
        if op.source != "external":
            continue
        context = contexts.get(op.id)
        if context is None or context_problem(context, operation_id=op.id, part_no=batches[op.batch_id].part_no, sequence=op.seq):
            continue
        group = SimpleNamespace(merge_mode=context["merge_mode"], group_id=context_group_key(context))
        groups[op.id] = merged_external_group_identity(op, group=group)
    periods = merged_actual_group_intervals(groups, seeds, actual_ids)
    return {op_id: {"start": periods[group][0].isoformat(), "end": periods[group][1].isoformat()}
            for op_id, group in groups.items() if op_id not in actual_ids and group in periods}


def preflight_external_cycles(facts, batches, operations, projections):
    contexts = {row["operation_id"]: row for row in facts.tables.get("BatchExternalContexts", [])}
    if not any(op["source"] == "external" and (contexts.get(op["id"]) or {}).get("merge_mode") == "merged"
               and projections[facts.operation_ref(op)]["first_actual_start"] for op in operations):
        return {}
    svc = ScheduleService(facts.conn)
    version = svc.history_repo.get_latest_version()
    prior = _prior_execution_projections(facts, version, projections)
    models = [SimpleNamespace(**op) for op in operations]
    _, fixed, completed, seeds, _, _ = build_execution_guardrails_from_projections(
        svc, models, prev_version=version, execution_projections=prior)
    batch_models = {batch["batch_id"]: SimpleNamespace(**batch) for batch in batches}
    return external_execution_cycles(facts.tables, batch_models, models, seeds, fixed | completed)


def _prior_execution_projections(facts, version, projections):
    rows = ScheduleExecutionFactsRepository(facts.conn).latest_plan_rows(version)
    refs = {facts.operation_refs[row["op_id"]] for row in rows}
    supplied = dict(projections)
    missing = sorted(refs - set(supplied))
    ledger = ExecutionLedgerService(facts.conn)
    for offset in range(0, len(missing), 10000):
        supplied.update({item.operation_ref: item.to_dict() for item in ledger.project_operations(missing[offset:offset + 10000])})
    return restore_execution_projections([supplied[ref] for ref in sorted(refs)])
