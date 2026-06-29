"""端到端定量证据：局搜/GRASP 的 batch_order 旋钮在 SGS 派工下是死键。

用真实 ``GreedyScheduler`` 解码(非 stub)枚举一个小实例的全部批次顺序，量化
"批次顺序重排能产生多少种不同结果"——这正是 item 6/7/8 业务邻域局搜唯一在动
的决策维度(5/6 邻域 + GRASP/IG 都改 batch_order)。

固化的现状(若将来真的修复了搜索空间，应更新本测试)：
- SGS 模式下，批次顺序对 slack/cr/atc 三种派工规则全部为死键(distinct==1)：
  batch_order 是 ``build_dispatch_key`` 的末位 tie-break，几乎从不影响 ``min()`` 选择，
  所以局搜在 SGS 下空烧迭代预算、0 改进。
- batch_order 派工模式下，批次顺序是有效旋钮(distinct>1)，可达 oracle 最优。
- no-op 分两种：SGS 已最优时无害；SGS 次优时有害(局搜本该补足却补不了)。

参见 review 记忆 scheduler-item678-actuator-misplacement-2026-06 /
scheduler-sgs-localsearch-noop-2026-06。
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Tuple

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.services.scheduler.run.optimizer_proof_cases import (
    TinyBatchSpec,
    TinyBenchmarkCase,
    TinyOperationSpec,
)
from core.services.scheduler.run.optimizer_proof_oracle import (
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
    run_exact_oracle,
)

OBJECTIVE = "min_overdue"
SGS_RULES = ("slack", "cr", "atc")


def _decode_signature(case: TinyBenchmarkCase, *, dispatch_mode: str, dispatch_rule: str, batch_order) -> Tuple[float, ...]:
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    _results, summary, _strategy, _params = scheduler.schedule(
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
    metrics = compute_metrics(_results, batch_objects(case))
    return (float(summary.failed_ops),) + tuple(float(v) for v in objective_score(OBJECTIVE, metrics))


def _distinct_signatures(case: TinyBenchmarkCase, *, dispatch_mode: str, dispatch_rule: str) -> List[Tuple[float, ...]]:
    batch_ids = [b.batch_id for b in case.batches]
    seen = {
        _decode_signature(case, dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule, batch_order=perm)
        for perm in itertools.permutations(batch_ids)
    }
    return sorted(seen)


def _op(op_id: int, batch_id: str) -> TinyOperationSpec:
    return TinyOperationSpec(
        op_id=op_id, op_code=f"S{op_id}", batch_id=batch_id, seq=1,
        machine_id="machine-main", operator_id="operator-main", duration_hours=24.0,
    )


def _harmful_case() -> TinyBenchmarkCase:
    # batch-a / batch-d 都要求当天第一个完工(due 01-02)互相挤占 -> 批次先后决定 overdue，
    # 但 SGS 锁死在次优解。
    return TinyBenchmarkCase(
        slug="single-machine-due-pressure",
        objective_name=OBJECTIVE,
        batches=(
            TinyBatchSpec(batch_id="batch-a", due_date="2026-01-02"),
            TinyBatchSpec(batch_id="batch-b", due_date="2026-01-03"),
            TinyBatchSpec(batch_id="batch-c", due_date="2026-01-04"),
            TinyBatchSpec(batch_id="batch-d", due_date="2026-01-02"),
        ),
        operations=(_op(1, "batch-a"), _op(2, "batch-b"), _op(3, "batch-c"), _op(4, "batch-d")),
        dispatch_mode="sgs",
        dispatch_rule="slack",
    )


def _harmless_case() -> TinyBenchmarkCase:
    # 交期递增、互不挤占，SGS 按 slack 即达最优 overdue=0。
    return TinyBenchmarkCase(
        slug="single-machine-edd-feasible",
        objective_name=OBJECTIVE,
        batches=(
            TinyBatchSpec(batch_id="batch-p", due_date="2026-01-02"),
            TinyBatchSpec(batch_id="batch-q", due_date="2026-01-03"),
            TinyBatchSpec(batch_id="batch-r", due_date="2026-01-04"),
        ),
        operations=(_op(1, "batch-p"), _op(2, "batch-q"), _op(3, "batch-r")),
        dispatch_mode="sgs",
        dispatch_rule="slack",
    )


def _overdue(signature) -> float:
    return float(signature[1])  # score = (failed_ops, overdue_count, ...)


def test_batch_order_is_active_actuator_in_batch_order_mode() -> None:
    """batch_order 派工模式下，批次顺序是有效旋钮(能产生多种结果，可达 oracle 最优)。"""
    for case in (_harmful_case(), _harmless_case()):
        signatures = _distinct_signatures(case, dispatch_mode="batch_order", dispatch_rule="slack")
        assert len(signatures) > 1, f"{case.slug}: batch_order 模式批次顺序应是有效旋钮"
        oracle = run_exact_oracle(case, objective_name=OBJECTIVE)
        assert oracle.best_score is not None
        # 最佳批次顺序能达到精确最优 overdue。
        assert _overdue(signatures[0]) == float(oracle.best_score[1])


def test_batch_order_is_dead_key_in_sgs_mode_for_all_rules() -> None:
    """SGS 派工下，批次顺序对 slack/cr/atc 三种规则全部为死键(distinct==1)——局搜空转。"""
    for case in (_harmful_case(), _harmless_case()):
        for rule in SGS_RULES:
            signatures = _distinct_signatures(case, dispatch_mode="sgs", dispatch_rule=rule)
            assert len(signatures) == 1, (
                f"{case.slug} sgs/{rule}: 期望批次顺序为死键(全排列同一结果)，"
                f"实得 {len(signatures)} 种——若搜索空间已修复请更新本测试"
            )


def test_sgs_dead_key_is_harmful_when_sgs_is_suboptimal() -> None:
    """有害空转实例：SGS 锁定值严格劣于 oracle 最优，而 batch_order 旋钮能达最优、SGS 却拧不动。"""
    case = _harmful_case()
    oracle = run_exact_oracle(case, objective_name=OBJECTIVE)
    assert oracle.best_score is not None
    oracle_overdue = float(oracle.best_score[1])
    sgs_locked = _distinct_signatures(case, dispatch_mode="sgs", dispatch_rule="slack")
    bo_best = _distinct_signatures(case, dispatch_mode="batch_order", dispatch_rule="slack")[0]
    # batch_order 能达最优；SGS 锁死在更差的 overdue 上，且重排救不了。
    assert _overdue(bo_best) == oracle_overdue
    assert _overdue(sgs_locked[0]) > oracle_overdue


def test_sgs_dead_key_is_harmless_when_sgs_already_optimal() -> None:
    """无害空转实例：SGS 锁定值已是 oracle 最优，no-op 不造成损失。"""
    case = _harmless_case()
    oracle = run_exact_oracle(case, objective_name=OBJECTIVE)
    assert oracle.best_score is not None
    sgs_locked = _distinct_signatures(case, dispatch_mode="sgs", dispatch_rule="slack")
    assert _overdue(sgs_locked[0]) == float(oracle.best_score[1])
