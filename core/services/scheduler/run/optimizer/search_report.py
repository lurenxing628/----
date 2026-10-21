from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .candidate_fingerprint import (
    CandidateFingerprint,
    build_candidate_fingerprint,
    jsonable_fingerprint_payload,
    score_strictly_better,
)
from .search_report_helpers import (
    append_fingerprint_event,
    candidate_summary,
    empty_acceptance_counter,
    empty_neighborhood_counter,
    final_report_payload,
    improved_from_conditions,
    list_copy,
    safe_acceptance_event,
    safe_neighborhood_move,
    safe_text,
    safe_vns_event,
)
from .search_report_helpers import fingerprint_changed as has_fingerprint_changed
from .search_report_helpers import safe_reason as normalize_reason

SEARCH_REPORT_SCHEMA_VERSION = 2


@dataclass
class OptimizationSearchReportState:
    algorithm_profile: str
    seed: int
    time_budget_seconds: int
    objective_name: str
    started_at: float
    candidate_profile: Optional[Dict[str, Any]] = None
    evaluated_candidates: int = 0
    accepted_candidates: int = 0
    current_accepted_candidates: int = 0
    best_improved_candidates: int = 0
    rejected_candidates: int = 0
    iterations: int = 0
    initial_fingerprint: Optional[tuple] = None
    best_fingerprint: Optional[tuple] = None
    initial_candidate_fingerprint: Optional[Dict[str, Any]] = None
    best_candidate_fingerprint: Optional[Dict[str, Any]] = None
    best_origin: Optional[str] = None
    initial_score: List[Any] = field(default_factory=list)
    best_score: List[Any] = field(default_factory=list)
    candidate_fingerprints: Set[tuple] = field(default_factory=set)
    accepted_fingerprints: Set[tuple] = field(default_factory=set)
    fingerprint_events: List[Dict[str, Any]] = field(default_factory=list)
    skipped_phases: List[Dict[str, Any]] = field(default_factory=list)
    rejection_summary: Dict[str, int] = field(default_factory=dict)
    attempt_summary: List[Dict[str, Any]] = field(default_factory=list)
    neighborhood_moves: List[Dict[str, Any]] = field(default_factory=list)
    neighborhood_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    acceptance_events: List[Dict[str, Any]] = field(default_factory=list)
    acceptance_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    vns_events: List[Dict[str, Any]] = field(default_factory=list)
    vns_summary: Dict[str, Any] = field(default_factory=dict)
    best_acceptance_passed: bool = False
    best_acceptance_event_count: int = 0
    deadline_reached: bool = False
    iteration_limit_reached: bool = False
    search_exhausted: bool = False
    local_search_entered: bool = False
    local_search_improved: bool = False
    optional_warmstart_failed: bool = False
    _candidate_sequence: int = field(default=0, init=False, repr=False)
    _best_candidate: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False, compare=False)
    _best_identity: Optional[CandidateFingerprint] = field(default=None, init=False, repr=False, compare=False)
    candidate_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)
    candidate_clock: Optional[Callable[[], float]] = field(default=None, repr=False, compare=False)
    candidate_acceptance_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)
    reference_capture_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)

    def next_candidate_id(self) -> int:
        self._candidate_sequence += 1
        return self._candidate_sequence

    def fingerprint_identity(self, candidate: Dict[str, Any]) -> Optional[CandidateFingerprint]:
        """The retained best's stable identity; its comparison context is recomputed by the caller."""
        return self._best_identity if candidate is self._best_candidate else None

    def sync_best_reference(self, candidate: Optional[Dict[str, Any]], *, origin: str = "shared_archive_reference") -> None:
        """Adopt an already decoded comparison reference without recording new search work."""
        if candidate is None or candidate is self._best_candidate:
            return
        identity = self._candidate_fingerprint(candidate, seen=self.candidate_fingerprints)
        self._best_candidate, self._best_identity = candidate, identity
        self.best_fingerprint = identity.output_key
        report_dict = identity.to_report_dict()
        score_list = list(candidate.get("score") or ())
        self.best_candidate_fingerprint = report_dict
        self.best_origin = origin
        self.best_score = score_list
        self.candidate_fingerprints.add(identity.output_key)
        if self.initial_fingerprint is None:
            self.initial_fingerprint = identity.output_key
            self.initial_candidate_fingerprint = report_dict
            self.initial_score = list(score_list)

    def _observe_candidate(self, candidate: Dict[str, Any], *, origin: str, verified: bool) -> None:
        if self.candidate_observer is None:
            return
        if self.candidate_clock is None:
            raise ValueError("A shared candidate observer requires the common search clock.")
        elapsed_ms = max(int((self.candidate_clock() - self.started_at) * 1000), 0)
        self.candidate_observer(candidate=candidate, origin=origin, verified=verified, elapsed_ms=elapsed_ms)

    def mark_phase_skipped(self, phase: str, reason: str, **extra: Any) -> None:
        row: Dict[str, Any] = {"phase": safe_text(phase), "reason": safe_text(reason)}
        for key, value in extra.items():
            if value is not None:
                row[str(key)] = jsonable_fingerprint_payload(value)
        if row not in self.skipped_phases:
            self.skipped_phases.append(row)

    def update_candidate_profile(self, **fields: Any) -> None:
        if self.candidate_profile is None:
            self.candidate_profile = {}
        profile = self.candidate_profile
        for key, value in fields.items():
            if value is not None:
                profile[str(key)] = jsonable_fingerprint_payload(value)

    def best_fingerprint_changed(self) -> bool:
        return has_fingerprint_changed(self.initial_fingerprint, self.best_fingerprint)

    def mark_candidate_evaluated(self, candidate: Dict[str, Any], *, origin: str,
                                 remember_fingerprint: bool = True,
                                 fingerprint: Optional[CandidateFingerprint] = None) -> CandidateFingerprint:
        """Count real work; an unverified checkpoint trial must not occupy the validated duplicate set."""
        self.evaluated_candidates += 1
        self._observe_candidate(candidate, origin=origin, verified=remember_fingerprint)
        fingerprint = self._candidate_fingerprint(candidate, seen=self.candidate_fingerprints, identity=fingerprint)
        if remember_fingerprint:
            self.candidate_fingerprints.add(fingerprint.output_key)
        append_fingerprint_event(self.fingerprint_events, origin=origin, status="evaluated", fingerprint=fingerprint)
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            self._record_rejection_reason("same_fingerprint")
        return fingerprint

    def mark_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        acceptance_event: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[CandidateFingerprint] = None,
    ) -> None:
        fingerprint = self._candidate_fingerprint(candidate, seen=self.accepted_fingerprints, identity=fingerprint)
        if fingerprint.output_key not in self.candidate_fingerprints:
            self.evaluated_candidates += 1
            self.candidate_fingerprints.add(fingerprint.output_key)
            self._observe_candidate(candidate, origin=origin, verified=True)
        was_initial = self.initial_fingerprint is None
        if self.initial_fingerprint is None:
            self.initial_fingerprint = fingerprint.output_key
            self.initial_candidate_fingerprint = fingerprint.to_report_dict()
            self.initial_score = list(candidate.get("score") or [])
        self.best_fingerprint = fingerprint.output_key
        self._best_candidate, self._best_identity = candidate, fingerprint
        self.best_candidate_fingerprint = fingerprint.to_report_dict()
        self.best_origin = str(origin)
        self.best_score = list(candidate.get("score") or [])
        self.accepted_candidates += 1
        if self.candidate_acceptance_observer is not None:
            self.candidate_acceptance_observer(candidate=candidate)
        self.accepted_fingerprints.add(fingerprint.output_key)
        if not was_initial:
            self.best_improved_candidates += 1
        append_fingerprint_event(self.fingerprint_events, origin=origin, status="accepted", fingerprint=fingerprint)
        if len(self.attempt_summary) < 12:
            self._append_attempt_summary(candidate_summary(candidate, origin=origin, status="best_improved" if not was_initial else "accepted"))
        if acceptance_event is not None:
            self.mark_acceptance_event(acceptance_event, best_improved=not was_initial, current_accepted=True)

    def mark_current_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        acceptance_event: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[CandidateFingerprint] = None,
    ) -> None:
        fingerprint = self._candidate_fingerprint(candidate, seen=self.accepted_fingerprints, identity=fingerprint)
        if fingerprint.output_key not in self.candidate_fingerprints:
            self.evaluated_candidates += 1
            self.candidate_fingerprints.add(fingerprint.output_key)
            self._observe_candidate(candidate, origin=origin, verified=True)
        self.accepted_candidates += 1
        self.current_accepted_candidates += 1
        if self.candidate_acceptance_observer is not None:
            self.candidate_acceptance_observer(candidate=candidate)
        self.accepted_fingerprints.add(fingerprint.output_key)
        append_fingerprint_event(self.fingerprint_events, origin=origin, status="current_accepted", fingerprint=fingerprint)
        if len(self.attempt_summary) < 12:
            self._append_attempt_summary(candidate_summary(candidate, origin=origin, status="current_accepted"))
        if acceptance_event is not None:
            self.mark_acceptance_event(acceptance_event, best_improved=False, current_accepted=True)

    def mark_candidate_rejected(self, *, reason: str) -> None:
        self._record_rejection_reason(reason)

    def mark_acceptance_event(
        self,
        event: Dict[str, Any],
        *,
        best_improved: bool = False,
        current_accepted: bool = False,
    ) -> None:
        row = safe_acceptance_event(event)
        name = row["acceptance_name"]
        bucket = self.acceptance_summary.get(name)
        if bucket is None:
            bucket = empty_acceptance_counter()
            self.acceptance_summary[name] = bucket
        bucket["attempted"] += 1
        accepted = row["accepted"]
        if accepted:
            bucket["accepted"] += 1
        else:
            bucket["rejected"] += 1
        if current_accepted and not best_improved:
            bucket["non_improving_accepted"] += 1
        if best_improved and accepted:
            self.best_acceptance_passed = True
            self.best_acceptance_event_count += 1
        if len(self.acceptance_events) < 50:
            row["best_improved"] = bool(best_improved)
            row["current_accepted"] = bool(current_accepted)
            self.acceptance_events.append(row)

    def set_effective_neighborhoods(
        self,
        *,
        configured: Any,
        effective: Any,
        reason: str,
        dispatch_mode: str,
    ) -> None:
        profile = dict(self.candidate_profile or {})
        configured_values = list_copy(configured)
        effective_values = list_copy(effective)
        if configured_values:
            profile["configured_neighborhoods"] = configured_values
        if effective_values:
            profile["effective_neighborhoods"] = effective_values
        reason_text = safe_text(reason)
        if reason_text:
            profile["effective_neighborhood_reason"] = reason_text
        dispatch_text = safe_text(dispatch_mode)
        if dispatch_text:
            profile["effective_dispatch_mode"] = dispatch_text
        self.candidate_profile = profile

    def mark_vns_event(self, event: Dict[str, Any]) -> None:
        row = safe_vns_event(event)
        self.vns_summary = {
            "current_neighborhood": row["next_neighborhood"],
            "neighborhood_index": row["next_neighborhood_index"],
            "shake_count": row["shake_count"],
            "no_improve_count": row["no_improve_count"],
            "noop_count": row["noop_count"],
            "fallback_count": row["fallback_count"],
            "last_switch_reason": row["neighborhood_switch_reason"],
        }
        if len(self.vns_events) < 50:
            self.vns_events.append(row)

    def mark_neighborhood_move(self, move: Dict[str, Any]) -> None:
        row = safe_neighborhood_move(move)
        name = row["neighborhood_name"]
        bucket = self.neighborhood_summary.get(name)
        if bucket is None:
            bucket = empty_neighborhood_counter()
            self.neighborhood_summary[name] = bucket
        bucket["attempted"] += 1
        if row["noop"]:
            bucket["noop"] += 1
        else:
            bucket["effective"] += 1
        if row["fallback_used"]:
            bucket["fallback"] += 1
        if row["candidate_rejected"]:
            bucket["rejected"] += 1
        if len(self.neighborhood_moves) < 50:
            self.neighborhood_moves.append(row)

    def mark_optional_warmstart_failed(self, *, reason: str = "optional_warmstart_failed") -> None:
        self.optional_warmstart_failed = True
        self.mark_candidate_rejected(reason=reason or "optional_warmstart_failed")

    def mark_deadline_reached(self) -> None:
        self.deadline_reached = True

    def mark_iteration_limit_reached(self) -> None:
        self.iteration_limit_reached = True

    def mark_search_exhausted(self) -> None:
        """Every neighbor the search could still propose had already been decoded."""
        self.search_exhausted = True

    def set_iterations(self, value: int) -> None:
        self.iterations = max(int(self.iterations), int(value or 0))

    def _append_attempt_summary(self, row: Dict[str, Any]) -> None:
        if len(self.attempt_summary) >= 12:
            return
        self.attempt_summary.append(row)

    def _record_rejection_reason(self, reason: str) -> None:
        safe_reason = normalize_reason(reason)
        self.rejected_candidates += 1
        self.rejection_summary[safe_reason] = int(self.rejection_summary.get(safe_reason, 0)) + 1

    def _candidate_fingerprint(self, candidate: Dict[str, Any], *, seen: Set[tuple],
                               identity: Optional[CandidateFingerprint] = None) -> CandidateFingerprint:
        return build_candidate_fingerprint(
            candidate,
            objective_name=self.objective_name,
            parent_fingerprint=self._best_identity,
            seen_output_fingerprints=seen,
            identity=identity,
            candidate_id=self.next_candidate_id() if identity is None else identity.candidate_id,
        )

    def _improvement_conditions(self, fingerprint_changed: bool) -> Dict[str, Any]:
        score_improved = score_strictly_better(self.best_score, self.initial_score)
        acceptance = safe_text((self.candidate_profile or {}).get("acceptance")) or "improve_only"
        acceptance_passed = bool(
            self.best_acceptance_passed
            and self.best_acceptance_event_count > 0
            and self.best_candidate_fingerprint
        )
        return {
            "output_changed": bool(fingerprint_changed),
            "score_strictly_better": bool(score_improved),
            "acceptance": acceptance,
            "acceptance_passed": bool(acceptance_passed),
        }

    def finalize(
        self,
        *,
        runtime_ms: int,
        attempts: List[Dict[str, Any]],
        improvement_trace: List[Dict[str, Any]],
        stop_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        final_stop = stop_reason or self._infer_stop_reason()
        fingerprint_changed = has_fingerprint_changed(self.initial_fingerprint, self.best_fingerprint)
        improvement_conditions = self._improvement_conditions(fingerprint_changed)
        improved = improved_from_conditions(improvement_conditions)
        return final_report_payload(
            self,
            runtime_ms=runtime_ms,
            attempts=attempts,
            improvement_trace=improvement_trace,
            final_stop=final_stop,
            schema_version=SEARCH_REPORT_SCHEMA_VERSION,
            fingerprint_changed=fingerprint_changed,
            improvement_conditions=improvement_conditions,
            improved=improved,
        )

    def _infer_stop_reason(self) -> str:
        if self.deadline_reached:
            return "time_budget"
        if self.iteration_limit_reached:
            return "iteration_limit"
        if self.search_exhausted:
            return "search_exhausted"
        if self.best_origin == "baseline":
            return "baseline_scheduled"
        if self.rejected_candidates and self.accepted_candidates == 0:
            return "all_candidates_rejected"
        if self.local_search_entered and not self.local_search_improved:
            return "no_improvement"
        return "completed"

__all__ = ["SEARCH_REPORT_SCHEMA_VERSION", "OptimizationSearchReportState"]
