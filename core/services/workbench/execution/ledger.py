"""Public SELECT-only ledger queries, usable inside an existing plan read snapshot."""

from datetime import datetime
from typing import Callable, Optional

from core.models.workbench_execution_input import reject
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.execution.projection import projection_resource_refs
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from core.services.workbench.facts.execution_projection import ExecutionContextFactory, attach_context
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from data.repositories.workbench_execution_source_repo import EMPTY_SOURCE_CONTENT


def _check_workspace_tasks(tasks, facts, plan_ref):
    for task in tasks:
        actual = facts["comparison_tasks"].get(task["operation_ref"])
        if actual is None or actual["task_ref"] != task["task_ref"] or task["plan_ref"] != plan_ref:
            reject("提交的计划任务和系统里记的不是同一条。请刷新后重试。", "constraint_conflict", 409)


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
                 context_factory: Optional[ExecutionContextFactory] = None,
                 current_plan_provider=current_execution_plan):
        if context_factory is not None and not callable(context_factory):
            raise TypeError("Ledger context factory must be callable.")
        super().__init__(conn, current_plan_provider=current_plan_provider, clock=clock)
        self.context_factory = context_factory

    @staticmethod
    def fact_snapshot(facts, operation_ref):
        reports = facts["reports"].get(operation_ref, {})
        return plain_plan_facts({"operation": facts["operations"][operation_ref],
                "current_task": facts["current_tasks"].get(operation_ref), "plan": facts["plan"],
                "reports": reports,
                "voids": {ref: facts["voids"][ref] for ref in reports if ref in facts["voids"]},
                "legacy": facts["legacy"].get(operation_ref, []),
                "unresolved": operation_ref in facts["unresolved"],
                "legacy_source_state": facts["legacy_source"]["states"].get(operation_ref, EMPTY_SOURCE_CONTENT)})

    def project_loaded(self, facts, *, contexts=True):
        projections = super().project_loaded(facts)
        if not contexts or self.context_factory is None:
            return projections
        return [attach_context(row, self.context_factory,
                               self.fact_snapshot(facts, row.operation_ref)) for row in projections]

    def workspace_projection(self, plan_ref, tasks):
        with self.read_snapshot():
            refs = [task["operation_ref"] for task in tasks]
            facts = self.load_many(refs, comparison_plan_ref=plan_ref)
            _check_workspace_tasks(tasks, facts, plan_ref)
            projections = self.project_loaded(facts)
            resources = self.resources({ref for row in projections for ref in projection_resource_refs(row)})
            plain = [row.to_dict() for row in projections]
            return {"available": True, "time_basis": "factory_local", "projections": plain,
                    "resources": {"machines": [row for row in resources if row["kind"] == "machine"],
                                  "operators": [row for row in resources if row["kind"] == "operator"]},
                    "snapshot_facts": {**facts["clock"], "projections": _stable_projection_rows(plain),
                                       "resources": resources,
                                       "legacy_source_states": facts["legacy_source"]["states"]}}
