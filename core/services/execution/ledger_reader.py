"""SELECT-only ledger snapshots with an explicitly supplied current-plan reader.

All judgement over WorkbenchExecutionRepository facts (missing schema, unknown refs,
row caps, ref syntax) lives here; the repository only reads what is stored.
"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from sqlite3 import Connection
from typing import Callable, Optional

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_execution_input import MAX_FACT_ROWS, MAX_OPERATIONS, MAX_REPORT_BYTES, public_ref, reject
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_execution_source_repo import WorkbenchExecutionSourceRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

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
        if len(values) > MAX_OPERATIONS:
            reject("执行工序超过单次10000条读取上限。", "query_too_large", 413)
        result = self.repo.operation_rows(values)
        if set(result) != set(values):
            reject("工序关联资料缺失，请刷新重选；仍无法打开时请联系维护人员。", "entity_not_found", 404)
        return result

    def task_header(self, task_ref):
        public_ref(task_ref)
        row = self.repo.task_headers([task_ref]).get(task_ref)
        if row is None or row["operation_ref"] is None:
            reject("任务不存在或报工关联资料缺失，请刷新重选。", "entity_not_found", 404)
        return row

    def task_map(self, operation_refs, plan_ref):
        result = {}
        for row in self.repo.task_rows(operation_refs, plan_ref):
            if row["operation_ref"] in result:
                reject("同一份计划里这道工序出现了两条安排，系统没有继续读取，请联系维护人员核对数据。", "constraint_conflict", 409)
            result[row["operation_ref"]] = row
        return result

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
            try:
                yield dict(self._snapshot_clock)
            finally:
                self._snapshot_clock = None

    def _current_plan(self):
        return self.current_plan_provider(self.conn)

    def load(self, operation_refs, *, comparison_plan_ref=None):
        """Private stored facts, not a public response or a second ledger."""
        operations = self.operation_rows(operation_refs)
        plan = self._current_plan()
        if comparison_plan_ref is not None:
            WorkbenchPlanIdentityRepository(self.conn).resolve_plan(comparison_plan_ref)
        legacy = _capped(self.repo.legacy, operations, "历史现场记录超过读取上限，请缩小范围。")
        source = WorkbenchExecutionSourceRepository(self.conn).read(legacy)
        reports = _capped(self.repo.reports, operations, "报工及更正历史超过读取上限，请缩小范围。")
        voids = _capped(self.repo.report_voids, operations, "报工撤销历史超过读取上限，请缩小范围。")
        current_plan_ref = plan["plan_ref"] if plan else None
        current_tasks = self.task_map(operations, current_plan_ref)
        # Both fields retain independent plain rows, but the same admitted plan
        # needs only one complete mapping read in this caller's snapshot.
        comparison_tasks = ({ref: dict(row) for ref, row in current_tasks.items()}
                            if comparison_plan_ref is not None and comparison_plan_ref == current_plan_ref
                            else self.task_map(operations, comparison_plan_ref))
        return {"operations": operations,
                "reports": reports,
                "voids": voids,
                "legacy": legacy, "legacy_source": source,
                "current_tasks": current_tasks,
                "comparison_tasks": comparison_tasks, "plan": plan,
                "unresolved": self.repo.unresolved_operations(operations), "clock": self.revision_clock()}

    def project_loaded(self, facts):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Ledger clock must return naive factory-local datetime.")
        result = []
        for ref, op in facts["operations"].items():
            histories = facts["reports"].get(ref, {})
            reports = sorted((report_dto(rows) for rows in histories.values()), key=lambda row: (row.recorded_at, row.report_no))
            voids = facts["voids"]
            voided = [{"report": report.to_dict(), "void_fact": {key: value for key, value in voids[report.report_ref].items()
                       if key != "request_key"}} for report in reports if report.report_ref in voids]
            reports = [report for report in reports if report.report_ref not in voids]
            projection = project_execution(op, reports, facts["legacy"].get(ref, []),
                current_task=facts["current_tasks"].get(ref), comparison_task=facts["comparison_tasks"].get(ref),
                plan_identity=facts["plan"], now=now, unresolved=ref in facts["unresolved"])
            result.append(_attach_source_changes(replace(projection, voided_reports=voided), facts["legacy_source"]))
        if len(canonical_json([row.to_dict() for row in result]).encode("utf-8")) > MAX_REPORT_BYTES:
            reject("这次要读的报工记录超过了单次读取上限，系统没有截断历史，请缩小工序范围后再读。", "query_too_large", 413)
        return result

    def project_operations(self, operation_refs, *, comparison_plan_ref=None):
        with self.read_snapshot():
            return self.project_loaded(self.load(operation_refs, comparison_plan_ref=comparison_plan_ref))
