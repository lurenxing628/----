"""候选对比运行期的纯辅助函数（从 schedule_candidate_runner 抽出，降低单文件体量、便于独立复用）。

这些函数只做：候选打分元组/字符串/字典列表的值归一与强制、候选 cfg 与排产输入派生、
运行预算解析、候选健康度评估、图健康上下文提取。它们无状态、不构造 CandidatePlan、不触达编排流程；
逐字等价于原内联实现，仅物理位置改变。
"""

from __future__ import annotations

import math
from dataclasses import is_dataclass, replace
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, cast

from core.infrastructure.errors import ValidationError

from .schedule_candidate_health import CandidateHealth, evaluate_candidate_health, unavailable_health
from .schedule_candidate_specs import CANDIDATE_KIND_CRITICAL_CHAIN, CandidateRunSpec


def _candidate_score(outcome: Any) -> Tuple[float, ...]:
    return tuple(float(item) for item in tuple(outcome.best_score))


def _string_list(value: Any) -> List[str]:
    return [str(item) for item in list(value or [])]


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    return [dict(item) for item in list(value or []) if isinstance(item, dict)]


def _candidate_cfg(base_cfg: Any, spec: CandidateRunSpec) -> Any:
    graph_mode = "on" if spec.graph_enabled else "off"
    return replace(
        base_cfg,
        algo_mode=str(getattr(base_cfg, "algo_mode", "") or "").strip().lower(),
        graph_analysis_mode=graph_mode,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
    )


def _replace_schedule_input_cfg(schedule_input: Any, *, cfg: Any) -> Any:
    if is_dataclass(schedule_input) and not isinstance(schedule_input, type):
        return replace(cast(Any, schedule_input), cfg=cfg)
    if hasattr(schedule_input, "__dict__"):
        data = dict(vars(schedule_input))
        data["cfg"] = cfg
        return SimpleNamespace(**data)
    raise TypeError("schedule_input 必须是 dataclass 或普通对象，才能构造候选级输入。")


def _candidate_health(
    spec: CandidateRunSpec,
    *,
    baseline_results: List[Any],
    outcome: Any,
    graph_preparation: Any,
) -> CandidateHealth:
    if spec.kind != CANDIDATE_KIND_CRITICAL_CHAIN:
        return unavailable_health("baseline")
    if not baseline_results:
        return unavailable_health("baseline_result_unavailable")
    graph_metrics = _graph_health_context_payload(graph_preparation)
    return evaluate_candidate_health(
        baseline_results=baseline_results,
        candidate_results=list(outcome.results or []),
        graph_metrics=graph_metrics,
    )


def _graph_health_context_payload(graph_preparation: Any) -> Dict[str, Any]:
    health_context = getattr(graph_preparation, "graph_health_context", None)
    if isinstance(health_context, dict):
        return dict(health_context)
    return {}


def _resolve_total_budget(run_time_budget_seconds: Optional[float], *, cfg: Any) -> float:
    if run_time_budget_seconds is None:
        return float(cfg.time_budget_seconds)
    if isinstance(run_time_budget_seconds, bool):
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds")
    try:
        budget = float(run_time_budget_seconds)
    except Exception as exc:
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds") from exc
    if budget <= 0:
        raise ValidationError("这次找更好排法先试多久必须大于 0 秒。", field="run_time_budget_seconds")
    return budget


def _public_budget(total_budget: float) -> Optional[float]:
    if not math.isfinite(total_budget):
        return None
    return float(total_budget)


def _dict_or_none(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("图分析结果必须是 dict 或 None。")
