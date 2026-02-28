from __future__ import annotations

import os
import sys
from datetime import date, datetime
from types import SimpleNamespace

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import core.algorithms.greedy.scheduler as greedy_scheduler_module
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.algorithms.sort_strategies import SortStrategy


class _DummyCalendar:
    pass


class _SpySorter:
    def __init__(self, captured):
        self._captured = captured

    def sort(self, batches, *, base_date=None):
        self._captured["base_date"] = base_date
        return list(batches)

    def get_name(self) -> str:
        return "spy_sorter"


def test_greedy_scheduler_passes_start_dt_date_to_sorter(monkeypatch):
    captured = {}

    def _fake_create(cls, strategy, **kwargs):
        captured["strategy"] = strategy
        captured["kwargs"] = kwargs
        return _SpySorter(captured)

    monkeypatch.setattr(greedy_scheduler_module.StrategyFactory, "create", classmethod(_fake_create))

    scheduler = GreedyScheduler(calendar_service=_DummyCalendar(), config_service={})
    start_dt = datetime(2032, 1, 2, 8, 30, 0)

    scheduler.schedule(
        operations=[],
        batches={},
        strategy=SortStrategy.WEIGHTED,
        strategy_params={"priority_weight": 0.4, "due_weight": 0.5},
        start_dt=start_dt,
    )

    assert captured["strategy"] == SortStrategy.WEIGHTED
    assert captured["base_date"] == start_dt.date()


def test_greedy_scheduler_weighted_order_uses_start_dt_base_date(monkeypatch):
    captured = {}

    def _fake_dispatch_batch_order(*args, **kwargs):
        captured["sorted_batch_ids"] = [str(getattr(op, "batch_id", "") or "") for op in kwargs["sorted_ops"]]
        return int(kwargs.get("scheduled_count", 0)), int(kwargs.get("failed_count", 0))

    monkeypatch.setattr(greedy_scheduler_module, "dispatch_batch_order", _fake_dispatch_batch_order)

    scheduler = GreedyScheduler(calendar_service=_DummyCalendar(), config_service={})
    start_dt = datetime(2032, 1, 4, 8, 0, 0)

    batches = {
        "A_late": SimpleNamespace(
            priority="normal",
            due_date=date(2032, 1, 6),
            ready_status="yes",
            ready_date=None,
            created_at=None,
        ),
        "B_early": SimpleNamespace(
            priority="normal",
            due_date=date(2032, 1, 5),
            ready_status="yes",
            ready_date=None,
            created_at=None,
        ),
    }

    operations = [
        SimpleNamespace(id=1, batch_id="A_late", seq=1),
        SimpleNamespace(id=2, batch_id="B_early", seq=1),
    ]

    scheduler.schedule(
        operations=operations,
        batches=batches,
        strategy=SortStrategy.WEIGHTED,
        strategy_params={"priority_weight": 0.0, "due_weight": 1.0},
        start_dt=start_dt,
    )

    assert captured["sorted_batch_ids"][:2] == ["B_early", "A_late"]
