from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import core.services.scheduler.schedule_optimizer as schedule_optimizer_module
from core.algorithms.sort_strategies import SortStrategy
from core.services.scheduler.schedule_optimizer import _run_local_search


class _FakeTime:
    def __init__(self, *, start: float = 1000.0, step: float = 0.01):
        self._now = float(start)
        self._step = float(step)

    def time(self) -> float:
        self._now += self._step
        return self._now


class _DeterministicRandom:
    def random(self):
        return 0.1  # 永远走 swap

    def sample(self, seq, n):
        return [0, 1]

    def randrange(self, n):
        return 0

    def randint(self, a, b):
        return a


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
        "results": [],
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
    )
    return schedule_calls


def test_local_search_dedups_duplicate_neighbors_when_order_large(monkeypatch):
    schedule_calls = _run_case(monkeypatch, order_length=10)
    assert len(schedule_calls) == 1


def test_local_search_keeps_retrying_duplicates_when_order_small(monkeypatch):
    schedule_calls = _run_case(monkeypatch, order_length=5)
    assert len(schedule_calls) >= 2
