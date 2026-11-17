"""Public SELECT-only ledger queries, usable inside an existing plan read snapshot."""

from typing import Optional

from core.services.execution.ledger_reader import ExecutionLedgerReader, ExecutionLedgerReadScope
from core.services.execution.projection import projection_resource_refs
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from core.services.workbench.facts.execution_projection import ExecutionContextFactory, attach_context


class ExecutionLedgerService(ExecutionLedgerReader):
    def __init__(self, conn, *, context_factory: Optional[ExecutionContextFactory] = None,
                 current_plan_provider=current_execution_plan):
        super().__init__(conn, current_plan_provider=current_plan_provider)
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
        events_count = self.repo.active_revision_count(refs)
        if any(ref == operation_ref for ref in refs):
            facts = self.load(scope, [operation_ref], comparison_plan_ref=plan_ref, include_history=True)
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
        need_history = include_history or self.context_factory is not None
        facts = self.load_many(scope, refs, comparison_plan_ref=plan_ref, include_history=need_history)
        projections = self.project_loaded(facts, include_history=include_history)
        raw_resources = self.resources(scope, {ref for row in projections for ref in projection_resource_refs(row)})
        resources = {
            "machines": [row for row in raw_resources if row["kind"] == "machine"],
            "operators": [row for row in raw_resources if row["kind"] == "operator"],
        }
        plain = [row.to_dict() for row in projections]
        return {"available": True, "time_basis": "factory_local", "projections": plain, "resources": resources}
