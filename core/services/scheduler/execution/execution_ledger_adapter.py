"""Read-only bridge from permanent ledger identities to legacy execution scopes."""

from contextlib import contextmanager
from dataclasses import replace

from core.infrastructure.errors import AppError, ErrorCode
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_execution import ExecutionProjection
from core.services.execution.ledger_reader import ExecutionLedgerReader
from data.repositories.workbench_execution_repo import chunks

from .execution_ledger_guard import ledger_fact_changes
from .execution_plan_identity import current_execution_plan


def _unavailable(reason, *, op_id=None):
    details = {"reason": reason}
    if op_id is not None:
        details["op_id"] = op_id
    return AppError(ErrorCode.SCHEDULE_CONFLICT,
                    "执行台账或任务身份不完整，本次没有写入排程。请核对迁移与原报工记录。", details=details)


def _ledger_required(conn):
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if "SchemaVersion" not in names:
        raise _unavailable("execution_ledger_schema_version_missing")
    row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
    if row is None or type(row[0]) is not int or row[0] < 0:
        raise _unavailable("execution_ledger_schema_version_invalid")
    if row[0] >= 25 or names.intersection(execution_ledger_objects()):
        return True
    if "WorkbenchCommandReceipts" in names and conn.execute(
        "SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1"
    ).fetchone():
        raise _unavailable("execution_ledger_missing_with_receipts")
    # Only a pre-v25 database with no ledger objects or receipts uses legacy reads.
    return False


@contextmanager
def ledger_read_snapshot(conn):
    with TransactionManager(conn).transaction():
        if not _ledger_required(conn):
            yield None
            return
        ledger = ExecutionLedgerReader(conn, current_plan_provider=current_execution_plan)
        try:
            with ledger.read_snapshot():
                yield ledger
        except WorkbenchCommandRejected as exc:
            raise _unavailable(exc.code) from exc


def _scope_tasks(conn, scopes):
    by_identity = {}
    # Keep the bounded primary-key lookup first on older SQLite planners too.
    for part in chunks(sorted({scope.schedule_id for scope in scopes})):
        marks = ",".join("?" for _ in part)
        cursor = conn.execute(f"""SELECT s.id, s.version, s.op_id, bo.batch_id,
            r.operation_ref, t.ref AS task_ref, p.ref AS plan_ref
            FROM Schedule s CROSS JOIN BatchOperations bo ON bo.id=s.op_id
            CROSS JOIN WorkbenchPlanSourceRefs r ON r.kind='schedule_row' AND r.active=1
                AND r.source_key=CAST(s.id AS TEXT) AND r.version=s.version AND r.operation_id=s.op_id
                AND r.source_table='schedule' AND r.owner_key=CAST(s.version AS TEXT)
            CROSS JOIN WorkbenchPlanSourceRefs o ON o.ref=r.operation_ref AND o.kind='operation'
                AND o.active=1 AND o.source_key=CAST(bo.id AS TEXT)
            CROSS JOIN WorkbenchPlanSourceRefs p ON p.kind='official' AND p.active=1 AND p.version=s.version
                AND p.source_key=CAST(s.version AS TEXT) AND p.plan_role='adopted' AND p.source_table='schedule'
            JOIN WorkbenchTaskRefs t ON t.row_ref=r.ref AND t.plan_ref=p.ref
            WHERE s.id IN ({marks})""", part)
        for row in cursor:
            key = tuple(row[:4])
            if key in by_identity:
                raise _unavailable("execution_ledger_scope_ambiguous", op_id=row[2])
            by_identity[key] = {"operation_ref": row[4], "task_ref": row[5], "plan_ref": row[6]}
    result = {}
    for scope in scopes:
        task = by_identity.get((scope.schedule_id, scope.schedule_version, scope.op_id, scope.batch_id))
        if task is None:
            raise _unavailable("execution_ledger_scope_missing", op_id=scope.op_id)
        result[scope] = task
    return result


def _require_reported_operation_scopes(conn):
    row = conn.execute("""SELECT o.source_key FROM WorkbenchPlanSourceRefs o
        WHERE o.kind='operation' AND o.active=1
          AND EXISTS (SELECT 1 FROM WorkbenchProductionReports p WHERE p.operation_ref=o.ref)
          AND NOT EXISTS (
            SELECT 1 FROM WorkbenchPlanSourceRefs r JOIN Schedule s
              ON s.id=CAST(r.source_key AS INTEGER) AND r.source_key=CAST(s.id AS TEXT)
                AND r.operation_id=s.op_id AND r.version=s.version
            WHERE r.operation_ref=o.ref AND r.kind='schedule_row' AND r.active=1)
        LIMIT 1""").fetchone()
    if row is not None:
        raise _unavailable("execution_ledger_report_scope_missing", op_id=int(row[0]))


def _supplied_projection_map(execution_projections, refs, plan):
    result = {}
    for row in execution_projections:
        if not isinstance(row, ExecutionProjection) or row.operation_ref in result:
            raise _unavailable("execution_ledger_projection_invalid_or_duplicate")
        if row.plan_identity != plan:
            raise _unavailable("execution_ledger_projection_plan_changed")
        result[row.operation_ref] = row
    if set(result) != set(refs):
        raise _unavailable("execution_ledger_projection_scope_mismatch")
    return result


def _load_projections(ledger, refs, execution_projections):
    if execution_projections is None:
        loaded = ledger.load(refs)
        projections = {row.operation_ref: row for row in ledger.project_loaded(loaded)}
        plan, ledger_revision = loaded["plan"], loaded["clock"]["ledger_revision"]
    else:
        plan = ledger._current_plan()
        projections = _supplied_projection_map(execution_projections, refs, plan)
        ledger_revision = ledger.repo.clock()["ledger_revision"]
    return projections, plan, ledger_revision


def _adapt_scope_facts(legacy_facts, tasks, projections, plan, ledger_revision, resources):
    result = dict(legacy_facts)
    for scope, task in tasks.items():
        projection = projections[task["operation_ref"]]
        if plan and scope.schedule_version == plan["version"] and (
            projection.current_task_ref != task["task_ref"]
        ):
            raise _unavailable("execution_ledger_current_task_mismatch", op_id=scope.op_id)
        fact = legacy_facts[scope]
        changes = ledger_fact_changes(fact, projection, resources)
        if changes is None:
            continue
        projection_resources = {ref: resources.get(ref) for ref in _projection_resource_refs(projection)}
        digest = input_fingerprint({"scope_task": task, "ledger_revision": ledger_revision,
                                    "projection": _snapshot_projection(projection), "resources": projection_resources})
        result[scope] = replace(fact, state_revision=fact.state_revision + ":ledger-v1:" + digest, **changes)
    return result


def adapt_ledger_facts(ledger, legacy_facts, *, execution_projections=None):
    _require_reported_operation_scopes(ledger.conn)
    scopes = [scope for scope in legacy_facts if scope.source_table == SOURCE_SCHEDULE
              and scope.effective_plan_role == ROLE_ADOPTED and scope.scenario_id is None]
    if not scopes:
        if execution_projections:
            raise _unavailable("execution_ledger_projection_scope_mismatch")
        return legacy_facts
    tasks = _scope_tasks(ledger.conn, scopes)
    refs = list(dict.fromkeys(task["operation_ref"] for task in tasks.values()))
    projections, plan, ledger_revision = _load_projections(ledger, refs, execution_projections)
    resource_refs = {ref for row in projections.values() for ref in _projection_resource_refs(row)}
    resources = {row["ref"]: row for row in ledger.repo.resources(resource_refs)}
    return _adapt_scope_facts(legacy_facts, tasks, projections, plan, ledger_revision, resources)


def _projection_resource_refs(projection):
    refs = {getattr(report, field) for report in projection.reports
            for field in ("actual_machine_ref", "actual_operator_ref") if getattr(report, field)}
    refs.update(fact[field] for fact in projection.legacy_facts
                for field in ("actual_machine_ref", "actual_operator_ref") if fact[field])
    return refs


def _snapshot_projection(projection):
    payload = projection.to_dict()
    payload.pop("write_context")
    payload.pop("comparison_task_ref")
    for report in payload["reports"]:
        report.pop("write_context")
    return payload
