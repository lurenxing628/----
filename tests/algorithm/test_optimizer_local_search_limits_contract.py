"""Local search iteration semantics (2026-09-18): an iteration is a decode, idle rounds are bounded.

Before, every round counted toward ``time_budget_seconds * 20`` iterations, so a cheap baseline hit
the count at half its slice while duplicate and no-op rounds burned the rest. Now the decode limit
comes from the remaining slice and the incumbent's measured decode cost, duplicates are never
decoded twice, a bounded idle streak ends the search as ``search_exhausted``, and every decoded
candidate carries its own measured decode time.
"""

from __future__ import annotations

import math
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithms.sort_strategies import SortStrategy
from core.services.scheduler.run.optimizer_candidate_profile import (
    ITERATION_CEILING,
    ITERATION_FLOOR,
    RESTART_CEILING,
    RESTART_FLOOR,
)
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_local_search_limits import (
    LIMIT_SOURCE_DECODE_COST_UNKNOWN,
    LIMIT_SOURCE_MEASURED_DECODE_COST,
    LIMIT_SOURCE_NO_FINITE_DEADLINE,
    STOP_ITERATION_LIMIT,
    STOP_SEARCH_EXHAUSTED,
    STOP_TIME_BUDGET,
    LocalSearchCounters,
    derive_local_search_limits,
    local_search_stop_reason,
)
from core.services.scheduler.run.optimizer_local_search_round import _record_improvement
from core.services.scheduler.run.optimizer_neighborhood_moves import CRITICAL_CHAIN, NeighborhoodMove
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer_search_state import compact_attempts, init_seen_hashes
from tests.algorithm.test_optimizer_grasp_ig_candidate_construction_contract import _recording_schedule, _run_phase
from tests.algorithm.test_optimizer_vns_sa_local_search_contract import (
    _candidate,
    _result,
    _run_local_search_once,
    _summary,
)


def test_measured_decode_cost_bounds_the_decodes_to_what_the_slice_can_pay() -> None:
    limits = derive_local_search_limits(remaining_seconds=2.0, decode_cost_seconds=0.004, neighborhood_count=2)
    assert limits.source == LIMIT_SOURCE_MEASURED_DECODE_COST
    assert limits.affordable_decodes == 500 and limits.decode_limit == 500
    assert limits.restart_after == 500 // 8
    assert limits.idle_round_limit == 2 * limits.restart_after + 2
    assert (limits.remaining_ms, limits.decode_cost_ms) == (2000, 4)


@pytest.mark.parametrize("remaining, cost, expected", [
    (0.5, 0.05, ITERATION_FLOOR),
    (60.0, 0.001, ITERATION_CEILING),
    (0.0, 0.01, ITERATION_FLOOR),
])
def test_decode_limit_is_clamped_to_the_profile_window(remaining, cost, expected) -> None:
    limits = derive_local_search_limits(remaining_seconds=remaining, decode_cost_seconds=cost, neighborhood_count=1)
    assert limits.decode_limit == expected
    assert RESTART_FLOOR <= limits.restart_after <= RESTART_CEILING


def test_unknown_cost_and_no_deadline_fall_back_to_the_ceiling_and_say_so() -> None:
    unknown = derive_local_search_limits(remaining_seconds=3.0, decode_cost_seconds=0.0, neighborhood_count=1)
    assert unknown.source == LIMIT_SOURCE_DECODE_COST_UNKNOWN and unknown.decode_limit == ITERATION_CEILING
    assert unknown.affordable_decodes is None and unknown.decode_cost_ms is None
    endless = derive_local_search_limits(remaining_seconds=math.inf, decode_cost_seconds=0.01, neighborhood_count=1)
    assert endless.source == LIMIT_SOURCE_NO_FINITE_DEADLINE and endless.decode_limit == ITERATION_CEILING
    assert endless.remaining_ms is None
    report = endless.to_report_dict()
    assert report["policy"] == "measured_decode_budget_v1" and report["decode_limit"] == ITERATION_CEILING


@pytest.mark.parametrize("cost", [-1.0, math.nan, math.inf, True, "0.1"])
def test_invalid_decode_cost_is_rejected(cost) -> None:
    with pytest.raises(ValueError):
        derive_local_search_limits(remaining_seconds=1.0, decode_cost_seconds=cost, neighborhood_count=1)


def test_stop_reason_precedence_is_time_then_decodes_then_exhaustion() -> None:
    def _reason(*, now_value: float, decodes: int, idle_rounds: int):
        return local_search_stop_reason(
            now_value=now_value, deadline=10.0, decodes=decodes, decode_limit=5, idle_rounds=idle_rounds, idle_round_limit=3,
        )

    assert _reason(now_value=10.0, decodes=9, idle_rounds=9) == STOP_TIME_BUDGET
    assert _reason(now_value=9.0, decodes=5, idle_rounds=9) == STOP_ITERATION_LIMIT
    assert _reason(now_value=9.0, decodes=4, idle_rounds=3) == STOP_SEARCH_EXHAUSTED
    assert _reason(now_value=9.0, decodes=4, idle_rounds=2) is None


def test_counters_reset_the_idle_streak_on_every_decode() -> None:
    counters = LocalSearchCounters()
    counters.record_round(decode_attempted=False, duplicate=True)
    counters.record_round(decode_attempted=False, noop=True)
    assert (counters.decodes, counters.idle_rounds, counters.duplicate_rounds, counters.noop_rounds) == (0, 2, 1, 1)
    counters.record_round(decode_attempted=True)
    assert (counters.decodes, counters.idle_rounds) == (1, 0)
    assert counters.to_report_dict() == {"decodes": 1, "idle_rounds_at_stop": 0, "duplicate_rounds": 1, "noop_rounds": 1}


def test_seen_hashes_track_every_order_length() -> None:
    assert init_seen_hashes(["B1", "B2"], {"order": ["B2", "B1"]}) == {("B1", "B2"), ("B2", "B1")}
    assert init_seen_hashes(["B1"], None) == {("B1",)}


def test_local_candidates_carry_their_measured_decode_time() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=1, overdue_count=1)

    def _better_schedule(*args: Any, **kwargs: Any):
        return [
            _result(2, batch_id="B1", start_offset=0),
            _result(1, batch_id="B0", start_offset=1),
        ], _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned, report = _run_local_search_once(best=best, acceptance="improve_only", schedule_fn=_better_schedule)
    assert returned is not best and report["best_origin"] == "local_search"
    # The step clock advances 10 ms per reading; the decode is measured from the round's reading.
    assert returned["initial_decode_runtime_ms"] == pytest.approx(20.0)


def test_grasp_ig_candidates_carry_their_measured_decode_time() -> None:
    calls: List[Dict[str, Any]] = []
    best, attempts, _trace = _run_phase(schedule_fn=_recording_schedule(calls))
    assert best is not None and calls
    assert best["initial_decode_runtime_ms"] >= 0.0
    assert "initial_decode_runtime_ms" in best


def _improvement(order: List[str]) -> Dict[str, Any]:
    return {
        "metrics": SimpleNamespace(to_dict=lambda: {}), "score": (0.0, float(len(order))), "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {}, "dispatch_mode": "batch_order", "dispatch_rule": "slack", "order": list(order),
        "summary": SimpleNamespace(failed_ops=0), "algo_stats": {},
    }


def test_every_best_improvement_is_recorded_and_the_final_best_survives_compaction() -> None:
    attempts = [{"tag": f"start:s{i}", "dispatch_mode": "batch_order", "score": [0.0, 100.0 + i]} for i in range(12)]
    move = NeighborhoodMove(
        schema_version=1, neighborhood_name=CRITICAL_CHAIN, move_kind="move", input_scope="batch_order",
        batch_order=("B1",), changed_decision_count=1, expected_effect="test", dispatch_mode="batch_order", dispatch_rule="slack",
    )
    for length in (3, 2, 1):
        _record_improvement(
            candidate=_improvement(["B"] * length), move=move, attempts=attempts, improvement_trace=[], clock=lambda: 0.0, t_begin=0.0,
        )
    assert len(attempts) == 15
    compacted = compact_attempts(attempts, limit=12)
    assert len(compacted) == 12
    assert compacted[0]["score"] == [0.0, 1.0]


class _ConstantClock:
    def __call__(self) -> float:
        return 1000.0


class _DeterministicRandom:
    def random(self) -> float:
        return 0.1

    def sample(self, seq, n):
        return list(seq)[:n]

    def randrange(self, n: int) -> int:
        return 0

    def randint(self, a: int, b: int) -> int:
        return a


def test_local_search_without_a_deadline_still_terminates_as_exhausted() -> None:
    best = {
        "results": [], "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        "strategy": SortStrategy.PRIORITY_FIRST, "params": {}, "dispatch_mode": "sgs", "dispatch_rule": "slack",
        "order": ["B1", "B2"], "metrics": SimpleNamespace(to_dict=lambda: {}), "score": (0.0,),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }
    decodes: List[Dict[str, Any]] = []

    def _worse_schedule(*args: Any, **kwargs: Any):
        decodes.append(dict(kwargs))
        summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=1, warnings=[], errors=[])
        return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    state = OptimizationSearchReportState("multi_start_local_search", 3, 1, "min_overdue", 1000.0)
    state.mark_candidate_accepted(best, origin="multi_start")
    returned = run_local_search(
        algo_mode="improve", best=best, version=3, time_budget_seconds=1, deadline=math.inf,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[], batches={}, start_dt=datetime(2026, 1, 1, 8, 0, 0), end_date=None, downtime_map={},
        seed_sr_list=[], dispatch_mode_cfg="sgs", dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue",
        attempts=[], improvement_trace=[], optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}, t_begin=1000.0,
        readiness_gate_enabled=False, strict_mode=False, clock=_ConstantClock(), rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_worse_schedule, search_report_state=state,
    )
    assert returned is best
    report = state.finalize(runtime_ms=0, attempts=[], improvement_trace=[])
    assert report["stop_reason"] == STOP_SEARCH_EXHAUSTED
    # Every decode was a distinct decision: no rule token or shaken order decoded twice.
    decisions = {(call["dispatch_rule"], tuple(call["batch_order_override"])) for call in decodes}
    assert len(decisions) == len(decodes) == report["iterations"]
    assert state.candidate_profile is not None
    limits = state.candidate_profile["local_search_limits"]
    assert limits["source"] == LIMIT_SOURCE_NO_FINITE_DEADLINE and limits["decode_limit"] == ITERATION_CEILING
