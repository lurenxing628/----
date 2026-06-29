"""第 8 阶段：VNS / acceptance 局部搜索升级合同测试。"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.services.scheduler.run.optimizer_acceptance import decide_acceptance
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_local_search_state import LocalSearchState, candidate_can_update_best
from core.services.scheduler.run.optimizer_neighborhood_moves import (
    BUSINESS_NEIGHBORHOODS,
    CRITICAL_CHAIN,
    SGS_DISPATCH_RULE,
    TARDY_WINDOW,
)
from core.services.scheduler.run.optimizer_proof_cases import TinyBatchSpec, TinyBenchmarkCase, TinyOperationSpec
from core.services.scheduler.run.optimizer_proof_oracle import (
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
)
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer_vns import VnsState
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from tests._support.optimizer_benchmark_grading import smtwt_overdue_case
from tests._support.optimizer_benchmark_loaders import load_smtwt_instances

_START = datetime(2026, 1, 1, 8, 0, 0)


class _Clock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01) -> None:
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


class _PickSecondRandom(_DeterministicRandom):
    def randrange(self, n: int) -> int:
        return 1 if int(n) > 1 else 0


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
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=2,
        scheduled_ops=2 - failed_ops,
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _metrics(*, overdue_count: int = 0, tardiness: float = 0.0) -> ScheduleMetrics:
    return ScheduleMetrics(
        overdue_count=overdue_count,
        total_tardiness_hours=tardiness,
        makespan_hours=2.0,
        changeover_count=0,
        weighted_tardiness_hours=tardiness,
    )


def _candidate(*, order: List[str], failed_ops: int, overdue_count: int = 0) -> Dict[str, Any]:
    metrics = _metrics(overdue_count=overdue_count, tardiness=float(overdue_count))
    return {
        "results": [_result(1, batch_id=order[0], start_offset=0), _result(2, batch_id=order[1], start_offset=1)],
        "summary": _summary(failed_ops=failed_ops),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": list(order),
        "metrics": metrics,
        "score": (float(failed_ops), float(overdue_count), float(overdue_count)),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
    }


def _tiny_op(op_id: int, batch_id: str) -> TinyOperationSpec:
    return TinyOperationSpec(
        op_id=op_id,
        op_code=f"S{op_id}",
        batch_id=batch_id,
        seq=1,
        machine_id="machine-main",
        operator_id="operator-main",
        duration_hours=24.0,
    )


def _improvable_batch_order_case() -> TinyBenchmarkCase:
    return TinyBenchmarkCase(
        slug="vns-real-greedy-improvement",
        objective_name="min_overdue",
        batches=(
            TinyBatchSpec(batch_id="batch-a", due_date="2026-01-02"),
            TinyBatchSpec(batch_id="batch-b", due_date="2026-01-03"),
            TinyBatchSpec(batch_id="batch-c", due_date="2026-01-04"),
            TinyBatchSpec(batch_id="batch-d", due_date="2026-01-02"),
        ),
        operations=(
            _tiny_op(1, "batch-a"),
            _tiny_op(2, "batch-b"),
            _tiny_op(3, "batch-c"),
            _tiny_op(4, "batch-d"),
        ),
    )


def _real_candidate_for_order(order: List[str]) -> Dict[str, Any]:
    case = _improvable_batch_order_case()
    batches = batch_objects(case)
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, strategy, params = scheduler.schedule(
        operations=[_operation_object(op) for op in case.operations],
        batches=batches,
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        batch_order_override=list(order),
        seed_results=[],
        strict_mode=True,
    )
    metrics = compute_metrics(results, batches)
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": dict(params or {}),
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": list(order),
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + tuple(float(item) for item in objective_score("min_overdue", metrics)),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
        "seed_result_count": 0,
        "locked_seed_range": [],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(order)},
    }


def _real_sgs_candidate_for_rule(rule: str) -> Tuple[Dict[str, Any], TinyBenchmarkCase]:
    case = smtwt_overdue_case(load_smtwt_instances(40)[0])
    batches = batch_objects(case)
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, strategy, params = scheduler.schedule(
        operations=[_operation_object(op) for op in case.operations],
        batches=batches,
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt,
        dispatch_mode="sgs",
        dispatch_rule=rule,
        seed_results=[],
        strict_mode=True,
    )
    metrics = compute_metrics(results, batches)
    order = [batch.batch_id for batch in case.batches]
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": dict(params or {}),
        "dispatch_mode": "sgs",
        "dispatch_rule": rule,
        "order": order,
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + tuple(float(item) for item in objective_score("min_overdue", metrics)),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
        "seed_result_count": 0,
        "locked_seed_range": [],
        "mutable_scope": {"scope": "dispatch_rule", "batch_count": len(order)},
    }, case


def _real_schedule_fn(scheduler: Any, **kwargs: Any):
    return scheduler.schedule(**kwargs)


def _candidate_three_batches() -> Dict[str, Any]:
    return {
        "results": [
            _result(1, batch_id="B0", start_offset=0),
            _result(2, batch_id="B1", start_offset=1),
            _result(3, batch_id="B2", start_offset=2),
        ],
        "summary": _summary(failed_ops=0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": ["B0", "B1", "B2"],
        "metrics": _metrics(),
        "score": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {"best": True},
    }


def _run_local_search_once(
    *,
    best: Dict[str, Any],
    acceptance: str,
    schedule_fn: Any,
    dispatch_mode_cfg: str = "sgs",
    dispatch_rule_cfg: str = "slack",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    report_state = OptimizationSearchReportState(
        algorithm_profile="vns_sa",
        seed=42,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
        candidate_profile={"acceptance": acceptance, "neighborhoods": [CRITICAL_CHAIN]},
    )
    report_state.mark_candidate_accepted(best, origin="multi_start")
    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=42,
        time_budget_seconds=1,
        deadline=1000.005,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg=dispatch_mode_cfg,
        dispatch_rule_cfg=dispatch_rule_cfg,
        resource_pool=None,
        objective_name="min_overdue",
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_Clock(start=1000.0, step=0.01),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=schedule_fn,
        search_report_state=report_state,
        neighborhoods=(CRITICAL_CHAIN,),
        acceptance=acceptance,
    )
    return returned, report_state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])


def test_threshold_accepts_non_improving_candidate_as_current_without_best_improvement() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=0)
    best["score"] = (0.0, 0.0, 0.0, 0.0, 2.0, 0.0)

    def _same_score_schedule(*args: Any, **kwargs: Any):
        return list(best["results"]), _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned, report = _run_local_search_once(best=best, acceptance="threshold", schedule_fn=_same_score_schedule)

    assert returned is best
    assert report["accepted_candidates"] == 2
    assert report["accepted_distinct_candidates"] == 1
    assert report["current_accepted_candidates"] == 1
    assert report["best_improved_candidates"] == 0
    assert report["best_origin"] == "multi_start"
    assert report["improved"] is False
    assert report["improvement_conditions"]["acceptance_passed"] is False
    assert report["acceptance_summary"]["threshold"]["non_improving_accepted"] == 1


def test_improve_only_updates_best_only_for_accepted_changed_better_output() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=1, overdue_count=1)

    def _better_schedule(*args: Any, **kwargs: Any):
        return [
            _result(3, batch_id="B1", start_offset=0),
            _result(4, batch_id="B0", start_offset=1),
        ], _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned, report = _run_local_search_once(best=best, acceptance="improve_only", schedule_fn=_better_schedule)

    assert returned is not best
    assert returned["score"] < best["score"]
    assert report["best_improved_candidates"] == 1
    assert report["best_origin"] == "local_search"
    assert report["improved"] is True
    assert report["improvement_conditions"]["fingerprint_changed"] is True
    assert report["improvement_conditions"]["score_strictly_better"] is True
    assert report["improvement_conditions"]["acceptance_passed"] is True


def test_vns_local_search_sgs_candidate_switches_dispatch_rule() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=1, overdue_count=1)
    decode_calls: List[Dict[str, Any]] = []

    def _recording_schedule(*args: Any, **kwargs: Any):
        decode_calls.append(dict(kwargs))
        return [
            _result(3, batch_id="B1", start_offset=0),
            _result(4, batch_id="B0", start_offset=1),
        ], _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    _run_local_search_once(best=best, acceptance="improve_only", schedule_fn=_recording_schedule)

    assert decode_calls
    assert {str(call.get("dispatch_mode")) for call in decode_calls} == {"sgs"}
    assert decode_calls[0]["dispatch_rule"] == "cr"
    assert decode_calls[0]["batch_order_override"] == ["B0", "B1"]


def test_record_to_record_accepts_candidate_within_best_record_distance_as_current() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=0)
    best["score"] = (0.0, 0.0, 0.0, 0.0, 2.0, 0.0)

    def _same_score_schedule(*args: Any, **kwargs: Any):
        return list(best["results"]), _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned, report = _run_local_search_once(best=best, acceptance="record_to_record", schedule_fn=_same_score_schedule)

    assert returned is best
    assert report["current_accepted_candidates"] == 1
    assert report["best_improved_candidates"] == 0
    assert report["acceptance_summary"]["record_to_record"]["non_improving_accepted"] == 1
    assert report["improved"] is False


def test_threshold_rejects_candidate_with_more_failed_ops_even_when_objective_within_threshold() -> None:
    decision = decide_acceptance(
        acceptance_name="threshold",
        candidate_score=(1.0, 0.0, 0.0),
        current_score=(0.0, 100.0, 100.0),
        best_score=(0.0, 100.0, 100.0),
        iteration=0,
        max_iterations=100,
        random_seed=42,
        rnd=random.Random(42),
    )

    assert decision.accepted is False
    assert decision.acceptance_reason == "failed_ops_worse"
    assert decision.score_delta == 1.0


def test_record_to_record_rejects_candidate_with_more_failed_ops_than_record() -> None:
    decision = decide_acceptance(
        acceptance_name="record_to_record",
        candidate_score=(1.0, 0.0, 0.0),
        current_score=(2.0, 0.0, 0.0),
        best_score=(0.0, 100.0, 100.0),
        iteration=0,
        max_iterations=100,
        random_seed=42,
        rnd=random.Random(42),
    )

    assert decision.accepted is False
    assert decision.acceptance_reason == "failed_ops_worse"
    assert decision.record_distance == 1.0
    assert decision.score_delta_reference == "current_score"
    assert decision.record_distance_reference == "best_score"


def test_local_search_state_keeps_current_and_best_separate() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=0)
    worse = _candidate(order=["B1", "B0"], failed_ops=1)
    state = LocalSearchState.from_best(best, resource_pool=None)

    state.accept_current(worse)

    assert state.current is worse
    assert state.best is best
    assert state.current_order == ["B1", "B0"]


def test_local_search_reset_restores_current_payload_to_best() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=0)
    best["resource_pool"] = {"best": True}
    worse = _candidate(order=["B1", "B0"], failed_ops=1)
    worse["resource_pool"] = {"current": True}
    state = LocalSearchState.from_best(best, resource_pool=None)
    state.accept_current(worse)

    state.reset_current_to_best(order=["B2", "B0", "B1"])

    assert state.current is best
    assert state.best is best
    assert state.current_order == ["B2", "B0", "B1"]
    assert state.current_resource_pool == {"best": True}


def test_best_update_requires_candidate_fingerprint_even_without_report() -> None:
    best = _candidate(order=["B0", "B1"], failed_ops=1, overdue_count=1)
    better = _candidate(order=["B1", "B0"], failed_ops=0)

    assert candidate_can_update_best(candidate=better, best=best, fingerprint=None) is False


def test_vns_switches_neighborhood_even_without_search_report_state() -> None:
    best = _candidate_three_batches()
    best["dispatch_mode"] = "batch_order"
    batches = {
        "B0": SimpleNamespace(due_date=date(2026, 1, 2)),
        "B1": SimpleNamespace(due_date=date(2025, 12, 31)),
        "B2": SimpleNamespace(due_date=date(2026, 1, 2)),
    }
    decode_orders: List[Tuple[str, ...]] = []

    def _same_schedule(*args: Any, **kwargs: Any):
        decode_orders.append(tuple(kwargs.get("batch_order_override") or ()))
        return list(best["results"]), _summary(failed_ops=0), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=42,
        time_budget_seconds=1,
        deadline=1000.0015,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches=batches,
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
        clock=_Clock(start=1000.0, step=0.001),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_same_schedule,
        search_report_state=None,
        neighborhoods=(CRITICAL_CHAIN, TARDY_WINDOW),
        acceptance="improve_only",
    )

    assert returned is best
    assert decode_orders[:2] == [("B2", "B0", "B1"), ("B1", "B0", "B2")]


def test_vns_real_greedy_local_search_updates_best_on_batch_order_path() -> None:
    best = _real_candidate_for_order(["batch-a", "batch-d", "batch-b", "batch-c"])
    case = _improvable_batch_order_case()
    report_state = OptimizationSearchReportState(
        algorithm_profile="vns_sa",
        seed=1,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only", "neighborhoods": [CRITICAL_CHAIN, TARDY_WINDOW]},
    )
    report_state.mark_candidate_accepted(best, origin="multi_start")
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []

    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.08,
        scheduler=GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config()),
        algo_ops_to_schedule=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case),
        start_dt=case.start_dt,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        clock=_Clock(start=1000.0, step=0.01),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_real_schedule_fn,
        search_report_state=report_state,
        neighborhoods=(CRITICAL_CHAIN, TARDY_WINDOW),
        acceptance="improve_only",
    )
    report = report_state.finalize(runtime_ms=20, attempts=attempts, improvement_trace=trace)

    assert returned is not None
    assert returned["score"] < best["score"]
    assert report["best_origin"] == "local_search"
    assert report["best_improved_candidates"] >= 1
    assert report["improved"] is True


def test_vns_real_greedy_local_search_updates_best_on_sgs_rule_path() -> None:
    best, case = _real_sgs_candidate_for_rule("slack")
    report_state = OptimizationSearchReportState(
        algorithm_profile="vns_sa",
        seed=1,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only", "neighborhoods": list(BUSINESS_NEIGHBORHOODS)},
    )
    report_state.mark_candidate_accepted(best, origin="multi_start")
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []

    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.08,
        scheduler=GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config()),
        algo_ops_to_schedule=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case),
        start_dt=case.start_dt,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        clock=_Clock(start=1000.0, step=0.01),
        rng_factory=lambda _seed: _PickSecondRandom(),
        schedule_fn=_real_schedule_fn,
        search_report_state=report_state,
        neighborhoods=BUSINESS_NEIGHBORHOODS,
        valid_dispatch_rules=["slack", "cr", "atc"],
        acceptance="improve_only",
    )
    report = report_state.finalize(runtime_ms=20, attempts=attempts, improvement_trace=trace)

    assert returned is not None
    assert returned["dispatch_rule"] == "atc"
    assert returned["score"] < best["score"]
    assert report["best_origin"] == "local_search"
    assert report["neighborhood_summary"][SGS_DISPATCH_RULE]["effective"] >= 1
    assert report["candidate_profile"]["configured_neighborhoods"] == list(BUSINESS_NEIGHBORHOODS)
    assert report["candidate_profile"]["effective_neighborhoods"] == [SGS_DISPATCH_RULE]
    public_report, diagnostics = project_search_report(report)
    profile_public = public_report["profile_public"]
    assert profile_public["configured_neighborhoods"] == list(BUSINESS_NEIGHBORHOODS)
    assert profile_public["effective_neighborhoods"] == [SGS_DISPATCH_RULE]
    assert "neighborhoods" not in profile_public
    assert set(public_report["neighborhood_summary"]) == {SGS_DISPATCH_RULE}
    assert diagnostics["profile_diagnostics"]["effective_neighborhood_reason"] == "sgs_dispatch_rule_only"
    assert report["improved"] is True


def test_graph_ready_local_search_skips_batch_order_neighborhoods() -> None:
    best = _real_candidate_for_order(["batch-a", "batch-d", "batch-b", "batch-c"])
    report_state = OptimizationSearchReportState(
        algorithm_profile="vns_sa",
        seed=1,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only", "neighborhoods": [CRITICAL_CHAIN]},
    )
    report_state.mark_candidate_accepted(best, origin="multi_start")
    schedule_calls: List[Dict[str, Any]] = []

    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.08,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=True,
        strict_mode=False,
        clock=_Clock(start=1000.0, step=0.01),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=lambda *args, **kwargs: schedule_calls.append(dict(kwargs)),
        graph_ready_context={"enabled": True},
        search_report_state=report_state,
        neighborhoods=(CRITICAL_CHAIN,),
        acceptance="improve_only",
    )
    report = report_state.finalize(runtime_ms=20, attempts=[], improvement_trace=[])

    assert returned is best
    assert schedule_calls == []
    assert report["skipped_phases"] == [
        {"phase": "local_search", "reason": "graph_ready_requires_graph_neighborhood"}
    ]


def test_simulated_annealing_acceptance_is_seeded_and_deterministic() -> None:
    first = decide_acceptance(
        acceptance_name="simulated_annealing",
        candidate_score=(0.0, 1.0),
        current_score=(0.0, 0.0),
        best_score=(0.0,),
        iteration=1,
        max_iterations=200,
        random_seed=42,
        rnd=random.Random(42),
    )
    second = decide_acceptance(
        acceptance_name="simulated_annealing",
        candidate_score=(0.0, 1.0),
        current_score=(0.0, 0.0),
        best_score=(0.0,),
        iteration=1,
        max_iterations=200,
        random_seed=42,
        rnd=random.Random(42),
    )

    assert first.to_report_dict() == second.to_report_dict()
    assert first.random_seed == 42
    assert first.deterministic_random_draw is not None
    assert first.worse_solution_allowed is True


def test_simulated_annealing_rejects_candidate_with_more_failed_ops() -> None:
    decision = decide_acceptance(
        acceptance_name="simulated_annealing",
        candidate_score=(1.0, 0.0, 0.0),
        current_score=(0.0, 100.0, 100.0),
        best_score=(0.0, 100.0, 100.0),
        iteration=0,
        max_iterations=100,
        random_seed=1,
        rnd=random.Random(1),
    )

    assert decision.accepted is False
    assert decision.acceptance_reason == "failed_ops_worse"
    assert decision.score_delta == 1.0
    assert decision.deterministic_random_draw is None


def test_vns_switches_neighborhood_after_no_improvement_and_resets_after_best_improvement() -> None:
    state = VnsState((CRITICAL_CHAIN, TARDY_WINDOW))

    first = state.record_round(best_improved=False, noop=False, fallback_used=False)
    assert first["current_neighborhood"] == CRITICAL_CHAIN
    assert first["next_neighborhood"] == TARDY_WINDOW
    assert first["neighborhood_switch_reason"] == "no_best_improvement_next_neighborhood"

    second = state.record_round(best_improved=True, noop=False, fallback_used=False)
    assert second["current_neighborhood"] == TARDY_WINDOW
    assert second["next_neighborhood"] == CRITICAL_CHAIN
    assert second["neighborhood_switch_reason"] == "best_improved_reset"
