from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace

from core.algorithms.sort_strategies import SortStrategy
from core.services.scheduler.schedule_optimizer_steps import _run_multi_start


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
