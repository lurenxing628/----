from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_candidate_fingerprint import score_strictly_better

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

ACCEPTANCE_SCHEMA_VERSION = 1
DEFAULT_THRESHOLD = 1.0
MIN_TEMPERATURE = 0.001


@dataclass(frozen=True)
class AcceptanceDecision:
    acceptance_name: str
    accepted: bool
    acceptance_reason: str
    score_delta: float
    score_delta_reference: str
    threshold: Optional[float]
    temperature: Optional[float]
    record_distance: Optional[float]
    record_distance_reference: Optional[str]
    random_seed: int
    deterministic_random_draw: Optional[float]
    worse_solution_allowed: bool

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": ACCEPTANCE_SCHEMA_VERSION,
            "acceptance_name": str(self.acceptance_name),
            "accepted": bool(self.accepted),
            "acceptance_reason": str(self.acceptance_reason),
            "score_delta": float(self.score_delta),
            "score_delta_reference": str(self.score_delta_reference),
            "threshold": self.threshold,
            "temperature": self.temperature,
            "record_distance": self.record_distance,
            "record_distance_reference": self.record_distance_reference,
            "random_seed": int(self.random_seed),
            "deterministic_random_draw": self.deterministic_random_draw,
            "worse_solution_allowed": bool(self.worse_solution_allowed),
        }


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
    random_seed: int,
    rnd: Any,
) -> AcceptanceDecision:
    name = validate_acceptance_name(acceptance_name)
    delta_current = _score_delta(candidate_score, current_score)
    delta_record = _score_delta(candidate_score, best_score)
    objective_delta_current = _score_delta(candidate_score, current_score, start_index=1)
    objective_delta_record = _score_delta(candidate_score, best_score, start_index=1)
    better_than_current = score_strictly_better(candidate_score, current_score)
    progress = _progress(iteration=iteration, max_iterations=max_iterations)
    threshold = DEFAULT_THRESHOLD * (1.0 - progress)
    temperature = max(threshold, MIN_TEMPERATURE)

    if name == ACCEPTANCE_IMPROVE_ONLY:
        return _decision(
            name=name,
            accepted=better_than_current,
            reason="score_improved" if better_than_current else "not_improved",
            delta_current=delta_current,
            threshold=None,
            temperature=None,
            record_distance=None,
            random_seed=random_seed,
            random_draw=None,
        )
    if name == ACCEPTANCE_THRESHOLD:
        failed_ops_worse = _failed_ops_worse(candidate_score, current_score)
        accepted = False if failed_ops_worse else (better_than_current or objective_delta_current <= threshold)
        return _decision(
            name=name,
            accepted=accepted,
            reason=(
                "failed_ops_worse"
                if failed_ops_worse
                else ("within_threshold" if accepted and not better_than_current else ("score_improved" if accepted else "threshold_rejected"))
            ),
            delta_current=delta_current if failed_ops_worse else objective_delta_current,
            threshold=threshold,
            temperature=None,
            record_distance=None,
            random_seed=random_seed,
            random_draw=None,
        )
    if name == ACCEPTANCE_RECORD_TO_RECORD:
        failed_ops_worse = _failed_ops_worse(candidate_score, best_score)
        accepted = False if failed_ops_worse else (better_than_current or objective_delta_record <= threshold)
        return _decision(
            name=name,
            accepted=accepted,
            reason=(
                "failed_ops_worse"
                if failed_ops_worse
                else ("within_record_distance" if accepted and not better_than_current else ("score_improved" if accepted else "record_distance_rejected"))
            ),
            delta_current=delta_current if failed_ops_worse else objective_delta_current,
            threshold=threshold,
            temperature=None,
            record_distance=delta_record if failed_ops_worse else objective_delta_record,
            random_seed=random_seed,
            random_draw=None,
        )
    return _simulated_annealing_decision(
        name=name,
        better_than_current=better_than_current,
        delta_current=delta_current,
        failed_ops_worse=_failed_ops_worse(candidate_score, current_score),
        temperature=temperature,
        random_seed=random_seed,
        rnd=rnd,
    )


def _simulated_annealing_decision(
    *,
    name: str,
    better_than_current: bool,
    delta_current: float,
    failed_ops_worse: bool,
    temperature: float,
    random_seed: int,
    rnd: Any,
) -> AcceptanceDecision:
    if failed_ops_worse:
        return _decision(
            name=name,
            accepted=False,
            reason="failed_ops_worse",
            delta_current=delta_current,
            threshold=None,
            temperature=temperature,
            record_distance=None,
            random_seed=random_seed,
            random_draw=None,
        )
    if better_than_current:
        return _decision(
            name=name,
            accepted=True,
            reason="score_improved",
            delta_current=delta_current,
            threshold=None,
            temperature=temperature,
            record_distance=None,
            random_seed=random_seed,
            random_draw=None,
        )
    random_draw = float(rnd.random())
    probability = math.exp(-max(delta_current, 0.0) / max(temperature, MIN_TEMPERATURE))
    accepted = random_draw <= probability
    return _decision(
        name=name,
        accepted=accepted,
        reason="annealing_probability" if accepted else "annealing_rejected",
        delta_current=delta_current,
        threshold=None,
        temperature=temperature,
        record_distance=None,
        random_seed=random_seed,
        random_draw=random_draw,
    )


def _decision(
    *,
    name: str,
    accepted: bool,
    reason: str,
    delta_current: float,
    threshold: Optional[float],
    temperature: Optional[float],
    record_distance: Optional[float],
    random_seed: int,
    random_draw: Optional[float],
) -> AcceptanceDecision:
    return AcceptanceDecision(
        acceptance_name=name,
        accepted=bool(accepted),
        acceptance_reason=str(reason),
        score_delta=float(round(delta_current, 6)),
        score_delta_reference="current_score",
        threshold=_round_optional(threshold),
        temperature=_round_optional(temperature),
        record_distance=_round_optional(record_distance),
        record_distance_reference="best_score" if record_distance is not None else None,
        random_seed=int(random_seed),
        deterministic_random_draw=_round_optional(random_draw),
        # 报表里的 worse_solution_allowed 不是“本次候选已经作为更差排程被接收”的结果。
        # 它只说明当前接受准则是否允许探索更差的 current：除 improve_only 外，
        # threshold / record_to_record / simulated_annealing 都可能为了跳出局部最优接收
        # 非改进候选。真正是否接收看 accepted 和 acceptance_reason；是否进入最终 best，
        # 还要再过 score_strictly_better 与候选指纹门禁。
        worse_solution_allowed=name != ACCEPTANCE_IMPROVE_ONLY,
    )


def _failed_ops_worse(candidate_score: Any, reference_score: Any) -> bool:
    candidate = _score_tuple(candidate_score)
    reference = _score_tuple(reference_score)
    if not candidate or not reference:
        return False
    return candidate[0] > reference[0]


def _score_delta(candidate_score: Any, reference_score: Any, *, start_index: int = 0) -> float:
    candidate = _score_tuple(candidate_score)
    reference = _score_tuple(reference_score)
    if not candidate or not reference:
        return 0.0
    index = max(int(start_index), 0)
    candidate = candidate[index:]
    reference = reference[index:]
    for cand_value, ref_value in zip(candidate, reference):
        delta = cand_value - ref_value
        if delta:
            return float(delta)
    return float(len(candidate) - len(reference))


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)):
        return ()
    out = []
    for item in score:
        try:
            out.append(float(item))
        except (TypeError, ValueError, OverflowError):
            return ()
    return tuple(out)


def _progress(*, iteration: int, max_iterations: int) -> float:
    if max_iterations <= 0:
        return 1.0
    value = float(max(int(iteration), 0)) / float(max_iterations)
    return min(max(value, 0.0), 1.0)


def _round_optional(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(round(float(value), 6))


__all__ = [
    "ACCEPTANCE_IMPROVE_ONLY",
    "ACCEPTANCE_RECORD_TO_RECORD",
    "ACCEPTANCE_SCHEMA_VERSION",
    "ACCEPTANCE_SIMULATED_ANNEALING",
    "ACCEPTANCE_THRESHOLD",
    "ALLOWED_ACCEPTANCES",
    "AcceptanceDecision",
    "decide_acceptance",
    "validate_acceptance_name",
]
