"""合同测试（A08）：图 profile 候选的 runtime_ms 必须是该候选自身耗时。

同分 tie-break 合同声明"偏好更快候选"（GRAPH_READY_SELECTION_TIEBREAKER 的 runtime_ms 维度，
消费点 optimizer_candidate_comparison.candidate_runtime_ms）。若把"自优化开始的累计流逝时间"
写进候选 payload，则 runtime_ms 随 profile 评估序号单调递增，同分 tie-break 实际退化为
"偏好更早评估的 profile"。本文件锁 per-candidate 计时语义：先评估的慢候选不得靠评估顺序胜出。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.services.scheduler.run.optimizer_candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer_graph_ready_candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_WEIGHT_GRID_ORIGIN,
    GraphReadyWeightProfile,
)

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


class _ManualClock:
    """手动推进的时钟：只有 schedule_fn 里显式 advance 才流逝，便于精确断言耗时。"""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


def _profile(slug: str) -> GraphReadyWeightProfile:
    weights = {
        "critical_path": 1.0,
        "successor_count": 1.0,
        "downstream_work_hours": 1.0,
        "bottleneck_machine": 1.0,
    }
    return GraphReadyWeightProfile(
        slug=slug,
        profile_order=0,
        raw_weights=dict(weights),
        effective_weights=dict(weights),
        candidate_origin=GRAPH_READY_WEIGHT_GRID_ORIGIN,
        candidate_policy="fixed_weight_grid",
    )


def _metric() -> Dict[str, Any]:
    return {
        "is_on_critical_path": True,
        "critical_path_rank": 1,
        "downstream_critical_minutes": 60.0,
        "impact_count": 1.0,
        "bottleneck_machine_score": 0.0,
    }


def _result(op_id: int, batch_id: str, offset: int) -> ScheduleResult:
    start_time = _START + timedelta(hours=offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-{op_id}",
        batch_id=batch_id,
        seq=op_id * 10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name="cut",
    )


def _summary(results: List[ScheduleResult]) -> ScheduleSummary:
    return ScheduleSummary(
        success=True,
        total_ops=len(results),
        scheduled_ops=len(results),
        failed_ops=0,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _batches() -> Dict[str, Any]:
    return {
        batch_id: SimpleNamespace(batch_id=batch_id, priority="normal", due_date="2026-01-10", ready_status="yes")
        for batch_id in ("B1", "B2")
    }


def _make_schedule_fn(clock: _ManualClock, cost_seconds_by_slug: Dict[str, float]):
    def _schedule(scheduler: Any, **kwargs: Any):
        params = dict(kwargs.get("strategy_params") or {})
        slug = str((params.get("graph_ready_profile") or {}).get("weight_profile_slug") or "")
        clock.advance(cost_seconds_by_slug[slug])
        results = [_result(1, "B1", 0), _result(2, "B2", 1)]
        return results, _summary(results), kwargs.get("strategy"), params

    return _schedule


def _evaluate(profile: GraphReadyWeightProfile, *, clock: _ManualClock, schedule_fn: Any) -> Dict[str, Any]:
    return evaluate_graph_ready_candidate(
        profile=profile,
        graph_ready_context={},
        metrics_by_op_id={1: _metric(), 2: _metric()},
        scheduler=SimpleNamespace(_last_algo_stats={}),
        strict_mode=False,
        algo_ops_to_schedule=[SimpleNamespace(id=1, batch_id="B1"), SimpleNamespace(id=2, batch_id="B2")],
        batches=_batches(),
        strategy=SortStrategy.PRIORITY_FIRST,
        params={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        order=["B1", "B2"],
        seed_sr_list=[],
        dispatch_rule="slack",
        resource_pool=None,
        objective_name=_OBJECTIVE,
        optimizer_algo_stats={},
        schedule_fn=schedule_fn,
        readiness_gate_enabled=False,
        version=7,
        clock=clock,
    )


def test_candidate_runtime_ms_is_per_candidate_cost_not_cumulative_elapsed() -> None:
    clock = _ManualClock()
    schedule_fn = _make_schedule_fn(clock, {"slow_profile": 0.5, "fast_profile": 0.25})

    slow = _evaluate(_profile("slow_profile"), clock=clock, schedule_fn=schedule_fn)
    fast = _evaluate(_profile("fast_profile"), clock=clock, schedule_fn=schedule_fn)

    assert slow["runtime_ms"] == 500
    # 累计流逝时间语义下这里会是 750（500+250）；per-candidate 语义下必须是 250。
    assert fast["runtime_ms"] == 250


def test_same_score_tiebreak_prefers_faster_candidate_not_earlier_evaluated() -> None:
    clock = _ManualClock()
    schedule_fn = _make_schedule_fn(clock, {"slow_profile": 0.5, "fast_profile": 0.25})

    slow = _evaluate(_profile("slow_profile"), clock=clock, schedule_fn=schedule_fn)
    fast = _evaluate(_profile("fast_profile"), clock=clock, schedule_fn=schedule_fn)
    assert slow["score"] == fast["score"]

    # 后评估但更快的候选必须在同分 tie-break 中胜出；先评估的慢候选不得靠评估顺序保住 best。
    assert candidate_is_preferred(
        candidate=fast,
        incumbent=slow,
        candidate_origin=GRAPH_READY_WEIGHT_GRID_ORIGIN,
        incumbent_origin=GRAPH_READY_WEIGHT_GRID_ORIGIN,
        candidate_fingerprint=None,
        incumbent_fingerprint_changed=False,
    ) is True
    assert candidate_is_preferred(
        candidate=slow,
        incumbent=fast,
        candidate_origin=GRAPH_READY_WEIGHT_GRID_ORIGIN,
        incumbent_origin=GRAPH_READY_WEIGHT_GRID_ORIGIN,
        candidate_fingerprint=None,
        incumbent_fingerprint_changed=False,
    ) is False
