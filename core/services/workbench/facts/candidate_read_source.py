"""Read one verified candidate source inside the caller's existing snapshot."""

from dataclasses import dataclass, field
from functools import cached_property

from core.models.workbench_run_candidate import reference

from .candidate_effort import candidate_operation_effort_projection
from .candidate_facts import GenerationFacts
from .candidate_projection import validate_manifest
from .candidate_tasks import (
    project_validated_tasks,
    unplanned_projection,
    validate_saved_tasks,
)
from .candidate_values import corrupt
from .gantt_graph import candidate_gantt_graph


def candidate_snapshot_identity(run_ref, candidate_ref):
    """Permanent source identity; query scope is bound by the read context."""
    return {"read_contract_version": 1, "run_ref": run_ref, "candidate_ref": candidate_ref}


@dataclass(frozen=True)
class CandidateReadSource:
    run: dict
    candidate: dict
    disposition: dict
    capture: dict
    facts: GenerationFacts
    raw_tasks: list
    catalog: list
    scheduled_op_ids: set
    # validate_manifest rejects a missing receipt whenever its candidate rows exist.
    receipt: dict
    task_intervals: dict
    prepared_tasks: dict
    _task_by_row_ref: dict = field(default_factory=dict, repr=False)
    _unplanned_by_ref: dict = field(default_factory=dict, repr=False)

    @property
    def snapshot_identity(self):
        return candidate_snapshot_identity(self.run["run_ref"], self.candidate["candidate_ref"])

    @cached_property
    def tasks(self):
        return self.project_tasks(self.raw_tasks)

    @cached_property
    def unplanned(self):
        return self.project_unplanned(self.disposition)

    def project_tasks(self, rows):
        missing = [row for row in rows if row["row_ref"] not in self._task_by_row_ref]
        if missing:
            for task in project_validated_tasks(
                missing, self.candidate, self.facts, self.task_intervals,
                prepared_tasks=self.prepared_tasks,
            ):
                self._task_by_row_ref[task["row_ref"]] = task
        return [self._task_by_row_ref[row["row_ref"]] for row in rows]

    def project_unplanned(self, disposition):
        missing = {ref: row for ref, row in disposition.items() if ref not in self._unplanned_by_ref}
        if missing:
            for item in unplanned_projection(missing, self.raw_tasks, self.facts):
                self._unplanned_by_ref[item["operation_ref"]] = item
            for ref in missing:
                self._unplanned_by_ref.setdefault(ref, None)
        return [
            item
            for ref in disposition
            for item in (self._unplanned_by_ref[ref],)
            if item is not None
        ]

    @cached_property
    def gantt_graph(self):
        resource_keys = {
            row["row_ref"]: (row["payload"]["machine_id"], row["payload"]["operator_id"])
            for row in self.raw_tasks
        }
        return candidate_gantt_graph(
            self.tasks,
            self.facts,
            resource_keys,
            scope="full_candidate",
            unavailable_reason="此候选方案未保存完整的工艺前后关系，暂时无法显示关联线和关键链。",
            task_intervals=self.task_intervals,
        )

    @cached_property
    def operation_effort_projection(self):
        return candidate_operation_effort_projection(self)


def candidate_manifest(store, run_ref):
    run = store.run(run_ref)
    receipt = store.receipt(run)
    rows = store.candidates(run_ref)
    validate_manifest(run, rows, receipt)
    return run, rows, receipt


def read_candidate_source(store, candidate_ref, *, prepared=None):
    """Reuse the caller's verified packet, or load an independent source once.

    A prepared packet belongs to this caller's current SQLite snapshot. Its
    run/catalog/receipt have already passed the common manifest check and its
    disposition was parsed from that receipt; raw and projected tasks may also
    be handed over together after validation.
    """
    reference(candidate_ref)
    if prepared is None:
        run_ref = store.candidate_run(candidate_ref)
        run, rows, receipt = candidate_manifest(store, run_ref)
        candidate = next((row for row in rows if row["candidate_ref"] == candidate_ref), None)
        if candidate is None:
            corrupt()
        capture = store.capture(run_ref)
        facts = store.generation_facts(capture)
        disposition = store.dispositions(receipt, facts, capture)
        raw_tasks = store.tasks(candidate_ref)
    else:
        run, rows, receipt = prepared["run"], prepared["rows"], prepared["receipt"]
        candidate = prepared["candidate"]
        capture = prepared["capture"]
        facts = prepared["facts"]
        disposition = prepared["disposition"]
        raw_tasks = prepared["raw_tasks"] if "raw_tasks" in prepared else store.tasks(candidate_ref)
    if prepared is not None and "task_intervals" in prepared and "scheduled_op_ids" in prepared:
        ids = prepared["scheduled_op_ids"]
        intervals = prepared["task_intervals"]
        prepared_tasks = prepared["prepared_tasks"]
    else:
        if len(raw_tasks) != candidate["task_count"]:
            corrupt()
        prepared_tasks = {}
        _, intervals, ids = validate_saved_tasks(raw_tasks, candidate, facts, prepared_tasks=prepared_tasks)
    source = CandidateReadSource(
        run, candidate, disposition, capture, facts, raw_tasks, rows, ids,
        receipt=receipt, task_intervals=intervals, prepared_tasks=prepared_tasks,
    )
    if prepared is not None and "tasks" in prepared:
        object.__setattr__(source, "tasks", prepared["tasks"])
        for task in prepared["tasks"]:
            source._task_by_row_ref[task["row_ref"]] = task
    return source
