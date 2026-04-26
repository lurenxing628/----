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
) -> None:
    attempts.append(
        {
            "tag": candidate_tag(strategy_key, dispatch_mode, dispatch_rule),
            "strategy": strategy_key,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "source": "candidate_rejected",
            "origin": validation_error_origin(exc),
        }
    )


def append_rejected_local_attempt(
    *,
    attempts: List[Dict[str, Any]],
    move: str,
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> None:
    append_unique_rejected_attempt(
        attempts,
        {
            "tag": f"local:{move}",
            "strategy": strategy.value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "source": "candidate_rejected",
            "origin": validation_error_origin(exc),
        },
    )


def evaluate_optional_start_candidate(
    *,
    evaluate: Callable[[], Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    strategy_key: str,
    dispatch_mode: str,
    dispatch_rule: str,
    primary: Tuple[str, str, str],
    strict_mode: bool,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode) or (strategy_key, dispatch_mode, dispatch_rule) == primary:
            raise
        append_rejected_start_attempt(
            attempts=attempts,
            strategy_key=strategy_key,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
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
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate()
    except ValidationError as exc:
        if bool(strict_mode):
            raise
        append_rejected_local_attempt(
            attempts=attempts,
            move=move,
            strategy=strategy,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        return None
