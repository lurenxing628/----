"""Shared helpers for SMTWT optimizer comparison benchmarks."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithms import GreedyScheduler
from core.services.scheduler.run.optimizer_proof_oracle import _ContinuousCalendar, _default_config
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState

SMTWT_COMPARE_SCHEMA_VERSION = 1
SMTWT_OBJECTIVE_NAME = "min_overdue"
DEFAULT_SMTWT_PROFILES = (
    "greedy",
    "local_search",
    "grasp_ig",
    "graph_ready_v1",
    "graph_ready_v2_no_repair",
    "graph_ready_v2_with_repair",
    "portfolio_all",
)


def normalize_profiles(profiles: Sequence[str]) -> Tuple[str, ...]:
    out: List[str] = []
    for item in profiles:
        text = str(item or "").strip().lower()
        if text == "graph_ready":
            text = "graph_ready_v1"
        if text and text not in out:
            out.append(text)
    return tuple(out or DEFAULT_SMTWT_PROFILES)


def make_scheduler() -> GreedyScheduler:
    return GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())


def schedule_with_scheduler(scheduler: GreedyScheduler, **kwargs: Any) -> Any:
    return scheduler.schedule(**kwargs)


def make_report_state(*, profile: str, seed: int, context: Dict[str, Any]) -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile=profile,
        seed=int(seed),
        time_budget_seconds=int(context["time_budget_seconds"]),
        objective_name=SMTWT_OBJECTIVE_NAME,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=True,
    )


def score_tuple(value: Any) -> Tuple[float, ...]:
    score = valid_score_tuple(value)
    return score if score is not None else (float("inf"),)


def valid_score_tuple(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (list, tuple)):
        return None
    if not value:
        return None
    score: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        score.append(number)
    return tuple(score)


def score_list(value: Any) -> List[float]:
    score = valid_score_tuple(value)
    return list(score or ())


def row_key(row: Dict[str, Any]) -> Tuple[str, int]:
    return str(row.get("case_slug") or ""), int(row.get("seed") or 0)


def first_changed_delta(actual: Tuple[float, ...], baseline: Tuple[float, ...]) -> float:
    for actual_item, baseline_item in zip(actual, baseline):
        delta = float(actual_item) - float(baseline_item)
        if abs(delta) > 1e-9:
            return delta
    return 0.0


def mean(values: Any) -> float:
    items = [float(item or 0.0) for item in values]
    return round(sum(items) / len(items), 6) if items else 0.0


class BenchmarkClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        self.now += 0.01
        return self.now
