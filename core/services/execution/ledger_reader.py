"""SELECT-only ledger snapshots with an explicitly supplied current-plan reader.

All judgement over WorkbenchExecutionRepository facts (missing schema, unknown refs,
row caps, ref syntax) lives here; the repository only reads what is stored.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from sqlite3 import Connection
from typing import Any, Callable, Dict, Optional

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_execution_input import MAX_FACT_ROWS, MAX_OPERATIONS, public_ref, reject
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.execution_ledger_scope_repo import ExecutionLedgerScopeRepository
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .projection import active_report_dto, project_execution, report_dto


def _capped(read, refs, message):
    result, count = read(refs, MAX_FACT_ROWS)
    if count > MAX_FACT_ROWS:
        reject(message, "query_too_large", 413)
    return result


def project_loaded_operation(facts, ref, *, include_history: bool = True):
    op = facts["operations"][ref]
    active_loaded = facts.get("active_loaded")
    if active_loaded is not None and ref in active_loaded:
        if include_history:
            raise RuntimeError("Full report history requires load(..., include_history=True).")
        reports = [
            active_report_dto(row)
            for row in facts["active_reports"].get(ref, ())
        ]
        return project_execution(
            op,
            reports,
            current_task=facts["current_tasks"].get(ref),
            comparison_task=facts["comparison_tasks"].get(ref),
            plan_identity=facts["plan"],
        )
    voids = facts["voids"]
    histories = facts["reports"].get(ref, {})
    if set(facts["report_heads"].get(ref, ())) - set(histories):
        reject("报工来源或更正记录损坏，请核对报工数据；仍不行请联系维护人员。", "storage_failure", 500)
    reports = sorted(
        (report_dto(rows, operation_ref=ref, report_ref=report_ref, include_history=include_history)
         for report_ref, rows in histories.items()),
        key=lambda row: (row.recorded_at, row.report_no),
    )
    voided = []
    if voids:
        if include_history:
            voided = [
                {
                    "report": report.to_dict(),
                    "void_fact": {key: value for key, value in voids[report.report_ref].items() if key != "request_key"},
                }
                for report in reports
                if report.report_ref in voids
            ]
        reports = [report for report in reports if report.report_ref not in voids]
    projection = project_execution(
        op,
        reports,
        current_task=facts["current_tasks"].get(ref),
        comparison_task=facts["comparison_tasks"].get(ref),
        plan_identity=facts["plan"],
    )
    if voided:
        projection = replace(projection, voided_reports=voided)
    return projection


def project_loaded_facts(facts, *, include_history: bool = True):
    return [project_loaded_operation(facts, ref, include_history=include_history) for ref in facts["operations"]]


@dataclass
class ExecutionLedgerReadScope:
    reader: "ExecutionLedgerReader"
    clock: Dict[str, Any]
    plan: Optional[dict] = None
    plan_read: bool = False
    operations: Dict[str, Any] = field(default_factory=dict)
    task_maps: Dict[Any, Dict[str, Any]] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    comparison_plans: Dict[str, WorkbenchPlanLocator] = field(default_factory=dict)
    facts: Dict[str, Any] = field(
        default_factory=lambda: {
            "loaded": set(),
            "active_loaded": set(),
            "active_reports": {},
            "reports": {},
            "report_heads": {},
            "voids": {},
            "scope_tasks": {},
        }
    )

    @property
    def conn(self):
        return self.reader.conn


class ExecutionLedgerReader:
    def __init__(self, conn, *, current_plan_provider: Callable[[Connection], Optional[dict]]):
        self.conn = conn
        self.current_plan_provider = current_plan_provider
        self.repo = WorkbenchExecutionRepository(conn)

    # ---- judgement over repository facts ----

    def read_clock(self):
        clock = self.repo.clock()
        if clock is None:
            reject("报工或计划状态资料缺失，请联系维护人员核对。", "execution_ledger_unavailable", 409)
        return clock

    def revision_clock(self, scope: ExecutionLedgerReadScope):
        return scope.clock

    def seed_operations(self, scope: ExecutionLedgerReadScope, rows):
        scope.operations.update((row["operation_ref"], row) for row in rows)

    def operation_rows(self, scope: ExecutionLedgerReadScope, refs):
        values = list(dict.fromkeys(public_ref(ref) for ref in refs))
        return self._operation_rows(scope, values)

    def _operation_rows(self, scope: ExecutionLedgerReadScope, values):
        if len(values) > MAX_OPERATIONS:
            reject(f"执行工序超过单次{MAX_OPERATIONS}条读取上限。", "query_too_large", 413)
        stored = scope.operations
        missing = [ref for ref in values if ref not in stored]
        if missing:
            stored.update(self.repo.operation_rows(missing))
        result = {ref: stored[ref] for ref in values if ref in stored}
        if len(result) != len(values):
            reject("工序关联资料缺失，请刷新重选；仍无法打开时请联系维护人员。", "entity_not_found", 404)
        return result

    def task_map(self, scope: ExecutionLedgerReadScope, operation_refs, plan_ref, *, cohort=False):
        if plan_ref is None:
            return {}
        refs = list(operation_refs)
        stored = scope.task_maps.setdefault(plan_ref, {})
        missing = [ref for ref in refs if ref not in stored]
        if missing:
            rows = self.repo.cohort_task_rows(missing, plan_ref) if cohort else self.repo.task_rows(missing, plan_ref)
            result = {row["operation_ref"]: row for row in rows}
            stored.update((ref, result.get(ref)) for ref in missing)
        return {ref: stored[ref] for ref in refs if stored[ref] is not None}

    def resources(self, scope: ExecutionLedgerReadScope, refs):
        refs = sorted(set(refs))
        stored = scope.resources
        missing = [ref for ref in refs if ref not in stored]
        if missing:
            found = {row["ref"]: row for row in self.repo.resources(missing)}
            stored.update((ref, found.get(ref)) for ref in missing)
        return [stored[ref] for ref in refs if stored[ref] is not None]

    def scope_task_rows(self, scope: ExecutionLedgerReadScope, schedule_ids):
        """Permanent scope bindings, reusing admitted official task mappings."""
        stored = scope.facts["scope_tasks"]
        wanted = set(schedule_ids)
        pending = wanted.difference(stored)
        if pending:
            bindings = scope.comparison_plans
            operations = scope.operations
            current_ref = scope.plan["plan_ref"] if scope.plan else None
            for plan_ref, tasks in scope.task_maps.items():
                locator = bindings.get(plan_ref)
                if plan_ref != current_ref and (locator is None or locator.plan_role != "adopted"):
                    continue
                for operation_ref, task in tasks.items():
                    if task is None or task["schedule_id"] not in pending or task["schedule_id"] in stored:
                        continue
                    schedule_id = task["schedule_id"]
                    stored[schedule_id] = []
                    operation = operations.get(operation_ref)
                    if (
                        operation is not None
                        and operation["identity_active"] == 1
                        and operation["id"] == task["op_id"]
                    ):
                        stored[schedule_id].append((
                            schedule_id, task["version"], task["op_id"], operation["batch_id"],
                            operation_ref, task["task_ref"], plan_ref, operation["source"],
                            task["start_time"], task["end_time"], task["machine_id"], task["operator_id"], task["lock_status"],
                            operation["setup_hours"], operation["unit_hours"], task["start_us"], task["end_us"],
                        ))
        missing = sorted(wanted.difference(stored))
        if missing:
            found = {key: [] for key in missing}
            for row in ExecutionLedgerScopeRepository(self.conn).scope_task_rows(missing):
                found[row[0]].append(row)
            stored.update(found)
            for rows in found.values():
                for row in rows:
                    tasks = scope.task_maps.setdefault(row[6], {})
                    task = {
                        "task_ref": row[5],
                        "plan_ref": row[6],
                        "operation_ref": row[4],
                        "op_id": row[2],
                        "version": row[1],
                        "schedule_id": row[0],
                        **dict(zip(("start_time", "end_time", "machine_id", "operator_id", "lock_status"), row[8:13])),
                        "start_us": row[15],
                        "end_us": row[16],
                    }
                    tasks[row[4]] = task
        return [row for schedule_id in sorted(wanted) for row in stored[schedule_id]]

    def reported_operation_without_schedule_row(self, scope: ExecutionLedgerReadScope):
        stored = scope.facts
        if "reported_scope" not in stored:
            stored["reported_scope"] = ExecutionLedgerScopeRepository(self.conn).reported_operation_without_schedule_row()
        return stored["reported_scope"]

    def report_header(self, *, report_ref):
        public_ref(report_ref)
        return self.repo.report_header(report_ref=report_ref)

    # ---- snapshots and projections ----

    @contextmanager
    def read_snapshot(self):
        """One cached ledger view per read transaction; a caller's open transaction is joined, never nested."""
        with ExitStack() as owned:
            if not self.conn.in_transaction:
                owned.enter_context(TransactionManager(self.conn).transaction())
            yield ExecutionLedgerReadScope(reader=self, clock=self.read_clock())

    def current_plan(self, scope: ExecutionLedgerReadScope):
        if not scope.plan_read:
            scope.plan = self.current_plan_provider(self.conn)
            scope.plan_read = True
        return scope.plan

    def load(
        self,
        scope: ExecutionLedgerReadScope,
        operation_refs,
        *,
        comparison_plan_ref=None,
        include_history: bool = True,
        _admitted_refs=False,
    ):
        """Private stored facts, not a public response or a second ledger."""
        operations = (
            self._operation_rows(scope, operation_refs)
            if _admitted_refs
            else self.operation_rows(scope, operation_refs)
        )
        plan = self.current_plan(scope)
        if comparison_plan_ref is not None and (plan is None or comparison_plan_ref != plan["plan_ref"]):
            admitted = scope.comparison_plans
            if comparison_plan_ref not in admitted:
                admitted[comparison_plan_ref] = WorkbenchPlanIdentityRepository(self.conn).resolve_plan(comparison_plan_ref)
        stored = scope.facts
        current_plan_ref = plan["plan_ref"] if plan else None
        current_tasks = self.task_map(scope, operations, current_plan_ref)
        comparison_tasks = (
            current_tasks
            if comparison_plan_ref is not None and comparison_plan_ref == current_plan_ref
            else self.task_map(scope, operations, comparison_plan_ref)
        )
        if not include_history:
            missing_active = [
                ref for ref in operations if ref not in stored["active_loaded"] and ref not in stored["loaded"]
            ]
            if missing_active:
                active, active_count = self.repo.active_reports(missing_active, MAX_FACT_ROWS)
                if active_count > MAX_FACT_ROWS:
                    reject("报工及更正历史超过读取上限，请缩小范围。", "query_too_large", 413)
                stored["active_reports"].update(active)
                stored["active_loaded"].update(missing_active)
            active_loaded = {ref for ref in operations if ref in stored["active_loaded"] and ref not in stored["loaded"]}
            active_reports = {ref: stored["active_reports"][ref] for ref in active_loaded if ref in stored["active_reports"]}
            full_refs = [ref for ref in operations if ref not in active_loaded]
            reports = {ref: stored["reports"][ref] for ref in full_refs if ref in stored["reports"]}
            report_heads = {ref: stored["report_heads"][ref] for ref in full_refs if ref in stored["report_heads"]}
            report_refs = {report_ref for group in reports.values() for report_ref in group}
            voids = {ref: stored["voids"][ref] for ref in report_refs if ref in stored["voids"]}
            orphan_count = sum(len(refs) for refs in report_heads.values()) - len(report_refs)
            active_total = sum(len(rows) for rows in active_reports.values())
            history_total = sum(len(rows) for group in reports.values() for rows in group.values()) + orphan_count
            if active_total + history_total > MAX_FACT_ROWS or len(voids) > MAX_FACT_ROWS:
                reject("报工及历史记录超过读取上限，请缩小范围。", "query_too_large", 413)
            return {
                "operations": operations,
                "active_loaded": active_loaded,
                "active_reports": active_reports,
                "reports": reports,
                "report_heads": report_heads,
                "voids": voids,
                "current_tasks": current_tasks,
                "comparison_tasks": comparison_tasks,
                "plan": plan,
                "clock": scope.clock,
            }
        missing = {ref: row for ref, row in operations.items() if ref not in stored["loaded"]}
        if missing:
            reports, report_heads, report_count = self.repo.reports(missing, MAX_FACT_ROWS)
            if report_count > MAX_FACT_ROWS:
                reject("报工及更正历史超过读取上限，请缩小范围。", "query_too_large", 413)
            voids = _capped(self.repo.report_voids, missing, "报工撤销历史超过读取上限，请缩小范围。")
            stored["reports"].update(reports)
            stored["report_heads"].update(report_heads)
            stored["voids"].update(voids)
            stored["loaded"].update(missing)
        reports = {ref: stored["reports"][ref] for ref in operations if ref in stored["reports"]}
        report_heads = {ref: stored["report_heads"][ref] for ref in operations if ref in stored["report_heads"]}
        report_refs = {report_ref for group in reports.values() for report_ref in group}
        voids = {ref: stored["voids"][ref] for ref in report_refs if ref in stored["voids"]}
        orphan_count = sum(len(refs) for refs in report_heads.values()) - len(report_refs)
        if (sum(len(rows) for group in reports.values() for rows in group.values()) + orphan_count > MAX_FACT_ROWS
                or len(voids) > MAX_FACT_ROWS):
            reject("报工及历史记录超过读取上限，请缩小范围。", "query_too_large", 413)
        return {"operations": operations, "reports": reports, "report_heads": report_heads, "voids": voids,
                "current_tasks": current_tasks, "comparison_tasks": comparison_tasks, "plan": plan,
                "clock": scope.clock}

    def load_many(
        self,
        scope: ExecutionLedgerReadScope,
        operation_refs,
        *,
        comparison_plan_ref=None,
        include_history: bool = True,
    ):
        """Read a complete cohort in bounded batches under one ledger snapshot.

        The operation/fact limits apply to each repository read, not to a
        paginated consumer's complete cohort. Merge facts before projection so
        reports, revisions, voids and task bindings keep the same semantics as
        one admitted load.
        """
        refs = list(dict.fromkeys(public_ref(ref) for ref in operation_refs))
        if len(refs) <= MAX_OPERATIONS:
            return self.load(
                scope,
                refs,
                comparison_plan_ref=comparison_plan_ref,
                include_history=include_history,
                _admitted_refs=True,
            )
        # A SQL parameter chunk otherwise scans the same plan again.
        # Keep only this cohort in the existing, request-local map;
        # operation and report facts still use their bounded loads.
        plan = self.current_plan(scope)
        for plan_ref in dict.fromkeys([plan["plan_ref"] if plan else None, comparison_plan_ref]):
            self.task_map(scope, refs, plan_ref, cohort=True)
        result = self.load(
            scope,
            refs[:MAX_OPERATIONS],
            comparison_plan_ref=comparison_plan_ref,
            include_history=include_history,
            _admitted_refs=True,
        )
        for start in range(MAX_OPERATIONS, len(refs), MAX_OPERATIONS):
            batch = self.load(
                scope,
                refs[start:start + MAX_OPERATIONS],
                comparison_plan_ref=comparison_plan_ref,
                include_history=include_history,
                _admitted_refs=True,
            )
            for key in ("operations", "reports", "report_heads", "voids", "current_tasks", "comparison_tasks"):
                result[key].update(batch[key])
            if not include_history:
                result["active_loaded"].update(batch["active_loaded"])
                result["active_reports"].update(batch["active_reports"])
        return result

    def project_operation(self, facts, ref, *, include_history: bool = True):
        return project_loaded_operation(facts, ref, include_history=include_history)

    def project_loaded(self, facts, *, include_history: bool = True):
        return [self.project_operation(facts, ref, include_history=include_history) for ref in facts["operations"]]

    def project_operations(self, scope: ExecutionLedgerReadScope, operation_refs):
        return self.project_loaded(self.load_many(scope, operation_refs))
