from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence, Tuple

from core.errors import ValidationError

from .candidate_fingerprint import score_strictly_better

ACCEPTANCE_IMPROVE_ONLY = "improve_only"
ACCEPTANCE_THRESHOLD = "threshold"
ACCEPTANCE_RECORD_TO_RECORD = "record_to_record"
ACCEPTANCE_SIMULATED_ANNEALING = "simulated_annealing"

ALLOWED_ACCEPTANCES: Tuple[str, ...] = (
    ACCEPTANCE_IMPROVE_ONLY,
    ACCEPTANCE_THRESHOLD,
    ACCEPTANCE_RECORD_TO_RECORD,
    ACCEPTANCE_SIMULATED_ANNEALING,
)

DEFAULT_THRESHOLD = 1.0
MIN_TEMPERATURE = 0.001


@dataclass(frozen=True)
class AcceptanceDecision:
    accepted: bool


def validate_acceptance_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    if text not in set(ALLOWED_ACCEPTANCES):
        raise ValidationError(
            f"未知接受准则“{name}”，本阶段只允许：{', '.join(ALLOWED_ACCEPTANCES)}。",
            field="acceptance",
        )
    return text


def decide_acceptance(
    *,
    acceptance_name: str,
    candidate_score: Any,
    current_score: Any,
    best_score: Any,
    iteration: int,
    max_iterations: int,
    rnd: Any,
) -> AcceptanceDecision:
    name = validate_acceptance_name(acceptance_name)
    better_than_current = score_strictly_better(candidate_score, current_score)

    if name == ACCEPTANCE_IMPROVE_ONLY:
        return AcceptanceDecision(accepted=better_than_current)
    progress = _progress(iteration=iteration, max_iterations=max_iterations)
    threshold = DEFAULT_THRESHOLD * (1.0 - progress)
    temperature = max(threshold, MIN_TEMPERATURE)
    if name == ACCEPTANCE_THRESHOLD:
        return _threshold_decision(
            candidate_score=candidate_score,
            current_score=current_score,
            better_than_current=better_than_current,
            threshold=threshold,
        )
    if name == ACCEPTANCE_RECORD_TO_RECORD:
        return _record_to_record_decision(
            candidate_score=candidate_score,
            best_score=best_score,
            better_than_current=better_than_current,
            threshold=threshold,
        )
    return _simulated_annealing_decision(
        better_than_current=better_than_current,
        delta_current=_score_delta(candidate_score, current_score),
        failed_ops_worse=_failed_ops_worse(candidate_score, current_score),
        temperature=temperature,
        rnd=rnd,
    )


def _threshold_decision(
    *,
    candidate_score: Any,
    current_score: Any,
    better_than_current: bool,
    threshold: float,
) -> AcceptanceDecision:
    failed_ops_worse = _failed_ops_worse(candidate_score, current_score)
    objective_delta_current = _score_delta(candidate_score, current_score, start_index=1)
    accepted = False if failed_ops_worse else (better_than_current or objective_delta_current <= threshold)
    return AcceptanceDecision(accepted=bool(accepted))


def _record_to_record_decision(
    *,
    candidate_score: Any,
    best_score: Any,
    better_than_current: bool,
    threshold: float,
) -> AcceptanceDecision:
    failed_ops_worse = _failed_ops_worse(candidate_score, best_score)
    objective_delta_record = _score_delta(candidate_score, best_score, start_index=1)
    accepted = False if failed_ops_worse else (better_than_current or objective_delta_record <= threshold)
    return AcceptanceDecision(accepted=bool(accepted))


def _simulated_annealing_decision(
    *,
    better_than_current: bool,
    delta_current: float,
    failed_ops_worse: bool,
    temperature: float,
    rnd: Any,
) -> AcceptanceDecision:
    if failed_ops_worse:
        return AcceptanceDecision(accepted=False)
    if better_than_current:
        return AcceptanceDecision(accepted=True)
    random_draw = float(rnd.random())
    probability = math.exp(-max(delta_current, 0.0) / max(temperature, MIN_TEMPERATURE))
    return AcceptanceDecision(accepted=random_draw <= probability)


# 候选分数都是本进程解码算出的 (失败工序数,) + 目标分量 元组，非空且全是有限数字。
def _failed_ops_worse(candidate_score: Sequence[float], reference_score: Sequence[float]) -> bool:
    return candidate_score[0] > reference_score[0]


def _score_delta(candidate_score: Sequence[float], reference_score: Sequence[float], *, start_index: int = 0) -> float:
    candidate = candidate_score[start_index:]
    reference = reference_score[start_index:]
    for cand_value, ref_value in zip(candidate, reference):
        delta = cand_value - ref_value
        if delta:
            return float(delta)
    return float(len(candidate) - len(reference))


def _progress(*, iteration: int, max_iterations: int) -> float:
    if max_iterations <= 0:
        return 1.0
    value = float(max(int(iteration), 0)) / float(max_iterations)
    return min(max(value, 0.0), 1.0)


__all__ = [
    "ACCEPTANCE_IMPROVE_ONLY",
    "ACCEPTANCE_RECORD_TO_RECORD",
    "ACCEPTANCE_SIMULATED_ANNEALING",
    "ACCEPTANCE_THRESHOLD",
    "ALLOWED_ACCEPTANCES",
    "AcceptanceDecision",
    "decide_acceptance",
    "validate_acceptance_name",
]
