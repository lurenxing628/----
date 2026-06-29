"""回归测试：GRASP / IG 候选构造合同（roadmap item 6）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_candidate_profile import build_candidate_profile, derive_grasp_ig_limits
from core.services.scheduler.run.optimizer_grasp_ig_candidates import run_grasp_ig_candidates
from core.services.scheduler.run.optimizer_proof_cases import TinyBatchSpec, TinyBenchmarkCase, TinyOperationSpec
from core.services.scheduler.run.optimizer_proof_oracle import (
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
)
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.schedule_candidate_persistence_models import operation_log_algo_summary
from core.services.scheduler.run.schedule_optimizer import _default_runtime, optimize_schedule
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary
from core.services.scheduler.summary.summary_size_guard_fields import minimal_summary_for_size_guard

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"
_BASE_ORDER = ["B1", "B2", "B3", "B4"]


class _Clock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01) -> None:
        self._now = float(start)
        self._step = float(step)

    def __call__(self) -> float:
        current = self._now
        self._now += self._step
        return current


class _SeedAwareRandom:
    def __init__(self, seed: int) -> None:
        self._seed = int(seed)

    def randrange(self, n: int) -> int:
        if int(n) <= 0:
            return 0
        self._seed = (self._seed * 1103515245 + 12345) & 0x7FFFFFFF
        return self._seed % int(n)

    def sample(self, seq: Any, n: int) -> List[Any]:
        values = list(seq)
        if not values or int(n) <= 0:
            return []
        start = self.randrange(len(values))
        rotated = values[start:] + values[:start]
        return rotated[: int(n)]


class _StaticRandom:
    def randrange(self, n: int) -> int:
        return 0

    def sample(self, seq: Any, n: int) -> List[Any]:
        return list(seq)[: int(n)]


def _summary(results: List[ScheduleResult], *, failed_ops: int = 0) -> ScheduleSummary:
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=len(results),
        scheduled_ops=len(results),
        failed_ops=int(failed_ops),
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _result(index: int, batch_id: str, *, machine_id: str = "MC-1", operator_id: str = "OP-1") -> ScheduleResult:
    start_time = _START + timedelta(hours=index)
    return ScheduleResult(
        op_id=index + 1,
        op_code=f"{batch_id}-{index + 1}",
        batch_id=batch_id,
        seq=(index + 1) * 10,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name="cut",
    )


def _results_for_order(
    order: List[str], *, machine_id: str = "MC-1", operator_id: str = "OP-1"
) -> List[ScheduleResult]:
    return [_result(index, batch_id, machine_id=machine_id, operator_id=operator_id) for index, batch_id in enumerate(order)]


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
        slug="grasp-ig-real-greedy-improvement",
        objective_name=_OBJECTIVE,
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


def _batches(order: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        batch_id: SimpleNamespace(
            batch_id=batch_id,
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
        for batch_id in list(order or _BASE_ORDER)
    }


def _score(metrics: ScheduleMetrics, *, failed_ops: int = 0) -> Tuple[float, ...]:
    return (float(failed_ops),) + objective_score(_OBJECTIVE, metrics)


def _candidate(
    order: List[str],
    *,
    results: Optional[List[ScheduleResult]] = None,
    failed_ops: int = 0,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decoded = list(results if results is not None else _results_for_order(order))
    metrics = compute_metrics(decoded, _batches(order))
    return {
        "results": decoded,
        "summary": _summary(decoded, failed_ops=failed_ops),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": dict(params or {}),
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": list(order),
        "metrics": metrics,
        "score": _score(metrics, failed_ops=failed_ops),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
        "seed_result_count": 0,
        "locked_seed_range": [],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(order)},
    }


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
        "score": (float(summary.failed_ops),) + tuple(float(item) for item in objective_score(_OBJECTIVE, metrics)),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
        "resource_pool": {},
        "seed_result_count": 0,
        "locked_seed_range": [],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(order)},
    }


def _construction(*, grasp_restarts: int = 2, ig_restarts: int = 1) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "seed_source": "optimizer_version",
        "grasp": {
            "configured_restarts": int(grasp_restarts),
            "effective_restarts": int(grasp_restarts),
            "configured_rcl_size": 3,
            "effective_rcl_size": 3,
        },
        "iterated_greedy": {
            "configured_restarts": int(ig_restarts),
            "effective_restarts": int(ig_restarts),
            "configured_destruction_size": 2,
            "effective_destruction_size": 2,
        },
    }


def _state(*, candidate_profile: Optional[Dict[str, Any]] = None) -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile="grasp_ig",
        seed=42,
        time_budget_seconds=5,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile=candidate_profile or {"acceptance": "improve_only"},
    )


def _run_phase(
    *,
    version: int = 42,
    best: Optional[Dict[str, Any]] = None,
    candidate_construction: Optional[Dict[str, Any]] = None,
    schedule_fn: Callable[..., Any],
    strict_mode: bool = False,
    search_report_state: Optional[OptimizationSearchReportState] = None,
    valid_dispatch_rules: Optional[List[str]] = None,
    rng_factory: Optional[Callable[[int], Any]] = None,
    graph_ready_context: Optional[Any] = None,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    clock = _Clock()
    out = run_grasp_ig_candidates(
        algo_mode="improve",
        best=best,
        version=int(version),
        candidate_construction=dict(candidate_construction or _construction()),
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches=_batches(),
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: list(_BASE_ORDER),
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=list(valid_dispatch_rules or ["slack", "cr"]),
        resource_pool=None,
        objective_name=_OBJECTIVE,
        deadline=2000.0,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=bool(strict_mode),
        graph_ready_context=graph_ready_context,
        clock=clock,
        rng_factory=rng_factory or (lambda seed: _SeedAwareRandom(seed)),
        schedule_fn=schedule_fn,
        search_report_state=search_report_state,
    )
    return out, attempts, trace


def _recording_schedule(calls: List[Dict[str, Any]], *, fixed_results: Optional[List[ScheduleResult]] = None):
    def _schedule(_scheduler: Any, **kwargs: Any):
        order = list(kwargs.get("batch_order_override") or [])
        calls.append(
            {
                "order": order,
                "dispatch_mode": str(kwargs.get("dispatch_mode") or ""),
                "dispatch_rule": str(kwargs.get("dispatch_rule") or ""),
                "strategy_params": dict(kwargs.get("strategy_params") or {}),
            }
        )
        results = list(fixed_results if fixed_results is not None else _results_for_order(order))
        return results, _summary(results), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    return _schedule


class _SchedulerForOptimize:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        results = []
        summary = _summary(results)
        used_params = dict(strategy_params or {})
        used_params["dispatch_mode"] = str(kwargs.get("dispatch_mode") or "")
        used_params["dispatch_rule"] = str(kwargs.get("dispatch_rule") or "")
        return results, summary, strategy, used_params


def _cfg(**overrides: Any) -> SimpleNamespace:
    data: Dict[str, Any] = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 1.0,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "algo_mode": "improve",
        "objective": "min_overdue",
        "time_budget_seconds": 5,
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_candidate_weight_count": 5,
        "graph_selection_policy": "balanced",
        "graph_overdue_tolerance_count": 1,
        "graph_tardiness_tolerance_ratio": 0.10,
        "graph_debug_export": "no",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _cfg_svc() -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first",),
        VALID_DISPATCH_MODES=("batch_order", "sgs"),
        VALID_DISPATCH_RULES=("slack", "cr"),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


def test_grasp_ig_profile_budget_is_seeded_and_clamped() -> None:
    limits = derive_grasp_ig_limits(999)
    assert limits["seed_source"] == "optimizer_version"
    assert limits["grasp"]["configured_restarts"] == 999
    assert limits["grasp"]["effective_restarts"] == 6
    assert limits["iterated_greedy"]["configured_restarts"] == 500
    assert limits["iterated_greedy"]["effective_restarts"] == 4

    profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=42,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=False,
    )
    assert profile.profile == "vns_sa"
    assert profile.candidate_strategy_families == ("multi_start", "grasp", "iterated_greedy")
    assert profile.repair == "sgs"
    assert profile.acceptance == "improve_only"


def test_optimizer_main_entry_invokes_grasp_ig_phase_after_multi_start() -> None:
    calls: List[Dict[str, Any]] = []
    phase_order: List[str] = []

    def _run_multi_start_hook(**kwargs: Any):
        phase_order.append("multi_start")
        return kwargs.get("best")

    def _run_grasp_ig_hook(**kwargs: Any):
        phase_order.append("grasp_ig")
        calls.append(dict(kwargs))
        return kwargs.get("best")

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **kwargs: _SchedulerForOptimize(**kwargs),
        clock=_Clock(),
        rng_factory=lambda seed: _SeedAwareRandom(seed),
        run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
        run_multi_start=_run_multi_start_hook,
        run_grasp_ig_candidates=_run_grasp_ig_hook,
        run_local_search=lambda **kwargs: kwargs.get("best"),
    )

    assert _default_runtime().run_grasp_ig_candidates is not None
    outcome = optimize_schedule(
        calendar_service=SimpleNamespace(),
        cfg_svc=_cfg_svc(),
        cfg=_cfg(),
        algo_ops_to_schedule=[],
        batches=_batches(),
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=42,
        logger=None,
        _runtime=runtime,
    )

    assert len(calls) == 1
    assert phase_order == ["multi_start", "grasp_ig"]
    call = calls[0]
    assert call["algo_mode"] == "improve"
    assert call["version"] == 42
    assert call["batch_order_enabled"] is True
    assert call["candidate_construction"]["grasp"]["effective_restarts"] == 5
    assert outcome.search_report["algorithm_profile"] == "vns_sa"


def test_optimizer_main_entry_does_not_leak_candidate_construction_through_used_params() -> None:
    runtime = OptimizerRuntime(
        scheduler_factory=lambda **kwargs: _SchedulerForOptimize(**kwargs),
        clock=_Clock(),
        rng_factory=lambda seed: _SeedAwareRandom(seed),
        run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
        run_multi_start=lambda **kwargs: kwargs.get("best"),
        run_grasp_ig_candidates=run_grasp_ig_candidates,
        run_local_search=lambda **kwargs: kwargs.get("best"),
    )

    outcome = optimize_schedule(
        calendar_service=SimpleNamespace(),
        cfg_svc=_cfg_svc(),
        cfg=_cfg(),
        algo_ops_to_schedule=[],
        batches=_batches(),
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=42,
        logger=None,
        _runtime=runtime,
    )

    assert outcome.search_report["best_origin"] in {"grasp", "ig"}
    assert "candidate_construction" not in outcome.used_params
    exposed_text = json.dumps(
        {
            "result_summary_strategy_params": outcome.used_params,
            "service_result_strategy_params": outcome.used_params,
            "operation_log_strategy_params": outcome.used_params,
            "attempts": outcome.attempts,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "candidate_construction" not in exposed_text


def test_grasp_ig_candidates_are_deterministic_by_seed_and_decode_with_batch_order() -> None:
    first_calls: List[Dict[str, Any]] = []
    second_calls: List[Dict[str, Any]] = []
    third_calls: List[Dict[str, Any]] = []

    _run_phase(version=42, schedule_fn=_recording_schedule(first_calls))
    _run_phase(version=42, schedule_fn=_recording_schedule(second_calls))
    _run_phase(version=43, schedule_fn=_recording_schedule(third_calls))

    assert first_calls == second_calls
    assert [call["order"] for call in first_calls] != [call["order"] for call in third_calls]
    assert len(first_calls) == 3
    assert {call["dispatch_mode"] for call in first_calls} == {"batch_order"}
    assert all("candidate_construction" in call["strategy_params"] for call in first_calls)


def test_duplicate_grasp_ig_candidate_specs_are_deduped_before_decode() -> None:
    construction = _construction(grasp_restarts=3, ig_restarts=0)
    construction["grasp"]["effective_rcl_size"] = 1
    calls: List[Dict[str, Any]] = []

    _run_phase(
        candidate_construction=construction,
        schedule_fn=_recording_schedule(calls),
        valid_dispatch_rules=["slack"],
        rng_factory=lambda _seed: _StaticRandom(),
    )

    assert len(calls) == 1
    assert calls[0]["order"] == _BASE_ORDER
    assert calls[0]["dispatch_mode"] == "batch_order"


def test_grasp_ig_decode_validation_error_is_rejected_or_fail_loud() -> None:
    def _failing_schedule(_scheduler: Any, **_kwargs: Any):
        raise ValidationError("SGS 解码失败", field="resource")

    state = _state()
    out, attempts, _trace = _run_phase(
        candidate_construction=_construction(grasp_restarts=1, ig_restarts=0),
        schedule_fn=_failing_schedule,
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=[])
    assert out is None
    assert report["rejected_candidates"] == 1
    assert report["rejection_summary"]["validation_error"] == 1
    assert attempts[0]["source"] == "candidate_rejected"
    assert attempts[0]["tag"].startswith("grasp:")

    with pytest.raises(ValidationError):
        _run_phase(
            candidate_construction=_construction(grasp_restarts=1, ig_restarts=0),
            schedule_fn=_failing_schedule,
            strict_mode=True,
        )


def test_collapsed_grasp_ig_outputs_do_not_inflate_distinct_or_improved() -> None:
    collapsed_results = _results_for_order(_BASE_ORDER)
    baseline = _candidate(_BASE_ORDER, results=collapsed_results)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")

    best, attempts, trace = _run_phase(
        best=baseline,
        candidate_construction=_construction(grasp_restarts=2, ig_restarts=1),
        schedule_fn=_recording_schedule([], fixed_results=collapsed_results),
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert best is baseline
    assert report["evaluated_candidates"] == 4
    assert report["distinct_candidates"] == 1
    assert report["accepted_candidates"] == 1
    assert report["accepted_distinct_candidates"] == 1
    assert report["rejection_summary"]["same_fingerprint"] == 3
    assert report["best_origin"] == "multi_start"
    assert report["improved"] is False


def test_grasp_ig_uses_unified_candidate_tie_breaker_for_changed_same_score_output() -> None:
    baseline = _candidate(_BASE_ORDER)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")
    changed_results = _results_for_order(["B4", "B3", "B2", "B1"])

    best, attempts, trace = _run_phase(
        best=baseline,
        candidate_construction=_construction(grasp_restarts=1, ig_restarts=0),
        schedule_fn=_recording_schedule([], fixed_results=changed_results),
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert best is not baseline
    assert best is not None
    assert best["score"] == baseline["score"]
    assert report["best_origin"] == "grasp"
    assert report["best_fingerprint_changed"] is True
    assert report["improvement_conditions"]["score_strictly_better"] is False
    assert report["improved"] is False


def test_best_origin_can_report_grasp_when_batch_order_decoded_candidate_really_improves() -> None:
    baseline = _candidate(_BASE_ORDER, failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")

    _best, attempts, trace = _run_phase(
        best=baseline,
        candidate_construction=_construction(grasp_restarts=1, ig_restarts=0),
        schedule_fn=_recording_schedule([]),
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert report["best_origin"] == "grasp"
    assert report["accepted_candidates"] == 2
    assert report["improvement_conditions"] == {
        "fingerprint_changed": True,
        "score_strictly_better": True,
        "acceptance": "improve_only",
        "acceptance_passed": False,
    }
    assert report["acceptance_events"] == []
    assert report["improved"] is False


def test_grasp_ig_real_greedy_candidate_improves_batch_order_path() -> None:
    case = _improvable_batch_order_case()
    baseline = _real_candidate_for_order(["batch-a", "batch-d", "batch-b", "batch-c"])
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    construction = _construction(grasp_restarts=1, ig_restarts=0)
    construction["grasp"]["effective_rcl_size"] = 1

    best = run_grasp_ig_candidates(
        algo_mode="improve",
        best=baseline,
        version=1,
        candidate_construction=construction,
        scheduler=GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config()),
        algo_ops_to_schedule=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case),
        start_dt=case.start_dt,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: ["batch-a", "batch-b", "batch-c", "batch-d"],
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack"],
        resource_pool=None,
        objective_name=_OBJECTIVE,
        deadline=2000.0,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=None,
        clock=_Clock(),
        rng_factory=lambda _seed: _StaticRandom(),
        schedule_fn=lambda scheduler, **kwargs: scheduler.schedule(**kwargs),
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert best is not None
    assert best["score"] < baseline["score"]
    assert best["dispatch_mode"] == "batch_order"
    assert report["best_origin"] == "grasp"
    assert report["improvement_conditions"]["acceptance_passed"] is False
    assert report["acceptance_events"] == []
    assert report["improved"] is False


def test_best_origin_can_report_ig_when_iterated_greedy_candidate_really_improves() -> None:
    baseline = _candidate(_BASE_ORDER, failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")
    calls: List[Dict[str, Any]] = []

    def _schedule(_scheduler: Any, **kwargs: Any):
        order = list(kwargs.get("batch_order_override") or [])
        calls.append({"order": order, "dispatch_mode": str(kwargs.get("dispatch_mode") or "")})
        failed_ops = 1 if len(calls) == 1 else 0
        results = _results_for_order(order)
        return results, _summary(results, failed_ops=failed_ops), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    _best, attempts, trace = _run_phase(
        best=baseline,
        candidate_construction=_construction(grasp_restarts=1, ig_restarts=1),
        schedule_fn=_schedule,
        search_report_state=state,
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert [attempt["tag"].split(":", 1)[0] for attempt in attempts] == ["grasp", "ig"]
    assert {call["dispatch_mode"] for call in calls} == {"batch_order"}
    assert report["best_origin"] == "ig"
    assert report["accepted_candidates"] == 2
    assert report["improvement_conditions"]["acceptance_passed"] is False
    assert report["acceptance_events"] == []
    assert report["improved"] is False


def test_grasp_ig_skips_graph_ready_path_until_graph_neighborhood_exists() -> None:
    state = _state()
    best = _candidate(_BASE_ORDER)
    state.mark_candidate_accepted(best, origin="multi_start")
    calls: List[Dict[str, Any]] = []

    out, attempts, trace = _run_phase(
        best=best,
        candidate_construction=_construction(grasp_restarts=1, ig_restarts=0),
        schedule_fn=_recording_schedule(calls),
        search_report_state=state,
        graph_ready_context={"enabled": True},
    )
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=trace)

    assert out is best
    assert calls == []
    assert report["skipped_phases"] == [
        {"phase": "grasp_ig_candidate_construction", "reason": "graph_ready_uses_graph_candidate_phase"}
    ]


def test_candidate_construction_metadata_splits_decision_fingerprint_but_not_output_fingerprint() -> None:
    results = _results_for_order(_BASE_ORDER)
    grasp = _candidate(
        _BASE_ORDER,
        results=results,
        params={"candidate_construction": {"family": "grasp", "restart_index": 0, "rcl_size": 3}},
    )
    grasp["mutable_scope"] = {
        "scope": "candidate_construction_batch_order",
        "batch_count": len(_BASE_ORDER),
        "candidate_source": "grasp",
        "restart_index": 0,
    }
    ig = _candidate(
        _BASE_ORDER,
        results=results,
        params={"candidate_construction": {"family": "iterated_greedy", "restart_index": 0, "destruction_size": 2}},
    )
    ig["mutable_scope"] = {
        "scope": "candidate_construction_batch_order",
        "batch_count": len(_BASE_ORDER),
        "candidate_source": "iterated_greedy",
        "restart_index": 0,
    }

    grasp_fp = build_candidate_fingerprint(grasp, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    ig_fp = build_candidate_fingerprint(ig, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    assert grasp_fp.decision_fingerprint != ig_fp.decision_fingerprint
    assert grasp_fp.output_fingerprint == ig_fp.output_fingerprint


def test_grasp_ig_public_operation_log_and_size_guard_do_not_leak_raw_inputs() -> None:
    profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=42,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=False,
    )
    secret_order = ["B-INTERNAL-1", "B-INTERNAL-2"]
    secret_results = _results_for_order(secret_order, machine_id="MC-SECRET", operator_id="OP-SECRET")
    baseline = _candidate(secret_order, results=secret_results, failed_ops=1)
    better = _candidate(list(reversed(secret_order)), results=secret_results)
    state = _state(candidate_profile=profile.to_report_dict())
    state.mark_candidate_accepted(baseline, origin="multi_start")
    state.mark_candidate_accepted(better, origin="grasp")
    attempts = [
        {
            "tag": "grasp:r0|batch_order:slack",
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "used_params": {"candidate_construction": {"raw_order": secret_order}},
            "score": list(better["score"]),
            "failed_ops": 0,
            "metrics": better["metrics"].to_dict(),
        }
    ]
    report = state.finalize(runtime_ms=10, attempts=attempts, improvement_trace=[{"raw_order": secret_order}])

    public, diagnostics = project_search_report(report)
    assert public["profile_public"]["candidate_strategy_families"] == ["multi_start", "grasp", "iterated_greedy"]
    assert diagnostics["profile_diagnostics"]["candidate_construction"]["grasp"]["effective_restarts"] == 5
    assert diagnostics["best_candidate_fingerprint"]["output_fingerprint"]

    public_log = operation_log_algo_summary({"algo": {"search_report": report}})
    minimal = minimal_summary_for_size_guard({"algo": {"search_report": report}}, original_size=999999, diagnostics_truncated=True)
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    public_log_text = json.dumps(public_log, ensure_ascii=False, sort_keys=True)
    minimal_text = json.dumps(minimal["algo"]["search_report"], ensure_ascii=False, sort_keys=True)
    for text in (public_text, public_log_text, minimal_text):
        for forbidden in (
            "decision_fingerprint",
            "output_fingerprint",
            "parent_fingerprint",
            "MC-SECRET",
            "OP-SECRET",
            "B-INTERNAL",
            "raw_order",
            "candidate_construction",
        ):
            assert forbidden not in text


def test_grasp_ig_attempt_source_labels_are_safe_public_text() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "attempts": [
                {
                    "tag": "grasp:r0|batch_order:slack",
                    "strategy": "priority_first",
                    "dispatch_mode": "batch_order",
                    "dispatch_rule": "slack",
                    "used_params": {"candidate_construction": {"raw_order": ["B-INTERNAL"]}},
                    "score": [0.0],
                    "failed_ops": 0,
                    "metrics": {"overdue_count": 0},
                },
                {
                    "tag": "ig:r0|batch_order:cr",
                    "strategy": "priority_first",
                    "dispatch_mode": "batch_order",
                    "dispatch_rule": "cr",
                    "used_params": {"candidate_construction": {"raw_order": ["B-INTERNAL"]}},
                    "score": [0.0],
                    "failed_ops": 0,
                    "metrics": {"overdue_count": 0},
                },
            ]
        }
    )

    attempts = public_algo["attempts"]
    assert attempts[0]["source_label"] == "GRASP（贪心随机自适应搜索）候选起点"
    assert attempts[1]["source_label"] == "迭代贪心候选起点"
    assert "used_params" not in attempts[0]
    public_text = json.dumps(public_algo, ensure_ascii=False, sort_keys=True)
    assert "B-INTERNAL" not in public_text
    assert diagnostics["optimizer"]["attempts"][0]["tag"] == "grasp:r0|batch_order:slack"
