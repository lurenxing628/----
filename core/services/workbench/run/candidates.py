"""Self-contained permanent candidate catalog and full-scope workspace service."""

from core.models.workbench_run_candidate import blocked_reasons, read_capabilities
from core.services.workbench.facts.candidate_delivery import candidate_delivery_risks
from core.services.workbench.facts.candidate_projection import (
    algorithm_facts,
    baseline_capture,
    candidate_summary,
)
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import (
    filter_workspace,
    task_span,
)
from core.services.workbench.facts.candidate_values import gap
from core.services.workbench.facts.run_history_projection import (
    stored_scope_input_keys,
    stored_scope_value_valid,
)


class WorkbenchRunCandidateQueryService:
    def __init__(self, conn):
        self.store = CandidateStore(conn)

    def catalog(self, scope):
        """Return the public DTO and source identity, independent of page number."""
        with self.store.snapshot():
            from .decision_source import DecisionSource
            source = DecisionSource(self.store, scope.run_ref)
            run, rows = source.run, source.rows
            summaries = [(row["sequence"], source.saved_candidate_catalog(row["candidate_ref"])) for row in rows]
            state = {"read_contract_version": 1, "run_ref": run["run_ref"], "run_state": run["state"]}
            filtered = [(seq, item) for seq, item in summaries if scope.status in ("all", item["status"])]

            def sort(item):
                seq, dto = item
                value = seq if scope.sort == "sequence" else dto[scope.sort]
                return (value is None, value, seq, dto["candidate_ref"])

            filtered.sort(key=sort, reverse=scope.order == "desc")
            offset = (scope.page - 1) * scope.size
            data = {"run_ref": run["run_ref"], "run_state": run["state"],
                    "candidates": [item for _, item in filtered[offset:offset + scope.size]],
                    "page": {"number": scope.page, "size": scope.size, "total": len(filtered),
                             "has_more": offset + scope.size < len(filtered)},
                    "candidate_count": len(rows), "catalog_complete": run["state"] not in ("queued", "running"),
                    "capabilities": read_capabilities(), "blocked_reasons": blocked_reasons()}
            return data, state

    def identity(self, candidate_ref):
        with self.store.snapshot():
            data = self.store.candidate_identity(candidate_ref)
            return data, {"read_contract_version": 1, **data}

    def workspace(self, scope):
        """No UI paging: every persisted task in the exact requested scope is returned."""
        with self.store.snapshot():
            from .decision_source import DecisionSource
            source = DecisionSource(self.store, self.store.candidate_run(scope.candidate_ref), selected_candidate_ref=scope.candidate_ref)
            return self._workspace(source.candidate_source(scope.candidate_ref), scope)

    @staticmethod
    def _workspace(source, scope):
        tasks, unplanned = filter_workspace(source.tasks, source.unplanned, scope)
        effort = source.operation_effort_projection
        tasks = [dict(row, operation_effort=effort[row["operation_ref"]]) for row in tasks]
        unplanned = [dict(row, operation_effort=effort[row["operation_ref"]]) for row in unplanned]
        delivery = candidate_delivery_risks(source.candidate, source.facts, source.tasks, source.disposition, scope,
                                            source.capture["input"], tasks, unplanned)
        data = {"candidate": candidate_summary(source.candidate, source.disposition,
                                                scheduled_op_ids=source.scheduled_op_ids),
                "generation": _generation(source.run, source.capture, source.candidate), "tasks": tasks, "task_count": len(tasks),
                "gantt_graph": source.gantt_graph,
                "tasks_complete": True, "candidate_task_count": source.candidate["task_count"],
                "candidate_span": task_span(source.tasks), "task_span": task_span(tasks),
                "unplanned_operations": unplanned,
                "unplanned_operation_count": len(unplanned),
                "time_scope": {"range_start": scope.range_start, "range_end": scope.range_end,
                               "interval": "half_open_overlap", "time_basis": "factory_local",
                               "unplanned_policy": "included_without_time_interval"},
                "batch_ref": scope.batch_ref, "capabilities": read_capabilities(),
                "blocked_reasons": blocked_reasons(),
                "data_gaps": [], "delivery_risks": delivery}
        return data, source.snapshot_identity


def _generation(run, capture, candidate):
    settings = capture["input"]
    values, gaps = {}, []
    for key in stored_scope_input_keys(settings):
        value = settings.get(key)
        valid = stored_scope_value_valid(key, value)
        values[key] = value if valid else None
        if not valid:
            gaps.append(gap("input." + key, "not_recorded" if value is None else "invalid_stored_value"))
    values["time_budget_seconds"] = settings["time_budget_seconds"]
    return {"run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
            "current_entities_consulted": False, "formal_version_allocated": False,
            "input": values, "data_gaps": gaps, "algorithm": algorithm_facts(candidate["artifact"]),
            "baseline": baseline_capture(capture["baseline"], run["accepted_at"])}
