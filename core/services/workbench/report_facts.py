"""Real ReportEngine/ExecutionReview facts, with current-official identity guards."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_report import MAX_REPORT_EVENTS, MAX_REPORT_OPERATIONS
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from core.services.report.report_engine import ReportEngine
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from core.services.workbench.plan_projection import project_plan
from core.services.workbench.plan_queries import WorkbenchPlanQueryService


class ReportReadEngine(ReportEngine):
    """Keep the domain's guarded read and labels; retain typed inputs privately."""

    def _execution_review_rows(self, plan_rows):
        self.plan_rows = [dict(row) for row in plan_rows]
        # Only plan labels come from the old renderer. Execution has one ledger owner.
        return [self._execution_review_row(row, None) for row in self.plan_rows]


class WorkbenchReportFacts:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.plans = WorkbenchPlanQueryService(conn, logger)
        self.engine = ReportReadEngine(conn, logger)

    def read_snapshot(self):
        return self.plans.read_snapshot()

    def current_plan(self, scope):
        ref = scope.plan_ref
        if ref is None:
            version = self.engine.latest_version()
            if not version:
                raise WorkbenchCommandRejected("plan_unavailable", "当前没有正式计划，不能生成现场分析。")
            ref = self.plans.references.get_plan_ref(WorkbenchPlanLocator(version, ROLE_ADOPTED))
        locator = self.plans.references.resolve_plan(ref)
        if locator.plan_role != ROLE_ADOPTED or locator.scenario_id is not None:
            raise WorkbenchCommandRejected("plan_not_current_official", "执行分析只认当前正式采用计划，不能使用候选或模拟方案。")
        _, entry, span = self.plans._selected(ref)
        plan = project_plan(entry, ref)
        if not plan["is_current_official"]:
            raise WorkbenchCommandRejected("plan_not_current_official", "所选计划不是当前可执行的正式计划，未切换到其他版本。")
        return replace(scope, plan_ref=ref), plan, locator.version, span

    def _resource_maps(self, rows):
        maps = {}
        for kind, table, key in (("machine", "Machines", "machine_id"), ("operator", "Operators", "operator_id"),
                                 ("batch", "Batches", "batch_id")):
            keys = {str(row[key]) for row in rows if row.get(key) not in (None, "")}
            identities = self.plans.entities.active_map(kind, sorted(keys))
            if set(identities) != keys:
                raise WorkbenchCommandRejected("identity_missing", "批次或实际资源永久引用缺失，读取不会补建或猜测对象。")
            labels = {}
            if kind != "batch":
                values = sorted(keys)
                for start in range(0, len(values), 400):
                    chunk = values[start:start + 400]
                    sql = "SELECT " + key + ", name FROM " + table + " WHERE " + key + " IN (" + ",".join("?" for _ in chunk) + ")"
                    labels.update((str(row[0]), row[1]) for row in self.conn.execute(sql, chunk))
            maps[kind] = {key: {"ref": identity.ref, "label": labels.get(key) or (key if kind == "batch" else "未命名资源")}
                          for key, identity in identities.items()}
        return maps

    def read(self, scope, as_of=None):
        if as_of is None:
            as_of = datetime.now().replace(microsecond=0)
        if not isinstance(as_of, datetime) or as_of.tzinfo is not None:
            raise ValueError("Report as_of must be a factory-local naive datetime.")
        if scope.plan_finish_date_from:
            ensure_report_date_range_within_limit(date.fromisoformat(scope.plan_finish_date_from), date.fromisoformat(scope.plan_finish_date_to))
        scope, plan, version, span = self.current_plan(scope)
        count = self.conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=?", (version,)).fetchone()[0]
        if count > MAX_REPORT_OPERATIONS:
            raise WorkbenchCommandRejected("query_too_large", "正式计划工序或事件超出本批完整读取上限，未截断数据。", 413)
        report = self.engine.execution_review(version)
        rows = self.engine.plan_rows
        if len({row["op_id"] for row in rows}) != len(rows):
            raise WorkbenchCommandRejected("plan_unavailable", "正式计划含重复工序，不能重复计入完成率。")
        operation_refs = self.plans.references.get_operation_refs(row["op_id"] for row in rows)
        task_refs = self.plans.references.get_task_refs(scope.plan_ref, rows)
        tasks = [{"plan_ref": scope.plan_ref, "operation_ref": operation_refs[row["op_id"]],
                  "task_ref": task_refs[row["schedule_id"]]} for row in rows]
        ledger = ExecutionLedgerService(self.conn, clock=lambda: as_of).workspace_projection(scope.plan_ref, tasks)
        events_count = sum(len(row["legacy_facts"]) + sum(len(report["correction_history"]) for report in row["reports"])
                           for row in ledger["projections"])
        if events_count > MAX_REPORT_EVENTS:
            raise WorkbenchCommandRejected("query_too_large", "执行事实或修订历史超出完整读取上限，未截断数据。", 413)
        resources = self._resource_maps(rows)
        facts = {"plan": plan, "scope": scope, "span": span, "rows": rows,
                 "ledger": ledger, "labels": report["rows"], "resources": resources,
                 "operation_refs": operation_refs, "task_refs": task_refs}
        facts["fingerprint"] = input_fingerprint(plain_plan_facts({
            "revision": self.plans.references.read_revision(), "plan": plan, "rows": rows,
            "ledger": ledger["snapshot_facts"], "resources": resources,
            "operation_refs": facts["operation_refs"], "task_refs": facts["task_refs"],
        }))
        return facts
