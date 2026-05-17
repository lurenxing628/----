from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
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
        algo_mode="greedy",
        objective="min_overdue",
        time_budget_seconds=5,
        dispatch_mode="sgs",
        dispatch_rule="cr",
        auto_assign_enabled="no",
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def _cfg_svc() -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "weighted", "fifo", "edd"),
        VALID_DISPATCH_MODES=("sgs",),
        VALID_DISPATCH_RULES=("cr", "atc"),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


def _stub_scheduler_result():
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )
    return [], summary, SimpleNamespace(value="priority_first"), {}

def test_optimizer_seed_results_strict_mode_fail_fast(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.services.scheduler.run.schedule_optimizer._schedule_with_optional_strict_mode",
        lambda *args, **kwargs: _stub_scheduler_result(),
    )

    with pytest.raises(ValidationError) as exc_info:
        optimize_schedule(
            calendar_service=SimpleNamespace(),
            cfg_svc=_cfg_svc(),
            cfg=_cfg(),
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 4, 2, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[{"op_id": 1, "start_time": None, "end_time": None}, "bad-item"],
            resource_pool=None,
            version=1,
            logger=None,
            strict_mode=True,
        )

    details = getattr(exc_info.value, "details", None) or {}
    assert "无效" in str(exc_info.value), exc_info.value
    assert "seed_results" not in str(exc_info.value), exc_info.value
    assert details.get("reason") == "invalid_seed_results", details
    assert int(details.get("invalid_seed_count") or 0) == 2, details
    assert list(details.get("invalid_seed_samples") or []), details
    assert all("start_time" not in str(item.get("error") or "") for item in details.get("invalid_seed_samples") or []), details
    assert all("end_time" not in str(item.get("error") or "") for item in details.get("invalid_seed_samples") or []), details


def test_optimizer_seed_results_relaxed_mode_fail_fast(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.services.scheduler.run.schedule_optimizer._schedule_with_optional_strict_mode",
        lambda *args, **kwargs: _stub_scheduler_result(),
    )

    with pytest.raises(ValidationError) as exc_info:
        optimize_schedule(
            calendar_service=SimpleNamespace(),
            cfg_svc=_cfg_svc(),
            cfg=_cfg(),
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 4, 2, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[{"op_id": 1, "start_time": None, "end_time": None}, "bad-item"],
            resource_pool=None,
            version=1,
            logger=None,
            strict_mode=False,
        )

    details = getattr(exc_info.value, "details", None) or {}
    assert "无效" in str(exc_info.value), exc_info.value
    assert details.get("reason") == "invalid_seed_results", details
    assert int(details.get("invalid_seed_count") or 0) == 2, details
    assert list(details.get("invalid_seed_samples") or []), details
