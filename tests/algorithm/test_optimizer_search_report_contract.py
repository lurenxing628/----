"""回归测试：OptimizationSearchReport 合同。

本文件只守 item 3 搜索报告合同：每个成功 OptimizationOutcome 都带明确 search_report；
strict ValidationError 仍 fail-loud；public 投影只给安全摘要，内部 fingerprint/raw attempts 留 diagnostics。
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest import mock

import pytest

from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.schedule_candidate_persistence_models import operation_log_algo_summary
from core.services.scheduler.run.schedule_optimizer import optimize_schedule
from core.services.scheduler.run.schedule_optimizer_steps import _run_multi_start, _run_ortools_warmstart
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


class _Clock:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01) -> None:
        self._now = float(start)
        self._step = float(step)

    def __call__(self) -> float:
        current = self._now
        self._now += self._step
        return current


class _ConstantClock:
    def __call__(self) -> float:
        return 1000.0


class _Scheduler:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        summary = SimpleNamespace(
            success=True,
            total_ops=int(len(operations or [])),
            scheduled_ops=int(len(operations or [])),
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        used_params = dict(strategy_params or {})
        used_params["dispatch_mode"] = str(kwargs.get("dispatch_mode") or "")
        used_params["dispatch_rule"] = str(kwargs.get("dispatch_rule") or "")
        return [], summary, strategy, used_params


class _RejectingSgsScheduler(_Scheduler):
    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        if str(kwargs.get("dispatch_mode") or "") == "sgs":
            raise ValidationError("SGS 候选缺少资源", field="resource")
        return super().schedule(operations, batches, strategy=strategy, strategy_params=strategy_params, **kwargs)


class _DeterministicRandom:
    def random(self):
        return 0.1

    def sample(self, seq, n):
        return [0, 1]

    def randrange(self, n):
        return 0

    def randint(self, a, b):
        return a


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


def _cfg_svc(*, dispatch_modes=("batch_order",), dispatch_rules=("slack",)) -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first",),
        VALID_DISPATCH_MODES=tuple(dispatch_modes),
        VALID_DISPATCH_RULES=tuple(dispatch_rules),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


def _batches() -> Dict[str, Any]:
    return {
        "B1": SimpleNamespace(
            batch_id="B1",
            priority="normal",
            due_date="2026-01-02",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
    }


def _runtime(
    *,
    scheduler_factory=lambda **kwargs: _Scheduler(**kwargs),
    clock: Optional[Any] = None,
    run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
    run_multi_start=lambda **kwargs: kwargs.get("best"),
    run_local_search=lambda **kwargs: kwargs.get("best"),
) -> OptimizerRuntime:
    return OptimizerRuntime(
        scheduler_factory=scheduler_factory,
        clock=clock or _Clock(),
        rng_factory=lambda _seed: _DeterministicRandom(),
        run_ortools_warmstart=run_ortools_warmstart,
        run_multi_start=run_multi_start,
        run_local_search=run_local_search,
    )


def _optimize(**kwargs: Any):
    params: Dict[str, Any] = {
        "calendar_service": SimpleNamespace(),
        "cfg_svc": _cfg_svc(),
        "cfg": _cfg(),
        "algo_ops_to_schedule": [],
        "batches": _batches(),
        "start_dt": datetime(2026, 1, 1, 8, 0, 0),
        "end_date": None,
        "downtime_map": {},
        "seed_results": [],
        "resource_pool": None,
        "version": 42,
        "logger": None,
        "_runtime": _runtime(),
    }
    params.update(kwargs)
    return optimize_schedule(**params)


def _required_report_fields() -> set:
    return {
        "schema_version",
        "algorithm_profile",
        "seed",
        "stop_reason",
        "best_origin",
        "time_budget_seconds",
        "runtime_ms",
        "iterations",
        "evaluated_candidates",
        "distinct_candidates",
        "accepted_candidates",
        "accepted_distinct_candidates",
        "rejected_candidates",
        "initial_fingerprint",
        "best_fingerprint",
        "initial_candidate_fingerprint",
        "best_candidate_fingerprint",
        "distinct_fingerprint_scope",
        "distinct_fingerprint_description",
        "best_fingerprint_changed",
        "best_score",
        "objective_name",
        "attempts",
        "public_attempt_summary",
        "improvement_trace",
        "fingerprint_events",
        "neighborhood_moves",
        "neighborhood_summary",
        "improvement_conditions",
        "skipped_phases",
        "rejection_summary",
    }


def test_every_optimizer_outcome_has_baseline_search_report() -> None:
    outcome = _optimize(_runtime=_runtime())

    report = outcome.search_report
    assert _required_report_fields() <= set(report)
    assert report["stop_reason"] == "baseline_scheduled"
    assert report["best_origin"] == "baseline"
    assert report["seed"] == 42
    assert report["evaluated_candidates"] == 1
    assert report["accepted_candidates"] == 1


def test_multi_start_success_records_evaluated_candidates_and_best_origin() -> None:
    outcome = _optimize(
        _runtime=_runtime(run_multi_start=_run_multi_start),
        cfg_svc=_cfg_svc(dispatch_modes=("batch_order",), dispatch_rules=("slack",)),
    )

    report = outcome.search_report
    assert report["best_origin"] == "multi_start"
    assert report["stop_reason"] == "completed"
    assert report["evaluated_candidates"] >= 1
    assert report["distinct_candidates"] >= 1
    assert report["accepted_candidates"] >= 1


def test_optional_warmstart_failure_is_diagnostic_and_does_not_override_best_origin() -> None:
    with mock.patch(
        "core.algorithms.ortools_bottleneck.try_solve_bottleneck_batch_order",
        side_effect=RuntimeError("optional warmstart boom"),
    ):
        outcome = _optimize(
            cfg=_cfg(ortools_enabled="yes"),
            _runtime=_runtime(
                run_ortools_warmstart=_run_ortools_warmstart,
                run_multi_start=_run_multi_start,
            ),
        )

    report = outcome.search_report
    assert report["best_origin"] == "multi_start"
    assert report["stop_reason"] != "optional_warmstart_failed"
    assert report["rejection_summary"]["optional_warmstart_failed"] == 1
    assert any(attempt.get("source") == "candidate_rejected" for attempt in report["attempts"])


def test_non_strict_candidate_rejected_increments_report_rejections() -> None:
    outcome = _optimize(
        cfg_svc=_cfg_svc(dispatch_modes=("batch_order", "sgs"), dispatch_rules=("slack",)),
        _runtime=_runtime(
            scheduler_factory=lambda **kwargs: _RejectingSgsScheduler(**kwargs),
            run_multi_start=_run_multi_start,
        ),
    )

    report = outcome.search_report
    assert report["best_origin"] == "multi_start"
    assert report["rejected_candidates"] == 1
    assert report["rejection_summary"]["validation_error"] == 1
    assert any(attempt.get("source") == "candidate_rejected" for attempt in report["attempts"])


def test_strict_validation_error_remains_fail_loud() -> None:
    with pytest.raises(ValidationError):
        _optimize(
            cfg=_cfg(dispatch_mode="sgs"),
            cfg_svc=_cfg_svc(dispatch_modes=("sgs",), dispatch_rules=("slack",)),
            strict_mode=True,
            _runtime=_runtime(
                scheduler_factory=lambda **kwargs: _RejectingSgsScheduler(**kwargs),
                run_multi_start=_run_multi_start,
            ),
        )


def _best_candidate() -> Dict[str, Any]:
    return {
        "results": [],
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0,),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }


def _non_improving_schedule(*args: Any, **kwargs: Any):
    summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=1, warnings=[], errors=[])
    return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})


def test_local_search_time_budget_and_iteration_limit_are_reported() -> None:
    best = _best_candidate()
    time_state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=7,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
    )
    time_state.mark_candidate_accepted(best, origin="multi_start")
    run_local_search(
        algo_mode="improve",
        best=best,
        version=7,
        time_budget_seconds=1,
        deadline=1000.05,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
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
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_Clock(start=1000.0, step=0.02),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_non_improving_schedule,
        search_report_state=time_state,
    )
    assert time_state.finalize(runtime_ms=50, attempts=[], improvement_trace=[])["stop_reason"] == "time_budget"

    iteration_state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=8,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
    )
    iteration_state.mark_candidate_accepted(best, origin="multi_start")
    run_local_search(
        algo_mode="improve",
        best=best,
        version=8,
        time_budget_seconds=1,
        deadline=2000.0,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
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
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_ConstantClock(),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_non_improving_schedule,
        search_report_state=iteration_state,
    )
    report = iteration_state.finalize(runtime_ms=50, attempts=[], improvement_trace=[])
    assert report["stop_reason"] == "iteration_limit"
    assert report["iterations"] == 200


def test_no_improvement_stop_reason_when_local_search_entered_without_gain() -> None:
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=11,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
    )
    state.mark_candidate_accepted(_best_candidate(), origin="multi_start")
    state.local_search_entered = True
    state.local_search_improved = False

    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["stop_reason"] == "no_improvement"
    assert report["best_origin"] == "multi_start"


def test_all_candidates_rejected_stop_reason_when_nothing_accepted() -> None:
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=12,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
    )
    state.mark_candidate_rejected(reason="validation_error")
    state.mark_candidate_rejected(reason="noop_neighbor")

    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["stop_reason"] == "all_candidates_rejected"
    assert report["accepted_candidates"] == 0
    assert report["rejected_candidates"] == 2


def test_local_search_skipped_phase_is_reported() -> None:
    state = OptimizationSearchReportState(
        algorithm_profile="baseline",
        seed=9,
        time_budget_seconds=1,
        objective_name="min_overdue",
        started_at=1000.0,
    )

    run_local_search(
        algo_mode="greedy",
        best=_best_candidate(),
        version=9,
        time_budget_seconds=1,
        deadline=float("inf"),
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
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
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_ConstantClock(),
        rng_factory=lambda _seed: _DeterministicRandom(),
        schedule_fn=_non_improving_schedule,
        search_report_state=state,
    )

    assert state.skipped_phases == [{"phase": "local_search", "reason": "algo_mode_not_improve"}]


def test_search_report_public_projection_keeps_internal_fields_in_diagnostics_only() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "search_report": {
                "schema_version": 1,
                "algorithm_profile": "multi_start_local_search",
                "seed": 42,
                "stop_reason": "time_budget",
                "best_origin": "local_search",
                "time_budget_seconds": 5,
                "runtime_ms": 5010,
                "iterations": 200,
                "evaluated_candidates": 10,
                "distinct_candidates": 3,
                "accepted_candidates": 2,
                "accepted_distinct_candidates": 2,
                "rejected_candidates": 7,
                "initial_fingerprint": "internal-fp-op:SECRET",
                "best_fingerprint": "internal-best-fp",
                "initial_candidate_fingerprint": {
                    "decision_fingerprint": "decision-op:SECRET",
                    "output_fingerprint": "output-op:SECRET",
                },
                "best_candidate_fingerprint": {
                    "decision_fingerprint": "decision-best",
                    "output_fingerprint": "output-best",
                },
                "distinct_fingerprint_scope": "decoded_output",
                "distinct_fingerprint_description": "distinct_candidates 按正式 SGS 解码结果去重",
                "best_fingerprint_changed": True,
                "best_score": [0.0, "op:SECRET"],
                "objective_name": "min_overdue",
                "attempts": [{"tag": "local:swap", "candidate_id": "CANDIDATE-SECRET"}],
                "public_attempt_summary": [
                    {
                        "origin": "local_search",
                        "status": "accepted",
                        "strategy": "priority_first",
                        "dispatch_mode": "sgs",
                        "dispatch_rule": "slack",
                        "score": [0.0],
                        "failed_ops": 0,
                    }
                ],
                "improvement_trace": [{"candidate_id": "CANDIDATE-SECRET"}],
                "fingerprint_events": [{"output_fingerprint": "output-op:SECRET"}],
                "neighborhood_moves": [
                    {
                        "neighborhood_name": "critical_chain",
                        "move_kind": "pull_latest_chain_batch",
                        "diagnostics": {"op_id": "op:SECRET", "machine_id": "MC-SECRET"},
                    }
                ],
                "neighborhood_summary": {
                    "critical_chain": {"attempted": 2, "effective": 1, "noop": 1, "fallback": 0, "rejected": 1},
                    "op:SECRET": {"attempted": 9},
                },
                "improvement_conditions": {"acceptance": "improve_only"},
                "skipped_phases": [{"phase": "ortools_warmstart", "reason": "time_budget", "op_id": 1}],
                "rejection_summary": {"noop_neighbor": 7, "op_id": 1},
                "improved": True,
            }
        }
    )

    public_report = public_algo["search_report"]
    public_text = json.dumps(public_report, ensure_ascii=False, sort_keys=True)
    for forbidden in ("op:", "candidate_id", "initial_fingerprint", '"best_fingerprint"', "attempts_public", '"attempts"'):
        assert forbidden not in public_text
    assert public_report["stop_reason"] == "time_budget"
    assert public_report["best_origin"] == "local_search"
    assert public_report["distinct_fingerprint_scope"] == "decoded_output"
    assert public_report["best_score"] == [0.0]
    assert public_report["rejection_summary"] == {"noop_neighbor": 7}
    assert public_report["public_attempt_summary"][0]["origin"] == "local_search"
    assert public_report["neighborhood_summary"] == {
        "critical_chain": {"attempted": 2, "effective": 1, "noop": 1, "fallback": 0, "rejected": 1}
    }

    diagnostic_report = diagnostics["optimizer"]["search_report"]
    assert diagnostic_report["initial_fingerprint"] == "internal-fp-op:SECRET"
    assert diagnostic_report["best_fingerprint"] == "internal-best-fp"
    assert diagnostic_report["best_candidate_fingerprint"]["output_fingerprint"] == "output-best"
    assert diagnostic_report["fingerprint_events"][0]["output_fingerprint"] == "output-op:SECRET"
    assert diagnostic_report["neighborhood_moves"][0]["diagnostics"]["op_id"] == "op:SECRET"
    assert diagnostic_report["improvement_conditions"]["acceptance"] == "improve_only"
    assert diagnostic_report["attempts"][0]["candidate_id"] == "CANDIDATE-SECRET"


def test_operation_log_algo_summary_keeps_search_report_public_only() -> None:
    summary = {
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "search_report": {
                "stop_reason": "time_budget",
                "best_origin": "local_search",
                "runtime_ms": 5010,
                "evaluated_candidates": 10,
                "initial_fingerprint": "internal-fp-op:SECRET",
                "best_fingerprint": "internal-best-fp",
                "attempts": [{"candidate_id": "CANDIDATE-SECRET"}],
                "neighborhood_summary": {
                    "critical_chain": {"attempted": 2, "effective": 1, "noop": 1, "fallback": 0, "rejected": 1}
                },
                "neighborhood_moves": [
                    {
                        "neighborhood_name": "critical_chain",
                        "move_kind": "pull_latest_chain_batch",
                        "diagnostics": {"op_id": "op:SECRET", "machine_id": "MC-SECRET"},
                    }
                ],
            },
        },
        "diagnostics": {
            "optimizer": {
                "search_report": {
                    "attempts": [{"candidate_id": "CANDIDATE-SECRET"}],
                }
            }
        },
    }

    public_log_algo = operation_log_algo_summary(summary)
    public_text = json.dumps(public_log_algo, ensure_ascii=False, sort_keys=True)
    assert public_log_algo["search_report"]["stop_reason"] == "time_budget"
    assert public_log_algo["search_report"]["neighborhood_summary"]["critical_chain"]["attempted"] == 2
    for forbidden in ("op:", "machine_id", "candidate_id", "initial_fingerprint", '"best_fingerprint"', '"attempts"'):
        assert forbidden not in public_text
