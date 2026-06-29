from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.infrastructure.errors import ValidationError

from .optimizer_acceptance import ALLOWED_ACCEPTANCES
from .optimizer_candidate_fingerprint import (
    DISTINCT_FINGERPRINT_DESCRIPTION,
    DISTINCT_FINGERPRINT_SCOPE,
    CandidateFingerprint,
    jsonable_fingerprint_payload,
)
from .optimizer_neighborhood_moves import ALLOWED_NEIGHBORHOODS


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def candidate_summary(candidate: Dict[str, Any], *, origin: str, status: str) -> Dict[str, Any]:
    strategy = candidate.get("strategy")
    summary = candidate.get("summary")
    return {
        "origin": str(origin),
        "status": str(status),
        "strategy": safe_text(getattr(strategy, "value", strategy)),
        "dispatch_mode": safe_text(candidate.get("dispatch_mode")),
        "dispatch_rule": safe_text(candidate.get("dispatch_rule")),
        "score": list(candidate.get("score") or []),
        "failed_ops": int(getattr(summary, "failed_ops", 0) or 0),
    }


def safe_reason(reason: str) -> str:
    text = safe_text(reason)
    return text or "candidate_rejected"


def fingerprint_changed(initial_fingerprint: Optional[str], best_fingerprint: Optional[str]) -> bool:
    return bool(initial_fingerprint and best_fingerprint and initial_fingerprint != best_fingerprint)


def append_fingerprint_event(rows: List[Dict[str, Any]], *, origin: str, status: str, fingerprint: CandidateFingerprint) -> None:
    if len(rows) >= 12:
        return
    row = fingerprint.to_report_dict()
    row["origin"] = str(origin)
    row["status"] = str(status)
    rows.append(row)


def safe_neighborhood_move(move: Dict[str, Any]) -> Dict[str, Any]:
    name = safe_text(move.get("neighborhood_name"))
    move_kind = safe_text(move.get("move_kind"))
    input_scope = safe_text(move.get("input_scope"))
    if name not in set(ALLOWED_NEIGHBORHOODS):
        raise ValidationError(f"非法邻域移动：未知邻域“{name or move.get('neighborhood_name')}”。", field="neighborhood_move")
    if not move_kind or not input_scope:
        raise ValidationError("非法邻域移动：缺少 move_kind 或 input_scope。", field="neighborhood_move")
    row = _base_move_row(move, name=name, move_kind=move_kind, input_scope=input_scope)
    fallback_reason = safe_text(move.get("fallback_reason"))
    if fallback_reason:
        row["fallback_reason"] = fallback_reason
    diagnostics = move.get("diagnostics")
    if isinstance(diagnostics, dict):
        row["diagnostics"] = jsonable_fingerprint_payload(diagnostics)
    return row


def safe_acceptance_event(event: Dict[str, Any]) -> Dict[str, Any]:
    name = safe_text(event.get("acceptance_name"))
    if name not in set(ALLOWED_ACCEPTANCES):
        raise ValidationError(f"非法接受事件：未知接受准则“{name or event.get('acceptance_name')}”。", field="acceptance")
    return {
        "schema_version": int(event.get("schema_version") or 1),
        "acceptance_name": name,
        "accepted": bool(event.get("accepted")),
        "acceptance_reason": safe_text(event.get("acceptance_reason")),
        "score_delta": float(event.get("score_delta") or 0.0),
        "score_delta_reference": safe_text(event.get("score_delta_reference")) or "current_score",
        "threshold": optional_float(event.get("threshold")),
        "temperature": optional_float(event.get("temperature")),
        "record_distance": optional_float(event.get("record_distance")),
        "record_distance_reference": safe_text(event.get("record_distance_reference")),
        "random_seed": int(event.get("random_seed") or 0),
        "deterministic_random_draw": optional_float(event.get("deterministic_random_draw")),
        "worse_solution_allowed": bool(event.get("worse_solution_allowed")),
    }


def safe_vns_event(event: Dict[str, Any]) -> Dict[str, Any]:
    current = safe_text(event.get("current_neighborhood"))
    next_name = safe_text(event.get("next_neighborhood"))
    if current not in set(ALLOWED_NEIGHBORHOODS) or next_name not in set(ALLOWED_NEIGHBORHOODS):
        raise ValidationError("非法 VNS 事件：未知业务邻域。", field="vns")
    return {
        "schema_version": int(event.get("schema_version") or 1),
        "current_neighborhood": current,
        "neighborhood_index": max(int(event.get("neighborhood_index") or 0), 0),
        "next_neighborhood": next_name,
        "next_neighborhood_index": max(int(event.get("next_neighborhood_index") or 0), 0),
        "neighborhood_switch_reason": safe_text(event.get("neighborhood_switch_reason")),
        "shake_count": max(int(event.get("shake_count") or 0), 0),
        "no_improve_count": max(int(event.get("no_improve_count") or 0), 0),
        "noop_count": max(int(event.get("noop_count") or 0), 0),
        "fallback_count": max(int(event.get("fallback_count") or 0), 0),
        "best_improved": bool(event.get("best_improved")),
    }


def final_report_payload(state: Any, **payload: Any) -> Dict[str, Any]:
    return {
        "schema_version": int(payload["schema_version"]),
        "algorithm_profile": str(state.algorithm_profile),
        "candidate_profile": dict_copy(state.candidate_profile),
        "seed": int(state.seed),
        "stop_reason": payload["final_stop"],
        "best_origin": str(state.best_origin or "baseline"),
        "time_budget_seconds": int(state.time_budget_seconds),
        "runtime_ms": max(int(payload["runtime_ms"]), 0),
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
        "initial_candidate_fingerprint": dict_copy(state.initial_candidate_fingerprint),
        "best_candidate_fingerprint": dict_copy(state.best_candidate_fingerprint),
        "distinct_fingerprint_scope": DISTINCT_FINGERPRINT_SCOPE,
        "distinct_fingerprint_description": DISTINCT_FINGERPRINT_DESCRIPTION,
        "best_fingerprint_changed": bool(payload["fingerprint_changed"]),
        "best_score": list_copy(state.best_score),
        "objective_name": str(state.objective_name),
        "attempts": list_copy(payload["attempts"]),
        "public_attempt_summary": list_copy(state.attempt_summary),
        "improvement_trace": list_copy(payload["improvement_trace"]),
        "fingerprint_events": list_copy(state.fingerprint_events),
        "neighborhood_moves": list_copy(state.neighborhood_moves),
        "neighborhood_summary": dict_copy(state.neighborhood_summary),
        "acceptance_events": list_copy(state.acceptance_events),
        "acceptance_summary": dict_copy(state.acceptance_summary),
        "vns_events": list_copy(state.vns_events),
        "vns_summary": dict_copy(state.vns_summary),
        "improvement_conditions": payload["improvement_conditions"],
        "skipped_phases": list_copy(state.skipped_phases),
        "rejection_summary": dict(state.rejection_summary),
        "improved": bool(payload["improved"]),
    }


def empty_neighborhood_counter() -> Dict[str, int]:
    return {"attempted": 0, "effective": 0, "noop": 0, "fallback": 0, "rejected": 0}


def empty_acceptance_counter() -> Dict[str, int]:
    return {"attempted": 0, "accepted": 0, "rejected": 0, "non_improving_accepted": 0}


def optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def list_copy(value: Any) -> List[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def dict_copy(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def improved_from_conditions(conditions: Dict[str, Any]) -> bool:
    return all(bool(conditions.get(key)) for key in ("fingerprint_changed", "score_strictly_better", "acceptance_passed"))


def _base_move_row(move: Dict[str, Any], *, name: str, move_kind: str, input_scope: str) -> Dict[str, Any]:
    return {
        "schema_version": int(move.get("schema_version") or 1),
        "name": name,
        "neighborhood_name": name,
        "scope": input_scope,
        "move_kind": move_kind,
        "input_scope": input_scope,
        "selected_operation_ids": list_copy(move.get("selected_operation_ids")),
        "selected_batch_ids": list_copy(move.get("selected_batch_ids")),
        "selected_machine_ids": list_copy(move.get("selected_machine_ids")),
        "reason": safe_text(move.get("reason")),
        "changed_decision_count": max(int(move.get("changed_decision_count") or 0), 0),
        "expected_effect": safe_text(move.get("expected_effect")),
        "noop": bool(move.get("noop")),
        "fallback_used": bool(move.get("fallback_used")),
        "candidate_rejected": safe_text(move.get("candidate_rejected")),
    }
