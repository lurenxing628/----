"""Self-contained permanent candidate catalog and full-scope workspace service."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from core.models.workbench_command import input_fingerprint
from core.models.workbench_preflight import stored_hold_window_valid
from core.models.workbench_run_candidate import blocked_reasons, read_capabilities
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import candidate_summary, dispositions, validate_manifest
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import (
    filter_workspace,
    task_span,
    tasks_projection,
    unplanned_projection,
)
from core.services.workbench.facts.candidate_values import corrupt, gap

from .candidate_delivery import candidate_delivery_risks


@dataclass(frozen=True)
class CandidateReadSource:
    run: dict
    candidate: dict
    disposition: Optional[dict]
    capture: dict
    facts: GenerationFacts
    raw_tasks: list
    tasks: list
    unplanned: Optional[list]


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
            return self._workspace(self._source(scope.candidate_ref), scope)

    def _source(self, candidate_ref):
        """Load and verify once for projections owned by this read snapshot."""
        run_ref = self.store.candidate_run(candidate_ref)
        run, rows, disposition = self._load(run_ref)
        candidate = next(row for row in rows if row["candidate_ref"] == candidate_ref)
        capture = self.store.capture(run_ref)
        facts = GenerationFacts(capture)
        raw_tasks = self.store.tasks(candidate_ref)
        if len(raw_tasks) != candidate["task_count"]:
            corrupt()
        tasks = tasks_projection(raw_tasks, candidate, facts)
        return CandidateReadSource(run, candidate, disposition, capture, facts, raw_tasks,
                                   tasks, unplanned_projection(disposition, tasks, facts))

    @staticmethod
    def _workspace(source, scope):
        tasks, unplanned = filter_workspace(source.tasks, source.unplanned, scope)
        delivery = candidate_delivery_risks(source.candidate, source.facts, source.tasks, source.disposition, scope,
                                            source.capture["input"], tasks, unplanned)
        data = {"candidate": candidate_summary(source.candidate, source.disposition),
                "generation": _generation(source.run, source.capture), "tasks": tasks, "task_count": len(tasks),
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
        return data, input_fingerprint(data)


def _generation(run, capture):
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
    baseline = capture["baseline"].get("rows")
    return {"run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
            "current_entities_consulted": False, "formal_version_allocated": False,
            "input": values, "data_gaps": gaps,
            "baseline": {"captured_task_count": len(baseline) if type(baseline) is list else None,
                         "comparison_available": False, "reason": {"code": "candidate_baseline_comparison_not_connected",
                         "message": "排产时的正式计划已经存下来了，这个列表还不支持逐道工序对比。请打开候选方案详情查看对比。"}}}
