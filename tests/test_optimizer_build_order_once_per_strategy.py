from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_optimizer_steps import _run_multi_start, _run_ortools_warmstart


class _Scheduler:
    def __init__(self) -> None:
        self.calls = []
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        self.calls.append((getattr(strategy, "value", str(strategy)), kwargs.get("dispatch_mode"), kwargs.get("dispatch_rule")))
        summary = SimpleNamespace(
            success=True,
            total_ops=int(len(operations or [])),
            scheduled_ops=int(len(operations or [])),
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return [], summary, strategy, dict(strategy_params or {})


class _RejectingSgsScheduler(_Scheduler):
    def schedule(self, operations, batches, strategy=None, strategy_params=None, **kwargs):
        self.calls.append((getattr(strategy, "value", str(strategy)), kwargs.get("dispatch_mode"), kwargs.get("dispatch_rule")))
        if kwargs.get("dispatch_mode") == "sgs":
            raise ValidationError("SGS 候选缺少资源", field="resource")
        summary = SimpleNamespace(
            success=False,
            total_ops=int(len(operations or [])),
            scheduled_ops=0,
            failed_ops=1,
            warnings=[],
            errors=["batch_order 正常失败"],
            duration_seconds=0.0,
        )
        return [], summary, strategy, dict(strategy_params or {})


def _strict_optimizer_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=1.0,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        algo_mode="improve",
        objective="min_overdue",
        time_budget_seconds=1,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def test_build_order_is_cached_per_strategy_within_single_multi_start_call():
    scheduler = _Scheduler()
    build_calls = []

    def _build_order(strategy, params):
        build_calls.append((strategy.value, tuple(sorted((params or {}).items()))))
        return ["B1"]

    def _invoke_multi_start() -> dict[str, object] | None:
        return _run_multi_start(
            keys=["priority_first"],
            dispatch_modes=["batch_order", "sgs"],
            dispatch_rule_cfg="slack",
            valid_dispatch_rules=["slack", "cr"],
            scheduler=scheduler,
            algo_ops_to_schedule=[],
            batches={"B1": SimpleNamespace(batch_id="B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            cfg={},
            resource_pool=None,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            build_order=_build_order,
            optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
            strict_mode=False,
        )

    best = _invoke_multi_start()
    assert best is not None
    assert len(build_calls) == 1
    assert scheduler.calls == [
        (SortStrategy.PRIORITY_FIRST.value, "batch_order", "slack"),
        (SortStrategy.PRIORITY_FIRST.value, "sgs", "slack"),
        (SortStrategy.PRIORITY_FIRST.value, "sgs", "cr"),
    ]

    _invoke_multi_start()
    assert len(build_calls) == 2, "第二次 multi-start 调用不应复用上一次的本地缓存"


def test_multi_start_records_optional_sgs_validation_error_without_losing_primary_best():
    scheduler = _RejectingSgsScheduler()
    attempts = []

    best = _run_multi_start(
        keys=["priority_first"],
        dispatch_modes=["batch_order", "sgs"],
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack"],
        scheduler=scheduler,
        algo_ops_to_schedule=[object()],
        batches={"B1": SimpleNamespace(batch_id="B1")},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        cfg={},
        resource_pool=None,
        objective_name="min_overdue",
        deadline=time.time() + 30,
        attempts=attempts,
        improvement_trace=[],
        best=None,
        t_begin=time.time(),
        build_order=lambda strategy, params: ["B1"],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        strict_mode=False,
    )

    assert best is not None
    assert best["dispatch_mode"] == "batch_order"
    rejected = [attempt for attempt in attempts if attempt.get("source") == "candidate_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["tag"] == "start:priority_first|sgs:slack"
    assert rejected[0]["origin"]["field"] == "resource"
    assert "score" not in rejected[0]


def test_multi_start_strict_mode_raises_non_primary_sgs_validation_error():
    scheduler = _RejectingSgsScheduler()

    with pytest.raises(ValidationError) as exc_info:
        _run_multi_start(
            keys=["priority_first"],
            dispatch_modes=["batch_order", "sgs"],
            dispatch_rule_cfg="slack",
            valid_dispatch_rules=["slack"],
            scheduler=scheduler,
            algo_ops_to_schedule=[object()],
            batches={"B1": SimpleNamespace(batch_id="B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            cfg=_strict_optimizer_cfg(),
            resource_pool=None,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            build_order=lambda strategy, params: ["B1"],
            optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
            strict_mode=True,
        )

    assert exc_info.value.field == "resource"
    assert scheduler.calls == [
        (SortStrategy.PRIORITY_FIRST.value, "batch_order", "slack"),
        (SortStrategy.PRIORITY_FIRST.value, "sgs", "slack"),
    ]


def test_multi_start_raises_primary_sgs_validation_error_without_fallback_to_batch_order():
    scheduler = _RejectingSgsScheduler()

    with pytest.raises(ValidationError) as exc_info:
        _run_multi_start(
            keys=["priority_first"],
            dispatch_modes=["sgs", "batch_order"],
            dispatch_rule_cfg="slack",
            valid_dispatch_rules=["slack"],
            scheduler=scheduler,
            algo_ops_to_schedule=[object()],
            batches={"B1": SimpleNamespace(batch_id="B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            cfg={},
            resource_pool=None,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            build_order=lambda strategy, params: ["B1"],
            optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
            strict_mode=False,
        )

    assert exc_info.value.field == "resource"
    assert scheduler.calls == [(SortStrategy.PRIORITY_FIRST.value, "sgs", "slack")]


def test_multi_start_partial_object_cfg_is_normalized_before_weighted_params():
    scheduler = _Scheduler()
    build_calls = []

    def _build_order(strategy, params):
        build_calls.append((strategy.value, dict(params or {})))
        return ["B1"]

    best = _run_multi_start(
        keys=["weighted"],
        dispatch_modes=["batch_order"],
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack", "cr"],
        scheduler=scheduler,
        algo_ops_to_schedule=[],
        batches={"B1": SimpleNamespace(batch_id="B1")},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        cfg=SimpleNamespace(sort_strategy="weighted", objective="min_overdue"),
        resource_pool=None,
        objective_name="min_overdue",
        deadline=time.time() + 30,
        attempts=[],
        improvement_trace=[],
        best=None,
        t_begin=time.time(),
        build_order=_build_order,
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        strict_mode=False,
    )

    assert best is not None
    assert build_calls == [
        (
            SortStrategy.WEIGHTED.value,
            {
                "priority_weight": 0.4,
                "due_weight": 0.5,
            },
        )
    ]


def test_ortools_partial_object_cfg_strict_error_is_not_swallowed_as_warmstart_failure():
    optimizer_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    with pytest.raises(ValidationError):
        _run_ortools_warmstart(
            algo_mode="improve",
            cfg=SimpleNamespace(sort_strategy="weighted", objective="min_overdue", ortools_enabled="yes"),
            strategy_enum=SortStrategy.WEIGHTED,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            scheduler=_Scheduler(),
            algo_ops_to_schedule=[],
            batches={"B1": SimpleNamespace(batch_id="B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            dispatch_mode_cfg="batch_order",
            dispatch_rule_cfg="slack",
            resource_pool=None,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            logger=None,
            optimizer_algo_stats=optimizer_algo_stats,
            strict_mode=True,
        )

    assert not optimizer_algo_stats["fallback_counts"], "strict 配置错误不应被记成 OR-Tools 预热失败"


def test_ortools_strict_mode_raises_candidate_validation_error(monkeypatch):
    import core.algorithms.ortools_bottleneck as ob

    monkeypatch.setattr(ob, "try_solve_bottleneck_batch_order", lambda **_kwargs: ["B1"])
    cfg = _strict_optimizer_cfg()
    cfg.ortools_enabled = "yes"
    scheduler = _RejectingSgsScheduler()
    optimizer_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    with pytest.raises(ValidationError) as exc_info:
        _run_ortools_warmstart(
            algo_mode="improve",
            cfg=cfg,
            strategy_enum=SortStrategy.PRIORITY_FIRST,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            scheduler=scheduler,
            algo_ops_to_schedule=[object()],
            batches={"B1": SimpleNamespace(batch_id="B1")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            dispatch_mode_cfg="sgs",
            dispatch_rule_cfg="slack",
            resource_pool=None,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            logger=None,
            optimizer_algo_stats=optimizer_algo_stats,
            strict_mode=True,
        )

    assert exc_info.value.field == "resource"
    assert not optimizer_algo_stats["fallback_counts"], "strict 候选错误不应被记成 OR-Tools 预热失败"
