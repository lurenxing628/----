"""Read-only bridge from permanent ledger identities to execution scopes."""

from contextlib import ExitStack, contextmanager
from dataclasses import replace

from core.errors import AppError, ErrorCode
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection
from core.services.execution.ledger_reader import ExecutionLedgerReader, ExecutionLedgerReadScope
from core.services.execution.projection import projection_resource_refs

from .execution_ledger_guard import ledger_fact_changes
from .execution_plan_identity import current_execution_plan


def _unavailable(reason, *, op_id=None):
    details = {"reason": reason}
    if op_id is not None:
        details["op_id"] = op_id
    return AppError(ErrorCode.SCHEDULE_CONFLICT,
                    "报工记录还没有准备好，或和排产任务对不上，系统无法用这些记录确认排产约束。请刷新重试；仍不行请联系维护人员。",
                    details=details)


@contextmanager
def ledger_read_snapshot(conn):
    reader = ExecutionLedgerReader(conn, current_plan_provider=current_execution_plan)
    with ExitStack() as stack:
        try:
            scope = stack.enter_context(reader.read_snapshot())
        except WorkbenchCommandRejected as exc:
            raise _unavailable(exc.code) from exc
        yield scope


def _scope_tasks(scope: ExecutionLedgerReadScope, scopes):
    by_identity = {}
    rows = scope.reader.scope_task_rows(scope, sorted({item.schedule_id for item in scopes}))
    for row in rows:
        key = tuple(row[:4])
        if key in by_identity:
            raise _unavailable("execution_ledger_scope_ambiguous", op_id=row[2])
        setup_hours, unit_hours = row[13], row[14]
        by_identity[key] = {
            "operation_ref": row[4],
            "task_ref": row[5],
            "source": row[7],
            "setup_hours": setup_hours,
            "unit_hours": unit_hours,
        }
    result = {}
    for item in scopes:
        task = by_identity.get((item.schedule_id, item.schedule_version, item.op_id, item.batch_id))
        if task is None:
            raise _unavailable("execution_ledger_scope_missing", op_id=item.op_id)
        result[item] = task
    return result


def _require_reported_operation_scopes(scope: ExecutionLedgerReadScope):
    row = scope.reader.reported_operation_without_schedule_row(scope)
    if row is not None:
        raise _unavailable("execution_ledger_report_scope_missing", op_id=int(row[0]))


def _supplied_projection_map(execution_projections, refs, plan):
    result = {}
    for row in execution_projections:
        if not isinstance(row, ExecutionProjection) or row.operation_ref in result:
            raise _unavailable("execution_ledger_projection_invalid_or_duplicate")
        if not same(row.plan_identity, plan):
            raise _unavailable("execution_ledger_projection_plan_changed")
        result[row.operation_ref] = row
    if set(result) != set(refs):
        raise _unavailable("execution_ledger_projection_scope_mismatch")
    return result


def _load_projections(scope: ExecutionLedgerReadScope, refs, execution_projections):
    plan = scope.reader.current_plan(scope)
    projections = _supplied_projection_map(execution_projections, refs, plan)
    return projections, plan, scope.reader.revision_clock(scope)["ledger_revision"]


def _adapt_scope_facts(facts, tasks, projections, plan, ledger_revision, resources):
    result = {}
    for scope, task in tasks.items():
        projection = projections[task["operation_ref"]]
        if plan and scope.schedule_version == plan["version"] and (
            projection.current_task_ref != task["task_ref"]
        ):
            raise _unavailable("execution_ledger_current_task_mismatch", op_id=scope.op_id)
        fact = facts[scope]
        changes = ledger_fact_changes(
            projection,
            resources,
            source=task["source"],
            setup_hours=task["setup_hours"],
            unit_hours=task["unit_hours"],
        )
        if changes is None:
            result[scope] = replace(fact, target_quantity=projection.target_quantity, quantity_basis=projection.target_basis)
            continue
        revision = fact.state_revision + ":ledger-v2:" + str(ledger_revision)
        result[scope] = replace(fact, target_quantity=projection.target_quantity, quantity_basis=projection.target_basis,
                                state_revision=revision, **changes)
    return result


def adapt_ledger_facts(scope: ExecutionLedgerReadScope, facts, *, execution_projections):
    try:
        _require_reported_operation_scopes(scope)
        if not facts:
            if execution_projections:
                raise _unavailable("execution_ledger_projection_scope_mismatch")
            return facts
        tasks = _scope_tasks(scope, facts)
        refs = list(dict.fromkeys(task["operation_ref"] for task in tasks.values()))
        projections, plan, ledger_revision = _load_projections(scope, refs, execution_projections)
        resource_refs = {ref for row in projections.values() for ref in projection_resource_refs(row)}
        resources = {row["ref"]: row for row in scope.reader.resources(scope, resource_refs)}
        return _adapt_scope_facts(facts, tasks, projections, plan, ledger_revision, resources)
    except WorkbenchCommandRejected as exc:
        raise _unavailable(exc.code) from exc
