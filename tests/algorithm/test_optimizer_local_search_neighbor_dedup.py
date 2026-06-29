"""回归测试：_run_local_search 局部搜索业务邻域的去重与拒绝记录契约。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Tuple, cast

import pytest

import core.services.scheduler.schedule_optimizer as schedule_optimizer_module
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_neighborhood_moves import CRITICAL_CHAIN
from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.schedule_optimizer import _run_local_search
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


class _FakeTime:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01):
        self._now = float(start)
        self._step = float(step)

    def time(self) -> float:
        self._now += self._step
        return self._now


class _DeterministicRandom:
    def random(self):
        return 0.1

    def sample(self, seq, n):
        return [0, 1]

    def randrange(self, n):
        return 0

    def randint(self, a, b):
        return a


def _first_critical_chain_order(order_length: int) -> Tuple[str, ...]:
    return ("B1", "B0", *(f"B{i}" for i in range(2, order_length)))


def _critical_chain_results(latest_batch_id: str = "B1"):
    earlier_batch_id = "B0" if latest_batch_id != "B0" else "B1"
    return [
        SimpleNamespace(batch_id=earlier_batch_id, end_time=datetime(2026, 1, 1, 9, 0, 0), seq=10),
        SimpleNamespace(batch_id=latest_batch_id, end_time=datetime(2026, 1, 1, 10, 0, 0), seq=10),
    ]


def _run_case(monkeypatch, *, order_length: int):
    fake_time = _FakeTime()
    monkeypatch.setattr(schedule_optimizer_module.time, "time", fake_time.time)
    monkeypatch.setattr(schedule_optimizer_module.random, "Random", lambda seed: _DeterministicRandom())

    schedule_calls = []

    def _fake_schedule_with_optional_strict_mode(*args, **kwargs):
        schedule_calls.append(tuple(kwargs.get("batch_order_override") or []))
        summary = SimpleNamespace(
            success=False,
            total_ops=0,
            scheduled_ops=0,
            failed_ops=1,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    monkeypatch.setattr(schedule_optimizer_module, "_schedule_with_optional_strict_mode", _fake_schedule_with_optional_strict_mode)

    best = {
        "results": _critical_chain_results("B1"),
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": [f"B{i}" for i in range(order_length)],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }

    _run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.05,
        scheduler=cast(Any, SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}})),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
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
        strict_mode=False,
        neighborhoods=(CRITICAL_CHAIN,),
    )
    return schedule_calls


def test_local_search_dedups_duplicate_neighbors_when_order_large(monkeypatch):
    schedule_calls = _run_case(monkeypatch, order_length=10)
    assert schedule_calls == [_first_critical_chain_order(10)]


def test_local_search_keeps_retrying_duplicates_when_order_small(monkeypatch):
    schedule_calls = _run_case(monkeypatch, order_length=5)
    assert len(schedule_calls) >= 2
    assert set(schedule_calls) == {_first_critical_chain_order(5)}


def test_local_search_records_rejected_neighbor_and_keeps_existing_best(monkeypatch):
    fake_time = _FakeTime()
    monkeypatch.setattr(schedule_optimizer_module.time, "time", fake_time.time)
    monkeypatch.setattr(schedule_optimizer_module.random, "Random", lambda seed: _DeterministicRandom())

    def _rejecting_schedule_with_optional_strict_mode(*args, **kwargs):
        raise ValidationError("局部搜索候选缺少资源", field="resource")

    monkeypatch.setattr(schedule_optimizer_module, "_schedule_with_optional_strict_mode", _rejecting_schedule_with_optional_strict_mode)

    best = {
        "results": _critical_chain_results("B2"),
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }
    attempts = []

    returned = _run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.05,
        scheduler=cast(Any, SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}})),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        strict_mode=False,
        neighborhoods=(CRITICAL_CHAIN,),
    )

    assert returned is best
    rejected = [attempt for attempt in attempts if attempt.get("source") == "candidate_rejected"]
    assert rejected == [
        {
            "tag": "local:critical_chain",
            "strategy": SortStrategy.PRIORITY_FIRST.value,
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "source": "candidate_rejected",
            "origin": {
                "type": "ValidationError",
                "field": "resource",
                "message": "[1001] 局部搜索候选缺少资源",
            },
        }
    ]


def test_local_search_strict_mode_raises_rejected_neighbor_validation_error(monkeypatch):
    fake_time = _FakeTime()
    monkeypatch.setattr(schedule_optimizer_module.time, "time", fake_time.time)
    monkeypatch.setattr(schedule_optimizer_module.random, "Random", lambda seed: _DeterministicRandom())

    def _rejecting_schedule_with_optional_strict_mode(*args, **kwargs):
        raise ValidationError("局部搜索候选缺少资源", field="resource")

    monkeypatch.setattr(schedule_optimizer_module, "_schedule_with_optional_strict_mode", _rejecting_schedule_with_optional_strict_mode)

    best = {
        "results": _critical_chain_results("B2"),
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }

    with pytest.raises(ValidationError) as exc_info:
        _run_local_search(
            algo_mode="improve",
            best=best,
            version=1,
            time_budget_seconds=1,
            deadline=1000.05,
            scheduler=cast(Any, SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}})),
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
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
                strict_mode=True,
                neighborhoods=(CRITICAL_CHAIN,),
            )

    assert exc_info.value.field == "resource"


def test_local_search_records_rejected_neighbor_after_existing_attempt_cap(monkeypatch):
    fake_time = _FakeTime()
    monkeypatch.setattr(schedule_optimizer_module.time, "time", fake_time.time)
    monkeypatch.setattr(schedule_optimizer_module.random, "Random", lambda seed: _DeterministicRandom())

    def _rejecting_schedule_with_optional_strict_mode(*args, **kwargs):
        raise ValidationError("局部搜索候选缺少资源", field="resource")

    monkeypatch.setattr(schedule_optimizer_module, "_schedule_with_optional_strict_mode", _rejecting_schedule_with_optional_strict_mode)

    best = {
        "results": _critical_chain_results("B2"),
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }
    attempts = [
        {
            "tag": f"start:priority_first|batch_order:r{i}",
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": f"r{i}",
            "score": [float(i)],
        }
        for i in range(12)
    ]

    _run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.05,
        scheduler=cast(Any, SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}})),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        strict_mode=False,
        neighborhoods=(CRITICAL_CHAIN,),
    )

    rejected = [attempt for attempt in attempts if attempt.get("source") == "candidate_rejected"]
    assert rejected == [
        {
            "tag": "local:critical_chain",
            "strategy": SortStrategy.PRIORITY_FIRST.value,
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "source": "candidate_rejected",
            "origin": {
                "type": "ValidationError",
                "field": "resource",
                "message": "[1001] 局部搜索候选缺少资源",
            },
        }
    ]

    compacted = compact_attempts(attempts, limit=12)
    public_algo, diagnostics = project_public_algo_summary({"attempts": compacted})
    assert len(public_algo["attempts"]) == 11
    assert all(attempt.get("source") != "candidate_rejected" for attempt in public_algo["attempts"])
    diagnostic_rejections = list(
        filter(
            lambda attempt: attempt.get("source") == "candidate_rejected",
            diagnostics["optimizer"]["attempts"],
        )
    )
    assert diagnostic_rejections == rejected


def test_local_search_keeps_distinct_rejected_neighbor_origins(monkeypatch):
    fake_time = _FakeTime()
    monkeypatch.setattr(schedule_optimizer_module.time, "time", fake_time.time)
    monkeypatch.setattr(schedule_optimizer_module.random, "Random", lambda seed: _DeterministicRandom())

    errors = [
        ValidationError("局部搜索候选缺少资源", field="resource"),
        ValidationError("局部搜索候选工时非法", field="hours"),
    ]

    schedule_calls = []
    call_index = {"value": 0}

    def _recording_rejecting_schedule(*args, **kwargs):
        schedule_calls.append(tuple(kwargs.get("batch_order_override") or []))
        idx = min(call_index["value"], len(errors) - 1)
        call_index["value"] += 1
        raise errors[idx]

    monkeypatch.setattr(schedule_optimizer_module, "_schedule_with_optional_strict_mode", _recording_rejecting_schedule)

    best = {
        "results": _critical_chain_results("B2"),
        "summary": SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[], duration_seconds=0.0),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": SimpleNamespace(to_dict=lambda: {}),
        "score": (0.0, 0.0, 0.0),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }
    attempts = []

    _run_local_search(
        algo_mode="improve",
        best=best,
        version=1,
        time_budget_seconds=1,
        deadline=1000.05,
        scheduler=cast(Any, SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}})),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name="min_overdue",
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        strict_mode=False,
        neighborhoods=(CRITICAL_CHAIN,),
    )

    rejected_attempts = [attempt for attempt in attempts if attempt.get("source") == "candidate_rejected"]
    assert len(schedule_calls) > len(rejected_attempts)
    assert rejected_attempts == [
        {
            "tag": "local:critical_chain",
            "strategy": SortStrategy.PRIORITY_FIRST.value,
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "source": "candidate_rejected",
            "origin": {
                "type": "ValidationError",
                "field": "resource",
                "message": "[1001] 局部搜索候选缺少资源",
            },
        },
        {
            "tag": "local:critical_chain",
            "strategy": SortStrategy.PRIORITY_FIRST.value,
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "source": "candidate_rejected",
            "origin": {
                "type": "ValidationError",
                "field": "hours",
                "message": "[1001] 局部搜索候选工时非法",
            },
        },
    ]
