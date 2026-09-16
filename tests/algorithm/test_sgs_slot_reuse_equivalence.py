"""Full real-SGS output equality with run-scoped overlap reuse on and off."""

from contextlib import nullcontext
from dataclasses import asdict
from unittest.mock import patch

import pytest

from core.algorithm_runtime.downtime import SegmentOverlapIndex
from core.algorithms.greedy.dispatch import sgs
from tests._support.sgs_slot_reuse_case import make_case, make_scheduler


def run(*, enabled, auto=True, graph=False, window=False, rule="slack", scheduler=None, zero=False):
    scheduler = scheduler or make_scheduler()
    kwargs = make_case(batch_count=8, ops_per_batch=4, auto=auto, graph=graph, window=window)
    kwargs["dispatch_rule"] = rule
    if zero:
        kwargs["operations"][0].setup_hours = 0
        kwargs["operations"][0].unit_hours = 0
    if window:
        kwargs["operations"][5].setup_hours = 100
    context = nullcontext() if enabled else patch.object(sgs, "sgs_overlap_reuse", lambda timeline, **_kwargs: nullcontext())
    with context, patch("sqlite3.connect", side_effect=AssertionError("no database")):
        results, summary, strategy, params = scheduler.schedule(**kwargs)
    summary_data = asdict(summary)
    summary_data.pop("duration_seconds")
    if window:
        assert summary.failed_ops > 0
    return dict(results=[asdict(item) for item in results], summary=summary_data,
                strategy=strategy, params=params, stats=scheduler._last_algo_stats)


@pytest.mark.parametrize("rule", ["slack", "cr", "atc"])
@pytest.mark.parametrize("auto, graph, window", [
    (True, False, False), (False, False, False), (True, True, False),
    (False, True, False), (True, True, True), (False, True, True),
])
def test_all_results_summary_failures_and_counters_equal(rule, auto, graph, window):
    assert run(enabled=True, rule=rule, auto=auto, graph=graph, window=window, zero=True) == run(
        enabled=False, rule=rule, auto=auto, graph=graph, window=window, zero=True,
    )


def test_real_schedule_materializes_less_without_skipping_calendar_calls(monkeypatch):
    calls = []
    original = SegmentOverlapIndex._materialize

    def counted(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(SegmentOverlapIndex, "_materialize", counted)
    calendar = make_scheduler().calendar
    with patch.object(type(calendar), "add_working_hours", autospec=True, side_effect=type(calendar).add_working_hours) as add:
        before = run(enabled=False)
        before_calls, before_calendar_calls = len(calls), add.call_count
        calls.clear()
        add.reset_mock()
        after = run(enabled=True)
        assert before == after
        assert add.call_count == before_calendar_calls
        assert 0 < len(calls) < before_calls // 5


def test_same_scheduler_repeated_runs_do_not_share_overlap_indexes(monkeypatch):
    runs, current = [], []
    original = SegmentOverlapIndex.__init__

    def collect(self, segments):
        current.append(self)
        original(self, segments)

    monkeypatch.setattr(SegmentOverlapIndex, "__init__", collect)
    scheduler = make_scheduler()
    first = run(enabled=True, scheduler=scheduler)
    runs.append(list(current))
    current.clear()
    second = run(enabled=True, scheduler=scheduler)
    assert first == second
    assert len(current) == len(runs[0]) > 0
    assert not {id(index) for index in current}.intersection(id(index) for index in runs[0])
