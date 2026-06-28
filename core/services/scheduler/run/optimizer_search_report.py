from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .optimizer_candidate_fingerprint import (
    DISTINCT_FINGERPRINT_DESCRIPTION,
    DISTINCT_FINGERPRINT_SCOPE,
    CandidateFingerprint,
    build_candidate_fingerprint,
    jsonable_fingerprint_payload,
    score_strictly_better,
)

SEARCH_REPORT_SCHEMA_VERSION = 1


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


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


def _append_fingerprint_event(rows: List[Dict[str, Any]], *, origin: str, status: str, fingerprint: CandidateFingerprint) -> None:
    if len(rows) >= 12:
        return
    row = fingerprint.to_report_dict()
    row["origin"] = str(origin)
    row["status"] = str(status)
    rows.append(row)


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
    initial_candidate_fingerprint: Optional[Dict[str, Any]] = None
    best_candidate_fingerprint: Optional[Dict[str, Any]] = None
    best_origin: Optional[str] = None
    initial_score: List[Any] = field(default_factory=list)
    best_score: List[Any] = field(default_factory=list)
    candidate_fingerprints: Set[str] = field(default_factory=set)
    accepted_fingerprints: Set[str] = field(default_factory=set)
    fingerprint_events: List[Dict[str, Any]] = field(default_factory=list)
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
                row[str(key)] = jsonable_fingerprint_payload(value)
        if row not in self.skipped_phases:
            self.skipped_phases.append(row)

    def mark_candidate_evaluated(self, candidate: Dict[str, Any], *, origin: str) -> None:
        self.evaluated_candidates += 1
        fingerprint = self._candidate_fingerprint(candidate, seen=self.candidate_fingerprints)
        self.candidate_fingerprints.add(fingerprint.output_fingerprint)
        _append_fingerprint_event(self.fingerprint_events, origin=origin, status="evaluated", fingerprint=fingerprint)
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            self._record_rejection_reason("same_fingerprint")

    def mark_candidate_accepted(self, candidate: Dict[str, Any], *, origin: str) -> None:
        fingerprint = self._candidate_fingerprint(candidate, seen=self.accepted_fingerprints)
        if fingerprint.output_fingerprint not in self.candidate_fingerprints:
            self.evaluated_candidates += 1
            self.candidate_fingerprints.add(fingerprint.output_fingerprint)
        if self.initial_fingerprint is None:
            self.initial_fingerprint = fingerprint.output_fingerprint
            self.initial_candidate_fingerprint = fingerprint.to_report_dict()
            self.initial_score = list(candidate.get("score") or [])
        self.best_fingerprint = fingerprint.output_fingerprint
        self.best_candidate_fingerprint = fingerprint.to_report_dict()
        self.best_origin = str(origin)
        self.best_score = list(candidate.get("score") or [])
        self.accepted_candidates += 1
        self.accepted_fingerprints.add(fingerprint.output_fingerprint)
        _append_fingerprint_event(self.fingerprint_events, origin=origin, status="accepted", fingerprint=fingerprint)
        self._append_attempt_summary(_candidate_summary(candidate, origin=origin, status="accepted"))

    def mark_candidate_rejected(self, *, reason: str) -> None:
        self._record_rejection_reason(reason)

    def mark_optional_warmstart_failed(self, *, reason: str) -> None:
        self.optional_warmstart_failed = True
        self.mark_candidate_rejected(reason=reason or "optional_warmstart_failed")

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

    def _record_rejection_reason(self, reason: str) -> None:
        safe_reason = _safe_reason(reason)
        self.rejected_candidates += 1
        self.rejection_summary[safe_reason] = int(self.rejection_summary.get(safe_reason, 0)) + 1

    def _candidate_fingerprint(self, candidate: Dict[str, Any], *, seen: Set[str]) -> CandidateFingerprint:
        return build_candidate_fingerprint(
            candidate,
            objective_name=self.objective_name,
            parent_fingerprint=self.best_fingerprint,
            seen_output_fingerprints=seen,
        )

    def _improvement_conditions(self, fingerprint_changed: bool) -> Dict[str, Any]:
        score_improved = score_strictly_better(self.best_score, self.initial_score)
        acceptance = _safe_text((self.candidate_profile or {}).get("acceptance")) or "improve_only"
        # acceptance_passed 当前是 improve_only 专用代理:improve_only 下任何「baseline 之后再被接受」
        # 都必然严格更优,故 accepted_candidates>1 等价于「通过接受准则」。item 8 引入
        # threshold/record_to_record/simulated_annealing(会接受非改进解)后本式将失真,必须改为依据
        # 真实 acceptance 判定结果(acceptance 归 item 8,见 roadmap §4.3/§7)。
        acceptance_passed = bool(self.accepted_candidates > 1 and self.best_candidate_fingerprint)
        return {
            "fingerprint_changed": bool(fingerprint_changed),
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
        fingerprint_changed = _fingerprint_changed(self.initial_fingerprint, self.best_fingerprint)
        improvement_conditions = self._improvement_conditions(fingerprint_changed)
        improved = bool(
            improvement_conditions["fingerprint_changed"]
            and improvement_conditions["score_strictly_better"]
            and improvement_conditions["acceptance_passed"]
        )
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
            "initial_candidate_fingerprint": dict(self.initial_candidate_fingerprint or {}),
            "best_candidate_fingerprint": dict(self.best_candidate_fingerprint or {}),
            "distinct_fingerprint_scope": DISTINCT_FINGERPRINT_SCOPE,
            "distinct_fingerprint_description": DISTINCT_FINGERPRINT_DESCRIPTION,
            "best_fingerprint_changed": fingerprint_changed,
            "best_score": list(self.best_score or []),
            "objective_name": str(self.objective_name),
            "attempts": list(attempts or []),
            "public_attempt_summary": list(self.attempt_summary or []),
            "improvement_trace": list(improvement_trace or []),
            "fingerprint_events": list(self.fingerprint_events or []),
            "improvement_conditions": improvement_conditions,
            "skipped_phases": list(self.skipped_phases or []),
            "rejection_summary": dict(self.rejection_summary or {}),
            "improved": improved,
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
    "SEARCH_REPORT_SCHEMA_VERSION",
    "OptimizationSearchReportState",
]
