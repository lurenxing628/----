"""Self-contained permanent candidate catalog and full-scope workspace service."""

from datetime import date

from core.models.workbench_preflight import stored_hold_window_valid
from core.models.workbench_run_candidate import blocked_reasons, read_capabilities
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

from .candidate_delivery import candidate_delivery_risks


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
        if unplanned is not None:
            unplanned = [dict(row, operation_effort=effort[row["operation_ref"]]) for row in unplanned]
        delivery = candidate_delivery_risks(source.candidate, source.facts, source.tasks, source.disposition, scope,
                                            source.capture["input"], tasks, unplanned)
        data = {"candidate": candidate_summary(source.candidate, source.disposition),
                "generation": _generation(source.run, source.capture, source.candidate), "tasks": tasks, "task_count": len(tasks),
                "gantt_graph": source.gantt_graph,
                "tasks_complete": True, "candidate_task_count": source.candidate["task_count"],
                "candidate_span": task_span(source.tasks), "task_span": task_span(tasks),
                "unplanned_operations": unplanned,
                "unplanned_operation_count": len(unplanned) if unplanned is not None else None,
                "time_scope": {"range_start": scope.range_start, "range_end": scope.range_end,
                               "interval": "half_open_overlap", "time_basis": "factory_local",
                               "unplanned_policy": "included_without_time_interval"},
                "batch_ref": scope.batch_ref, "capabilities": read_capabilities(),
                "blocked_reasons": blocked_reasons(),
                "data_gaps": [] if unplanned is not None else [gap("unplanned_operations")], "delivery_risks": delivery}
        return data, source.snapshot_identity


def _generation(run, capture, candidate):
    settings = capture["input"]
    values, gaps = {}, []
    domains = {"missing_resource_policy": ("auto_assign", "exclude"), "completed_policy": ("preserve_actuals",), "material_strategy": ("strict", "stage", "split")}
    optional = tuple(key for key in ("material_strategy", "hold_window") if key in settings)
    for key in ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy") + optional:
        value = settings.get(key)
        if key in domains:
            valid = type(value) is str and value in domains[key]
        elif key == "hold_window":
            # 不设（null）是合法记录，不算缺口；读不懂的才记缺口并回显 null。
            valid = stored_hold_window_valid(value)
        elif key == "ready_check":
            valid = type(value) is bool
        else:
            try:
                valid = type(value) is str and date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
        values[key] = value if valid else None
        if not valid:
            gaps.append(gap("input." + key, "not_recorded" if value is None else "invalid_stored_value"))
    if candidate["artifact"].get("generation_policy_version") == "unified_search_v1":
        values["time_budget_seconds"] = settings["time_budget_seconds"]
    return {"run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
            "current_entities_consulted": False, "formal_version_allocated": False,
            "input": values, "data_gaps": gaps, "algorithm": algorithm_facts(candidate["artifact"]),
            "baseline": baseline_capture(capture["baseline"], run["accepted_at"])}
