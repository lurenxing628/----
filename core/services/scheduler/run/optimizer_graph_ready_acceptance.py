from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_acceptance import ACCEPTANCE_IMPROVE_ONLY, ACCEPTANCE_SCHEMA_VERSION
from .optimizer_candidate_fingerprint import score_strictly_better


def build_graph_ready_improve_only_acceptance_event(
    *,
    candidate_score: Any,
    incumbent_score: Any,
    seed: int,
) -> Optional[Dict[str, Any]]:
    candidate = _score_tuple(candidate_score)
    incumbent = _score_tuple(incumbent_score)
    if not score_strictly_better(candidate, incumbent):
        return None
    return {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "acceptance_name": ACCEPTANCE_IMPROVE_ONLY,
        "accepted": True,
        "acceptance_reason": "score_improved",
        "score_delta": _first_score_delta(candidate, incumbent),
        "score_delta_reference": "incumbent_score",
        "threshold": None,
        "temperature": None,
        "record_distance": None,
        "record_distance_reference": None,
        "random_seed": int(seed),
        "deterministic_random_draw": None,
        "worse_solution_allowed": False,
    }


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return ()
    return tuple(_finite_score_item(item) for item in score)


def _finite_score_item(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("GraphReady 接受事件分数必须是数字。", field="graph_ready_acceptance") from exc
    if not math.isfinite(number):
        raise ValidationError("GraphReady 接受事件分数必须是有限数字。", field="graph_ready_acceptance")
    return number


def _first_score_delta(candidate: Tuple[float, ...], incumbent: Tuple[float, ...]) -> float:
    for cand_value, incumbent_value in zip(candidate, incumbent):
        if cand_value != incumbent_value:
            return float(cand_value - incumbent_value)
    return 0.0


__all__ = ["build_graph_ready_improve_only_acceptance_event"]
