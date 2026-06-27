from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .optimizer_search_state import attempt_identity, is_candidate_rejected_attempt

SEARCH_REPORT_SCHEMA_VERSION = 1
FINGERPRINT_SCOPE = "report_candidate_identity"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _jsonable(enum_value)
    return {"type": value.__class__.__name__}


def stable_report_fingerprint(payload: Dict[str, Any]) -> str:
    text = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def candidate_report_fingerprint(candidate: Dict[str, Any], *, origin: str, objective_name: str) -> str:
    strategy = candidate.get("strategy")
    return stable_report_fingerprint(
        {
            "schema_version": SEARCH_REPORT_SCHEMA_VERSION,
            "fingerprint_scope": FINGERPRINT_SCOPE,
            "origin": origin,
            "objective_name": objective_name,
            "strategy": getattr(strategy, "value", strategy),
            "params": candidate.get("params") or {},
            "dispatch_mode": candidate.get("dispatch_mode"),
            "dispatch_rule": candidate.get("dispatch_rule"),
            "order": list(candidate.get("order") or []),
            "score": list(candidate.get("score") or []),
        }
    )


def attempt_report_fingerprint(attempt: Dict[str, Any], *, objective_name: str) -> str:
    if is_candidate_rejected_attempt(attempt):
        return stable_report_fingerprint(
            {
                "schema_version": SEARCH_REPORT_SCHEMA_VERSION,
                "fingerprint_scope": FINGERPRINT_SCOPE,
                "objective_name": objective_name,
                "attempt_identity": list(attempt_identity(attempt)),
            }
        )
    return stable_report_fingerprint(
        {
            "schema_version": SEARCH_REPORT_SCHEMA_VERSION,
            "fingerprint_scope": FINGERPRINT_SCOPE,
            "objective_name": objective_name,
            "tag": attempt.get("tag"),
            "strategy": attempt.get("strategy"),
            "dispatch_mode": attempt.get("dispatch_mode"),
            "dispatch_rule": attempt.get("dispatch_rule"),
            "score": list(attempt.get("score") or []),
        }
    )


def _candidate_summary(candidate: Dict[str, Any], *, origin: str, status: str) -> Dict[str, Any]:
    strategy = candidate.get("strategy")
    summary = candidate.get("summary")
    return {
        "origin": str(origin),
        "status": str(status),
        "strategy": _safe_text(getattr(strategy, "value", strategy)),
        "dispatch_mode": _safe_text(candidate.get("dispatch_mode")),
        "dispatch_rule": _safe_text(candidate.get("dispatch_rule")),
        "score": list(candidate.get("score") or []),
        "failed_ops": int(getattr(summary, "failed_ops", 0) or 0),
    }


def _safe_reason(reason: str) -> str:
    text = _safe_text(reason)
    return text or "candidate_rejected"


def _fingerprint_changed(initial_fingerprint: Optional[str], best_fingerprint: Optional[str]) -> bool:
    return bool(initial_fingerprint and best_fingerprint and initial_fingerprint != best_fingerprint)


@dataclass
class OptimizationSearchReportState:
    algorithm_profile: str
    seed: int
    time_budget_seconds: int
    objective_name: str
    started_at: float
    strict_mode: bool = False
    candidate_profile: Optional[Dict[str, Any]] = None
    evaluated_candidates: int = 0
    accepted_candidates: int = 0
    rejected_candidates: int = 0
    iterations: int = 0
    initial_fingerprint: Optional[str] = None
    best_fingerprint: Optional[str] = None
    best_origin: Optional[str] = None
    best_score: List[Any] = field(default_factory=list)
    candidate_fingerprints: Set[str] = field(default_factory=set)
    accepted_fingerprints: Set[str] = field(default_factory=set)
    skipped_phases: List[Dict[str, Any]] = field(default_factory=list)
    rejection_summary: Dict[str, int] = field(default_factory=dict)
    attempt_summary: List[Dict[str, Any]] = field(default_factory=list)
    deadline_reached: bool = False
    iteration_limit_reached: bool = False
    local_search_entered: bool = False
    local_search_improved: bool = False
    optional_warmstart_failed: bool = False

    def mark_phase_skipped(self, phase: str, reason: str, **extra: Any) -> None:
        row: Dict[str, Any] = {"phase": _safe_text(phase), "reason": _safe_text(reason)}
        for key, value in extra.items():
            if value is not None:
                row[str(key)] = _jsonable(value)
        if row not in self.skipped_phases:
            self.skipped_phases.append(row)

    def mark_candidate_evaluated(self, candidate: Dict[str, Any], *, origin: str) -> None:
        self.evaluated_candidates += 1
        fingerprint = candidate_report_fingerprint(candidate, origin=origin, objective_name=self.objective_name)
        self.candidate_fingerprints.add(fingerprint)

    def mark_candidate_accepted(self, candidate: Dict[str, Any], *, origin: str) -> None:
        fingerprint = candidate_report_fingerprint(candidate, origin=origin, objective_name=self.objective_name)
        if self.initial_fingerprint is None:
            self.initial_fingerprint = fingerprint
        self.best_fingerprint = fingerprint
        self.best_origin = str(origin)
        self.best_score = list(candidate.get("score") or [])
        self.accepted_candidates += 1
        self.accepted_fingerprints.add(fingerprint)
        self._append_attempt_summary(_candidate_summary(candidate, origin=origin, status="accepted"))

    def mark_candidate_rejected(self, *, reason: str, attempt: Optional[Dict[str, Any]] = None) -> None:
        safe_reason = _safe_reason(reason)
        self.rejected_candidates += 1
        self.rejection_summary[safe_reason] = int(self.rejection_summary.get(safe_reason, 0)) + 1
        if attempt is not None:
            self.candidate_fingerprints.add(attempt_report_fingerprint(attempt, objective_name=self.objective_name))

    def mark_optional_warmstart_failed(self, *, reason: str, attempt: Optional[Dict[str, Any]] = None) -> None:
        self.optional_warmstart_failed = True
        self.mark_candidate_rejected(reason=reason or "optional_warmstart_failed", attempt=attempt)

    def mark_deadline_reached(self) -> None:
        self.deadline_reached = True

    def mark_iteration_limit_reached(self) -> None:
        self.iteration_limit_reached = True

    def set_iterations(self, value: int) -> None:
        self.iterations = max(int(self.iterations), int(value or 0))

    def _append_attempt_summary(self, row: Dict[str, Any]) -> None:
        if len(self.attempt_summary) >= 12:
            return
        self.attempt_summary.append(dict(row))

    def finalize(
        self,
        *,
        runtime_ms: int,
        attempts: List[Dict[str, Any]],
        improvement_trace: List[Dict[str, Any]],
        stop_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        final_stop = stop_reason or self._infer_stop_reason()
        fingerprint_changed = _fingerprint_changed(self.initial_fingerprint, self.best_fingerprint)
        return {
            "schema_version": SEARCH_REPORT_SCHEMA_VERSION,
            "algorithm_profile": str(self.algorithm_profile),
            "candidate_profile": dict(self.candidate_profile or {}),
            "seed": int(self.seed),
            "stop_reason": final_stop,
            "best_origin": str(self.best_origin or "baseline"),
            "time_budget_seconds": int(self.time_budget_seconds),
            "runtime_ms": max(int(runtime_ms), 0),
            "iterations": int(self.iterations),
            "evaluated_candidates": int(self.evaluated_candidates),
            "distinct_candidates": int(len(self.candidate_fingerprints)),
            "accepted_candidates": int(self.accepted_candidates),
            "accepted_distinct_candidates": int(len(self.accepted_fingerprints)),
            "rejected_candidates": int(self.rejected_candidates),
            "initial_fingerprint": self.initial_fingerprint,
            "best_fingerprint": self.best_fingerprint,
            "fingerprint_scope": FINGERPRINT_SCOPE,
            "best_fingerprint_changed": fingerprint_changed,
            "best_score": list(self.best_score or []),
            "objective_name": str(self.objective_name),
            "attempts": list(attempts or []),
            "public_attempt_summary": list(self.attempt_summary or []),
            "improvement_trace": list(improvement_trace or []),
            "skipped_phases": list(self.skipped_phases or []),
            "rejection_summary": dict(self.rejection_summary or {}),
            "improved": fingerprint_changed,
        }

    def _infer_stop_reason(self) -> str:
        if self.deadline_reached:
            return "time_budget"
        if self.iteration_limit_reached:
            return "iteration_limit"
        if self.best_origin == "baseline":
            return "baseline_scheduled"
        if self.rejected_candidates and self.accepted_candidates == 0:
            return "all_candidates_rejected"
        if self.local_search_entered and not self.local_search_improved:
            return "no_improvement"
        return "completed"


__all__ = [
    "FINGERPRINT_SCOPE",
    "SEARCH_REPORT_SCHEMA_VERSION",
    "OptimizationSearchReportState",
    "attempt_report_fingerprint",
    "candidate_report_fingerprint",
    "stable_report_fingerprint",
]
