"""Read one verified candidate source inside the caller's existing snapshot."""

from dataclasses import dataclass
from functools import cached_property
from typing import Optional

from core.models.workbench_run_candidate import reference

from .candidate_effort import candidate_operation_effort_projection
from .candidate_facts import GenerationFacts
from .candidate_projection import dispositions, validate_manifest
from .candidate_tasks import tasks_projection_with_intervals, unplanned_projection
from .candidate_values import corrupt
from .gantt_graph import candidate_gantt_graph


@dataclass(frozen=True)
class CandidateReadSource:
    run: dict
    candidate: dict
    disposition: dict
    capture: dict
    facts: GenerationFacts
    raw_tasks: list
    tasks: list
    unplanned: list
    catalog: list
    scheduled_op_ids: Optional[set]
    # validate_manifest rejects a missing receipt whenever its candidate rows exist.
    receipt: dict

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


def read_candidate_source(store, candidate_ref, *, prepared=None):
    """Reuse the caller's verified packet, or load an independent source once.

    A prepared packet belongs to this caller's current SQLite snapshot. Its
    run/catalog/receipt have already passed the common manifest check; raw and
    projected tasks may also be handed over together after validation.
    """
    reference(candidate_ref)
    if prepared is None:
        run_ref = store.candidate_run(candidate_ref)
        run, rows, disposition, receipt = candidate_manifest(store, run_ref)
        candidate = next((row for row in rows if row["candidate_ref"] == candidate_ref), None)
        if candidate is None:
            corrupt()
        capture = store.capture(run_ref)
        facts = GenerationFacts(capture)
        raw_tasks = store.tasks(candidate_ref)
        tasks = None
    else:
        run, rows, receipt = prepared["run"], prepared["rows"], prepared["receipt"]
        run_ref = reference(run.get("run_ref"), stored=True)
        candidate = prepared["candidate"]
        if candidate.get("candidate_ref") != candidate_ref or candidate.get("run_ref") != run_ref:
            corrupt()
        saved = next((row for row in rows if row["candidate_ref"] == candidate_ref), None)
        if (saved is None or saved.get("run_ref", run_ref) != run_ref or
                any(saved.get(key) != candidate.get(key) for key in ("status", "task_count", "sequence"))):
            corrupt()
        capture = prepared["capture"]
        facts = prepared["facts"]
        disposition = prepared["disposition"]
        raw_tasks = prepared.get("raw_tasks")
        tasks = prepared.get("tasks")
        ids = prepared["scheduled_op_ids"] if tasks is not None else None
        if raw_tasks is None:
            if tasks is not None:
                corrupt()
            raw_tasks = store.tasks(candidate_ref)
    if disposition is None:
        # 有候选行的运行只能是已完成运行，它的回执必带 dispositions；缺了就是存档损坏。
        corrupt()
    if tasks is None:
        if len(raw_tasks) != candidate["task_count"]:
            corrupt()
        tasks, _, ids = tasks_projection_with_intervals(raw_tasks, candidate, facts)
    unplanned = unplanned_projection(disposition, tasks, facts)
    return CandidateReadSource(run, candidate, disposition, capture, facts, raw_tasks, tasks, unplanned, rows, ids,
                               receipt=receipt)
