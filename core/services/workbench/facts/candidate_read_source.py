"""Read one run's saved results and one verified candidate source inside the caller's existing snapshot."""

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Dict, Optional, Sequence, cast

from core.models.workbench_run_candidate import reference
from core.models.workbench_run_receipt import PersistedReceipt, RunReceipt

from .candidate_effort import candidate_operation_effort_projection
from .candidate_facts import GenerationFacts
from .candidate_projection import completed_dispositions, validate_manifest
from .candidate_tasks import (
    ValidatedCandidateTasks,
    project_validated_tasks,
    unplanned_projection,
    validate_candidate_tasks,
)
from .candidate_values import corrupt
from .decision_metrics import admission_operation_refs
from .gantt_graph import candidate_gantt_graph


def candidate_snapshot_identity(run_ref, candidate_ref):
    """Permanent source identity; query scope is bound by the read context."""
    return {"read_contract_version": 1, "run_ref": run_ref, "candidate_ref": candidate_ref}


@dataclass(frozen=True)
class SavedRun:
    """One run's saved archive as this snapshot read it: its head, its receipt (None while the run is queued or
    running) bound to the run's candidate list, its capture and the capture's generation facts."""

    run: Dict[str, Any]
    receipt: Optional[RunReceipt]
    capture: Dict[str, Any]
    facts: GenerationFacts

    @property
    def persisted(self) -> PersistedReceipt:
        """The receipt of a run with candidates: only a persisted receipt lists any (``validate_manifest``)."""
        return cast(PersistedReceipt, self.receipt)

    @cached_property
    def disposition(self) -> Dict[str, Dict[str, Any]]:
        """The dispositions saved with the run's candidate results, covering its admitted operations; only a run
        that saved results has them."""
        return completed_dispositions(self.persisted.dispositions,
                                      expected_refs=admission_operation_refs(self.facts, self.capture["input"]))


def load_saved_run(store, run, catalog: Sequence[Dict[str, Any]]) -> SavedRun:
    """The one load of a run's saved archive. ``catalog`` is the run's candidate list (store rows or the saved
    decision header's); the receipt must list exactly those candidates."""
    receipt = store.receipt(run)
    validate_manifest(catalog, receipt)
    capture = store.capture(run["run_ref"])
    return SavedRun(run, receipt, capture, store.generation_facts(capture))


@dataclass(frozen=True)
class CandidateReadSource:
    run: Dict[str, Any]
    candidate: Dict[str, Any]
    disposition: Dict[str, Dict[str, Any]]
    capture: Dict[str, Any]
    facts: GenerationFacts
    receipt: PersistedReceipt
    raw_tasks: list
    scheduled_op_ids: set
    task_intervals: dict
    prepared_tasks: dict
    _task_by_row_ref: dict = field(default_factory=dict, repr=False)
    _unplanned_by_ref: dict = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, run: SavedRun, candidate, tasks: ValidatedCandidateTasks, projected=()) -> "CandidateReadSource":
        """A candidate of a run already read in this snapshot. ``projected`` are task views the caller already
        projected from these validated rows; they seed the source's own projections."""
        return cls(
            run.run, candidate, run.disposition, run.capture, run.facts, run.persisted,
            tasks.raw_tasks, tasks.scheduled_op_ids, tasks.task_intervals, tasks.prepared_tasks,
            _task_by_row_ref={task["row_ref"]: task for task in projected},
        )

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
                missing, self.facts, self.task_intervals, prepared_tasks=self.prepared_tasks,
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
            row["row_ref"]: (row["machine_id"], row["operator_id"])
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


def read_candidate_source(store, candidate_ref) -> CandidateReadSource:
    """Load one candidate's source on its own: its run, the run's candidates and the candidate's saved tasks."""
    reference(candidate_ref)
    run_ref = store.candidate_run(candidate_ref)
    run, catalog = store.run(run_ref), store.candidates(run_ref)
    saved = load_saved_run(store, run, catalog)
    candidate = next((row for row in catalog if row["candidate_ref"] == candidate_ref), None)
    if candidate is None:
        corrupt()
    return CandidateReadSource.of(saved, candidate, validate_candidate_tasks(store, candidate, saved.facts))
