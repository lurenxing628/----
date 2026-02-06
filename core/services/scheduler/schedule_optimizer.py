from __future__ import annotations

import random
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import BatchForSort, GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.sort_strategies import parse_strategy
from core.algorithms.evaluation import compute_metrics, objective_score


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


def optimize_schedule(
    *,
    calendar_service: Any,
    cfg_svc: Any,
    cfg: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_results: List[Dict[str, Any]],
    resource_pool: Optional[Dict[str, Any]],
    version: int,
    logger: Any = None,
) -> OptimizationOutcome:
    """
    执行算法（支持 improve：多起点 + 目标函数 + 时间预算；可选 OR-Tools 起点）。

    说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。
    """
    # 算法层只读取“纯配置快照”，不依赖 ConfigService 形态（仍兼容旧形态）
    cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(cfg, dict) else None)
    scheduler = GreedyScheduler(calendar_service=calendar_service, config_service=cfg_snapshot, logger=logger)

    strategy_enum: SortStrategy = parse_strategy(getattr(cfg, "sort_strategy", None), default=SortStrategy.PRIORITY_FIRST)

    strategy_params: Optional[Dict[str, Any]] = None
    if strategy_enum == SortStrategy.WEIGHTED:
        strategy_params = {
            "priority_weight": float(cfg.priority_weight),
            "due_weight": float(cfg.due_weight),
        }

    algo_mode = (getattr(cfg, "algo_mode", "greedy") or "greedy").strip()
    objective_name = (getattr(cfg, "objective", "min_overdue") or "min_overdue").strip()
    time_budget_seconds = int(getattr(cfg, "time_budget_seconds", 20) or 20)
    time_budget_seconds = max(1, int(time_budget_seconds))

    def _parse_date(value: Any) -> Optional[Any]:
        if value is None:
            return None
        if hasattr(value, "date"):
            try:
                return value.date()
            except Exception:
                pass
        s = str(value).strip().replace("/", "-")
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("/", "-").replace("T", " ").replace("：", ":")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    batch_for_sort: List[BatchForSort] = []
    for b in batches.values():
        batch_for_sort.append(
            BatchForSort(
                batch_id=str(getattr(b, "batch_id", "") or ""),
                priority=str(getattr(b, "priority", "") or "normal"),
                due_date=_parse_date(getattr(b, "due_date", None)),
                ready_status=str(getattr(b, "ready_status", "") or "yes"),
                ready_date=_parse_date(getattr(b, "ready_date", None)),
                created_at=_parse_datetime(getattr(b, "created_at", None)),
            )
        )

    def _build_order(strategy0: SortStrategy, params: Dict[str, Any]) -> List[str]:
        sorter0 = StrategyFactory.create(strategy0, **(params or {}))
        return [x.batch_id for x in sorter0.sort(batch_for_sort)]

    # multi-start：策略集（先用当前策略，再补全其它策略）
    current_key = str(strategy_enum.value)
    if algo_mode == "improve":
        keys = [current_key] + [k for k in cfg_svc.VALID_STRATEGIES if k != current_key]  # type: ignore[attr-defined]
    else:
        keys = [current_key]

    best = None
    attempts: List[Dict[str, Any]] = []
    improvement_trace: List[Dict[str, Any]] = []

    t_begin = time.time()
    deadline = t_begin + (time_budget_seconds if algo_mode == "improve" else 10_000_000)

    # GreedyScheduler 需要 seed_results 为 ScheduleResult：这里转换一次
    seed_sr_list: List[ScheduleResult] = []
    if seed_results:
        for x in seed_results:
            try:
                seed_sr_list.append(
                    ScheduleResult(
                        op_id=int(x.get("op_id") or 0),
                        op_code=str(x.get("op_code") or ""),
                        batch_id=str(x.get("batch_id") or ""),
                        seq=int(x.get("seq") or 0),
                        machine_id=(str(x.get("machine_id") or "") or None),
                        operator_id=(str(x.get("operator_id") or "") or None),
                        start_time=x.get("start_time"),
                        end_time=x.get("end_time"),
                        source=str(x.get("source") or "internal"),
                        op_type_name=(str(x.get("op_type_name") or "") or None),
                    )
                )
            except Exception:
                continue

    # improve：规则随机化（派工规则）+ 多起点
    dispatch_mode_cfg = (getattr(cfg, "dispatch_mode", None) or "batch_order").strip() or "batch_order"
    dispatch_rule_cfg = (getattr(cfg, "dispatch_rule", None) or "slack").strip() or "slack"
    if algo_mode == "improve" and dispatch_mode_cfg == "sgs":
        dispatch_rules = [dispatch_rule_cfg] + [x for x in cfg_svc.VALID_DISPATCH_RULES if x != dispatch_rule_cfg]  # type: ignore[attr-defined]
    else:
        dispatch_rules = [dispatch_rule_cfg]

    # 可选：OR-Tools 高质量起点（瓶颈子问题）
    if algo_mode == "improve" and getattr(cfg, "ortools_enabled", "no") == "yes":
        try:
            from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

            remaining = float(deadline - time.time())
            # 时间预算不足时跳过 OR-Tools warm-start：
            # - remaining<=0：避免已经超时仍强行跑 1s
            # - remaining<1：避免 int(remaining)=0 被 tl=max(1,...) 拉回 1s 导致超时
            ort_order = None
            if remaining >= 1.0:
                tl_cfg = int(getattr(cfg, "ortools_time_limit_seconds", 5) or 5)
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
                        "priority_weight": float(cfg.priority_weight),
                        "due_weight": float(cfg.due_weight),
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
                try:
                    # 尽量带堆栈（便于定位依赖缺失/配置错误等）；若 logger 不支持 exc_info 参数则回退为拼接文本。
                    try:
                        logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}", exc_info=True)
                    except TypeError:
                        logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}\n{tb}")
                except Exception:
                    pass

    # 执行策略轮询（multi-start）
    for k in keys:
        if time.time() > deadline:
            break
        strat = parse_strategy(k, default=SortStrategy.PRIORITY_FIRST)
        params0: Dict[str, Any] = {}
        if strat == SortStrategy.WEIGHTED:
            params0 = {
                "priority_weight": float(cfg.priority_weight),
                "due_weight": float(cfg.due_weight),
            }

        for dr in dispatch_rules:
            if time.time() > deadline:
                break
            order = _build_order(strat, params0)
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
                dispatch_mode=dispatch_mode_cfg,
                dispatch_rule=dr,
                resource_pool=resource_pool,
            )
            metrics = compute_metrics(res, batches)
            score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
            attempts.append(
                {
                    "tag": f"start:{k}|{dispatch_mode_cfg}:{dr}",
                    "strategy": used_strat.value,
                    "dispatch_mode": dispatch_mode_cfg,
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
                "dispatch_mode": dispatch_mode_cfg,
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
                            "tag": f"start:{k}|{dispatch_mode_cfg}:{dr}",
                            "strategy": used_strat.value,
                            "dispatch_mode": dispatch_mode_cfg,
                            "dispatch_rule": dr,
                            "score": list(score),
                            "metrics": metrics.to_dict(),
                        }
                    )

    # 局部搜索（可选）：在 best batch_order 上做随机 swap/insert
    if algo_mode == "improve" and best is not None and len(best.get("order") or []) >= 2:
        rnd = random.Random(int(version))
        cur_order = list(best["order"])
        cur_strat = best["strategy"]
        cur_params = dict(best["params"] or {})
        cur_dispatch_mode = str(best.get("dispatch_mode") or dispatch_mode_cfg)
        cur_dispatch_rule = str(best.get("dispatch_rule") or dispatch_rule_cfg)
        it = 0
        it_limit = max(200, min(5000, int(time_budget_seconds) * 20))
        no_improve = 0
        restart_after = max(50, min(800, int(it_limit / 8) if it_limit > 0 else 200))
        while time.time() <= deadline and it < it_limit:
            it += 1
            cand_order = list(cur_order)
            n = len(cand_order)
            r0 = rnd.random()
            if r0 < 0.55:
                move = "swap"
            elif r0 < 0.85:
                move = "insert"
            else:
                move = "block"
            if move == "swap":
                i, j = rnd.sample(range(n), 2)
                cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
            elif move == "insert":
                i = rnd.randrange(n)
                j = rnd.randrange(n)
                x = cand_order.pop(i)
                cand_order.insert(j, x)
            else:
                # block move：抽取一段连续区间移动到另一位置
                if n >= 4:
                    i = rnd.randrange(n - 1)
                    max_len = min(6, n - i)
                    ln = rnd.randrange(2, max_len + 1)
                    block = cand_order[i : i + ln]
                    del cand_order[i : i + ln]
                    j = rnd.randrange(len(cand_order) + 1)
                    for t in reversed(block):
                        cand_order.insert(j, t)
                else:
                    # n<4 时 block move 会退化为空操作；改用 swap，避免浪费一次迭代
                    i, j = rnd.sample(range(n), 2)
                    cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                    move = "swap_fallback"

            # 兜底：避免空迭代（例如 insert 选到 i==j，或 block 回插原位）
            if cand_order == cur_order and n >= 2:
                i, j = rnd.sample(range(n), 2)
                cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                move = "swap_fallback"

            res, summ, used_strat, used_params = scheduler.schedule(
                operations=algo_ops_to_schedule,
                batches=batches,
                strategy=cur_strat,
                strategy_params=cur_params,
                start_dt=start_dt,
                end_date=end_date,
                machine_downtimes=downtime_map,
                batch_order_override=cand_order,
                seed_results=seed_sr_list,
                dispatch_mode=cur_dispatch_mode,
                dispatch_rule=cur_dispatch_rule,
                resource_pool=resource_pool,
            )
            metrics = compute_metrics(res, batches)
            score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
            if score < best["score"]:
                best = {
                    "results": res,
                    "summary": summ,
                    "strategy": used_strat,
                    "params": used_params,
                    "dispatch_mode": cur_dispatch_mode,
                    "dispatch_rule": cur_dispatch_rule,
                    "order": cand_order,
                    "metrics": metrics,
                    "score": score,
                }
                cur_order = list(cand_order)
                no_improve = 0
                if len(improvement_trace) < 200:
                    improvement_trace.append(
                        {
                            "elapsed_ms": int((time.time() - t_begin) * 1000),
                            "tag": f"local:{move}",
                            "strategy": used_strat.value,
                            "dispatch_mode": cur_dispatch_mode,
                            "dispatch_rule": cur_dispatch_rule,
                            "score": list(score),
                            "metrics": metrics.to_dict(),
                        }
                    )
                # 记录少量轨迹，避免 result_summary 过大
                if len(attempts) < 12:
                    attempts.append(
                        {
                            "tag": f"local:{move}",
                            "strategy": used_strat.value,
                            "dispatch_mode": cur_dispatch_mode,
                            "dispatch_rule": cur_dispatch_rule,
                            "score": list(score),
                            "failed_ops": int(summ.failed_ops),
                            "metrics": metrics.to_dict(),
                        }
                    )
            else:
                no_improve += 1

            # 多次重启（轻量 ILS）：长时间无改进则从 best 出发做随机 shake
            if no_improve >= restart_after and best is not None:
                no_improve = 0
                cur_order = list(best.get("order") or cur_order)
                # small shake：有限次 swap/insert
                shake = rnd.randint(3, 8)
                for _ in range(shake):
                    if len(cur_order) < 2:
                        break
                    if rnd.random() < 0.6:
                        i, j = rnd.sample(range(len(cur_order)), 2)
                        cur_order[i], cur_order[j] = cur_order[j], cur_order[i]
                    else:
                        i = rnd.randrange(len(cur_order))
                        j = rnd.randrange(len(cur_order))
                        x = cur_order.pop(i)
                        cur_order.insert(j, x)

    if best is None:
        # 理论上不会发生；兜底为原始单次
        results, summary, used_strategy, used_params = scheduler.schedule(
            operations=algo_ops_to_schedule,
            batches=batches,
            strategy=strategy_enum,
            strategy_params=strategy_params,
            start_dt=start_dt,
            end_date=end_date,
            machine_downtimes=downtime_map,
            seed_results=seed_sr_list,
            resource_pool=resource_pool,
        )
        best_metrics = compute_metrics(results, batches)
        best_score = (float(summary.failed_ops),) + objective_score(objective_name, best_metrics)
        best_order = _build_order(strategy_enum or SortStrategy.PRIORITY_FIRST, used_params or {})
        return OptimizationOutcome(
            results=results,
            summary=summary,
            used_strategy=used_strategy,
            used_params=used_params,
            metrics=best_metrics,
            best_score=best_score,
            best_order=best_order,
            attempts=attempts[:12],
            improvement_trace=improvement_trace[:200],
            algo_mode=algo_mode,
            objective_name=objective_name,
            time_budget_seconds=time_budget_seconds,
        )

    results = best["results"]
    summary = best["summary"]
    used_strategy = best["strategy"]
    used_params = best["params"]
    best_metrics = best["metrics"]
    best_score = best["score"]
    best_order = best["order"]

    return OptimizationOutcome(
        results=results,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        metrics=best_metrics,
        best_score=best_score,
        best_order=list(best_order or []),
        attempts=(attempts or [])[:12],
        improvement_trace=(improvement_trace or [])[:200],
        algo_mode=algo_mode,
        objective_name=objective_name,
        time_budget_seconds=time_budget_seconds,
    )

