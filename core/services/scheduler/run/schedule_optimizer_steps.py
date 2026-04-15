from __future__ import annotations

import inspect
import time
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import increment_counter, merge_algo_stats, snapshot_algo_stats
from core.algorithms.sort_strategies import parse_strategy
from core.models.enums import YesNo
from core.services.common.degradation import DegradationCollector
from core.services.common.field_parse import parse_field_float, parse_field_int

from ..number_utils import to_yes_no


class SchedulerLike(Protocol):
    def schedule(self, *args: Any, **kwargs: Any) -> Any:
        ...


def _is_yes(value: Any, *, default: str = YesNo.NO.value) -> bool:
    return to_yes_no(value, default=default) == YesNo.YES.value


def _cfg_float(
    _cfg_value,
    key: str,
    default: float,
    *,
    strict_mode: bool = False,
    algo_stats: Any = None,
    counter_key: Optional[str] = None,
    min_value: Optional[float] = None,
    min_inclusive: bool = True,
    min_violation_fallback: Any = None,
) -> float:
    collector = DegradationCollector()
    parsed = parse_field_float(
        _cfg_value(key, default),
        field=key,
        strict_mode=bool(strict_mode),
        scope="schedule_optimizer.runtime",
        fallback=float(default),
        collector=collector,
        min_value=min_value,
        min_inclusive=min_inclusive,
        min_violation_fallback=(default if min_violation_fallback is None else min_violation_fallback),
    )
    if collector:
        increment_counter(algo_stats, counter_key or f"optimizer_{key}_defaulted_count", bucket="param_fallbacks")
    return float(parsed)


def _cfg_int(
    _cfg_value,
    key: str,
    default: int,
    *,
    strict_mode: bool = False,
    algo_stats: Any = None,
    counter_key: Optional[str] = None,
    min_value: Optional[int] = None,
    min_violation_fallback: Any = None,
) -> int:
    collector = DegradationCollector()
    parsed = parse_field_int(
        _cfg_value(key, default),
        field=key,
        strict_mode=bool(strict_mode),
        scope="schedule_optimizer.runtime",
        fallback=int(default),
        collector=collector,
        min_value=min_value,
        min_violation_fallback=(default if min_violation_fallback is None else min_violation_fallback),
    )
    if collector:
        increment_counter(algo_stats, counter_key or f"optimizer_{key}_defaulted_count", bucket="param_fallbacks")
    return int(parsed)


def _scheduler_accepts_strict_mode(scheduler: SchedulerLike) -> Optional[bool]:
    schedule_fn = getattr(scheduler, "schedule", None)
    if not callable(schedule_fn):
        return False
    try:
        sig = inspect.signature(schedule_fn)
    except Exception:
        return None
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD or param.name == "strict_mode":
            return True
    return False


def _schedule_with_optional_strict_mode(scheduler: SchedulerLike, *, strict_mode: bool = False, **kwargs):
    supports_strict_mode = _scheduler_accepts_strict_mode(scheduler)
    if supports_strict_mode is False:
        return scheduler.schedule(**kwargs)
    if supports_strict_mode is True:
        return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))

    try:
        return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))
    except TypeError as exc:
        message = str(exc)
        if (
            "strict_mode" in message
            and ("unexpected keyword argument" in message or "got an unexpected keyword argument" in message)
        ):
            return scheduler.schedule(**kwargs)
        raise


def _run_ortools_warmstart(
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
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    t_begin: float,
    logger: Any,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> Optional[Dict[str, Any]]:
    # 可选：OR-Tools 高质量起点（瓶颈子问题）
    from core.algorithms.greedy.config_adapter import cfg_get

    def _cfg_value(key: str, default: Any = None) -> Any:
        return cfg_get(cfg, key, default)

    if algo_mode == "improve" and _is_yes(_cfg_value("ortools_enabled", None), default=YesNo.NO.value):
        try:
            from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

            remaining = float(deadline - time.time())
            # 时间预算不足时跳过 OR-Tools warm-start：
            # - remaining<=0：避免已经超时仍强行跑 1s
            # - remaining<1：避免 int(remaining)=0 被 tl=max(1,...) 拉回 1s 导致超时
            ort_order = None
            if remaining >= 1.0:
                tl_cfg = _cfg_int(
                    _cfg_value,
                    "ortools_time_limit_seconds",
                    5,
                    strict_mode=bool(strict_mode),
                    algo_stats=optimizer_algo_stats,
                    min_value=1,
                    min_violation_fallback=1,
                )
                tl = max(1, min(int(tl_cfg), int(remaining)))
                ort_order = try_solve_bottleneck_batch_order(
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    start_dt=start_dt,
                    time_limit_seconds=tl,
                    logger=logger,
                )
            if ort_order and time.time() <= deadline:
                # 用当前策略（仅用于“补齐 order 未覆盖的批次”）
                ort_strat = strategy_enum
                ort_params: Dict[str, Any] = {}
                if ort_strat == SortStrategy.WEIGHTED:
                    ort_params = {
                        "priority_weight": _cfg_float(
                            _cfg_value,
                            "priority_weight",
                            0.4,
                            strict_mode=bool(strict_mode),
                            algo_stats=optimizer_algo_stats,
                            min_value=0.0,
                        ),
                        "due_weight": _cfg_float(
                            _cfg_value,
                            "due_weight",
                            0.5,
                            strict_mode=bool(strict_mode),
                            algo_stats=optimizer_algo_stats,
                            min_value=0.0,
                        ),
                    }
                res, summ, used_strat, used_params = _schedule_with_optional_strict_mode(
                    scheduler,
                    strict_mode=bool(strict_mode),
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    strategy=ort_strat,
                    strategy_params=ort_params,
                    start_dt=start_dt,
                    end_date=end_date,
                    machine_downtimes=downtime_map,
                    batch_order_override=list(ort_order),
                    seed_results=seed_sr_list,
                    dispatch_mode=dispatch_mode_cfg,
                    dispatch_rule=dispatch_rule_cfg,
                    resource_pool=resource_pool,
                )
                metrics = compute_metrics(res, batches)
                score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
                algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
                attempts.append(
                    {
                        "tag": f"ortools:bottleneck|{dispatch_mode_cfg}:{dispatch_rule_cfg}",
                        "strategy": used_strat.value,
                        "dispatch_mode": dispatch_mode_cfg,
                        "dispatch_rule": dispatch_rule_cfg,
                        "score": list(score),
                        "failed_ops": int(summ.failed_ops),
                        "metrics": metrics.to_dict(),
                        "algo_stats": algo_stats,
                    }
                )
                cand = {
                    "results": res,
                    "summary": summ,
                    "strategy": used_strat,
                    "params": used_params,
                    "dispatch_mode": dispatch_mode_cfg,
                    "dispatch_rule": dispatch_rule_cfg,
                    "order": list(ort_order),
                    "metrics": metrics,
                    "score": score,
                    "algo_stats": algo_stats,
                }
                if best is None or score < best["score"]:
                    best = cand
                    if len(improvement_trace) < 200:
                        improvement_trace.append(
                            {
                                "elapsed_ms": int((time.time() - t_begin) * 1000),
                                "tag": f"ortools:bottleneck|{dispatch_mode_cfg}:{dispatch_rule_cfg}",
                                "strategy": used_strat.value,
                                "dispatch_mode": dispatch_mode_cfg,
                                "dispatch_rule": dispatch_rule_cfg,
                                "score": list(score),
                                "metrics": metrics.to_dict(),
                            }
                        )
        except Exception as e:
            # 可选项失败不阻断主流程
            increment_counter(optimizer_algo_stats if isinstance(optimizer_algo_stats, dict) else scheduler, "ortools_warmstart_failed_count")
            if logger:
                tb = traceback.format_exc(limit=10)
                # 尽量带堆栈（便于定位依赖缺失/配置错误等）；若 logger 不支持 exc_info 参数则回退为拼接文本。
                try:
                    logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}", exc_info=True)
                except TypeError:
                    logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}\n{tb}")
    return best


def _dispatch_rules_for_mode(dispatch_mode: str, dispatch_rule_cfg: str, valid_dispatch_rules: List[str]) -> List[str]:
    if dispatch_mode != "sgs":
        return [dispatch_rule_cfg]
    return [dispatch_rule_cfg] + [rule for rule in valid_dispatch_rules if rule != dispatch_rule_cfg]


def _resolve_multi_start_strategy_params(
    *,
    strategy: SortStrategy,
    _cfg_value,
    strict_mode: bool,
    optimizer_algo_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return {}
    return {
        "priority_weight": _cfg_float(
            _cfg_value,
            "priority_weight",
            0.4,
            strict_mode=bool(strict_mode),
            algo_stats=optimizer_algo_stats,
            min_value=0.0,
        ),
        "due_weight": _cfg_float(
            _cfg_value,
            "due_weight",
            0.5,
            strict_mode=bool(strict_mode),
            algo_stats=optimizer_algo_stats,
            min_value=0.0,
        ),
    }


def _get_cached_multi_start_order(
    *,
    strategy: SortStrategy,
    params: Dict[str, Any],
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]],
    build_order: Any,
) -> List[str]:
    cache_key = (str(strategy.value), tuple(sorted((str(key), value) for key, value in (params or {}).items())))
    if cache_key not in order_cache:
        order_cache[cache_key] = list(build_order(strategy, params))
    return list(order_cache[cache_key])


def _evaluate_multi_start_candidate(
    *,
    scheduler: SchedulerLike,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    order: List[str],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode: str,
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    res, summ, used_strat, used_params = _schedule_with_optional_strict_mode(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        batch_order_override=order,
        seed_results=seed_sr_list,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        resource_pool=resource_pool,
    )
    metrics = compute_metrics(res, batches)
    score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
        "metrics": metrics,
        "score": score,
        "algo_stats": algo_stats,
    }


def _run_multi_start(
    *,
    keys: List[str],
    dispatch_modes: List[str],
    dispatch_rule_cfg: str,
    valid_dispatch_rules: List[str],
    scheduler: SchedulerLike,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    cfg: Any,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    t_begin: float,
    build_order: Any,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> Optional[Dict[str, Any]]:
    from core.algorithms.greedy.config_adapter import cfg_get

    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]] = {}

    def _cfg_value(key: str, default: Any = None) -> Any:
        return cfg_get(cfg, key, default)

    # 执行策略轮询（multi-start）
    for dm in dispatch_modes:
        if time.time() > deadline:
            break
        dispatch_rules = _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules)
        for k in keys:
            if time.time() > deadline:
                break
            strat = parse_strategy(k, default=SortStrategy.PRIORITY_FIRST)
            params0 = _resolve_multi_start_strategy_params(
                strategy=strat,
                _cfg_value=_cfg_value,
                strict_mode=bool(strict_mode),
                optimizer_algo_stats=optimizer_algo_stats,
            )

            for dr in dispatch_rules:
                if time.time() > deadline:
                    break
                order = _get_cached_multi_start_order(
                    strategy=strat,
                    params=params0,
                    order_cache=order_cache,
                    build_order=build_order,
                )
                cand = _evaluate_multi_start_candidate(
                    scheduler=scheduler,
                    strict_mode=bool(strict_mode),
                    algo_ops_to_schedule=algo_ops_to_schedule,
                    batches=batches,
                    strategy=strat,
                    params=params0,
                    start_dt=start_dt,
                    end_date=end_date,
                    downtime_map=downtime_map,
                    order=order,
                    seed_sr_list=seed_sr_list,
                    dispatch_mode=dm,
                    dispatch_rule=dr,
                    resource_pool=resource_pool,
                    objective_name=objective_name,
                    optimizer_algo_stats=optimizer_algo_stats,
                )
                score = cand["score"]
                metrics = cand["metrics"]
                algo_stats = cand["algo_stats"]
                attempts.append(
                    {
                        "tag": f"start:{k}|{dm}:{dr}",
                        "strategy": cand["strategy"].value,
                        "dispatch_mode": dm,
                        "dispatch_rule": dr,
                        "score": list(score),
                        "failed_ops": int(cand["summary"].failed_ops),
                        "metrics": metrics.to_dict(),
                        "algo_stats": algo_stats,
                    }
                )
                if best is None or score < best["score"]:
                    best = cand
                    if len(improvement_trace) < 200:
                        improvement_trace.append(
                            {
                                "elapsed_ms": int((time.time() - t_begin) * 1000),
                                "tag": f"start:{k}|{dm}:{dr}",
                                "strategy": cand["strategy"].value,
                                "dispatch_mode": dm,
                                "dispatch_rule": dr,
                                "score": list(score),
                                "metrics": metrics.to_dict(),
                            }
                        )
    return best
