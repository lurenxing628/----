from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict

from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.schedule_optimizer import optimize_schedule


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=0.8,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        objective="min_overdue",
        time_budget_seconds=5,
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def _cfg_svc() -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "weighted", "fifo", "edd"),
        VALID_DISPATCH_MODES=("batch_order", "sgs"),
        VALID_DISPATCH_RULES=("slack", "cr"),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


class _Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return 1000.0 + self.calls


class _Scheduler:
    def __init__(self, *, calls: Dict[str, Any], calendar_service: Any, config_service: Any, logger: Any) -> None:
        calls["factory"] = {
            "calendar_service": calendar_service,
            "config_service": config_service,
            "logger": logger,
        }
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, **kwargs):
        summary = SimpleNamespace(
            success=True,
            total_ops=0,
            scheduled_ops=0,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})


def test_optimizer_uses_explicit_runtime_seam_without_global_monkeypatch() -> None:
    calls: Dict[str, Any] = {}
    clock = _Clock()

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **kwargs: _Scheduler(calls=calls, **kwargs),
        clock=clock,
        rng_factory=lambda _seed: None,
        run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
        run_multi_start=lambda **kwargs: kwargs.get("best"),
        run_local_search=lambda **kwargs: kwargs.get("best"),
    )

    outcome = optimize_schedule(
        calendar_service=SimpleNamespace(name="calendar"),
        cfg_svc=_cfg_svc(),
        cfg=_cfg(),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=1,
        logger=None,
        strict_mode=False,
        _runtime=runtime,
    )

    assert outcome.objective_name == "min_overdue"
    assert calls["factory"]["config_service"].objective == "min_overdue"
    assert clock.calls >= 1
