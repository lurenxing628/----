"""Public SELECT-only ledger queries, usable inside an existing plan read snapshot."""

from datetime import datetime
from typing import Callable, Optional

from core.models.workbench_execution_input import reject
from core.services.execution.ledger_reader import ExecutionLedgerReader, ExecutionLedgerReadScope
from core.services.execution.projection import projection_resource_refs
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from core.services.workbench.facts.execution_projection import ExecutionContextFactory, attach_context


def _check_workspace_tasks(tasks, facts, plan_ref):
    for task in tasks:
        actual = facts["comparison_tasks"].get(task["operation_ref"])
        if actual is None or actual["task_ref"] != task["task_ref"] or task["plan_ref"] != plan_ref:
            reject("提交的计划任务和系统里记的不是同一条。请刷新后重试。", "constraint_conflict", 409)


class ExecutionLedgerService(ExecutionLedgerReader):
    def __init__(self, conn, *, clock: Optional[Callable[[], datetime]] = None,
                 context_factory: Optional[ExecutionContextFactory] = None,
                 current_plan_provider=current_execution_plan):
        super().__init__(conn, current_plan_provider=current_plan_provider, clock=clock)
        self.context_factory = context_factory

    @staticmethod
    def fact_snapshot(facts, operation_ref):
        reports = facts["reports"].get(operation_ref, {})
        return {
            "operation": facts["operations"][operation_ref],
            "current_task": facts["current_tasks"].get(operation_ref),
            "plan": facts["plan"],
            "reports": reports,
            "voids": {ref: facts["voids"][ref] for ref in reports if ref in facts["voids"]},
        }

    def project_loaded(self, facts, *, include_history: bool = True):
        projections = super().project_loaded(facts, include_history=include_history)
        if self.context_factory is None:
            return projections
        return [attach_context(row, self.context_factory,
                               self.fact_snapshot(facts, row.operation_ref)) for row in projections]

    def operation_workspace_projection(self, scope: ExecutionLedgerReadScope, plan_ref, tasks, operation_ref):
        refs = [task["operation_ref"] for task in tasks]
        facts = self.load_many(scope, refs, comparison_plan_ref=plan_ref)
        _check_workspace_tasks(tasks, facts, plan_ref)
        for ref in facts["operations"]:
            if ref != operation_ref:
                self.validate_operation_reports(facts, ref)
        events_count = sum(
            len(history)
            for group in facts["reports"].values()
            for report_ref, history in group.items()
            if report_ref not in facts["voids"]
        )
        if operation_ref in facts["operations"]:
            projected = self.project_operation(facts, operation_ref, include_history=True)
            if self.context_factory is not None:
                projected = attach_context(
                    projected, self.context_factory, self.fact_snapshot(facts, operation_ref)
                )
            raw_resources = self.resources(scope, projection_resource_refs(projected))
            plain = [projected.to_dict()]
            resources = {
                "machines": [row for row in raw_resources if row["kind"] == "machine"],
                "operators": [row for row in raw_resources if row["kind"] == "operator"],
            }
        else:
            plain = []
            resources = {"machines": [], "operators": []}
        return (
            {"available": True, "time_basis": "factory_local", "projections": plain, "resources": resources},
            events_count,
        )

    def workspace_projection(self, scope: ExecutionLedgerReadScope, plan_ref, tasks, *, include_history: bool = True):
        refs = [task["operation_ref"] for task in tasks]
        facts = self.load_many(scope, refs, comparison_plan_ref=plan_ref)
        _check_workspace_tasks(tasks, facts, plan_ref)
        projections = self.project_loaded(facts, include_history=include_history)
        raw_resources = self.resources(scope, {ref for row in projections for ref in projection_resource_refs(row)})
        resources = {
            "machines": [row for row in raw_resources if row["kind"] == "machine"],
            "operators": [row for row in raw_resources if row["kind"] == "operator"],
        }
        plain = [row.to_dict() for row in projections]
        return {"available": True, "time_basis": "factory_local", "projections": plain, "resources": resources}
