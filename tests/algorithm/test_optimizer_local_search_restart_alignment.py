"""合同测试（A01）：局搜 restart 后 current 的 order/score/results 三元组必须对齐。

旧行为：restart 只把 current_order 换成扰动顺序，current 的 score/results 仍指向 best——
接受准则实际拿 best 分数当基准（improve_only 下扰动区域的非改进中间步一步走不进去），
邻域用 best 顺序的旧 results 选靶。修复合同：restart 时对扰动顺序立即做一次真实评估
（schedule_fn），current 三者同源；评估失败按既有候选失败路径留痕并整体退回 best。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from core.algorithms.evaluation import ScheduleMetrics
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_local_search_restart import restart_after_stall
from core.services.scheduler.run.optimizer_local_search_state import LocalSearchState
from core.services.scheduler.run.optimizer_neighborhood_moves import CRITICAL_CHAIN
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer_vns import VnsState

_START = datetime(2026, 1, 1, 8, 0, 0)
_BEST_ORDER = ("B0", "B1", "B2", "B3")
# _DeterministicRandom 下 _shake_order 对 best 顺序固定产出 swap(0,1) 三次的结果。
_SHAKEN_ORDER = ("B1", "B0", "B2", "B3")
# critical_chain 把 latest 批次往前挪一位。扰动点 results（latest=B2）上得到的候选顺序；四个批次
# 保证它既不是 best 顺序（已解码过，去重后不会再解码）也不是错位顺序。
_POST_RESTART_ORDER = ("B2", "B1", "B0", "B3")
# 若邻域仍用 best 的陈旧 results（latest=B3）在扰动顺序上选靶，会产出这个错位顺序。
_STALE_TARGET_ORDER = ("B1", "B3", "B0", "B2")
_PRE_RESTART_ORDER = ("B0", "B3", "B1", "B2")


class _Clock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.0001) -> None:
        self._now = float(start)
        self._step = float(step)

    def __call__(self) -> float:
        current = self._now
        self._now += self._step
        return current


class _DeterministicRandom:
    def random(self) -> float:
        return 0.1

    def sample(self, seq, n):
        return list(seq)[:n]

    def randrange(self, n: int) -> int:
        return 0

    def randint(self, a: int, b: int) -> int:
        return a


def _result(op_id: int, *, batch_id: str, start_offset: int) -> ScheduleResult:
    start_time = _START + timedelta(hours=start_offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-10",
        batch_id=batch_id,
        seq=10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name="cut",
    )


def _summary(*, failed_ops: int) -> ScheduleSummary:
    total_ops = 2 + failed_ops
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=total_ops,
        scheduled_ops=total_ops - failed_ops,
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _metrics() -> ScheduleMetrics:
    return ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=2.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )


def _results_latest(batch_id: str, *, other: str) -> List[ScheduleResult]:
    """两条结果、makespan 恒为 2 小时；latest_result 落在 batch_id 上。"""
    return [_result(1, batch_id=other, start_offset=0), _result(2, batch_id=batch_id, start_offset=1)]


def _best_candidate() -> Dict[str, Any]:
    return {
        "results": _results_latest("B3", other="B0"),
        "summary": _summary(failed_ops=1),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": list(_BEST_ORDER),
        "metrics": _metrics(),
        "score": (1.0, 0.0, 0.0, 2.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
    }


# 每个关键顺序 -> (failed_ops, latest 批次, 另一批次)。failed_ops 驱动分数：
# best=1 < 候选(2) < 扰动点(3)=预重启候选(3) < 其余顺序(4)，makespan 全部相同不干扰比较。
_SCHEDULE_MAP: Dict[Tuple[str, ...], Tuple[int, str, str]] = {
    _PRE_RESTART_ORDER: (3, "B0", "B2"),
    _SHAKEN_ORDER: (3, "B2", "B1"),
    _POST_RESTART_ORDER: (2, "B1", "B0"),
}
_OTHER_ORDER_RESULT = (4, "B0", "B1")


def _make_schedule_fn(calls: List[Tuple[str, ...]]):
    def _schedule(scheduler: Any, **kwargs: Any):
        order = tuple(kwargs.get("batch_order_override") or ())
        calls.append(order)
        if order == _STALE_TARGET_ORDER:
            raise AssertionError(f"stale-results targeting after restart: {order}")
        failed_ops, latest, other = _SCHEDULE_MAP.get(order, _OTHER_ORDER_RESULT)
        results = _results_latest(latest, other=other)
        return results, _summary(failed_ops=failed_ops), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    return _schedule


def _run_until_exhausted(best: Dict[str, Any], calls: List[Tuple[str, ...]]) -> Tuple[Any, Dict[str, Any]]:
    report_state = OptimizationSearchReportState(
        algorithm_profile="vns_sa",
        seed=42,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only", "neighborhoods": [CRITICAL_CHAIN]},
    )
    report_state.mark_candidate_accepted(best, origin="multi_start")
    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=42,
        time_budget_seconds=1,
        # No measured decode cost on this stub incumbent: the decode limit is the ceiling and the
        # search ends as exhausted once every reachable neighbor has been decoded.
        deadline=1005.0,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_Clock(),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_make_schedule_fn(calls),
        search_report_state=report_state,
        neighborhoods=(CRITICAL_CHAIN,),
        acceptance="improve_only",
    )
    return returned, report_state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])


def test_restart_evaluates_shaken_order_and_neighborhood_targets_aligned_results() -> None:
    calls: List[Tuple[str, ...]] = []
    returned, report = _run_until_exhausted(_best_candidate(), calls)

    # 第 1 次解码：从 best（latest=B2）选靶的候选被 improve_only 拒绝；之后同一决策只算空转，
    # 不再重复解码（2026-09-18 局搜迭代语义：迭代 = 解码，重复决策不占解码）。
    assert calls[0] == _PRE_RESTART_ORDER
    # 空转累计到 restart 阈值后，restart 对扰动顺序做真实评估——扰动顺序不允许不打分就当 current。
    assert calls[1] == _SHAKEN_ORDER
    # restart 后的邻域必须用对齐后的 results（latest=B0）选靶：陈旧 results（latest=B2）
    # 会产出 _STALE_TARGET_ORDER，被 stub 直接 AssertionError 拒绝。
    assert calls[2] == _POST_RESTART_ORDER
    assert _STALE_TARGET_ORDER not in calls
    # 每个顺序只解码一次；可达顺序解完后搜索见底，而不是靠迭代计数或时间预算收场。
    assert len(calls) == len(set(calls))
    assert report["stop_reason"] == "search_exhausted"
    assert report["iterations"] == len(calls)
    # best 棘轮语义不变：没有候选优于 best（failed_ops=1），返回值仍是 best。
    assert returned is not None
    assert returned["score"] == (1.0, 0.0, 0.0, 2.0, 0.0)
    assert report["best_origin"] == "multi_start"


def test_restart_acceptance_compares_against_aligned_current_score_not_best() -> None:
    calls: List[Tuple[str, ...]] = []
    _returned, report = _run_until_exhausted(_best_candidate(), calls)

    # 候选 failed_ops=2：劣于 best(1)、优于扰动点真实分(3)。improve_only 参照对齐后的
    # current 分数必须接受为 current；旧缺陷参照 best 分数会全程拒绝（该计数为 0）。
    assert report["current_accepted_candidates"] >= 1
    assert report["best_improved_candidates"] == 0


def _aligned_candidate(order: List[str]) -> Dict[str, Any]:
    candidate = _best_candidate()
    candidate["order"] = list(order)
    candidate["results"] = _results_latest("B0", other="B1")
    candidate["summary"] = _summary(failed_ops=3)
    candidate["score"] = (3.0, 0.0, 0.0, 2.0, 0.0)
    candidate["resource_pool"] = {"shaken": True}
    return candidate


def test_restart_state_keeps_current_triplet_from_evaluated_candidate() -> None:
    best = _best_candidate()
    state = LocalSearchState.from_best(best, resource_pool=None)
    seen_args: List[Tuple[Any, ...]] = []

    def _evaluator(shaken_order: List[str], move: Any, strategy: Any, params: Dict[str, Any], dispatch_mode: str, dispatch_rule: str):
        seen_args.append((list(shaken_order), strategy, dict(params), dispatch_mode, dispatch_rule))
        return _aligned_candidate(shaken_order), None

    outcome = restart_after_stall(
        local_state=state,
        rnd=_DeterministicRandom(),
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        vns_state=VnsState((CRITICAL_CHAIN,)),
        seen_hashes=set(),
        evaluate_shaken_order=_evaluator,
    )

    assert outcome.decode_attempted is True and outcome.budget_exhausted is None
    assert seen_args and seen_args[0][0] == list(_SHAKEN_ORDER)
    # 扰动顺序用 best 的策略状态评估。
    assert seen_args[0][1] is best["strategy"]
    assert seen_args[0][3] == "batch_order"
    # current 三元组同源：order/score/results 全部来自同一次真实评估。
    assert state.current is not best
    assert state.current_order == list(_SHAKEN_ORDER)
    assert state.current["order"] == list(_SHAKEN_ORDER)
    assert state.current["score"] == (3.0, 0.0, 0.0, 2.0, 0.0)
    assert state.current["results"] is not best["results"]
    assert state.current_resource_pool == {"shaken": True}
    # best 棘轮不动。
    assert state.best is best


def test_restart_state_falls_back_to_best_when_shaken_evaluation_fails() -> None:
    best = _best_candidate()
    state = LocalSearchState.from_best(best, resource_pool=None)

    restart_after_stall(
        local_state=state,
        rnd=_DeterministicRandom(),
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        vns_state=VnsState((CRITICAL_CHAIN,)),
        seen_hashes=set(),
        evaluate_shaken_order=lambda *args: (None, None),
    )

    # 评估失败：放弃扰动，current 整体退回 best——顺序也必须退回，不允许留下未评估顺序。
    assert state.current is best
    assert state.current_order == list(_BEST_ORDER)
    assert state.best is best


def test_restart_skips_shaken_order_already_decoded_in_this_search() -> None:
    best = _best_candidate()
    state = LocalSearchState.from_best(best, resource_pool=None)
    vns_state = VnsState((CRITICAL_CHAIN,))
    calls: List[List[str]] = []

    def _evaluator(shaken_order: List[str], *_args: Any):
        calls.append(list(shaken_order))
        return _aligned_candidate(shaken_order), None

    seen = {tuple(_SHAKEN_ORDER)}
    outcome = restart_after_stall(
        local_state=state, rnd=_DeterministicRandom(), dispatch_mode_cfg="batch_order", dispatch_rule_cfg="slack",
        vns_state=vns_state, seen_hashes=seen, evaluate_shaken_order=_evaluator,
    )

    # 扰动顺序本轮已解码过：不再解码，current 退回 best，shake 仍计入 vns 事件，并如实标记为重复。
    assert calls == []
    assert outcome.decode_attempted is False and outcome.duplicate is True and outcome.budget_exhausted is None
    assert state.current is best and state.current_order == list(_BEST_ORDER)
    assert vns_state.shake_count == 1


def test_restart_refused_by_the_budget_guard_is_not_a_duplicate_round() -> None:
    best = _best_candidate()
    state = LocalSearchState.from_best(best, resource_pool=None)

    outcome = restart_after_stall(
        local_state=state, rnd=_DeterministicRandom(), dispatch_mode_cfg="batch_order", dispatch_rule_cfg="slack",
        vns_state=VnsState((CRITICAL_CHAIN,)), seen_hashes=set(), evaluate_shaken_order=lambda *args: (None, "time_budget"),
    )

    # 预算守卫拒绝解码：既不是解码轮也不是重复轮，停止原因由 budget_exhausted 直接给出。
    assert outcome.decode_attempted is False and outcome.duplicate is False and outcome.budget_exhausted == "time_budget"
    assert state.current is best and state.current_order == list(_BEST_ORDER)
