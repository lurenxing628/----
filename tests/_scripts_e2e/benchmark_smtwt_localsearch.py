#!/usr/bin/env python3
"""SMTWT 250 实例:局搜(run_local_search)在 sgs vs batch_order 派工下的真实改进对比。

证明:sgs 派工下局搜应使用 SGS 专属旋钮,batch_order 派工下局搜应使用批次顺序旋钮。
基线与局搜均用真实 GreedyScheduler + 真实 schedule_fn;对比 Moore-Hodgson 精确最优 overdue。
只读实测:不写 tracked evidence,只打印到 stdout。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("repo root not found")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.algorithms import GreedyScheduler, SortStrategy  # noqa: E402
from core.algorithms.evaluation import compute_metrics, objective_score  # noqa: E402
from core.services.scheduler.run.optimizer_proof_oracle import (  # noqa: E402
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
)
from core.services.scheduler.run.schedule_optimizer import _run_local_search  # noqa: E402
from tests._support.benchmark_parallel import (  # noqa: E402
    DEFAULT_BENCHMARK_WORKERS,
    parallel_map_ordered,
    positive_worker_count,
)
from tests._support.optimizer_benchmark_grading import smtwt_overdue_case  # noqa: E402
from tests._support.optimizer_benchmark_loaders import (  # noqa: E402
    SmtwtInstance,
    load_smtwt_instances,
    moore_hodgson_min_tardy,
)

TIME_BUDGET = 1


def _baseline(case, mode):
    sch = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    res, summ, strat, params = sch.schedule(
        operations=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case), strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt, dispatch_mode=mode, dispatch_rule=case.dispatch_rule,
        seed_results=[], strict_mode=True,
    )
    m = compute_metrics(res, batch_objects(case))
    score = (float(summ.failed_ops),) + tuple(float(v) for v in objective_score("min_overdue", m))
    return res, summ, strat, params, m, score


def _local_search_overdue(case, mode, base):
    res, summ, strat, params, m, score = base
    order = [b.batch_id for b in case.batches]
    best = {
        "results": res, "summary": summ, "strategy": strat, "params": dict(params or {}),
        "dispatch_mode": mode, "dispatch_rule": "slack", "order": order,
        "metrics": m, "score": score, "algo_stats": {}, "resource_pool": {},
        "seed_result_count": 0, "locked_seed_range": [],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(order)},
    }
    sch = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    t0 = time.time()
    out = _run_local_search(
        algo_mode="improve", best=best, version=1,
        time_budget_seconds=TIME_BUDGET, deadline=t0 + TIME_BUDGET,
        scheduler=sch,
        algo_ops_to_schedule=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case), start_dt=case.start_dt, end_date=None, downtime_map={},
        seed_sr_list=[], dispatch_mode_cfg=mode, dispatch_rule_cfg="slack",
        resource_pool=None, objective_name="min_overdue",
        attempts=[], improvement_trace=[], optimizer_algo_stats={},
        t_begin=t0, readiness_gate_enabled=False, strict_mode=True,
    )
    return int(out["metrics"].overdue_count)


def _run_instance_task(task: Tuple[SmtwtInstance, str]) -> Dict[str, Any]:
    inst, mode = task
    case = smtwt_overdue_case(inst)
    opt = moore_hodgson_min_tardy(inst.processing_times, inst.due_dates)
    try:
        base = _baseline(case, mode)
        base_ov = int(base[4].overdue_count)
        ls_ov = _local_search_overdue(case, mode, base)
    except Exception as exc:  # 明确记录失败实例,不静默吞
        return {"ok": False, "name": inst.name, "error": str(exc)[:70]}
    return {
        "ok": True,
        "improved": ls_ov < base_ov,
        "base_gap": base_ov - opt,
        "ls_gap": ls_ov - opt,
    }


def _run(size, mode, workers: int):
    insts = load_smtwt_instances(size)
    improved = 0
    base_gap_sum = 0
    ls_gap_sum = 0
    failed: List[Tuple[str, str]] = []
    outcomes = parallel_map_ordered(_run_instance_task, [(inst, mode) for inst in insts], workers=workers)
    for outcome in outcomes:
        if not outcome.get("ok"):
            failed.append((str(outcome.get("name")), str(outcome.get("error"))))
            continue
        if bool(outcome.get("improved")):
            improved += 1
        base_gap_sum += int(outcome.get("base_gap") or 0)
        ls_gap_sum += int(outcome.get("ls_gap") or 0)
    n = len(insts) - len(failed)
    return n, improved, base_gap_sum, ls_gap_sum, failed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SMTWT local-search benchmark.")
    parser.add_argument("--workers", type=int, default=DEFAULT_BENCHMARK_WORKERS, help="parallel worker processes")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    workers = positive_worker_count(args.workers)
    had_failed_samples = False
    for mode in ("sgs", "batch_order"):
        print("=" * 64)
        print(f"局搜派工模式: {mode}  (TIME_BUDGET={TIME_BUDGET}s, workers={workers}, 对比 Moore-Hodgson 精确最优)")
        tot_n = tot_imp = tot_bg = tot_lg = 0
        for size in (40, 50):
            t0 = time.time()
            n, imp, bg, lg, failed = _run(size, mode, workers)
            if n <= 0:
                raise RuntimeError(f"wt{size} {mode}: all benchmark instances failed")
            print(
                f"  wt{size}: {n} 实例 | 局搜改进 {imp} 个 | baseline 平均 gap {bg / n:.2f} -> "
                f"局搜后 {lg / n:.2f} (缩小 {(bg - lg) / n:.2f}) | {time.time() - t0:.0f}s"
            )
            if failed:
                had_failed_samples = True
                print(f"    失败 {len(failed)} 个:", failed[:3])
            tot_n += n
            tot_imp += imp
            tot_bg += bg
            tot_lg += lg
        if tot_n <= 0:
            raise RuntimeError(f"{mode}: all benchmark instances failed")
        print(
            f"  合计 {tot_n} 实例: 局搜改进 {tot_imp} 个 ({100.0 * tot_imp / tot_n:.1f}%) | "
            f"gap {tot_bg / tot_n:.2f} -> {tot_lg / tot_n:.2f} (平均缩小 {(tot_bg - tot_lg) / tot_n:.2f})"
        )
    return 1 if had_failed_samples else 0


if __name__ == "__main__":
    raise SystemExit(main())
