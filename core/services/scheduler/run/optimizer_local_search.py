from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_search_state import init_seen_hashes


def _swap_neighbor(order: List[str], rnd: Any) -> Tuple[List[str], str]:
    cand_order = list(order)
    i, j = rnd.sample(range(len(cand_order)), 2)
    cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
    return cand_order, "swap"


def _insert_neighbor(order: List[str], rnd: Any) -> Tuple[List[str], str]:
    cand_order = list(order)
    i = rnd.randrange(len(cand_order))
    j = rnd.randrange(len(cand_order))
    item = cand_order.pop(i)
    cand_order.insert(j, item)
    return cand_order, "insert"


def _block_neighbor(order: List[str], rnd: Any) -> Tuple[List[str], str]:
    cand_order = list(order)
    n = len(cand_order)
    if n < 4:
        cand_order, _move = _swap_neighbor(cand_order, rnd)
        return cand_order, "swap_fallback"

    i = rnd.randrange(n - 1)
    max_len = min(6, n - i)
    ln = rnd.randrange(2, max_len + 1)
    block = cand_order[i : i + ln]
    del cand_order[i : i + ln]
    j = rnd.randrange(len(cand_order) + 1)
    for item in reversed(block):
        cand_order.insert(j, item)
    return cand_order, "block"


def _choose_neighbor(order: List[str], rnd: Any) -> Tuple[List[str], str]:
    r0 = rnd.random()
    if r0 < 0.55:
        cand_order, move = _swap_neighbor(order, rnd)
    elif r0 < 0.85:
        cand_order, move = _insert_neighbor(order, rnd)
    else:
        cand_order, move = _block_neighbor(order, rnd)

    if cand_order == order and len(order) >= 2:
        cand_order, _move = _swap_neighbor(order, rnd)
        move = "swap_fallback"
    return cand_order, move


def _evaluate_candidate(
    *,
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: Any,
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
    schedule_fn: Callable[..., Any],
) -> Dict[str, Any]:
    res, summ, used_strat, used_params = schedule_fn(
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
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "algo_stats": algo_stats,
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
        "metrics": metrics,
        "score": (float(summ.failed_ops),) + objective_score(objective_name, metrics),
    }


def _record_improvement(
    *,
    candidate: Dict[str, Any],
    move: str,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    clock: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    score = candidate["score"]
    used_strat = candidate["strategy"]
    used_params = candidate["params"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    if len(improvement_trace) < 200:
        improvement_trace.append(
            {
                "elapsed_ms": int((clock() - t_begin) * 1000),
                "tag": f"local:{move}",
                "strategy": used_strat.value,
                "dispatch_mode": dispatch_mode,
                "dispatch_rule": dispatch_rule,
                "score": list(score),
                "metrics": metrics.to_dict(),
            }
        )
    if len(attempts) < 12:
        attempts.append(
            {
                "tag": f"local:{move}",
                "strategy": used_strat.value,
                "dispatch_mode": dispatch_mode,
                "dispatch_rule": dispatch_rule,
                "used_params": dict(used_params or {}),
                "score": list(score),
                "failed_ops": int(candidate["summary"].failed_ops),
                "algo_stats": candidate["algo_stats"],
                "metrics": metrics.to_dict(),
            }
        )


def _shake_order(order: List[str], rnd: Any) -> List[str]:
    cur_order = list(order)
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
            item = cur_order.pop(i)
            cur_order.insert(j, item)
    return cur_order


def _should_skip_seen(cand_order: List[str], seen_hashes: Optional[set]) -> bool:
    if seen_hashes is None:
        return False
    cand_hash = tuple(cand_order)
    if cand_hash in seen_hashes:
        return True
    seen_hashes.add(cand_hash)
    return False


def run_local_search(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    time_budget_seconds: int,
    deadline: float,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    strict_mode: bool,
    clock: Callable[[], float],
    rng_factory: Callable[[int], Any],
    schedule_fn: Callable[..., Any],
) -> Optional[Dict[str, Any]]:
    if algo_mode != "improve" or best is None or len(best.get("order") or []) < 2:
        return best

    rnd = rng_factory(int(version))
    cur_order = list(best["order"])
    cur_strat = best["strategy"]
    cur_params = dict(best["params"] or {})
    cur_dispatch_mode = str(best.get("dispatch_mode") or dispatch_mode_cfg)
    cur_dispatch_rule = str(best.get("dispatch_rule") or dispatch_rule_cfg)
    it = 0
    it_limit = max(200, min(5000, int(time_budget_seconds) * 20))
    no_improve = 0
    restart_after = max(50, min(800, int(it_limit / 8) if it_limit > 0 else 200))
    seen_hashes = init_seen_hashes(cur_order, best)

    while clock() <= deadline and it < it_limit:
        it += 1
        cand_order, move = _choose_neighbor(cur_order, rnd)
        if _should_skip_seen(cand_order, seen_hashes):
            no_improve += 1
            continue

        candidate = _evaluate_candidate(
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=cur_strat,
            params=cur_params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=cand_order,
            seed_sr_list=seed_sr_list,
            dispatch_mode=cur_dispatch_mode,
            dispatch_rule=cur_dispatch_rule,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
        )
        if candidate["score"] < best["score"]:
            best = candidate
            cur_order = list(cand_order)
            no_improve = 0
            _record_improvement(
                candidate=candidate,
                move=move,
                attempts=attempts,
                improvement_trace=improvement_trace,
                clock=clock,
                t_begin=t_begin,
            )
        else:
            no_improve += 1

        if no_improve >= restart_after:
            no_improve = 0
            cur_order = _shake_order(list(best.get("order") or cur_order), rnd)
            seen_hashes = init_seen_hashes(cur_order, best)
    return best
