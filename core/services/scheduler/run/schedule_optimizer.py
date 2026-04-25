from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import increment_counter, merge_algo_stats, snapshot_algo_stats
from core.algorithms.greedy.scheduler import build_batch_sort_inputs, build_normalized_batches_map
from core.algorithms.value_domains import INTERNAL
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import choices_for
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.shared.strict_parse import parse_required_float, parse_required_int

from .schedule_optimizer_steps import (
    _run_multi_start,
    _run_ortools_warmstart,
    _schedule_with_optional_strict_mode,
)

_FIELD_LABELS = {
    "sort_strategy": "排序策略",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "派工规则",
    "objective": "优化目标",
    "algo_mode": "计算模式",
    "seed_results": "种子排产结果",
}


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(str(field).strip(), str(field).strip() or "配置项")


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


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return (float("inf"),)
    out: List[float] = []
    for x in score:
        try:
            out.append(float(x))
        except Exception:
            out.append(float("inf"))
    return tuple(out)


def _attempt_dispatch_mode(item: Dict[str, Any]) -> str:
    return str(item.get("dispatch_mode") or "")


def _attempt_tag(item: Dict[str, Any]) -> str:
    return str(item.get("tag") or "")


def _sorted_attempts_by_score(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(list(attempts or []), key=lambda item: _score_tuple(item.get("score")))


def _best_attempts_by_dispatch_mode(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_mode: Dict[str, Dict[str, Any]] = {}
    for item in attempts or []:
        mode = _attempt_dispatch_mode(item)
        current = best_by_mode.get(mode)
        if current is None or _score_tuple(item.get("score")) < _score_tuple(current.get("score")):
            best_by_mode[mode] = item
    return list(best_by_mode.values())


def _append_unique_best_attempts(
    selected: List[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    selected_tags = {_attempt_tag(item) for item in selected}
    for item in _sorted_attempts_by_score(attempts):
        tag = _attempt_tag(item)
        if tag in selected_tags:
            continue
        selected.append(item)
        selected_tags.add(tag)
        if len(selected) >= limit:
            break
    return selected


def _compact_attempts(attempts: List[Dict[str, Any]], *, limit: int = 12) -> List[Dict[str, Any]]:
    if len(attempts or []) <= limit:
        return list(attempts or [])
    selected = _best_attempts_by_dispatch_mode(attempts)
    selected = _append_unique_best_attempts(selected, attempts, limit=limit)
    selected.sort(key=lambda x: _score_tuple(x.get("score")))
    return selected[:limit]


def _require_choice(value: Any, *, field: str, valid_values: Tuple[str, ...]) -> str:
    label = _field_label(field)
    text = str(value or "").strip().lower()
    if text not in set(valid_values):
        raise ValidationError(f"“{label}”配置无效，请返回排产参数页重新选择。", field=field)
    return text


def _require_float(value: Any, *, field: str, min_value: float) -> float:
    return float(parse_required_float(value, field=field, min_value=min_value))


def _require_int(value: Any, *, field: str, min_value: int) -> int:
    return int(parse_required_int(value, field=field, min_value=min_value))


def _normalized_choice_values(values: Any) -> Tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _effective_choice_values(field: str, *, cfg_svc: Any, allowlist_attr: Optional[str] = None) -> Tuple[str, ...]:
    registry_values = tuple(str(item).strip().lower() for item in choices_for(field))
    if not allowlist_attr:
        return registry_values
    narrowed = _normalized_choice_values(getattr(cfg_svc, allowlist_attr, ()))
    if not narrowed:
        return registry_values
    narrowed_set = set(narrowed)
    return tuple(item for item in registry_values if item in narrowed_set)


def _record_optimizer_cfg_degradations(
    snapshot: Any,
    optimizer_algo_stats: Dict[str, Any],
    *,
    mapping: Dict[str, str],
) -> None:
    degradation_events = getattr(snapshot, "degradation_events", ()) or ()
    degraded_fields = {
        str((event or {}).get("field") or "").strip()
        for event in degradation_events
        if isinstance(event, dict)
    }
    for config_field, counter_key in mapping.items():
        if config_field in degraded_fields:
            increment_counter(optimizer_algo_stats, counter_key, bucket="param_fallbacks")


def _init_seen_hashes(cur_order: List[str], best: Optional[Dict[str, Any]]) -> Optional[set]:
    if len(cur_order) < 10:
        return None
    seen_hashes = {tuple(cur_order)}
    if isinstance(best, dict):
        best_order = tuple(best.get("order") or [])
        if best_order:
            seen_hashes.add(best_order)
    return seen_hashes


def _raise_invalid_seed_results_error(*, invalid_seed_count: int, invalid_seed_samples: List[Dict[str, Any]]) -> None:
    exc = ValidationError("种子排产结果中包含无效记录。", field="seed_results")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = "invalid_seed_results"
    exc.details["invalid_seed_count"] = int(invalid_seed_count)
    exc.details["invalid_seed_samples"] = list(invalid_seed_samples)
    raise exc


def _seed_result_sample(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__, "repr": repr(item)[:200]}
    return {
        "op_id": item.get("op_id"),
        "op_code": item.get("op_code"),
        "batch_id": item.get("batch_id"),
        "seq": item.get("seq"),
        "machine_id": item.get("machine_id"),
        "operator_id": item.get("operator_id"),
    }


def _coerce_seed_result_item(item: Any, *, idx: int) -> ScheduleResult:
    if not isinstance(item, dict):
        raise TypeError(f"第 {idx + 1} 条种子排产结果不是字典（实际类型：{type(item).__name__}）。")
    start_time, end_time = _coerce_seed_time_range(item, idx=idx)
    return ScheduleResult(
        op_id=int(item.get("op_id") or 0),
        op_code=str(item.get("op_code") or ""),
        batch_id=str(item.get("batch_id") or ""),
        seq=int(item.get("seq") or 0),
        machine_id=(str(item.get("machine_id") or "") or None),
        operator_id=(str(item.get("operator_id") or "") or None),
        start_time=start_time,
        end_time=end_time,
        source=str(item.get("source") or INTERNAL),
        op_type_name=(str(item.get("op_type_name") or "") or None),
    )


def _coerce_seed_time_range(item: Dict[str, Any], *, idx: int) -> Tuple[Any, Any]:
    start_time = item.get("start_time")
    end_time = item.get("end_time")
    if start_time is None or end_time is None:
        raise TypeError(f"第 {idx + 1} 条种子排产结果缺少开始时间或结束时间。")
    try:
        valid_time_range = start_time < end_time
    except Exception as exc:
        raise TypeError(f"第 {idx + 1} 条种子排产结果的时间区间无效：{exc}") from exc
    if not valid_time_range:
        raise TypeError(f"第 {idx + 1} 条种子排产结果的开始时间必须早于结束时间。")
    return start_time, end_time


def _coerce_seed_results(
    seed_results: List[Dict[str, Any]],
    *,
    optimizer_algo_stats: Dict[str, Any],
) -> List[ScheduleResult]:
    seed_sr_list: List[ScheduleResult] = []
    invalid_seed_samples: List[Dict[str, Any]] = []
    invalid_seed_count = 0
    for idx, item in enumerate(seed_results or []):
        try:
            seed_sr_list.append(_coerce_seed_result_item(item, idx=idx))
        except Exception as exc:
            invalid_seed_count += 1
            if len(invalid_seed_samples) < 5:
                invalid_seed_samples.append({"index": int(idx), "error": str(exc), "sample": _seed_result_sample(item)})

    increment_counter(optimizer_algo_stats, "optimizer_seed_result_invalid_count", invalid_seed_count)
    if invalid_seed_count > 0:
        optimizer_algo_stats.setdefault("fallback_samples", {})
        optimizer_algo_stats["fallback_samples"]["optimizer_seed_result_invalid_samples"] = list(invalid_seed_samples)
        _raise_invalid_seed_results_error(
            invalid_seed_count=invalid_seed_count,
            invalid_seed_samples=invalid_seed_samples,
        )
    return seed_sr_list


def _run_local_search(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    time_budget_seconds: int,
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
    objective_name: str,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    strict_mode: bool = False,
) -> Optional[Dict[str, Any]]:
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
        seen_hashes = _init_seen_hashes(cur_order, best)
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
                if n >= 4:
                    i = rnd.randrange(n - 1)
                    max_len = min(6, n - i)
                    ln = rnd.randrange(2, max_len + 1)
                    block = cand_order[i : i + ln]
                    del cand_order[i : i + ln]
                    j = rnd.randrange(len(cand_order) + 1)
                    for item in reversed(block):
                        cand_order.insert(j, item)
                else:
                    i, j = rnd.sample(range(n), 2)
                    cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                    move = "swap_fallback"

            if cand_order == cur_order and n >= 2:
                i, j = rnd.sample(range(n), 2)
                cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                move = "swap_fallback"

            if seen_hashes is not None:
                cand_hash = tuple(cand_order)
                if cand_hash in seen_hashes:
                    no_improve += 1
                    continue
                seen_hashes.add(cand_hash)

            res, summ, used_strat, used_params = _schedule_with_optional_strict_mode(
                scheduler,
                strict_mode=bool(strict_mode),
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
            algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
            score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
            if score < best["score"]:
                best = {
                    "algo_stats": algo_stats,
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
                if len(attempts) < 12:
                    attempts.append(
                        {
                            "tag": f"local:{move}",
                            "strategy": used_strat.value,
                            "dispatch_mode": cur_dispatch_mode,
                            "dispatch_rule": cur_dispatch_rule,
                            "used_params": dict(used_params or {}),
                            "score": list(score),
                            "failed_ops": int(summ.failed_ops),
                            "algo_stats": algo_stats,
                            "metrics": metrics.to_dict(),
                        }
                    )
            else:
                no_improve += 1

            if no_improve >= restart_after and best is not None:
                no_improve = 0
                cur_order = list(best.get("order") or cur_order)
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
                seen_hashes = _init_seen_hashes(cur_order, best)
    return best


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
    strict_mode: bool = False,
) -> OptimizationOutcome:
    """
    执行算法（支持 improve：多起点 + 目标函数 + 时间预算；可选 OR-Tools 起点）。

    说明：为保证兼容，本函数尽量保持与原 `ScheduleService.run_schedule()` 相同的口径与留痕结构。
    """
    optimizer_algo_stats: Dict[str, Any] = {"fallback_counts": {}, "param_fallbacks": {}}
    cfg = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=bool(strict_mode),
        source="scheduler.optimize_schedule",
    )
    seed_sr_list = _coerce_seed_results(seed_results, optimizer_algo_stats=optimizer_algo_stats)
    scheduler = GreedyScheduler(calendar_service=calendar_service, config_service=cfg, logger=logger)
    valid_strategies = _effective_choice_values("sort_strategy", cfg_svc=cfg_svc, allowlist_attr="VALID_STRATEGIES")
    valid_dispatch_modes = _effective_choice_values("dispatch_mode", cfg_svc=cfg_svc, allowlist_attr="VALID_DISPATCH_MODES")
    valid_dispatch_rules = _effective_choice_values("dispatch_rule", cfg_svc=cfg_svc, allowlist_attr="VALID_DISPATCH_RULES")
    valid_objectives = _effective_choice_values("objective", cfg_svc=cfg_svc, allowlist_attr="VALID_OBJECTIVES")
    valid_algo_modes = _effective_choice_values("algo_mode", cfg_svc=cfg_svc, allowlist_attr="VALID_ALGO_MODES")

    strategy_enum = SortStrategy(_require_choice(cfg.sort_strategy, field="sort_strategy", valid_values=valid_strategies))
    if strategy_enum == SortStrategy.WEIGHTED:
        _record_optimizer_cfg_degradations(
            cfg,
            optimizer_algo_stats,
            mapping={
                "priority_weight": "optimizer_priority_weight_defaulted_count",
                "due_weight": "optimizer_due_weight_defaulted_count",
            },
        )

    strategy_params: Optional[Dict[str, Any]] = None
    if strategy_enum == SortStrategy.WEIGHTED:
        strategy_params = {
            "priority_weight": _require_float(cfg.priority_weight, field="priority_weight", min_value=0.0),
            "due_weight": _require_float(cfg.due_weight, field="due_weight", min_value=0.0),
        }

    algo_mode = _require_choice(cfg.algo_mode, field="algo_mode", valid_values=valid_algo_modes)
    objective_name = _require_choice(cfg.objective, field="objective", valid_values=valid_objectives)
    time_budget_seconds = _require_int(cfg.time_budget_seconds, field="time_budget_seconds", min_value=1)

    normalized_batches_for_sort = build_normalized_batches_map(batches)

    def _build_order(strategy0: SortStrategy, params: Dict[str, Any]) -> List[str]:
        batch_for_sort = build_batch_sort_inputs(
            normalized_batches_for_sort,
            strict_mode=bool(strict_mode),
            strategy=strategy0,
        )
        sorter0 = StrategyFactory.create(strategy0, **(params or {}))
        return [item.batch_id for item in sorter0.sort(batch_for_sort, base_date=start_dt.date())]

    current_key = str(strategy_enum.value)
    if algo_mode == "improve":
        keys = [current_key] + [item for item in valid_strategies if item != current_key]
    else:
        keys = [current_key]

    best = None
    attempts: List[Dict[str, Any]] = []
    improvement_trace: List[Dict[str, Any]] = []

    t_begin = time.time()
    deadline = (t_begin + float(time_budget_seconds)) if algo_mode == "improve" else float("inf")

    dispatch_mode_cfg = _require_choice(cfg.dispatch_mode, field="dispatch_mode", valid_values=valid_dispatch_modes)
    dispatch_rule_cfg = _require_choice(cfg.dispatch_rule, field="dispatch_rule", valid_values=valid_dispatch_rules)
    if algo_mode == "improve":
        dispatch_modes = [dispatch_mode_cfg] + [item for item in valid_dispatch_modes if item != dispatch_mode_cfg]
    else:
        dispatch_modes = [dispatch_mode_cfg]

    best = _run_ortools_warmstart(
        algo_mode=algo_mode,
        cfg=cfg,
        strategy_enum=strategy_enum,
        objective_name=objective_name,
        deadline=deadline,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        dispatch_mode_cfg=dispatch_mode_cfg,
        dispatch_rule_cfg=dispatch_rule_cfg,
        resource_pool=resource_pool,
        attempts=attempts,
        improvement_trace=improvement_trace,
        best=best,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        logger=logger,
        strict_mode=bool(strict_mode),
    )

    best = _run_multi_start(
        keys=keys,
        dispatch_modes=dispatch_modes,
        dispatch_rule_cfg=dispatch_rule_cfg,
        valid_dispatch_rules=list(valid_dispatch_rules),
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        cfg=cfg,
        resource_pool=resource_pool,
        objective_name=objective_name,
        deadline=deadline,
        attempts=attempts,
        improvement_trace=improvement_trace,
        best=best,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        build_order=_build_order,
        strict_mode=bool(strict_mode),
    )

    best = _run_local_search(
        algo_mode=algo_mode,
        best=best,
        version=version,
        time_budget_seconds=time_budget_seconds,
        deadline=deadline,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        end_date=end_date,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        dispatch_mode_cfg=dispatch_mode_cfg,
        dispatch_rule_cfg=dispatch_rule_cfg,
        resource_pool=resource_pool,
        objective_name=objective_name,
        attempts=attempts,
        improvement_trace=improvement_trace,
        optimizer_algo_stats=optimizer_algo_stats,
        t_begin=t_begin,
        strict_mode=bool(strict_mode),
    )

    if best is None:
        results, summary, used_strategy, used_params = _schedule_with_optional_strict_mode(
            scheduler,
            strict_mode=bool(strict_mode),
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
        algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
        return OptimizationOutcome(
            results=results,
            summary=summary,
            used_strategy=used_strategy,
            used_params=used_params,
            metrics=best_metrics,
            best_score=best_score,
            best_order=best_order,
            attempts=_compact_attempts(attempts, limit=12),
            improvement_trace=improvement_trace[:200],
            algo_mode=algo_mode,
            objective_name=objective_name,
            time_budget_seconds=time_budget_seconds,
            algo_stats=algo_stats,
        )

    results = best["results"]
    summary = best["summary"]
    used_strategy = best["strategy"]
    used_params = best["params"]
    best_metrics = best["metrics"]
    best_score = best["score"]
    best_order = best["order"]
    best_algo_stats = best.get("algo_stats") if isinstance(best, dict) else None
    algo_stats = merge_algo_stats(best_algo_stats) if isinstance(best_algo_stats, dict) else merge_algo_stats(optimizer_algo_stats)

    return OptimizationOutcome(
        results=results,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        metrics=best_metrics,
        best_score=best_score,
        best_order=list(best_order or []),
        attempts=_compact_attempts(attempts, limit=12),
        improvement_trace=(improvement_trace or [])[:200],
        algo_mode=algo_mode,
        objective_name=objective_name,
        time_budget_seconds=time_budget_seconds,
        algo_stats=algo_stats,
    )
