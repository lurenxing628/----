"""Self-contained permanent candidate catalog and full-scope workspace service."""

from datetime import date

from core.models.workbench_command import input_fingerprint
from core.models.workbench_run_candidate import blocked_reasons, read_capabilities

from .run_candidate_delivery import candidate_delivery_risks
from .run_candidate_facts import GenerationFacts
from .run_candidate_projection import candidate_summary, dispositions, validate_manifest
from .run_candidate_storage import CandidateStore
from .run_candidate_tasks import filter_workspace, task_span, tasks_projection, unplanned_projection
from .run_candidate_values import corrupt, gap


class WorkbenchRunCandidateQueryService:
    def __init__(self, conn):
        self.store = CandidateStore(conn)

    def _load(self, run_ref):
        run = self.store.run(run_ref)
        receipt = self.store.receipt(run)
        rows = self.store.candidates(run_ref)
        validate_manifest(run, rows, receipt)
        return run, rows, dispositions(receipt)

    def catalog(self, scope):
        """Return (public DTO, full-catalog fingerprint), independent of page number."""
        with self.store.snapshot():
            run, rows, disposition = self._load(scope.run_ref)
            summaries = [(row["sequence"], candidate_summary(row, disposition)) for row in rows]
            state = input_fingerprint({"run": run, "candidates": summaries})
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

    def workspace(self, scope):
        """No UI paging: every persisted task in the exact requested scope is returned."""
        with self.store.snapshot():
            run_ref = self.store.candidate_run(scope.candidate_ref)
            run, rows, disposition = self._load(run_ref)
            candidate = next(row for row in rows if row["candidate_ref"] == scope.candidate_ref)
            summary = candidate_summary(candidate, disposition)
            capture = self.store.capture(run_ref)
            facts = GenerationFacts(capture)
            raw_tasks = self.store.tasks(scope.candidate_ref)
            if len(raw_tasks) != candidate["task_count"]:
                corrupt()
            tasks = tasks_projection(raw_tasks, candidate, facts)
            unplanned = unplanned_projection(disposition, tasks, facts)
            span = task_span(tasks)
            full_tasks = tasks
            tasks, unplanned = filter_workspace(tasks, unplanned, scope)
            delivery = candidate_delivery_risks(candidate, facts, full_tasks, disposition, scope,
                                                capture["input"], tasks, unplanned)
            generation = _generation(run, capture)
            gaps = [] if unplanned is not None else [gap("unplanned_operations")]
            data = {"candidate": summary, "generation": generation, "tasks": tasks, "task_count": len(tasks),
                    "tasks_complete": True, "candidate_task_count": candidate["task_count"],
                    "candidate_span": span, "task_span": task_span(tasks),
                    "unplanned_operations": unplanned,
                    "unplanned_operation_count": len(unplanned) if unplanned is not None else None,
                    "time_scope": {"range_start": scope.range_start, "range_end": scope.range_end,
                                   "interval": "half_open_overlap", "time_basis": "factory_local",
                                   "unplanned_policy": "included_without_time_interval"},
                    "batch_ref": scope.batch_ref, "capabilities": read_capabilities(),
                    "blocked_reasons": blocked_reasons(), "data_gaps": gaps, "delivery_risks": delivery}
            return data, input_fingerprint(data)


def _generation(run, capture):
    settings = capture["input"]
    values, gaps = {}, []
    domains = {"missing_resource_policy": ("auto_assign", "exclude"), "completed_policy": ("preserve_actuals",)}
    for key in ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy"):
        value = settings.get(key)
        if key in domains:
            valid = type(value) is str and value in domains[key]
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
    baseline = capture["baseline"].get("rows")
    return {"run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
            "current_entities_consulted": False, "formal_version_allocated": False,
            "input": values, "data_gaps": gaps,
            "baseline": {"captured_task_count": len(baseline) if type(baseline) is list else None,
                         "comparison_available": False, "reason": {"code": "candidate_baseline_comparison_not_connected",
                         "message": "已保留生成时正式基线，本读取模块尚未接入逐任务基线比较。"}}}
