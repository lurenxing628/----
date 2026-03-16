from __future__ import annotations

import time
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import parse_strategy
from core.models.enums import YesNo

from .number_utils import to_yes_no


def _is_yes(value: Any, *, default: str = YesNo.NO.value) -> bool:
    return to_yes_no(value, default=default) == YesNo.YES.value


def _run_ortools_warmstart(
    *,
    algo_mode: str,
    cfg: Any,
    strategy_enum: SortStrategy,
    objective_name: str,
    deadline: float,
    scheduler: GreedyScheduler,
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
                tl_cfg = int(_cfg_value("ortools_time_limit_seconds", 5) or 5)
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
                        "priority_weight": float(_cfg_value("priority_weight", 0.4) or 0.4),
                        "due_weight": float(_cfg_value("due_weight", 0.5) or 0.5),
                    }
                res, summ, used_strat, used_params = scheduler.schedule(
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
                attempts.append(
                    {
                        "tag": f"ortools:bottleneck|{dispatch_mode_cfg}:{dispatch_rule_cfg}",
                        "strategy": used_strat.value,
                        "dispatch_mode": dispatch_mode_cfg,
                        "dispatch_rule": dispatch_rule_cfg,
                        "score": list(score),
                        "failed_ops": int(summ.failed_ops),
                        "metrics": metrics.to_dict(),
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
            if logger:
                tb = traceback.format_exc(limit=10)
                # 尽量带堆栈（便于定位依赖缺失/配置错误等）；若 logger 不支持 exc_info 参数则回退为拼接文本。
                try:
                    logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}", exc_info=True)
                except TypeError:
                    logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}\n{tb}")
    return best


def _run_multi_start(
    *,
    keys: List[str],
    dispatch_modes: List[str],
    dispatch_rule_cfg: str,
    valid_dispatch_rules: List[str],
    scheduler: GreedyScheduler,
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
) -> Optional[Dict[str, Any]]:
    from core.algorithms.greedy.config_adapter import cfg_get

    def _cfg_value(key: str, default: Any = None) -> Any:
        return cfg_get(cfg, key, default)

    # 执行策略轮询（multi-start）
    for dm in dispatch_modes:
        if time.time() > deadline:
            break
        dispatch_rules = [dispatch_rule_cfg]
        if dm == "sgs":
            dispatch_rules = [dispatch_rule_cfg] + [x for x in valid_dispatch_rules if x != dispatch_rule_cfg]
        for k in keys:
            if time.time() > deadline:
                break
            strat = parse_strategy(k, default=SortStrategy.PRIORITY_FIRST)
            params0: Dict[str, Any] = {}
            if strat == SortStrategy.WEIGHTED:
                params0 = {
                    "priority_weight": float(_cfg_value("priority_weight", 0.4) or 0.4),
                    "due_weight": float(_cfg_value("due_weight", 0.5) or 0.5),
                }

            for dr in dispatch_rules:
                if time.time() > deadline:
                    break
                order = build_order(strat, params0)
                res, summ, used_strat, used_params = scheduler.schedule(
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    strategy=strat,
                    strategy_params=params0,
                    start_dt=start_dt,
                    end_date=end_date,
                    machine_downtimes=downtime_map,
                    batch_order_override=order,
                    seed_results=seed_sr_list,
                    dispatch_mode=dm,
                    dispatch_rule=dr,
                    resource_pool=resource_pool,
                )
                metrics = compute_metrics(res, batches)
                score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
                attempts.append(
                    {
                        "tag": f"start:{k}|{dm}:{dr}",
                        "strategy": used_strat.value,
                        "dispatch_mode": dm,
                        "dispatch_rule": dr,
                        "score": list(score),
                        "failed_ops": int(summ.failed_ops),
                        "metrics": metrics.to_dict(),
                    }
                )
                cand = {
                    "results": res,
                    "summary": summ,
                    "strategy": used_strat,
                    "params": used_params,
                    "dispatch_mode": dm,
                    "dispatch_rule": dr,
                    "order": order,
                    "metrics": metrics,
                    "score": score,
                }
                if best is None or score < best["score"]:
                    best = cand
                    if len(improvement_trace) < 200:
                        improvement_trace.append(
                            {
                                "elapsed_ms": int((time.time() - t_begin) * 1000),
                                "tag": f"start:{k}|{dm}:{dr}",
                                "strategy": used_strat.value,
                                "dispatch_mode": dm,
                                "dispatch_rule": dr,
                                "score": list(score),
                                "metrics": metrics.to_dict(),
                            }
                        )
    return best

