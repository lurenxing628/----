#!/usr/bin/env python3
"""定量探针：批次顺序(batch_order)重排在 SGS vs batch_order 两种派工模式下，
对真实 GreedyScheduler 解码结果(min_overdue 目标)的影响。

用途：把 review 结论"业务邻域局搜的 batch_order 旋钮在 SGS 下几乎是死键"从定性变定量。
做法：对一个有交期压力的小实例，枚举所有批次顺序，分别在两模式下用真实 GreedyScheduler
解码，统计各模式下能产生多少种不同的 (failed_ops, *objective) 结果签名。
签名集大小==1 表示该模式下批次顺序完全改不动结果(局搜空转)。

只读实验：不改生产代码、不写 tracked evidence，只打印 JSON 到 stdout。
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("repo root not found")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.algorithms import GreedyScheduler  # noqa: E402
from core.algorithms.evaluation import compute_metrics, objective_score  # noqa: E402
from core.algorithms.objective_specs import objective_metric_keys  # noqa: E402
from core.algorithms.sort_strategies import SortStrategy  # noqa: E402
from core.services.scheduler.run.optimizer_proof_cases import (  # noqa: E402
    TinyBatchSpec,
    TinyBenchmarkCase,
    TinyOperationSpec,
)
from core.services.scheduler.run.optimizer_proof_oracle import (  # noqa: E402
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
    run_exact_oracle,
)

OBJECTIVE = "min_overdue"


def _decode(case: TinyBenchmarkCase, *, dispatch_mode: str, dispatch_rule: str, batch_order):
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, _strategy, _params = scheduler.schedule(
        operations=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case),
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        batch_order_override=list(batch_order),
        seed_results=[],
        strict_mode=True,
    )
    metrics = compute_metrics(results, batch_objects(case))
    return (float(summary.failed_ops),) + tuple(float(v) for v in objective_score(OBJECTIVE, metrics))


def _fact(n: int) -> int:
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out


def _probe_mode(case: TinyBenchmarkCase, mode: str, dispatch_rule: str, batch_ids) -> dict:
    sigs: dict = {}
    for perm in itertools.permutations(batch_ids):
        sigs.setdefault(_decode(case, dispatch_mode=mode, dispatch_rule=dispatch_rule, batch_order=perm), []).append(list(perm))
    distinct = sorted(sigs.keys())
    return {
        "permutations_tried": _fact(len(batch_ids)),
        "distinct_result_signatures": len(distinct),
        "best_signature": list(distinct[0]),
        "worst_signature": list(distinct[-1]),
        "actuator_effective": len(distinct) > 1,
    }


def _probe_case(case: TinyBenchmarkCase) -> dict:
    batch_ids = [b.batch_id for b in case.batches]
    modes = {
        # batch_order 派工与 dispatch_rule 无关，只探一次。
        "batch_order": _probe_mode(case, "batch_order", "slack", batch_ids),
    }
    # SGS 派工 × 三种派工规则，证明 no-op 与规则选择无关。
    for rule in ("slack", "cr", "atc"):
        modes[f"sgs/{rule}"] = _probe_mode(case, "sgs", rule, batch_ids)
    oracle = run_exact_oracle(case, objective_name=OBJECTIVE)
    oracle_overdue = float((oracle.best_score or [0.0, 0.0])[1]) if oracle.best_score else None
    sgs_locked_overdue = float(modes["sgs/slack"]["best_signature"][1])
    bo_best_overdue = float(modes["batch_order"]["best_signature"][1])
    sgs_dead = all(not modes[f"sgs/{rule}"]["actuator_effective"] for rule in ("slack", "cr", "atc"))
    verdict = (
        f"batch_order 旋钮{'有效' if modes['batch_order']['actuator_effective'] else '无效'}"
        f"(可达 overdue={bo_best_overdue:g}); "
        f"SGS 下批次顺序{'对全部规则均为死键(局搜空转)' if sgs_dead else '部分规则可动'}"
        f"，锁定 overdue={sgs_locked_overdue:g}; oracle 最优 overdue={oracle_overdue:g}。"
        + (
            " SGS 锁死的是次优解，局搜的 batch_order 旋钮解锁不了(有害空转)。"
            if oracle_overdue is not None and sgs_locked_overdue > oracle_overdue
            else " SGS 已达该实例最优，no-op 无害。"
        )
    )
    return {
        "case": case.slug,
        "objective": OBJECTIVE,
        "score_components": ["failed_ops"] + list(objective_metric_keys(OBJECTIVE)),
        "oracle_status": oracle.status,
        "oracle_best_score": list(oracle.best_score or []),
        "modes": modes,
        "verdict": verdict,
    }


def _build_cases():
    machine, operator = "machine-main", "operator-main"

    def op(op_id: int, bid: str) -> TinyOperationSpec:
        return TinyOperationSpec(
            op_id=op_id, op_code=f"S{op_id}", batch_id=bid, seq=1,
            machine_id=machine, operator_id=operator, duration_hours=24.0,
        )

    # 单机 + 单操作员 + 4 批次，每批 1 道 24h 工序；连续日历下第 k 个完工 = start + k 天。
    return (
        # case1(有害空转)：A/D 都要求当天第一个完工(due 01-02)互相挤占 -> 批次先后直接决定 overdue，
        # 但 SGS 锁死在次优解。
        TinyBenchmarkCase(
            slug="single-machine-due-pressure",
            objective_name=OBJECTIVE,
            batches=(
                TinyBatchSpec(batch_id="batch-a", due_date="2026-01-02"),
                TinyBatchSpec(batch_id="batch-b", due_date="2026-01-03"),
                TinyBatchSpec(batch_id="batch-c", due_date="2026-01-04"),
                TinyBatchSpec(batch_id="batch-d", due_date="2026-01-02"),
            ),
            operations=(op(1, "batch-a"), op(2, "batch-b"), op(3, "batch-c"), op(4, "batch-d")),
            dispatch_mode="sgs",
            dispatch_rule="slack",
        ),
        # case2(无害空转对照)：交期递增、互不挤占，SGS 按 slack 即达最优 overdue=0；
        # 批次顺序在 SGS 下同样是死键，但锁定值已是最优，no-op 无害。
        TinyBenchmarkCase(
            slug="single-machine-edd-feasible",
            objective_name=OBJECTIVE,
            batches=(
                TinyBatchSpec(batch_id="batch-p", due_date="2026-01-02"),
                TinyBatchSpec(batch_id="batch-q", due_date="2026-01-03"),
                TinyBatchSpec(batch_id="batch-r", due_date="2026-01-04"),
            ),
            operations=(op(1, "batch-p"), op(2, "batch-q"), op(3, "batch-r")),
            dispatch_mode="sgs",
            dispatch_rule="slack",
        ),
    )


def main() -> int:
    print(json.dumps([_probe_case(case) for case in _build_cases()], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
