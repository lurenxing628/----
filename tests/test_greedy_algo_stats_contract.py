"""回归测试：greedy.algo_stats 计数器契约——increment_counter/merge_algo_stats 只接受整数增量（拒绝 str/float/Decimal/Fraction/bool 及坏的既有值），None sink 静默允许；ensure_algo_stats/snapshot_algo_stats 兼容 _last_algo_stats 旧字段并在快照失败时回退，不可写 sink 抛 RuntimeError；merge/snapshot 对 fallback_samples 深拷贝以防 merge 后被原对象篡改。"""

from __future__ import annotations

import copy
from decimal import Decimal
from fractions import Fraction

import pytest

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


class _RejectsStatsTarget:
    __slots__ = ()


def test_make_algo_stats_can_be_used_as_explicit_counter_sink() -> None:
    stats = make_algo_stats()

    increment_counter(stats, "x_count")
    increment_counter(stats, "x_count", 2)

    assert stats["fallback_counts"] == {"x_count": 3}


def test_missing_stats_sink_is_allowed_for_direct_compat_calls() -> None:
    increment_counter(None, "x_count")


def test_increment_counter_rejects_bad_amount_and_existing_value() -> None:
    stats = make_algo_stats()
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count", "坏数据")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count", 1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count", Decimal("1.5"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count", Fraction(3, 2))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count", True)  # type: ignore[arg-type]

    stats["fallback_counts"]["x_count"] = "坏数据"
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count")
    stats["fallback_counts"]["x_count"] = 1.5
    with pytest.raises(ValueError):
        increment_counter(stats, "x_count")


def test_merge_algo_stats_rejects_bad_counter_value() -> None:
    source = {"fallback_counts": {"x_count": "坏数据"}}

    with pytest.raises(ValueError):
        merge_algo_stats(source)

    with pytest.raises(ValueError):
        merge_algo_stats({"fallback_counts": {"x_count": 1.5}})
    with pytest.raises(ValueError):
        merge_algo_stats({"fallback_counts": {"x_count": Decimal("1.5")}})
    with pytest.raises(ValueError):
        merge_algo_stats({"fallback_counts": {"x_count": Fraction(3, 2)}})
    with pytest.raises(ValueError):
        merge_algo_stats({"fallback_counts": {"x_count": True}})


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


def test_unwritable_stats_sink_fails_instead_of_losing_counts() -> None:
    with pytest.raises(RuntimeError):
        ensure_algo_stats(_RejectsStatsTarget())


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
