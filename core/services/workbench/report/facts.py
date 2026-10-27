"""Current report facts, with current-official identity guards."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from core.models.content import content_text
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_report import MAX_REPORT_EVENTS, MAX_REPORT_OPERATIONS
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.plan.point_query import PointPlanCatalogRepository
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.workbench_report_facts_repo import WorkbenchReportFactsRepository

from .review_records import choice_directory


class WorkbenchReportFacts:
    def __init__(self, conn, logger=None):
        from core.services.report.report_engine import ReportEngine

        self.conn = conn
        self.repo = WorkbenchReportFactsRepository(conn, logger)
        self.plans = WorkbenchPlanQueryService(conn, logger)
        self.engine = ReportEngine(conn, logger)

    def read_snapshot(self):
        return self.plans.read_snapshot()

    def current_plan_metadata(self, scope):
        ref = scope.plan_ref
        if ref is None:
            version = PointPlanCatalogRepository(self.conn, logger=self.plans.logger).latest_version()
            if not version:
                raise WorkbenchCommandRejected("plan_unavailable", "当前没有正式计划，不能生成现场分析。")
            ref = self.plans.references.get_plan_ref(WorkbenchPlanLocator(version, ROLE_ADOPTED))
        resolution, entry, span = self.plans.selected_metadata(ref)
        if resolution.selected_role != ROLE_ADOPTED or resolution.scenario_id is not None:
            raise WorkbenchCommandRejected("plan_not_current_official", "现场分析只看当前正式计划，没有生成结果。候选方案和试调方案请到试调页查看。")
        plan = project_plan(entry, ref)
        if not plan["is_current_official"]:
            raise WorkbenchCommandRejected("plan_not_current_official", "请选择当前正式计划后重新分析。")
        return replace(scope, plan_ref=ref), plan, resolution, span

    def _resource_maps(self, rows):
        # 设备、人员、批次编号都经外键指向资料主表，主表各写入口拒绝空白编号；只有未分配的设备人员是 None。
        maps = {}
        for kind, key in (("machine", "machine_id"), ("operator", "operator_id"), ("batch", "batch_id")):
            keys = {row[key] for row in rows if row[key] is not None}
            identities = self.plans.entities.active_map(kind, sorted(keys))
            if set(identities) != keys:
                raise WorkbenchCommandRejected("identity_missing", "有批次或实际用到的设备人员在资料里查不到编号，分析没有生成。请到资料总览核对后重试。")
            name_key = kind + "_name"
            labels = {} if kind == "batch" else {row[key]: row[name_key] for row in rows if row[key] is not None}
            maps[kind] = {key: {"ref": identity.ref, "label": labels.get(key) or (key if kind == "batch" else "名称未填写")}
                          for key, identity in identities.items()}
        return maps

    def read(self, scope, as_of=None):
        if as_of is None:
            as_of = datetime.now().replace(microsecond=0)
        if not isinstance(as_of, datetime) or as_of.tzinfo is not None:
            raise ValueError("Report as_of must be a factory-local naive datetime.")
        if scope.plan_finish_date_from:
            ensure_report_date_range_within_limit(date.fromisoformat(scope.plan_finish_date_from), date.fromisoformat(scope.plan_finish_date_to))
        scope, plan, resolution, span = self.current_plan_metadata(scope)
        version = resolution.version
        batch = self.plans.entities.get(scope.batch_ref) if scope.batch_ref else None
        if scope.batch_ref and (batch is None or batch.kind != "batch" or not batch.active):
            raise WorkbenchCommandRejected("entity_not_found", "筛选记录已失效或类型不符，请重新选择。", 404)
        rows = self.repo.plan_rows(version, date_from=scope.plan_finish_date_from,
            date_to=scope.plan_finish_date_to, batch_id=batch.entity_key if batch else None,
            limit=MAX_REPORT_OPERATIONS + 1)
        if len(rows) > MAX_REPORT_OPERATIONS:
            raise WorkbenchCommandRejected("query_too_large", "这个范围的正式计划工序太多，一次读不完，没有生成结果。请缩小计划完工日期范围后重试。", 413)
        if len({row["op_id"] for row in rows}) != len(rows):
            raise WorkbenchCommandRejected("plan_unavailable", "正式计划里有重复的工序，完成率算不出来，没有生成结果。请联系维护人员核对这份计划。")
        task_refs = self.plans.references.get_task_refs(
            scope.plan_ref, ((row["schedule_id"], row["op_id"], row["version"]) for row in rows))
        operation_refs = self.plans.references.get_operation_refs(row["op_id"] for row in rows)
        tasks = [{"plan_ref": scope.plan_ref, "operation_ref": operation_refs[row["op_id"]],
                  "task_ref": task_refs[row["schedule_id"]]} for row in rows]
        ledger_reader = ExecutionLedgerService(self.conn, clock=lambda: as_of, current_plan_provider=lambda conn: plan)
        with ledger_reader.read_snapshot():
            ledger = ledger_reader.workspace_projection(scope.plan_ref, tasks)
            events_count = sum(len(row["legacy_facts"]) + sum(len(report["correction_history"]) for report in row["reports"])
                               for row in ledger["projections"])
            if events_count > MAX_REPORT_EVENTS:
                raise WorkbenchCommandRejected("query_too_large", "这个范围里的报工和更正记录太多，一次读不完，没有生成结果。请缩小计划完工日期范围后重试。", 413)
            if scope.plan_finish_date_from is None and scope.batch_ref is None:
                choice_resources = self._resource_maps(rows)
                resources = choice_resources
                actual_resources = ledger["resources"]
            else:
                choice_resources = self._resource_maps(self.repo.plan_resource_keys(version))
                resources = {kind: {row[key]: choice_resources[kind][row[key]] for row in rows if row[key] is not None}
                             for kind, key in (("machine", "machine_id"), ("operator", "operator_id"), ("batch", "batch_id"))}
                actual_rows = ledger_reader.resources(self.repo.actual_resource_refs(scope.plan_ref))
                actual_resources = {
                    "machines": [row for row in actual_rows if row["kind"] == "machine"],
                    "operators": [row for row in actual_rows if row["kind"] == "operator"],
                }
        choices = choice_directory(choice_resources, actual_resources)
        if scope.resource_ref and scope.resource_ref != "unassigned":
            kind = scope.resource_type
            if kind not in ("machine", "operator") or scope.resource_ref not in choices[kind]:
                identity = self.plans.entities.get(scope.resource_ref)
                if identity is None or identity.kind != kind or not identity.active:
                    raise WorkbenchCommandRejected("entity_not_found", "筛选记录已失效或类型不符，请重新选择。", 404)
        facts = {"plan": plan, "scope": scope, "span": span, "rows": rows,
                 "ledger": ledger, "resources": resources,
                 "operation_refs": operation_refs, "task_refs": task_refs, "choices": choices}
        # 只判断数据变没变：一次写成文本取摘要，不先 plain_plan_facts() 复制整份计划行和台账。
        facts["fingerprint"] = content_text({
            "revision": self.plans.references.read_revision(), "plan": plan, "rows": rows,
            "ledger": ledger["snapshot_facts"], "resources": resources,
            "operation_refs": facts["operation_refs"], "task_refs": facts["task_refs"], "choices": choices,
        })
        return facts
