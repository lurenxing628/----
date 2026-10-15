"""Shared optimizer result contract and actual decoder invocation evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy


@dataclass
class OptimizationOutcome:
    results: List[ScheduleResult]
    summary: Any  # ScheduleSummary（来自算法模块；保持与现有代码兼容）
    used_strategy: SortStrategy
    used_params: Dict[str, Any]
    metrics: Any  # ScheduleMetrics
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    algo_stats: Dict[str, Any] = field(default_factory=dict)
    search_report: Dict[str, Any] = field(default_factory=dict)
    # Dispatch mode and rule of the adopted plan; the rule may differ from the configured one
    # because multi-start and the rule neighborhood search the whole rule pool.
    dispatch_mode: str = ""
    dispatch_rule: str = ""
    process_evidence: Optional[Dict[str, Any]] = None


def _record_decoder_invocations(report: Dict[str, Any], scheduler: Any) -> None:
    if not isinstance(scheduler, GreedyScheduler):
        return
    value = vars(scheduler).get("_decode_invocations")
    if type(value) is int and value >= 0:
        report["decoder_invocations"] = value
