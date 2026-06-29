from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError

from .optimizer_acceptance import ALLOWED_ACCEPTANCES
from .optimizer_candidate_fingerprint import (
    DISTINCT_FINGERPRINT_DESCRIPTION,
    DISTINCT_FINGERPRINT_SCOPE,
    CandidateFingerprint,
    build_candidate_fingerprint,
    jsonable_fingerprint_payload,
    score_strictly_better,
)
from .optimizer_neighborhood_moves import ALLOWED_NEIGHBORHOODS

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


def _safe_neighborhood_move(move: Dict[str, Any]) -> Dict[str, Any]:
    name = _safe_text(move.get("neighborhood_name"))
    move_kind = _safe_text(move.get("move_kind"))
    input_scope = _safe_text(move.get("input_scope"))
    if name not in set(ALLOWED_NEIGHBORHOODS):
        raise ValidationError(f"非法邻域移动：未知邻域“{name or move.get('neighborhood_name')}”。", field="neighborhood_move")
    if not move_kind or not input_scope:
        raise ValidationError("非法邻域移动：缺少 move_kind 或 input_scope。", field="neighborhood_move")
    row: Dict[str, Any] = {
        "schema_version": int(move.get("schema_version") or 1),
        "name": name,
        "neighborhood_name": name,
        "scope": input_scope,
        "move_kind": move_kind,
        "input_scope": input_scope,
        "selected_operation_ids": _list_copy(move.get("selected_operation_ids")),
        "selected_batch_ids": _list_copy(move.get("selected_batch_ids")),
        "selected_machine_ids": _list_copy(move.get("selected_machine_ids")),
        "reason": _safe_text(move.get("reason")),
        "changed_decision_count": max(int(move.get("changed_decision_count") or 0), 0),
        "expected_effect": _safe_text(move.get("expected_effect")),
        "noop": bool(move.get("noop")),
        "fallback_used": bool(move.get("fallback_used")),
        "candidate_rejected": _safe_text(move.get("candidate_rejected")),
    }
    fallback_reason = _safe_text(move.get("fallback_reason"))
    if fallback_reason:
        row["fallback_reason"] = fallback_reason
    diagnostics = move.get("diagnostics")
    if isinstance(diagnostics, dict):
        row["diagnostics"] = jsonable_fingerprint_payload(diagnostics)
    return row


def _safe_acceptance_event(event: Dict[str, Any]) -> Dict[str, Any]:
    name = _safe_text(event.get("acceptance_name"))
    if name not in set(ALLOWED_ACCEPTANCES):
        raise ValidationError(f"非法接受事件：未知接受准则“{name or event.get('acceptance_name')}”。", field="acceptance")
    return {
        "schema_version": int(event.get("schema_version") or 1),
        "acceptance_name": name,
        "accepted": bool(event.get("accepted")),
        "acceptance_reason": _safe_text(event.get("acceptance_reason")),
        "score_delta": float(event.get("score_delta") or 0.0),
        "score_delta_reference": _safe_text(event.get("score_delta_reference")) or "current_score",
        "threshold": _optional_float(event.get("threshold")),
        "temperature": _optional_float(event.get("temperature")),
        "record_distance": _optional_float(event.get("record_distance")),
        "record_distance_reference": _safe_text(event.get("record_distance_reference")),
        "random_seed": int(event.get("random_seed") or 0),
        "deterministic_random_draw": _optional_float(event.get("deterministic_random_draw")),
        "worse_solution_allowed": bool(event.get("worse_solution_allowed")),
    }


def _safe_vns_event(event: Dict[str, Any]) -> Dict[str, Any]:
    current = _safe_text(event.get("current_neighborhood"))
    next_name = _safe_text(event.get("next_neighborhood"))
    allowed = set(ALLOWED_NEIGHBORHOODS)
    if current not in allowed or next_name not in allowed:
        raise ValidationError("非法 VNS 事件：未知业务邻域。", field="vns")
    return {
        "schema_version": int(event.get("schema_version") or 1),
        "current_neighborhood": current,
        "neighborhood_index": max(int(event.get("neighborhood_index") or 0), 0),
        "next_neighborhood": next_name,
        "next_neighborhood_index": max(int(event.get("next_neighborhood_index") or 0), 0),
        "neighborhood_switch_reason": _safe_text(event.get("neighborhood_switch_reason")),
        "shake_count": max(int(event.get("shake_count") or 0), 0),
        "no_improve_count": max(int(event.get("no_improve_count") or 0), 0),
        "noop_count": max(int(event.get("noop_count") or 0), 0),
        "fallback_count": max(int(event.get("fallback_count") or 0), 0),
        "best_improved": bool(event.get("best_improved")),
    }


def _empty_neighborhood_counter() -> Dict[str, int]:
    return {"attempted": 0, "effective": 0, "noop": 0, "fallback": 0, "rejected": 0}


def _empty_acceptance_counter() -> Dict[str, int]:
    return {"attempted": 0, "accepted": 0, "rejected": 0, "non_improving_accepted": 0}


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _list_copy(value: Any) -> List[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _dict_copy(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _improved_from_conditions(conditions: Dict[str, Any]) -> bool:
    return all(
        bool(conditions.get(key))
        for key in ("fingerprint_changed", "score_strictly_better", "acceptance_passed")
    )


def _final_report_payload(
    state: OptimizationSearchReportState,
    *,
    runtime_ms: int,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    final_stop: str,
    fingerprint_changed: bool,
    improvement_conditions: Dict[str, Any],
    improved: bool,
) -> Dict[str, Any]:
    return {
        "schema_version": SEARCH_REPORT_SCHEMA_VERSION,
        "algorithm_profile": str(state.algorithm_profile),
        "candidate_profile": _dict_copy(state.candidate_profile),
        "seed": int(state.seed),
        "stop_reason": final_stop,
        "best_origin": str(state.best_origin or "baseline"),
        "time_budget_seconds": int(state.time_budget_seconds),
        "runtime_ms": max(int(runtime_ms), 0),
        "iterations": int(state.iterations),
        "evaluated_candidates": int(state.evaluated_candidates),
        "distinct_candidates": int(len(state.candidate_fingerprints)),
        "accepted_candidates": int(state.accepted_candidates),
        "accepted_distinct_candidates": int(len(state.accepted_fingerprints)),
        "current_accepted_candidates": int(state.current_accepted_candidates),
        "best_improved_candidates": int(state.best_improved_candidates),
        "rejected_candidates": int(state.rejected_candidates),
        "initial_fingerprint": state.initial_fingerprint,
        "best_fingerprint": state.best_fingerprint,
        "initial_candidate_fingerprint": _dict_copy(state.initial_candidate_fingerprint),
        "best_candidate_fingerprint": _dict_copy(state.best_candidate_fingerprint),
        "distinct_fingerprint_scope": DISTINCT_FINGERPRINT_SCOPE,
        "distinct_fingerprint_description": DISTINCT_FINGERPRINT_DESCRIPTION,
        "best_fingerprint_changed": fingerprint_changed,
        "best_score": _list_copy(state.best_score),
        "objective_name": str(state.objective_name),
        "attempts": _list_copy(attempts),
        "public_attempt_summary": _list_copy(state.attempt_summary),
        "improvement_trace": _list_copy(improvement_trace),
        "fingerprint_events": _list_copy(state.fingerprint_events),
        "neighborhood_moves": _list_copy(state.neighborhood_moves),
        "neighborhood_summary": _dict_copy(state.neighborhood_summary),
        "acceptance_events": _list_copy(state.acceptance_events),
        "acceptance_summary": _dict_copy(state.acceptance_summary),
        "vns_events": _list_copy(state.vns_events),
        "vns_summary": _dict_copy(state.vns_summary),
        "improvement_conditions": improvement_conditions,
        "skipped_phases": _list_copy(state.skipped_phases),
        "rejection_summary": dict(state.rejection_summary),
        "improved": improved,
    }


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
    current_accepted_candidates: int = 0
    best_improved_candidates: int = 0
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

    def mark_candidate_evaluated(self, candidate: Dict[str, Any], *, origin: str) -> CandidateFingerprint:
        self.evaluated_candidates += 1
        fingerprint = self._candidate_fingerprint(candidate, seen=self.candidate_fingerprints)
        self.candidate_fingerprints.add(fingerprint.output_fingerprint)
        _append_fingerprint_event(self.fingerprint_events, origin=origin, status="evaluated", fingerprint=fingerprint)
        if fingerprint.same_as_parent or fingerprint.same_as_seen:
            self._record_rejection_reason("same_fingerprint")
        return fingerprint

    def mark_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        acceptance_event: Optional[Dict[str, Any]] = None,
    ) -> None:
        fingerprint = self._candidate_fingerprint(candidate, seen=self.accepted_fingerprints)
        if fingerprint.output_fingerprint not in self.candidate_fingerprints:
            self.evaluated_candidates += 1
            self.candidate_fingerprints.add(fingerprint.output_fingerprint)
        was_initial = self.initial_fingerprint is None
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
        if not was_initial:
            self.best_improved_candidates += 1
        _append_fingerprint_event(self.fingerprint_events, origin=origin, status="accepted", fingerprint=fingerprint)
        self._append_attempt_summary(_candidate_summary(candidate, origin=origin, status="best_improved" if not was_initial else "accepted"))
        if acceptance_event is not None:
            self.mark_acceptance_event(acceptance_event, best_improved=not was_initial, current_accepted=True)

    def mark_current_candidate_accepted(
        self,
        candidate: Dict[str, Any],
        *,
        origin: str,
        acceptance_event: Optional[Dict[str, Any]] = None,
    ) -> None:
        fingerprint = self._candidate_fingerprint(candidate, seen=self.accepted_fingerprints)
        if fingerprint.output_fingerprint not in self.candidate_fingerprints:
            self.evaluated_candidates += 1
            self.candidate_fingerprints.add(fingerprint.output_fingerprint)
        self.accepted_candidates += 1
        self.current_accepted_candidates += 1
        self.accepted_fingerprints.add(fingerprint.output_fingerprint)
        _append_fingerprint_event(self.fingerprint_events, origin=origin, status="current_accepted", fingerprint=fingerprint)
        self._append_attempt_summary(_candidate_summary(candidate, origin=origin, status="current_accepted"))
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
        row = _safe_acceptance_event(event)
        name = _safe_text(row.get("acceptance_name")) or "unknown"
        bucket = self.acceptance_summary.setdefault(name, _empty_acceptance_counter())
        bucket["attempted"] += 1
        if bool(row.get("accepted")):
            bucket["accepted"] += 1
        else:
            bucket["rejected"] += 1
        if current_accepted and not best_improved:
            bucket["non_improving_accepted"] += 1
        if best_improved and bool(row.get("accepted")):
            self.best_acceptance_passed = True
            self.best_acceptance_event_count += 1
        if len(self.acceptance_events) < 50:
            stored = dict(row)
            stored["best_improved"] = bool(best_improved)
            stored["current_accepted"] = bool(current_accepted)
            self.acceptance_events.append(stored)

    def set_effective_neighborhoods(
        self,
        *,
        configured: Any,
        effective: Any,
        reason: str,
        dispatch_mode: str,
    ) -> None:
        profile = dict(self.candidate_profile or {})
        configured_values = _list_copy(configured) or _list_copy(profile.get("configured_neighborhoods")) or _list_copy(profile.get("neighborhoods"))
        effective_values = _list_copy(effective)
        if configured_values:
            profile["configured_neighborhoods"] = configured_values
        if effective_values:
            profile["effective_neighborhoods"] = effective_values
        reason_text = _safe_text(reason)
        if reason_text:
            profile["effective_neighborhood_reason"] = reason_text
        dispatch_text = _safe_text(dispatch_mode)
        if dispatch_text:
            profile["effective_dispatch_mode"] = dispatch_text
        self.candidate_profile = profile

    def mark_vns_event(self, event: Dict[str, Any]) -> None:
        row = _safe_vns_event(event)
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
        row = _safe_neighborhood_move(move)
        name = _safe_text(row.get("neighborhood_name")) or "unknown"
        bucket = self.neighborhood_summary.setdefault(name, _empty_neighborhood_counter())
        bucket["attempted"] += 1
        if bool(row.get("noop")):
            bucket["noop"] += 1
        else:
            bucket["effective"] += 1
        if bool(row.get("fallback_used")):
            bucket["fallback"] += 1
        if _safe_text(row.get("candidate_rejected")):
            bucket["rejected"] += 1
        if len(self.neighborhood_moves) < 50:
            self.neighborhood_moves.append(row)

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
        acceptance_passed = bool(
            self.best_acceptance_passed
            and self.best_acceptance_event_count > 0
            and self.best_candidate_fingerprint
        )
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
        improved = _improved_from_conditions(improvement_conditions)
        return _final_report_payload(
            self,
            runtime_ms=runtime_ms,
            attempts=attempts,
            improvement_trace=improvement_trace,
            final_stop=final_stop,
            fingerprint_changed=fingerprint_changed,
            improvement_conditions=improvement_conditions,
            improved=improved,
        )

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
