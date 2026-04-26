from __future__ import annotations

import copy

from core.algorithms.greedy.algo_stats import (
    ensure_algo_stats,
    increment_counter,
    make_algo_stats,
    merge_algo_stats,
    snapshot_algo_stats,
)
from core.algorithms.greedy.run_context import ScheduleRunContext


class _LegacyStatsTarget:
    _last_algo_stats: dict


def test_make_algo_stats_can_be_used_as_explicit_counter_sink() -> None:
    stats = make_algo_stats()

    increment_counter(stats, "x_count")
    increment_counter(stats, "x_count", 2)

    assert stats["fallback_counts"] == {"x_count": 3}


def test_legacy_scheduler_stats_snapshot_still_works() -> None:
    target = _LegacyStatsTarget()
    ensure_algo_stats(target)

    increment_counter(target, "legacy_count")
    snapshot = snapshot_algo_stats(target)
    increment_counter(target, "legacy_count")

    assert snapshot["fallback_counts"] == {"legacy_count": 1}
    assert target._last_algo_stats["fallback_counts"] == {"legacy_count": 2}


def test_run_context_legacy_scheduler_repairs_bad_stats_sink() -> None:
    target = _LegacyStatsTarget()
    target._last_algo_stats = None  # type: ignore[assignment]

    context = ScheduleRunContext.from_legacy_scheduler(target)
    context.increment("legacy_repaired_count")

    assert target._last_algo_stats["fallback_counts"] == {"legacy_repaired_count": 1}


def test_run_context_external_fallback_writes_legacy_scheduler_stats() -> None:
    from core.algorithms.greedy.run_context import _ScheduleFacade

    target = _LegacyStatsTarget()
    target._last_algo_stats = None  # type: ignore[assignment]
    context = ScheduleRunContext.from_legacy_scheduler(target)
    facade = _ScheduleFacade(None, context.algo_stats)

    increment_counter(facade, "external_defaulted_count")

    assert target._last_algo_stats["fallback_counts"] == {"external_defaulted_count": 1}


def test_merge_algo_stats_deep_copies_fallback_samples() -> None:
    source = {
        "fallback_counts": {},
        "param_fallbacks": {},
        "fallback_samples": {"probe": [{"payload": []}]},
    }

    merged = merge_algo_stats(source)
    source["fallback_samples"]["probe"][0]["payload"].append("mutated-after-merge")

    assert merged["fallback_samples"]["probe"] == [{"payload": []}]


def test_snapshot_algo_stats_fallback_deep_copies_fallback_samples(monkeypatch) -> None:
    import core.algorithms.greedy.algo_stats as stats_mod

    target = _LegacyStatsTarget()
    target._last_algo_stats = {
        "fallback_counts": {},
        "param_fallbacks": {},
        "fallback_samples": {"probe": [{"payload": []}]},
    }
    real_deepcopy = copy.deepcopy

    def force_failure(_value):
        raise RuntimeError("force fallback")

    forced_failure = iter([force_failure])

    def fail_once(value):
        return next(forced_failure, real_deepcopy)(value)

    monkeypatch.setattr(stats_mod, "deepcopy", fail_once)

    snapshot = snapshot_algo_stats(target)
    target._last_algo_stats["fallback_samples"]["probe"][0]["payload"].append("mutated-after-snapshot")

    assert snapshot["fallback_samples"]["probe"] == [{"payload": []}]
