"""Read-only bridge from permanent ledger identities to legacy execution scopes."""

from contextlib import ExitStack, contextmanager
from dataclasses import replace

from core.errors import AppError, ErrorCode
from core.infrastructure.transaction import TransactionManager
from core.models.content import same
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection
from core.services.execution.ledger_reader import ExecutionLedgerReader
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
def ledger_read_snapshot(conn, *, ledger=None):
    with TransactionManager(conn).transaction():
        if ledger is not None and ledger.conn is not conn:
            raise ValueError("Execution ledger must belong to the current connection")
        ledger = ledger if ledger is not None else ExecutionLedgerReader(conn, current_plan_provider=current_execution_plan)
        with ExitStack() as stack:
            try:
                stack.enter_context(ledger.read_snapshot())
            except WorkbenchCommandRejected as exc:
                raise _unavailable(exc.code) from exc
            yield ledger


def _scope_tasks(ledger, scopes):
    by_identity = {}
    rows = ledger.scope_task_rows(sorted({scope.schedule_id for scope in scopes}))
    for row in rows:
        key = tuple(row[:4])
        if key in by_identity:
            raise _unavailable("execution_ledger_scope_ambiguous", op_id=row[2])
        setup_hours, unit_hours = row[13], row[14]
        by_identity[key] = {
            "operation_ref": row[4],
            "task_ref": row[5],
            "plan_ref": row[6],
            "source": row[7],
            "setup_hours": setup_hours,
            "unit_hours": unit_hours,
        }
    result = {}
    for scope in scopes:
        task = by_identity.get((scope.schedule_id, scope.schedule_version, scope.op_id, scope.batch_id))
        if task is None:
            raise _unavailable("execution_ledger_scope_missing", op_id=scope.op_id)
        result[scope] = task
    return result


def _require_reported_operation_scopes(ledger):
    row = ledger.reported_operation_without_schedule_row()
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


def _load_projections(ledger, refs, execution_projections):
    plan = ledger._current_plan()
    projections = _supplied_projection_map(execution_projections, refs, plan)
    return projections, plan, ledger.revision_clock()["ledger_revision"]


def _adapt_scope_facts(legacy_facts, tasks, projections, plan, ledger_revision, resources, refs_by_op):
    result = dict(legacy_facts)
    for scope, task in tasks.items():
        projection = projections[task["operation_ref"]]
        if plan and scope.schedule_version == plan["version"] and (
            projection.current_task_ref != task["task_ref"]
        ):
            raise _unavailable("execution_ledger_current_task_mismatch", op_id=scope.op_id)
        fact = legacy_facts[scope]
        changes = ledger_fact_changes(
            fact,
            projection,
            resources,
            source=task["source"],
            setup_hours=task["setup_hours"],
            unit_hours=task["unit_hours"],
        )
        if changes is None:
            result[scope] = replace(fact, target_quantity=projection.target_quantity, quantity_basis=projection.target_basis)
            continue
        projection_resources = {ref: resources.get(ref) for ref in refs_by_op[task["operation_ref"]]}
        protection = {"scope_task": task, "ledger_revision": ledger_revision,
                      "projection": _snapshot_projection(projection), "resources": projection_resources}
        revision = fact.state_revision + ":ledger-v2:" + str(ledger_revision)
        result[scope] = replace(fact, target_quantity=projection.target_quantity, quantity_basis=projection.target_basis,
                               state_revision=revision, execution_protection_content=protection, **changes)
    return result


def adapt_ledger_facts(ledger, legacy_facts, *, execution_projections):
    try:
        _require_reported_operation_scopes(ledger)
        scopes = [scope for scope in legacy_facts if scope.source_table == SOURCE_SCHEDULE
                  and scope.effective_plan_role == ROLE_ADOPTED and scope.scenario_id is None]
        if not scopes:
            if execution_projections:
                raise _unavailable("execution_ledger_projection_scope_mismatch")
            return legacy_facts
        tasks = _scope_tasks(ledger, scopes)
        refs = list(dict.fromkeys(task["operation_ref"] for task in tasks.values()))
        projections, plan, ledger_revision = _load_projections(ledger, refs, execution_projections)
        refs_by_op = {op_ref: projection_resource_refs(row) for op_ref, row in projections.items()}
        resource_refs = {ref for refs_set in refs_by_op.values() for ref in refs_set}
        resources = {row["ref"]: row for row in ledger.resources(resource_refs)}
        return _adapt_scope_facts(legacy_facts, tasks, projections, plan, ledger_revision, resources, refs_by_op)
    except WorkbenchCommandRejected as exc:
        raise _unavailable(exc.code) from exc


def _snapshot_projection(projection):
    payload = projection.to_dict()
    payload.pop("write_context")
    payload.pop("comparison_task_ref")
    for report in payload["reports"]:
        report.pop("write_context")
    return payload
