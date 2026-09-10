"""Public SELECT-only ledger queries, usable inside an existing plan read snapshot."""

from datetime import datetime
from typing import Callable, List, Optional

from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_execution_input import MAX_REPORT_BYTES, public_ref, reject
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from data.repositories.workbench_execution_source_repo import EMPTY_SOURCE_HASH
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .execution_ledger_projection import attach_context
from .plan_fact_serialization import plain_plan_facts


def _check_workspace_tasks(tasks, facts, plan_ref):
    for task in tasks:
        actual = facts["comparison_tasks"].get(task["operation_ref"])
        if actual is None or actual["task_ref"] != task["task_ref"] or task["plan_ref"] != plan_ref:
            reject("传入计划任务与永久身份不一致。", "constraint_conflict", 409)


def _actual_resources(repo, projections):
    refs = set()
    for row in projections:
        for report in row.reports:
            refs.update(getattr(report, field) for field in ("actual_machine_ref", "actual_operator_ref") if getattr(report, field))
        for fact in row.legacy_facts:
            refs.update(fact[field] for field in ("actual_machine_ref", "actual_operator_ref") if fact[field])
    return repo.resources(refs)


def _stable_projection_rows(rows):
    result = []
    for row in rows:
        stable = {key: value for key, value in row.items() if key != "write_context"}
        stable["reports"] = [{key: value for key, value in report.items() if key != "write_context"}
                             for report in row["reports"]]
        result.append(stable)
    return result


class ExecutionLedgerService(ExecutionLedgerReader):
    def __init__(self, conn, *, clock: Optional[Callable[[], datetime]] = None,
                 context_factory: Optional[Callable[[str, List[str], dict], dict]] = None):
        if context_factory is not None and not callable(context_factory):
            raise TypeError("Ledger context factory must be callable.")
        super().__init__(conn, current_plan_provider=current_execution_plan, clock=clock)
        self.context_factory = context_factory

    @staticmethod
    def fact_snapshot(facts, operation_ref):
        return plain_plan_facts({**facts["clock"], "operation": facts["operations"][operation_ref],
                "current_task": facts["current_tasks"].get(operation_ref), "plan": facts["plan"],
                "legacy_source_hash": facts["legacy_source"]["hashes"].get(operation_ref, EMPTY_SOURCE_HASH)})

    def project_loaded(self, facts, *, contexts=True):
        projections = super().project_loaded(facts)
        result = [attach_context(row, self.context_factory if contexts else None,
                                 self.fact_snapshot(facts, row.operation_ref)) for row in projections]
        if len(canonical_json([row.to_dict() for row in result]).encode("utf-8")) > MAX_REPORT_BYTES:
            reject("执行投影超过本次响应大小上限，未截断历史。", "query_too_large", 413)
        return result

    def get_task(self, task_ref, *, comparison_task_ref=None):
        with self.read_snapshot():
            task = self.repo.task(task_ref)
            comparison = self.repo.task(comparison_task_ref) if comparison_task_ref else task
            if any(not row["row_active"] or not row["plan_active"] for row in (task, comparison)):
                reject("原任务安排已移除，旧引用不会改指同号新安排。", "entity_not_found", 404)
            if comparison["operation_ref"] != task["operation_ref"]:
                reject("比较安排不属于同一执行工序实例。", "constraint_conflict", 409)
            projection = self.project_operations([task["operation_ref"]], comparison_plan_ref=comparison["plan_ref"])[0]
            if projection.comparison_task_ref != comparison["task_ref"]:
                reject("原比较任务绑定已变化，不能改指其他安排。", "constraint_conflict", 409)
            return projection

    def get_report(self, report_ref):
        with self.read_snapshot():
            row = self.repo.report_header(report_ref=report_ref)
            if row is None:
                reject("报工不存在，旧单号不会改指其他记录。", "entity_not_found", 404)
            projections = self.project_operations([row["operation_ref"]])
            return next(report for report in projections[0].reports if report.report_ref == report_ref)

    def find_report(self, report_no):
        with self.read_snapshot():
            row = self.repo.report_header(report_no=report_no)
            return self.get_report(row["report_ref"]) if row else None

    def snapshot(self, operation_ref):
        with self.read_snapshot():
            return self.fact_snapshot(self.load([public_ref(operation_ref)]), operation_ref)

    def list_tasks(self, plan_ref, *, size=100, after_task_ref=None):
        with self.read_snapshot():
            WorkbenchPlanIdentityRepository(self.conn).resolve_plan(plan_ref)
            rows = self.repo.page_tasks(plan_ref, size, after_task_ref)
            selected = rows[:size]
            projections = self.project_operations([row["operation_ref"] for row in selected], comparison_plan_ref=plan_ref)
            by_ref = {row.operation_ref: row.to_dict() for row in projections}
            return {"items": [by_ref[row["operation_ref"]] for row in selected], "has_more": len(rows) > size,
                    "next_task_ref": selected[-1]["task_ref"] if len(rows) > size else None}

    def workspace_projection(self, plan_ref, tasks):
        with self.read_snapshot():
            refs = [public_ref(task["operation_ref"]) for task in tasks]
            facts = self.load(refs, comparison_plan_ref=plan_ref)
            _check_workspace_tasks(tasks, facts, plan_ref)
            projections = self.project_loaded(facts)
            resources = _actual_resources(self.repo, projections)
            plain = [row.to_dict() for row in projections]
            return {"available": True, "time_basis": "factory_local", "projections": plain,
                    "resources": {"machines": [row for row in resources if row["kind"] == "machine"],
                                  "operators": [row for row in resources if row["kind"] == "operator"]},
                    "snapshot_facts": {**facts["clock"], "projection_hash": input_fingerprint(_stable_projection_rows(plain)),
                                       "resources_hash": input_fingerprint(resources),
                                       "legacy_source_hash": facts["legacy_source"]["hash"]}}
