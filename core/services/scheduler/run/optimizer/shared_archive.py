"""Owned schedules and objective projections for one optimizer session."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Dict, FrozenSet, Iterable, Iterator, List, Mapping, Optional, Set, Tuple, cast

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import OBJECTIVE_SCOPE_UNKNOWN
from core.models.objective import normalize_objective_name, objective_metric_keys, target_objectives_for

from .candidate_fingerprint import schedule_content_key

ContentKey = Tuple[Any, ...]
PartialScopeKey = Tuple[FrozenSet[int], FrozenSet[str]]


@dataclass(frozen=True)
class ScheduleScoreScope:
    scheduled_operation_ids: FrozenSet[int]
    complete_batch_ids: FrozenSet[str]
    objective_scope: str
    components_known: bool
    is_complete: bool

    @property
    def group_key(self) -> PartialScopeKey:
        return self.scheduled_operation_ids, self.complete_batch_ids


@dataclass(frozen=True)
class ScheduleEvaluation:
    field_order: Tuple[str, ...]
    score: Tuple[float, ...]


@dataclass(frozen=True)
class ScheduleArchiveEntry:
    """Metadata and evidence references owned by the archive."""

    entry_id: int
    content_key: ContentKey
    score_scope: ScheduleScoreScope
    evaluations: Mapping[str, ScheduleEvaluation]
    evidence_origin: Dict[str, Any]
    first_found_elapsed_ms: int


@dataclass(frozen=True)
class ArchiveObservation:
    entry_id: Optional[int] = None
    reason: Optional[str] = None
    reused: bool = False
    restored: bool = False
    initialized_objectives: Tuple[str, ...] = ()
    improved_objectives: Tuple[str, ...] = ()
    evidence_updated: bool = False


@dataclass(frozen=True)
class PartialScheduleGroup:
    entry_ids: Tuple[int, ...]
    best_by_objective: Mapping[str, int]


@dataclass
class _ContentIdentity:
    entry_id: int
    content_key: ContentKey
    first_found_elapsed_ms: int


@dataclass
class _StoredSchedule:
    identity: _ContentIdentity
    payload: Dict[str, Any]
    score_scope: ScheduleScoreScope
    evaluations: Dict[str, ScheduleEvaluation]
    evidence_origin: Dict[str, Any]


def _snapshot_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    # Fixed business seeds and input resource pools remain owned by the run input.
    # All other containers belong to this completed decode, including its decisions.
    out = {key: value if key in ("resource_pool", "seed_results") else deepcopy(value)
           for key, value in candidate.items() if key not in ("results", "summary", "metrics")}
    out["results"] = [replace(result) for result in candidate["results"]]
    out["summary"] = deepcopy(candidate["summary"])
    out["metrics"] = deepcopy(candidate["metrics"])
    return out


class SharedScheduleArchive:
    """Compare full schedules together and partial schedules only within their exact scope."""

    def __init__(
        self, primary_objective: str, target_objectives: Tuple[str, ...],
        expected_operation_ids: Iterable[int], batch_ids: Iterable[str], *, retention_limit: int = 64,
    ) -> None:
        self.primary_objective = normalize_objective_name(primary_objective)
        self.target_objectives = tuple(target_objectives)
        if self.target_objectives != target_objectives_for(self.primary_objective):
            raise ValueError("Target objectives must be the fixed set for the primary objective.")
        self._field_orders = {
            objective: ("failed_ops",) + objective_metric_keys(objective) for objective in self.target_objectives
        }
        if retention_limit < 1:
            raise ValueError("The schedule payload retention limit must be positive.")
        self.expected_operation_ids = frozenset(expected_operation_ids)
        self.batch_ids = frozenset(batch_ids)
        self.retention_limit = retention_limit
        self._identities: Dict[ContentKey, _ContentIdentity] = {}
        self._entries: Dict[int, _StoredSchedule] = {}
        self._best: Dict[str, int] = {}
        self._improvements = dict.fromkeys(self.target_objectives, 0)
        self._current: Dict[str, Optional[int]] = dict.fromkeys(self.target_objectives)
        self._starts: Dict[str, Tuple[int, ...]] = dict.fromkeys(self.target_objectives, ())
        self._active_entry_ids: Set[int] = set()
        self._retention_depth = 0
        self._partial: Dict[PartialScopeKey, Dict[str, int]] = {}
        self._partial_entry_ids: Dict[PartialScopeKey, List[int]] = {}
        self._next_entry_id = 1

    @property
    def best_by_objective(self) -> Dict[str, int]:
        return dict(self._best)

    @property
    def improvement_counts(self) -> Dict[str, int]:
        return dict(self._improvements)

    @property
    def current_by_objective(self) -> Dict[str, Optional[int]]:
        return dict(self._current)

    @property
    def starting_entries_by_objective(self) -> Dict[str, Tuple[int, ...]]:
        return dict(self._starts)

    @property
    def retained_entry_ids(self) -> Tuple[int, ...]:
        return tuple(self._entries)

    def __contains__(self, entry_id: object) -> bool:
        return entry_id in self._entries

    @property
    def partial_groups(self) -> Dict[PartialScopeKey, PartialScheduleGroup]:
        return {key: PartialScheduleGroup(tuple(self._partial_entry_ids[key]), dict(best))
                for key, best in self._partial.items()}

    def entry(self, entry_id: int) -> ScheduleArchiveEntry:
        stored = self._entries[entry_id]
        identity = stored.identity
        return ScheduleArchiveEntry(
            entry_id, identity.content_key, stored.score_scope, dict(stored.evaluations),
            stored.evidence_origin, identity.first_found_elapsed_ms,
        )

    def view(self, entry_id: int, *, objective: Optional[str] = None) -> Dict[str, Any]:
        """Return a stage's small fields while sharing the one owned decode payload."""
        objective = self.primary_objective if objective is None else objective
        self._require_objective(objective)
        stored = self._entries[entry_id]
        return dict(stored.payload, score=stored.evaluations[objective].score, _shared_entry_id=entry_id)

    def results(self, entry_id: int) -> List[ScheduleResult]:
        return self._entries[entry_id].payload["results"]

    def materialize(self, entry_id: int, *, objective: Optional[str] = None) -> Dict[str, Any]:
        """Give a public result independent ownership at its publication boundary."""
        objective = self.primary_objective if objective is None else objective
        self._require_objective(objective)
        stored = self._entries[entry_id]
        candidate = _snapshot_candidate(stored.payload)
        candidate["score"] = stored.evaluations[objective].score
        return candidate

    def register_decode(self, candidate: Dict[str, Any], *, verified: bool, elapsed_ms: int) -> ArchiveObservation:
        """Own a new verified decode; unknown trials retain only a temporary number."""
        if not self._has_completed_payload(candidate):
            return ArchiveObservation(reason="candidate_payload_missing")
        completion = candidate["metrics"].completion
        if completion is not None and completion.expected_operation_count != len(self.expected_operation_ids):
            return ArchiveObservation(reason="completion_scope_mismatch")
        key = schedule_content_key(candidate["results"])
        if not verified:
            identity = self._identities.get(key)
            if identity is not None:
                return ArchiveObservation(entry_id=identity.entry_id, reason="validation_unknown", reused=True)
            entry_id = self._next_entry_id
            self._next_entry_id += 1
            return ArchiveObservation(entry_id=entry_id, reason="validation_unknown")
        return self._register_verified(candidate, elapsed_ms=elapsed_ms, content_key=key)

    def finish_observation(self, observed: ArchiveObservation, candidate: Dict[str, Any], *,
                           origin: Dict[str, Any]) -> None:
        """Attach the selected stage evidence without registering or copying its rows again."""
        stored = self._entries[cast(int, observed.entry_id)]
        if not stored.evidence_origin or observed.evidence_updated or observed.restored:
            stored.evidence_origin = origin
            stored.payload.update({key: value for key, value in candidate.items()
                                   if not key.startswith("_") and key not in ("results", "summary", "metrics", "score")})

    def _register_verified(self, candidate: Dict[str, Any], *, elapsed_ms: int,
                           content_key: ContentKey) -> ArchiveObservation:
        identity = self._identities.get(content_key)
        if identity is not None and identity.entry_id in self._entries:
            stored = self._entries[identity.entry_id]
            if stored.score_scope.is_complete:
                return ArchiveObservation(entry_id=identity.entry_id, reused=True)
            scope = self._score_scope(candidate)
            if not self._evidence_can_upgrade(stored.score_scope, scope):
                return ArchiveObservation(entry_id=identity.entry_id, reused=True)
            evaluations = self._objective_evaluations(candidate)
            payload = dict(candidate, results=stored.payload["results"])
            self._remove_partial_entry(stored, keep_empty_scope=not scope.is_complete)
            stored.payload = payload
            stored.score_scope = scope
            stored.evaluations = evaluations
            stored.evidence_origin = {}
            initialized, improved = self._update_best(stored)
            self._evict_unreferenced()
            return ArchiveObservation(identity.entry_id, reused=True, evidence_updated=True,
                                      initialized_objectives=initialized, improved_objectives=improved)
        scope = self._score_scope(candidate)
        evaluations = self._objective_evaluations(candidate)
        restored = identity is not None
        if identity is None:
            identity = _ContentIdentity(self._next_entry_id, content_key, elapsed_ms)
            self._next_entry_id += 1
            self._identities[content_key] = identity
        payload = dict(candidate)
        stored = _StoredSchedule(identity, payload, scope, evaluations, {})
        self._entries[identity.entry_id] = stored
        initialized, improved = self._update_best(stored)
        self._evict_unreferenced()
        return ArchiveObservation(identity.entry_id, restored=restored,
                                  initialized_objectives=initialized, improved_objectives=improved)

    def _objective_evaluations(self, candidate: Dict[str, Any]) -> Dict[str, ScheduleEvaluation]:
        return {
            objective: ScheduleEvaluation(
                self._field_orders[objective],
                (candidate["summary"].failed_ops,) + objective_score(objective, candidate["metrics"]),
            ) for objective in self.target_objectives
        }

    @staticmethod
    def _evidence_can_upgrade(old: ScheduleScoreScope, new: ScheduleScoreScope) -> bool:
        return ((not old.is_complete and new.is_complete)
                or (old.group_key == new.group_key and not old.components_known and new.components_known))

    def accept_exploration(self, objective: str, entry_id: int) -> None:
        self._require_objective(objective)
        self._entries[entry_id]
        self._current[objective] = entry_id
        self._evict_unreferenced()

    def set_starting_entries(self, objective: str, entry_ids: Iterable[int]) -> None:
        self._require_objective(objective)
        unique = tuple(dict.fromkeys(entry_ids))
        if len(unique) > 3:
            raise ValueError("Each objective may retain at most three starting schedules.")
        for entry_id in unique:
            self._entries[entry_id]
        self._starts[objective] = unique
        self._evict_unreferenced()

    def set_active_entries(self, entry_ids: Iterable[int]) -> None:
        """Replace the schedules currently held by the active generators."""
        active = set(entry_ids)
        for entry_id in active:
            self._entries[entry_id]
        self._active_entry_ids = active
        self._evict_unreferenced()

    @contextmanager
    def retention_scope(self) -> Iterator[None]:
        """Defer eviction until an action has updated all of its references."""
        self._retention_depth += 1
        try:
            yield
        finally:
            self._retention_depth -= 1
            if self._retention_depth == 0:
                self._evict_unreferenced()

    def _require_objective(self, objective: str) -> None:
        if objective not in self.target_objectives:
            raise KeyError(objective)

    @staticmethod
    def _has_completed_payload(candidate: Dict[str, Any]) -> bool:
        return (isinstance(candidate, dict) and isinstance(candidate.get("results"), list)
                and (not candidate["results"] or isinstance(candidate["results"][0], ScheduleResult))
                and isinstance(candidate.get("summary"), ScheduleSummary)
                and isinstance(candidate.get("metrics"), ScheduleMetrics))

    def _score_scope(self, candidate: Dict[str, Any]) -> ScheduleScoreScope:
        results = candidate["results"]
        summary = candidate["summary"]
        completion = candidate["metrics"].completion
        if (
            completion is not None
            and completion.missing_operation_count == 0
            and completion.unexpected_result_count == 0
            and len(results) == len(self.expected_operation_ids)
            and summary.failed_ops == 0
            and not completion.incomplete_batch_ids
        ):
            is_complete = bool(
                summary.success is True
                and completion.objective_defined
                and completion.complete_batch_count == len(self.batch_ids)
            )
            return ScheduleScoreScope(
                self.expected_operation_ids,
                self.batch_ids,
                completion.objective_scope,
                completion.components_known,
                is_complete,
            )
        arranged = [result for result in results
                    if isinstance(result.start_time, datetime) and isinstance(result.end_time, datetime)
                    and result.end_time >= result.start_time]
        operation_ids = frozenset(result.op_id for result in arranged)
        if completion is None:
            return ScheduleScoreScope(operation_ids, frozenset(), OBJECTIVE_SCOPE_UNKNOWN, False, False)
        complete_batches = (
            self.batch_ids
            if not completion.incomplete_batch_ids
            else self.batch_ids - frozenset(completion.incomplete_batch_ids)
        )
        is_complete = bool(
            operation_ids == self.expected_operation_ids and len(arranged) == len(operation_ids)
            and len(arranged) == len(results) and summary.failed_ops == 0
            and summary.success is True
            and completion.missing_operation_count == 0 and completion.unexpected_result_count == 0
            and completion.objective_defined and completion.complete_batch_count == len(self.batch_ids)
        )
        return ScheduleScoreScope(operation_ids, complete_batches, completion.objective_scope,
                                  completion.components_known, is_complete)
    def _update_best(self, stored: _StoredSchedule) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        entry_id = stored.identity.entry_id
        if stored.score_scope.is_complete:
            best = self._best
        else:
            key = stored.score_scope.group_key
            best = self._partial.setdefault(key, {})
            members = self._partial_entry_ids.setdefault(key, [])
            if entry_id not in members:
                members.append(entry_id)
        if not stored.score_scope.components_known:
            return (), ()
        initialized, improved = [], []
        for objective in self.target_objectives:
            previous_id = best.get(objective)
            if previous_id is None:
                best[objective] = entry_id
                initialized.append(objective)
            elif stored.evaluations[objective].score < self._entries[previous_id].evaluations[objective].score:
                best[objective] = entry_id
                improved.append(objective)
                if stored.score_scope.is_complete:
                    self._improvements[objective] += 1
        return tuple(initialized), tuple(improved)

    def _protected_entry_ids(self) -> set:
        protected = set(self._best.values())
        protected.update(entry_id for entry_id in self._current.values() if entry_id is not None)
        protected.update(entry_id for entry_ids in self._starts.values() for entry_id in entry_ids)
        protected.update(self._active_entry_ids)
        if not self._best:
            # Stable sorting keeps the scope's first-observed order as the final tie break.
            scopes = sorted(self._partial, key=lambda key: (-len(key[0]), -len(key[1])))
            for key in scopes[:3]:
                if self._partial[key]:
                    protected.update(self._partial[key].values())
                else:
                    protected.add(self._partial_entry_ids[key][0])
        return protected

    def _evict_unreferenced(self) -> None:
        if self._retention_depth:
            return
        protected = self._protected_entry_ids()
        surplus = len(self._entries) - self.retention_limit
        for entry_id in tuple(self._entries):
            if surplus <= 0:
                break
            if entry_id not in protected:
                stored = self._entries.pop(entry_id)
                if not stored.score_scope.is_complete:
                    self._remove_partial_entry(stored)
                surplus -= 1

    def _remove_partial_entry(self, stored: _StoredSchedule, *, keep_empty_scope: bool = False) -> None:
        key = stored.score_scope.group_key
        members = self._partial_entry_ids[key]
        members.remove(stored.identity.entry_id)
        if not members:
            if keep_empty_scope:
                self._partial[key] = {}
            else:
                del self._partial[key]
                del self._partial_entry_ids[key]
            return
        best: Dict[str, int] = {}
        for entry_id in members:
            member = self._entries[entry_id]
            if not member.score_scope.components_known:
                continue
            for objective in self.target_objectives:
                previous_id = best.get(objective)
                if (previous_id is None or member.evaluations[objective].score
                        < self._entries[previous_id].evaluations[objective].score):
                    best[objective] = entry_id
        self._partial[key] = best


__all__ = ["ArchiveObservation", "PartialScheduleGroup", "ScheduleArchiveEntry", "ScheduleEvaluation",
           "ScheduleScoreScope", "SharedScheduleArchive"]
