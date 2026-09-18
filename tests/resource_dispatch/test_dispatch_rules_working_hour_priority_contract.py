"""Dispatch keys: working-hour slack inputs and order-preserving priority weighting for slack / CR.

Locks the 2026-09-18 decision: the scoring layer supplies slack_hours / time_left_hours in working hours;
without them the key keeps the wall-clock spans (pure contract callers, continuous calendars). Normal
batches (weight 1) keep their historic key values; heavier batches look tighter in both directions.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithm_contracts.dispatch_rules import ATC_K_LADDER, DispatchInputs, DispatchRule, build_dispatch_key

START = datetime(2026, 1, 9, 8, 0)
DUE = date(2026, 1, 12)
RULES = (DispatchRule.SLACK, DispatchRule.CR, DispatchRule.ATC)


def _inputs(rule, *, priority="normal", due=DUE, hours=8.0, avg=6.0, k=2.0, op_id=1, slack=None, time_left=None):
    return DispatchInputs(
        rule=rule, priority=priority, due_date=due, est_start=START, est_end=START + timedelta(hours=hours),
        proc_hours=hours, avg_proc_hours=avg, changeover_penalty=0, batch_order=0, batch_id="B", seq=1, op_id=op_id,
        atc_k=k, slack_hours=slack, time_left_hours=time_left,
    )


def _wall_clock(inp):
    due_dt = due_exclusive(inp.due_date)
    return (due_dt - inp.est_end).total_seconds() / 3600.0, (due_dt - inp.est_start).total_seconds() / 3600.0


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("k", ATC_K_LADDER)
def test_explicit_wall_clock_spans_reproduce_the_historic_key_exactly(rule, k):
    legacy = _inputs(rule, k=k)
    slack, time_left = _wall_clock(legacy)
    assert build_dispatch_key(_inputs(rule, k=k, slack=slack, time_left=time_left)) == build_dispatch_key(legacy)


@pytest.mark.parametrize("rule", (DispatchRule.SLACK, DispatchRule.CR, DispatchRule.ATC))
def test_working_hour_slack_ranks_the_tighter_batch_first_across_a_weekend(rule):
    # Two 4 h operations. A: starts Friday 12:00, due Monday -> 80 wall-clock hours of slack but 8 working hours.
    # B: starts Monday 08:00, due Tuesday -> 36 wall-clock hours of slack but 12 working hours.
    tighter = _inputs(rule, hours=4.0, slack=8.0, time_left=12.0, op_id=1)
    looser = _inputs(rule, hours=4.0, slack=12.0, time_left=16.0, op_id=2)
    assert build_dispatch_key(tighter) < build_dispatch_key(looser)
    calendar_tighter = _inputs(rule, hours=4.0, slack=80.0, time_left=84.0, op_id=1)
    calendar_looser = _inputs(rule, hours=4.0, slack=36.0, time_left=40.0, op_id=2)
    assert build_dispatch_key(calendar_looser) < build_dispatch_key(calendar_tighter)


@pytest.mark.parametrize("rule", (DispatchRule.SLACK, DispatchRule.CR))
def test_normal_priority_keeps_its_value_and_heavier_batches_look_tighter_in_both_directions(rule):
    normal = build_dispatch_key(_inputs(rule, slack=9.0, time_left=17.0))
    assert normal[0] == (9.0 if rule is DispatchRule.SLACK else 17.0 / 8.0)
    critical_ahead = build_dispatch_key(_inputs(rule, priority="critical", slack=10.0, time_left=18.0))
    urgent_ahead = build_dispatch_key(_inputs(rule, priority="urgent", slack=10.0, time_left=18.0))
    assert critical_ahead[0] < urgent_ahead[0] < normal[0]
    if rule is DispatchRule.SLACK:
        assert critical_ahead[0] == pytest.approx(10.0 / 3.0)
        assert urgent_ahead[0] == pytest.approx(10.0 / 2.0)
    normal_late = build_dispatch_key(_inputs(rule, slack=-5.0, time_left=3.0 if rule is DispatchRule.SLACK else -5.0))
    critical_late = build_dispatch_key(_inputs(rule, priority="critical", slack=-2.0, time_left=6.0 if rule is DispatchRule.SLACK else -2.0))
    assert critical_late[0] < normal_late[0]
    if rule is DispatchRule.SLACK:
        assert critical_late[0] == -6.0 and normal_late[0] == -5.0


@pytest.mark.parametrize("priority", ("normal", "urgent", "critical"))
def test_priority_scaling_preserves_order_within_one_priority(priority):
    keys = [build_dispatch_key(_inputs(DispatchRule.SLACK, priority=priority, slack=slack, time_left=slack + 8.0, op_id=i))[0]
            for i, slack in enumerate((-9.0, -1.0, 0.0, 0.5, 4.0, 40.0))]
    assert keys == sorted(keys)


def test_atc_is_unchanged_by_the_new_weighting_and_still_carries_its_own_weight():
    normal = build_dispatch_key(_inputs(DispatchRule.ATC, slack=8.0, time_left=16.0))
    urgent = build_dispatch_key(_inputs(DispatchRule.ATC, priority="urgent", slack=8.0, time_left=16.0))
    assert normal[0] == pytest.approx(-(1.0 / 8.0) * math.exp(-8.0 / 12.0))
    assert urgent[0] == pytest.approx(2.0 * normal[0])


@pytest.mark.parametrize("slack, time_left", [(8.0, None), (None, 8.0)])
def test_spans_must_be_supplied_together(slack, time_left):
    with pytest.raises(ValueError):
        build_dispatch_key(_inputs(DispatchRule.SLACK, slack=slack, time_left=time_left))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "8"])
def test_non_finite_or_non_numeric_spans_are_rejected(bad):
    with pytest.raises(ValueError):
        build_dispatch_key(_inputs(DispatchRule.SLACK, slack=bad, time_left=8.0))
    with pytest.raises(ValueError):
        build_dispatch_key(_inputs(DispatchRule.CR, slack=8.0, time_left=bad))
