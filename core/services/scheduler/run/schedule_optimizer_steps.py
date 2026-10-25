from __future__ import annotations

import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithms import SortStrategy
from core.algorithms.evaluation import objective_score
from core.errors import ValidationError
from core.services.scheduler.contracts.scheduler_like import SchedulerLike

from .optimizer.config import (
    ensure_optimizer_config_snapshot,
    is_ortools_enabled,
    ortools_time_limit_seconds,
    weighted_strategy_params,
)
from .optimizer.shared_budget import SharedSearchSkip
from .optimizer.shared_decode import decode_and_metrics
from .optimizer.step_report_hooks import (
    _record_ortools_candidate,
    _record_ortools_optional_failure,
)

if TYPE_CHECKING:
    from .optimizer.search_report import OptimizationSearchReportState
    from .optimizer.shared_decode import SharedDecodeSession


def _solve_ortools_order(
    *,
    deadline: float,
    now: Callable[[], float],
    snapshot: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    logger: Any,
    order_time_budget_seconds: Optional[float] = None,
) -> Optional[List[str]]:
    from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

    remaining = float(deadline - now())
    if order_time_budget_seconds is not None:
        remaining = min(remaining, order_time_budget_seconds)
    # 时间预算不足时跳过 OR-Tools warm-start：
    # - remaining<=0：避免已经超时仍强行跑 1s
    # - remaining<1：避免 int(remaining)=0 被 tl=max(1,...) 拉回 1s 导致超时
    if remaining < 1.0:
        return None

    tl_cfg = ortools_time_limit_seconds(snapshot)
    tl = max(1, min(int(tl_cfg), int(remaining)))
    return try_solve_bottleneck_batch_order(
        operations=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        time_limit_seconds=tl,
        logger=logger,
    )


def _ortools_strategy_params(snapshot: Any, *, strategy: SortStrategy) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return {}
    return weighted_strategy_params(snapshot)


def _evaluate_ortools_candidate(
    *,
    strict_mode: bool,
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    ort_order: List[str],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    decode_session: SharedDecodeSession,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        strict_mode=bool(strict_mode),
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        batch_order_override=list(ort_order),
        dispatch_mode=dispatch_mode_cfg,
        dispatch_rule=dispatch_rule_cfg,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_enabled=graph_ready_context is not None,
        graph_score_enabled=bool(graph_ready_context and graph_ready_context.get("score_enabled")),
        graph_priority_key_by_op_id=(graph_ready_context or {}).get("graph_priority_key_by_op_id"),
    )
    candidate = {
        "results": decoded.results,
        "summary": decoded.summary,
        "strategy": decoded.used_strategy,
        "params": decoded.used_params,
        "dispatch_mode": dispatch_mode_cfg,
        "dispatch_rule": dispatch_rule_cfg,
        "order": list(ort_order),
        "metrics": decoded.metrics,
        "score": (float(decoded.summary.failed_ops),) + objective_score(objective_name, decoded.metrics),
        "algo_stats": decoded.algo_stats,
        "resource_pool": resource_pool or {},
    }
    candidate["_shared_entry_id"] = decoded.entry_id
    candidate["_archive_observation"] = decoded.archive_observation
    if decoded.receipt is not None:
        candidate["decode_receipt"] = decoded.receipt
        if decoded.receipt["execution_kind"] == "decision_reused":
            source_runtime = decoded.receipt["source_runtime_ms"]
            source_initial = decoded.receipt["source_initial_decode_runtime_ms"]
            candidate["runtime_ms"] = source_runtime if source_runtime is not None else decoded.receipt["original_decode_ms"]
            candidate["initial_decode_runtime_ms"] = (
                source_initial if source_initial is not None else decoded.receipt["original_decode_ms"])
        else:
            candidate["runtime_ms"] = int(decoded.receipt["original_decode_ms"])
    return candidate


def _ortools_warmstart_skip_reason(
    *,
    algo_mode: str,
    snapshot: Any,
    deadline: float,
    now: Callable[[], float],
) -> Optional[str]:
    if algo_mode != "improve":
        return "algo_mode_not_improve"
    if not is_ortools_enabled(snapshot):
        return "disabled"
    if float(deadline - now()) < 1.0:
        return "time_budget"
    return None


def run_ortools_warmstart(
    *,
    algo_mode: str,
    cfg: Any,
    strategy_enum: SortStrategy,
    objective_name: str,
    deadline: float,
    scheduler: SchedulerLike,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    t_begin: float,
    logger: Any,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    readiness_gate_enabled: bool = False,
    graph_ready_context: Optional[Any] = None,
    strict_mode: bool = False,
    clock: Optional[Callable[[], float]] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
    decode_session: SharedDecodeSession,
) -> Optional[Dict[str, Any]]:
    # 可选：OR-Tools 高质量起点（瓶颈子问题）
    snapshot = ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))
    now = clock or time.time

    skip_reason = _ortools_warmstart_skip_reason(algo_mode=algo_mode, snapshot=snapshot, deadline=deadline, now=now)
    if skip_reason == "time_budget":
        _record_warmstart_shared_skip(attempts, SharedSearchSkip(skip_reason), strategy_enum,
                                      dispatch_mode_cfg, dispatch_rule_cfg)
        decode_session.budget.reject(skip_reason)
    if skip_reason:
        return best

    remaining = decode_session.budget.remaining()
    kind = "sgs_full" if dispatch_mode_cfg == "sgs" else "batch_order_full"
    order_time_budget_seconds = remaining - decode_session.budget.estimate(kind)
    if order_time_budget_seconds < 1.0:
        reason = "time_budget" if remaining <= 0.0 else "estimated_decode_cost"
        _record_warmstart_shared_skip(attempts, SharedSearchSkip(reason), strategy_enum,
                                      dispatch_mode_cfg, dispatch_rule_cfg)
        decode_session.budget.reject(reason)

    try:
        ort_order = _solve_ortools_order(
            deadline=deadline,
            now=now,
            snapshot=snapshot,
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            start_dt=start_dt,
            logger=logger,
            order_time_budget_seconds=order_time_budget_seconds,
        )
    except ValidationError as e:
        if bool(strict_mode):
            raise
        _record_ortools_optional_failure(
            attempts=attempts,
            strategy=strategy_enum,
            dispatch_mode=dispatch_mode_cfg,
            dispatch_rule=dispatch_rule_cfg,
            optimizer_algo_stats=optimizer_algo_stats,
            scheduler=scheduler,
            logger=logger,
            exc=e,
        )
        return best
    except SharedSearchSkip as exc:
        _record_warmstart_shared_skip(attempts, exc, strategy_enum, dispatch_mode_cfg, dispatch_rule_cfg)
        raise
    except Exception as e:
        _record_ortools_optional_failure(
            attempts=attempts,
            strategy=strategy_enum,
            dispatch_mode=dispatch_mode_cfg,
            dispatch_rule=dispatch_rule_cfg,
            optimizer_algo_stats=optimizer_algo_stats,
            scheduler=scheduler,
            logger=logger,
            exc=e,
        )
        return best

    if not ort_order:
        return best
    if now() >= deadline:
        _record_warmstart_shared_skip(attempts, SharedSearchSkip("time_budget"), strategy_enum,
                                      dispatch_mode_cfg, dispatch_rule_cfg)
        decode_session.budget.reject("time_budget")
        return best

    try:
        cand = _evaluate_ortools_candidate(
            strict_mode=bool(strict_mode),
            strategy=strategy_enum,
            params=_ortools_strategy_params(snapshot, strategy=strategy_enum),
            start_dt=start_dt,
            end_date=end_date,
            ort_order=list(ort_order),
            dispatch_mode_cfg=dispatch_mode_cfg,
            dispatch_rule_cfg=dispatch_rule_cfg,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
            decode_session=decode_session,
        )
    except SharedSearchSkip as exc:
        _record_warmstart_shared_skip(attempts, exc, strategy_enum, dispatch_mode_cfg, dispatch_rule_cfg)
        raise
    except ValidationError as e:
        if bool(strict_mode):
            raise
        _record_ortools_optional_failure(
            attempts=attempts,
            strategy=strategy_enum,
            dispatch_mode=dispatch_mode_cfg,
            dispatch_rule=dispatch_rule_cfg,
            optimizer_algo_stats=optimizer_algo_stats,
            scheduler=scheduler,
            logger=logger,
            exc=e,
        )
        return best

    return _record_ortools_candidate(
        best=best,
        candidate=cand,
        attempts=attempts,
        improvement_trace=improvement_trace,
        search_report_state=search_report_state,
        now=now,
        t_begin=t_begin,
    )


def _record_warmstart_shared_skip(
    attempts: List[Dict[str, Any]], exc: SharedSearchSkip, strategy: SortStrategy, dispatch_mode: str, dispatch_rule: str,
) -> None:
    attempts.append({
        "tag": f"ortools:bottleneck|{dispatch_mode}:{dispatch_rule}", "source": "ortools_warmstart",
        "candidate_status": "skipped", "reason": exc.reason, "request_id": exc.request_id,
        "decode_receipt": exc.receipt, "strategy": strategy.value,
        "dispatch_mode": dispatch_mode, "dispatch_rule": dispatch_rule,
    })


__all__ = [
    "run_ortools_warmstart",
]
