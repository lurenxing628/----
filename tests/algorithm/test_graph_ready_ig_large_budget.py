"""A large suffix has its own admission cost; small solvers keep the validated class."""

from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy import _BudgetExhausted, _IteratedGreedySearch
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_large import (
    LargeIteratedGreedySearch,
    search_type_for,
)


def _search(*, now=7.8, deadline=10.0, fraction=0.75, samples=((1.0, 2.8),)):
    search = object.__new__(LargeIteratedGreedySearch)
    search.clock, search.deadline = lambda: now, deadline
    search.limits = SimpleNamespace(max_decodes=10)
    search.report = {"decodes": 1, "budget_pruned_before_decode": 0}
    search._cost_samples, search._work_fraction = list(samples), fraction
    return search


@pytest.mark.parametrize("size", [4, 16, 24, 40, 48, 50, 127])
def test_small_order_uses_the_original_solver_class(size):
    assert search_type_for(SimpleNamespace(order=tuple(range(size)))) is _IteratedGreedySearch


def test_large_order_selects_suffix_admission():
    assert search_type_for(SimpleNamespace(order=tuple(range(5000)))) is LargeIteratedGreedySearch


def test_neighbourhood_setup_is_allowed_and_the_affordable_suffix_starts():
    search = _search()
    search._require_budget()  # A whole 2.8s decode would not fit the remaining 2.2s.
    search._before_decode()
    assert search.report["decodes"] == 2
    assert search.report["decode_admission"]["estimated_decode_ms"] == pytest.approx(2100)
    assert search.report["budget_pruned_before_decode"] == 0


def test_full_validation_still_requires_a_full_decode_budget():
    search = _search(fraction=1.0)
    with pytest.raises(_BudgetExhausted, match="decode_would_overrun"):
        search._before_decode()
    assert search.report["decodes"] == 1 and search.report["budget_pruned_before_decode"] == 1


def test_observed_suffix_cost_does_not_shrink_with_an_unmeasured_shorter_suffix():
    search = _search(fraction=0.25, samples=((1.0, 2.8), (0.75, 2.4)))
    with pytest.raises(_BudgetExhausted, match="decode_would_overrun"):
        search._before_decode()
    assert search.report["decode_admission"]["estimated_decode_ms"] == 2400


@pytest.mark.parametrize("now,decodes,reason", [(10, 1, "time_budget"), (9, 10, "decode_budget")])
def test_real_deadline_and_decode_cap_are_always_hard(now, decodes, reason):
    search = _search(now=now)
    search.report["decodes"] = decodes
    with pytest.raises(_BudgetExhausted, match=reason):
        search._before_decode()
    assert search.report["decodes"] == decodes
