from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_search_state import append_unique_rejected_attempt


def validation_error_origin(exc: ValidationError) -> Dict[str, Any]:
    return {"type": "ValidationError", "field": getattr(exc, "field", None), "message": str(exc)}


def candidate_tag(strategy_key: str, dispatch_mode: str, dispatch_rule: str) -> str:
    return f"start:{strategy_key}|{dispatch_mode}:{dispatch_rule}"


def append_rejected_start_attempt(
    *,
    attempts: List[Dict[str, Any]],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> Dict[str, Any]:
    attempt = {
        "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
        "strategy": strategy_key,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": validation_error_origin(exc),
    }
    attempts.append(attempt)
    return attempt


def append_rejected_local_attempt(
    *,
    attempts: List[Dict[str, Any]],
    move: str,
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> Dict[str, Any]:
    attempt = {
        "tag": f"local:{move}",
        "strategy": strategy.value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": validation_error_origin(exc),
    }
    append_unique_rejected_attempt(
        attempts,
        attempt,
    )
    return attempt


def append_rejected_reason_attempt(
    *,
    attempts: List[Dict[str, Any]],
    tag: str,
    strategy: str,
    dispatch_mode: str,
    dispatch_rule: str,
    reason: str,
    message: str,
) -> Dict[str, Any]:
    attempt = {
        "tag": tag,
        "strategy": strategy,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "source": "candidate_rejected",
        "origin": {"type": str(reason), "field": str(reason), "message": str(message)},
    }
    append_unique_rejected_attempt(attempts, attempt)
    return attempt


def evaluate_optional_start_candidate(
    *,
    evaluate: Callable[[], Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    primary: Tuple[str, str, str],
    strict_mode: bool,
    search_report_state: Any = None,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode) or (strategy_key, dispatch_mode, dispatch_rule) == primary:
            raise
        attempt = append_rejected_start_attempt(
            attempts=attempts,
            strategy_key=strategy_key,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error", attempt=attempt)
        return None


def evaluate_optional_local_candidate(
    *,
    evaluate: Callable[[], Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    move: str,
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    strict_mode: bool,
    search_report_state: Any = None,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode):
            raise
        attempt = append_rejected_local_attempt(
            attempts=attempts,
            move=move,
            strategy=strategy,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error", attempt=attempt)
        return None
