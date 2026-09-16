"""SELECT-only ledger snapshots with an explicitly supplied current-plan reader."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from sqlite3 import Connection
from typing import Callable, Optional

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import canonical_json
from core.models.workbench_execution_input import MAX_REPORT_BYTES, reject
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_execution_source_repo import WorkbenchExecutionSourceRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .projection import project_execution, report_dto
from .quality import gap


def _attach_source_changes(projection, source):
    changes = source["changes"].get(projection.operation_ref, [])
    gaps = [gap("legacy_source_changed", "旧原表与保留归档已不同；仍按归档展示，原完成证据未撤销。", **change)
            for change in changes]
    return replace(projection, data_gaps=projection.data_gaps + gaps) if gaps else projection


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

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            yield self.repo.clock()

    def _current_plan(self):
        return self.current_plan_provider(self.conn)

    def load(self, operation_refs, *, comparison_plan_ref=None):
        """Private stored facts, not a public response or a second ledger."""
        operations = self.repo.operation_rows(operation_refs)
        plan = self._current_plan()
        if comparison_plan_ref is not None:
            WorkbenchPlanIdentityRepository(self.conn).resolve_plan(comparison_plan_ref)
        legacy = self.repo.legacy(operations)
        source = WorkbenchExecutionSourceRepository(self.conn).read(legacy)
        return {"operations": operations, "reports": self.repo.reports(operations), "voids": self.repo.report_voids(operations), "legacy": legacy, "legacy_source": source,
                "current_tasks": self.repo.task_map(operations, plan["plan_ref"] if plan else None),
                "comparison_tasks": self.repo.task_map(operations, comparison_plan_ref), "plan": plan,
                "unresolved": self.repo.unresolved_operations(operations), "clock": self.repo.clock()}

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
            reject("执行投影超过本次响应大小上限，未截断历史。", "query_too_large", 413)
        return result

    def project_operations(self, operation_refs, *, comparison_plan_ref=None):
        with self.read_snapshot():
            return self.project_loaded(self.load(operation_refs, comparison_plan_ref=comparison_plan_ref))
