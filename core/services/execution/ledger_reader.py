"""SELECT-only ledger snapshots with an explicitly supplied current-plan reader.

All judgement over WorkbenchExecutionRepository facts (missing schema, unknown refs,
row caps, ref syntax) lives here; the repository only reads what is stored.
"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from sqlite3 import Connection
from typing import Any, Callable, Dict, Optional, cast

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import MAX_FACT_ROWS, MAX_OPERATIONS, public_ref, reject
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.execution_ledger_scope_repo import ExecutionLedgerScopeRepository
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_execution_source_repo import WorkbenchExecutionSourceRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .legacy import legacy_evidence
from .projection import project_execution, report_dto
from .quality import gap


def _attach_source_changes(projection, source):
    changes = source["changes"].get(projection.operation_ref, [])
    gaps = [gap("legacy_source_changed", "这条旧记录的来源数据后来被改过，界面仍按当时保存下来的内容显示，原完工记录没有撤销。", **change)
            for change in changes]
    return replace(projection, data_gaps=projection.data_gaps + gaps) if gaps else projection


def _capped(read, refs, message):
    result, count = read(refs, MAX_FACT_ROWS)
    if count > MAX_FACT_ROWS:
        reject(message, "query_too_large", 413)
    return result


class ExecutionLedgerReader:
    def __init__(self, conn, *, current_plan_provider: Callable[[Connection], Optional[dict]],
                 clock: Optional[Callable[[], datetime]] = None):
        if not callable(current_plan_provider):
            raise TypeError("Ledger current-plan provider must be callable.")
        if clock is not None and not callable(clock):
            raise TypeError("Ledger clock must be callable.")
        self.conn = conn
        self.current_plan_provider = current_plan_provider
        self.clock = datetime.now if clock is None else clock
        self.repo = WorkbenchExecutionRepository(conn)
        self._snapshot_clock = None
        self._snapshot_plan = None
        self._snapshot_plan_read = False
        self._snapshot_operations = None
        self._snapshot_task_maps = None
        self._snapshot_resources = None
        self._snapshot_comparison_plans = None
        self._snapshot_facts = None
        self._snapshot_legacy_evidence = None

    # ---- judgement over repository facts ----

    def require_schema(self):
        if self._snapshot_clock is not None:
            return
        if self.repo.schema_issues():
            raise WorkbenchCommandRejected("execution_ledger_unavailable", "报工数据库结构不完整，请联系维护人员升级数据库。")

    def revision_clock(self):
        if self._snapshot_clock is not None:
            return dict(self._snapshot_clock)
        clock = self.repo.clock()
        if clock is None:
            reject("报工或计划状态资料缺失，请联系维护人员核对。", "execution_ledger_unavailable", 409)
        return clock

    def operation_rows(self, refs):
        values = list(dict.fromkeys(public_ref(ref) for ref in refs))
        return self._operation_rows(values)

    def _operation_rows(self, values):
        if len(values) > MAX_OPERATIONS:
            reject("执行工序超过单次10000条读取上限。", "query_too_large", 413)
        stored = self._snapshot_operations
        if stored is None:
            result = self.repo.operation_rows(values)
        else:
            missing = [ref for ref in values if ref not in stored]
            if missing:
                stored.update(self.repo.operation_rows(missing))
            result = {ref: stored[ref] for ref in values if ref in stored}
        if set(result) != set(values):
            reject("工序关联资料缺失，请刷新重选；仍无法打开时请联系维护人员。", "entity_not_found", 404)
        return result

    def task_header(self, task_ref):
        public_ref(task_ref)
        row = self.repo.task_headers([task_ref]).get(task_ref)
        if row is None or row["operation_ref"] is None:
            reject("任务不存在或报工关联资料缺失，请刷新重选。", "entity_not_found", 404)
        return row

    def task_map(self, operation_refs, plan_ref, *, cohort=False):
        if plan_ref is None:
            return {}
        refs = list(operation_refs)
        stored = None if self._snapshot_task_maps is None else self._snapshot_task_maps.setdefault(plan_ref, {})
        missing = refs if stored is None else [ref for ref in refs if ref not in stored]
        result = {}
        if missing:
            rows = self.repo.cohort_task_rows(missing, plan_ref) if cohort else self.repo.task_rows(missing, plan_ref)
            for row in rows:
                if row["operation_ref"] in result:
                    reject("同一份计划里这道工序出现了两条安排，系统没有继续读取，请联系维护人员核对数据。", "constraint_conflict", 409)
                result[row["operation_ref"]] = row
        if stored is None:
            return result
        stored.update((ref, result.get(ref)) for ref in missing)
        return {ref: stored[ref] for ref in refs if stored[ref] is not None}

    def resources(self, refs):
        refs = sorted(set(refs))
        stored = self._snapshot_resources
        if stored is None:
            return self.repo.resources(refs)
        missing = [ref for ref in refs if ref not in stored]
        if missing:
            found = {row["ref"]: row for row in self.repo.resources(missing)}
            stored.update((ref, found.get(ref)) for ref in missing)
        return [stored[ref] for ref in refs if stored[ref] is not None]

    def scope_task_rows(self, schedule_ids):
        """Permanent legacy-scope bindings, reusing admitted official task mappings."""
        stored = self._snapshot_facts["scope_tasks"] if self._snapshot_facts is not None else {}
        wanted = set(schedule_ids)
        pending = wanted.difference(stored)
        if self._snapshot_task_maps is not None and pending:
            bindings = cast(Dict[str, WorkbenchPlanLocator], self._snapshot_comparison_plans)
            operations = cast(Dict[str, Dict[str, Any]], self._snapshot_operations)
            current_ref = self._snapshot_plan["plan_ref"] if self._snapshot_plan else None
            for plan_ref, tasks in self._snapshot_task_maps.items():
                locator = bindings.get(plan_ref)
                if plan_ref != current_ref and (locator is None or locator.plan_role != "adopted" or locator.scenario_id is not None):
                    continue
                for operation_ref, task in tasks.items():
                    if task is None or task["schedule_id"] not in pending or task["schedule_id"] in stored:
                        continue
                    schedule_id = task["schedule_id"]
                    stored[schedule_id] = []
                    operation = operations.get(operation_ref)
                    if (operation is not None and operation["identity_active"] == 1
                            and operation["id"] == task["op_id"] and task["identity_kind"] == "schedule_row"
                            and task["identity_source_table"] == "schedule" and task["row_source_key"] == str(schedule_id)
                            and task["owner_key"] == str(task["version"])):
                        stored[schedule_id].append((schedule_id, task["version"], task["op_id"], operation["batch_id"],
                            operation_ref, task["task_ref"], plan_ref, operation["source"]))
        missing = sorted(wanted - set(stored))
        if missing:
            found = {key: [] for key in missing}
            for row in ExecutionLedgerScopeRepository(self.conn).scope_task_rows(missing):
                found[row[0]].append(row)
            stored.update(found)
            if self._snapshot_task_maps is not None:
                for rows in found.values():
                    for row in rows:
                        tasks = self._snapshot_task_maps.setdefault(row[6], {})
                        task = {"task_ref": row[5], "plan_ref": row[6], "operation_ref": row[4],
                            "op_id": row[2], "version": row[1], "identity_kind": "schedule_row",
                            "identity_source_table": "schedule", "row_source_key": str(row[0]),
                            "owner_key": str(row[1]), "schedule_id": row[0],
                            **dict(zip(("start_time", "end_time", "machine_id", "operator_id", "lock_status"), row[8:]))}
                        if tasks.get(row[4]) is not None and tasks[row[4]]["task_ref"] != row[5]:
                            reject("同一份计划里这道工序出现了两条安排，系统没有继续读取，请联系维护人员核对数据。", "constraint_conflict", 409)
                        tasks[row[4]] = task
        return [row for schedule_id in sorted(wanted) for row in stored[schedule_id]]

    def reported_operation_without_schedule_row(self):
        stored = self._snapshot_facts
        if stored is None:
            return ExecutionLedgerScopeRepository(self.conn).reported_operation_without_schedule_row()
        if "reported_scope" not in stored:
            stored["reported_scope"] = ExecutionLedgerScopeRepository(self.conn).reported_operation_without_schedule_row()
        return stored["reported_scope"]

    def page_tasks(self, plan_ref, size, after):
        public_ref(plan_ref)
        if type(size) is not int or not 1 <= size <= 500:
            reject("执行任务分页大小须为1至500。", status=400)
        if after is not None:
            public_ref(after)
        return self.repo.page_tasks(plan_ref, size, after)

    def report_header(self, *, report_ref=None, report_no=None):
        if report_ref is not None:
            public_ref(report_ref)
        return self.repo.report_header(report_ref=report_ref, report_no=report_no)

    # ---- snapshots and projections ----

    @contextmanager
    def read_snapshot(self):
        if self._snapshot_clock is not None:
            yield dict(self._snapshot_clock)
            return
        with TransactionManager(self.conn).transaction():
            self.require_schema()
            self._snapshot_clock = self.revision_clock()
            self._snapshot_plan, self._snapshot_plan_read = None, False
            self._snapshot_operations, self._snapshot_task_maps, self._snapshot_resources = {}, {}, {}
            self._snapshot_comparison_plans = {}
            self._snapshot_legacy_evidence = {}
            self._snapshot_facts = {"loaded": set(), "reports": {}, "voids": {}, "legacy": {},
                                    "legacy_source": {"states": {}, "changes": {}}, "unresolved": set(), "scope_tasks": {}}
            try:
                yield dict(self._snapshot_clock)
            finally:
                self._snapshot_clock = None
                self._snapshot_plan, self._snapshot_plan_read = None, False
                self._snapshot_operations = self._snapshot_task_maps = self._snapshot_resources = None
                self._snapshot_comparison_plans = None
                self._snapshot_facts = None
                self._snapshot_legacy_evidence = None

    def _current_plan(self):
        if self._snapshot_clock is None:
            return self.current_plan_provider(self.conn)
        if not self._snapshot_plan_read:
            self._snapshot_plan = self.current_plan_provider(self.conn)
            self._snapshot_plan_read = True
        return self._snapshot_plan

    def load(self, operation_refs, *, comparison_plan_ref=None, _admitted_refs=False):
        """Private stored facts, not a public response or a second ledger."""
        operations = self._operation_rows(operation_refs) if _admitted_refs else self.operation_rows(operation_refs)
        plan = self._current_plan()
        if comparison_plan_ref is not None and (plan is None or comparison_plan_ref != plan["plan_ref"]):
            admitted = self._snapshot_comparison_plans
            if admitted is None or comparison_plan_ref not in admitted:
                locator = WorkbenchPlanIdentityRepository(self.conn).resolve_plan(comparison_plan_ref)
                if admitted is not None:
                    admitted[comparison_plan_ref] = locator
        stored = self._snapshot_facts
        if stored is None:
            stored = {"loaded": set(), "reports": {}, "voids": {}, "legacy": {},
                      "legacy_source": {"states": {}, "changes": {}}, "unresolved": set(), "scope_tasks": {}}
        missing = {ref: row for ref, row in operations.items() if ref not in stored["loaded"]}
        if missing:
            legacy = _capped(self.repo.legacy, missing, "历史现场记录超过读取上限，请缩小范围。")
            source = WorkbenchExecutionSourceRepository(self.conn).read(legacy)
            reports = _capped(self.repo.reports, missing, "报工及更正历史超过读取上限，请缩小范围。")
            voids = _capped(self.repo.report_voids, missing, "报工撤销历史超过读取上限，请缩小范围。")
            stored["legacy"].update(legacy)
            stored["reports"].update(reports)
            stored["voids"].update(voids)
            for key in ("states", "changes"):
                stored["legacy_source"][key].update(source[key])
            stored["unresolved"].update(self.repo.unresolved_operations(missing))
            stored["loaded"].update(missing)
        legacy = {ref: stored["legacy"][ref] for ref in operations if ref in stored["legacy"]}
        reports = {ref: stored["reports"][ref] for ref in operations if ref in stored["reports"]}
        report_refs = {report_ref for group in reports.values() for report_ref in group}
        voids = {ref: stored["voids"][ref] for ref in report_refs if ref in stored["voids"]}
        if (sum(len(rows) for rows in legacy.values()) > MAX_FACT_ROWS
                or sum(len(rows) for group in reports.values() for rows in group.values()) > MAX_FACT_ROWS
                or len(voids) > MAX_FACT_ROWS):
            reject("报工及历史记录超过读取上限，请缩小范围。", "query_too_large", 413)
        source = {key: {ref: values[ref] for ref in operations if ref in values}
                  for key, values in stored["legacy_source"].items()}
        current_plan_ref = plan["plan_ref"] if plan else None
        current_tasks = self.task_map(operations, current_plan_ref)
        comparison_tasks = (current_tasks
                            if comparison_plan_ref is not None and comparison_plan_ref == current_plan_ref
                            else self.task_map(operations, comparison_plan_ref))
        return {"operations": operations, "reports": reports, "voids": voids,
                "legacy": legacy, "legacy_source": source,
                "current_tasks": current_tasks, "comparison_tasks": comparison_tasks, "plan": plan,
                "unresolved": stored["unresolved"].intersection(operations), "clock": self.revision_clock()}

    def load_many(self, operation_refs, *, comparison_plan_ref=None):
        """Read a complete cohort in bounded batches under one ledger snapshot.

        The operation/fact limits apply to each repository read, not to a
        paginated consumer's complete cohort. Merge facts before projection so
        reports, revisions, voids and task bindings keep the same semantics as
        one admitted load.
        """
        refs = list(dict.fromkeys(public_ref(ref) for ref in operation_refs))
        with self.read_snapshot():
            if len(refs) <= MAX_OPERATIONS:
                return self.load(refs, comparison_plan_ref=comparison_plan_ref, _admitted_refs=True)
            # A SQL parameter chunk otherwise scans the same plan again.
            # Keep only this cohort in the existing, request-local map;
            # operation and report facts still use their bounded loads.
            plan = self._current_plan()
            for plan_ref in dict.fromkeys([plan["plan_ref"] if plan else None, comparison_plan_ref]):
                self.task_map(refs, plan_ref, cohort=True)
            result = self.load(refs[:MAX_OPERATIONS], comparison_plan_ref=comparison_plan_ref, _admitted_refs=True)
            for start in range(MAX_OPERATIONS, len(refs), MAX_OPERATIONS):
                batch = self.load(refs[start:start + MAX_OPERATIONS],
                                  comparison_plan_ref=comparison_plan_ref, _admitted_refs=True)
                for key in ("operations", "reports", "voids", "legacy", "current_tasks", "comparison_tasks"):
                    result[key].update(batch[key])
                for key in ("states", "changes"):
                    result["legacy_source"][key].update(batch["legacy_source"][key])
                result["unresolved"].update(batch["unresolved"])
            return result

    def project_loaded(self, facts):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Ledger clock must return naive factory-local datetime.")
        result = []
        evidence_by_operation = self._snapshot_legacy_evidence
        if evidence_by_operation is None:
            evidence_by_operation = {}
        for ref, op in facts["operations"].items():
            histories = facts["reports"].get(ref, {})
            reports = sorted((report_dto(rows) for rows in histories.values()), key=lambda row: (row.recorded_at, row.report_no))
            voids = facts["voids"]
            voided = [{"report": report.to_dict(), "void_fact": {key: value for key, value in voids[report.report_ref].items()
                       if key != "request_key"}} for report in reports if report.report_ref in voids]
            reports = [report for report in reports if report.report_ref not in voids]
            if ref not in evidence_by_operation:
                evidence_by_operation[ref] = legacy_evidence(facts["legacy"].get(ref, []), now)
            projection = project_execution(op, reports, evidence_by_operation[ref],
                current_task=facts["current_tasks"].get(ref), comparison_task=facts["comparison_tasks"].get(ref),
                plan_identity=facts["plan"], unresolved=ref in facts["unresolved"])
            if voided:
                projection = replace(projection, voided_reports=voided)
            result.append(_attach_source_changes(projection, facts["legacy_source"]))
        return result

    def project_operations(self, operation_refs, *, comparison_plan_ref=None):
        with self.read_snapshot():
            return self.project_loaded(self.load(operation_refs, comparison_plan_ref=comparison_plan_ref))
