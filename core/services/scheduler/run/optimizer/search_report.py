from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

from .candidate_fingerprint import (
    CandidateFingerprint,
    build_candidate_fingerprint,
)


@dataclass
class OptimizationSearchReportState:
    objective_name: str
    started_at: float
    initial_fingerprint: Optional[tuple] = None
    best_fingerprint: Optional[tuple] = None
    best_origin: Optional[str] = None
    candidate_fingerprints: Set[tuple] = field(default_factory=set)
    _best_candidate: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False, compare=False)
    _best_identity: Optional[CandidateFingerprint] = field(default=None, init=False, repr=False, compare=False)
    candidate_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)
    candidate_clock: Optional[Callable[[], float]] = field(default=None, repr=False, compare=False)
    candidate_acceptance_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)
    reference_capture_observer: Optional[Callable[..., None]] = field(default=None, repr=False, compare=False)

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
        self.best_origin = origin
        self.candidate_fingerprints.add(identity.output_key)
        if self.initial_fingerprint is None:
            self.initial_fingerprint = identity.output_key

    def _observe_candidate(self, candidate: Dict[str, Any], *, origin: str, verified: bool) -> None:
        if self.candidate_observer is None:
            return
        if self.candidate_clock is None:
            raise ValueError("A shared candidate observer requires the common search clock.")
        elapsed_ms = max(int((self.candidate_clock() - self.started_at) * 1000), 0)
        self.candidate_observer(candidate=candidate, origin=origin, verified=verified, elapsed_ms=elapsed_ms)

    def best_fingerprint_changed(self) -> bool:
        return bool(
            self.initial_fingerprint is not None
            and self.best_fingerprint is not None
            and self.initial_fingerprint != self.best_fingerprint
        )

    def mark_candidate_evaluated(self, candidate: Dict[str, Any], *, origin: str,
                                 remember_fingerprint: bool = True,
                                 fingerprint: Optional[CandidateFingerprint] = None) -> CandidateFingerprint:
        """Count real work; an unverified checkpoint trial must not occupy the validated duplicate set."""
        self._observe_candidate(candidate, origin=origin, verified=remember_fingerprint)
        fingerprint = self._candidate_fingerprint(candidate, seen=self.candidate_fingerprints, identity=fingerprint)
        if remember_fingerprint:
            self.candidate_fingerprints.add(fingerprint.output_key)
        return fingerprint

    def _ensure_verified_fingerprint(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        fingerprint: CandidateFingerprint,
    ) -> CandidateFingerprint:
        if fingerprint.output_key not in self.candidate_fingerprints:
            self.candidate_fingerprints.add(fingerprint.output_key)
            self._observe_candidate(candidate, origin=origin, verified=True)
        return fingerprint

    def mark_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        fingerprint: CandidateFingerprint,
    ) -> None:
        fingerprint = self._ensure_verified_fingerprint(candidate, origin=origin, fingerprint=fingerprint)
        if self.initial_fingerprint is None:
            self.initial_fingerprint = fingerprint.output_key
        self.best_fingerprint = fingerprint.output_key
        self._best_candidate, self._best_identity = candidate, fingerprint
        self.best_origin = str(origin)
        if self.candidate_acceptance_observer is not None:
            self.candidate_acceptance_observer(candidate=candidate)

    def mark_current_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        fingerprint: CandidateFingerprint,
    ) -> None:
        self._ensure_verified_fingerprint(candidate, origin=origin, fingerprint=fingerprint)
        if self.candidate_acceptance_observer is not None:
            self.candidate_acceptance_observer(candidate=candidate)

    def _candidate_fingerprint(self, candidate: Dict[str, Any], *, seen: Set[tuple],
                               identity: Optional[CandidateFingerprint] = None) -> CandidateFingerprint:
        return build_candidate_fingerprint(
            candidate,
            objective_name=self.objective_name,
            parent_fingerprint=self._best_identity,
            seen_output_fingerprints=seen,
            identity=identity,
        )


__all__ = ["OptimizationSearchReportState"]
