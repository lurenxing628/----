"""Read one verified candidate source inside the caller's existing snapshot."""

from dataclasses import dataclass
from functools import cached_property
from typing import Optional

from .candidate_effort import candidate_operation_effort_projection
from .candidate_facts import GenerationFacts
from .candidate_projection import dispositions, validate_manifest
from .candidate_tasks import tasks_projection, unplanned_projection
from .candidate_values import corrupt
from .gantt_graph import candidate_gantt_graph


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
    catalog: list
    receipt: Optional[dict] = None

    @property
    def snapshot_identity(self):
        """Permanent source identity; query scope is bound by the read context."""
        return {"read_contract_version": 1, "run_ref": self.run["run_ref"],
                "candidate_ref": self.candidate["candidate_ref"]}

    @cached_property
    def gantt_graph(self):
        return candidate_gantt_graph(self.tasks, self.facts, self.raw_tasks)

    @cached_property
    def operation_effort_projection(self):
        return candidate_operation_effort_projection(self)


def candidate_manifest(store, run_ref):
    run = store.run(run_ref)
    receipt = store.receipt(run)
    rows = store.candidates(run_ref)
    validate_manifest(run, rows, receipt)
    return run, rows, dispositions(receipt), receipt


def read_candidate_source(store, candidate_ref):
    """Load and verify once for projections owned by this read snapshot."""
    run_ref = store.candidate_run(candidate_ref)
    run, rows, disposition, receipt = candidate_manifest(store, run_ref)
    candidate = next(row for row in rows if row["candidate_ref"] == candidate_ref)
    capture = store.capture(run_ref)
    facts = GenerationFacts(capture)
    raw_tasks = store.tasks(candidate_ref)
    if len(raw_tasks) != candidate["task_count"]:
        corrupt()
    tasks = tasks_projection(raw_tasks, candidate, facts)
    return CandidateReadSource(run, candidate, disposition, capture, facts, raw_tasks,
                               tasks, unplanned_projection(disposition, tasks, facts), rows, receipt=receipt)
