"""Due-date seeds are bounded complete priorities, not fabricated schedules or quality proof."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_seed import build_due_date_seed

START = datetime(2026, 1, 1)


def _input(processing, due, order=None, offset=0):
    order = tuple(order or range(1, len(processing) + 1))
    rows, elapsed = [], offset
    for op_id in order:
        start = START + timedelta(hours=elapsed)
        elapsed += processing[op_id - 1]
        rows.append(SimpleNamespace(op_id=op_id, batch_id="B" + str(op_id), source="internal",
                                    machine_id="M", operator_id="O", start_time=start,
                                    end_time=START + timedelta(hours=elapsed)))
    links = {op_id: set() for op_id in order}
    parent = SimpleNamespace(order=order, batch_order=tuple(row.batch_id for row in rows), inherited=(),
                             predecessors=deepcopy(links), successors=deepcopy(links))
    return {"parent": parent, "candidate": {"results": rows, "summary": SimpleNamespace(success=True, failed_ops=0)},
            "metrics": {op_id: {"due_deadline_hours": due[op_id - 1]} for op_id in order},
            "graph_context": {"fixed_op_ids": set(), "predecessor_op_ids_by_op_id": deepcopy(links),
                              "successor_op_ids_by_op_id": deepcopy(links)},
            "start_dt": START, "clock": lambda: 0.0, "deadline": 10.0}


def test_two_deferred_sets_are_enumerated_and_improve_the_moore_seed():
    # Moore yields 5,3,4,2,1 with estimate (2,10); another two-job deferred set yields (2,7).
    kwargs = _input([9, 5, 1, 2, 2], [14, 5, 11, 14, 4], order=(5, 3, 4, 2, 1))
    before = deepcopy(kwargs)
    result = build_due_date_seed(**kwargs)
    assert result["status"] == "candidate" and result["reason"] == "estimated_improvement"
    assert result["order"] == (5, 2, 4, 3, 1)
    assert result["original_estimated_key"] == (2, 10.0)
    assert result["estimated_key"] == (2, 7.0)
    assert result["deferred_count"] == 2
    assert result["probes"] == 10
    assert result["construction_method"] == "enumerated_fixed_size_deferred_sets"
    assert result["construction_stop"] == "completed"
    assert kwargs == before
    assert result["requires_sgs_validation"] is True and result["optimality"] == "not_claimed"
    assert "results" not in result and "seed_results" not in result


def test_better_original_order_is_retained_instead_of_returning_a_worse_seed():
    result = build_due_date_seed(**_input([9, 5, 1, 2, 2], [14, 5, 11, 14, 4], order=(5, 2, 4, 3, 1)))
    assert result["status"] == "no_improvement" and result["order"] is None
    assert result["reason"] == "estimate_not_better"
    assert result["estimated_key"] == result["original_estimated_key"] == (2, 7.0)


@pytest.mark.parametrize("processing,due,key,deferred", [(1, 1, (1, 0.0), 1), (1, 1.01, (0, 0.0), 0), (0, 0, (1, 0.0), 1)])
def test_due_exclusive_counts_completion_at_deadline_as_late(processing, due, key, deferred):
    result = build_due_date_seed(**_input([processing], [due]))
    assert result["original_estimated_key"] == key
    assert result["deferred_count"] == deferred
    assert result["order"] is None


@pytest.mark.parametrize("offset,due,key,reported_offset", [(4, 5, (1, 0.0), 4.0), (5, 5, (1, 1.0), 5.0),
                                                           (-2, 1, (1, 0.0), 0.0)])
def test_estimate_keeps_the_nonnegative_common_start_offset(offset, due, key, reported_offset):
    result = build_due_date_seed(**_input([1], [due], offset=offset))
    assert result["estimated_start_offset_hours"] == reported_offset
    assert result["original_estimated_key"] == key


@pytest.mark.parametrize("size,method,probes,stop", [
    (64, "enumerated_fixed_size_deferred_sets", 2016, "completed"),
    (65, "bounded_single_exchange", 128, "completed"),
    (66, "bounded_single_exchange", 130, "completed"),
])
def test_combination_boundary_and_single_exchange_caps(size, method, probes, stop):
    result = build_due_date_seed(**_input([1] * size, [0, 0] + [1000] * (size - 2),
                                         order=tuple(range(size, 0, -1))))
    assert result["deferred_count"] == 2
    assert result["construction_method"] == method and result["probes"] == probes <= 2048
    assert result["construction_stop"] == stop
    assert isinstance(result["order"], tuple)
    assert len(result["order"]) == len(set(result["order"])) == size
    assert set(result["order"]) == set(range(1, size + 1))
    assert result["estimated_key"] < result["original_estimated_key"]


def test_large_deferred_count_uses_only_bounded_single_exchanges():
    result = build_due_date_seed(**_input([1] * 12, [0] * 3 + [100] * 9, order=tuple(range(12, 0, -1))))
    assert result["deferred_count"] == 3
    assert result["construction_method"] == "bounded_single_exchange_and_insertion"
    assert result["probes"] <= 2048


def test_single_exchange_uses_the_same_distinct_probe_cap_and_preserves_completed_best(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_seed as module

    monkeypatch.setattr(module, "_MAX_PROBES", 20)
    result = build_due_date_seed(**_input([1] * 12, [0] * 3 + [100] * 9, order=tuple(range(12, 0, -1))))
    assert result["probes"] == 20 and result["construction_stop"] == "probe_limit"
    assert result["estimated_key"] < result["original_estimated_key"]
    assert sorted(result["order"]) == list(range(1, 13))


def test_order_polish_uses_slack_between_on_time_jobs_without_adding_late_jobs():
    result = build_due_date_seed(**_input([1] * 5, [100, 100, 0, 0, 0], order=(1, 2, 3, 4, 5)))
    assert result["original_estimated_key"] == (3, 12.0)
    assert result["estimated_key"] == (3, 6.0)
    assert result["construction_method"] == "bounded_single_exchange_and_insertion"
    assert set(result["order"][:3]) == {3, 4, 5}
    assert result["probes"] <= 2048 and result["requires_sgs_validation"]


def test_expired_deadline_does_zero_probes_and_returns_no_order():
    kwargs = _input([2, 1], [2, 3])
    kwargs["deadline"] = 0.0
    result = build_due_date_seed(**kwargs)
    assert result["order"] is None and result["probes"] == 0
    assert result["status"] == "budget_exhausted"
    assert result["reason"] == result["construction_stop"] == "time_budget"


@pytest.mark.parametrize("last_live_call", [3, 20])
def test_clock_stop_during_construction_or_probing_never_emits_partial_order(last_live_call):
    kwargs = _input([9, 5, 1, 2, 2], [14, 5, 11, 14, 4], order=(5, 3, 4, 2, 1))
    calls = []

    def clock():
        calls.append(None)
        return 0.0 if len(calls) <= last_live_call else 1.0

    kwargs.update(clock=clock, deadline=1.0)
    result = build_due_date_seed(**kwargs)
    assert result["construction_stop"] == "time_budget"
    assert len(calls) == last_live_call + 1
    assert result["probes"] < 10
    if last_live_call == 3:
        assert result["probes"] == 0 and result["order"] is None
    if result["order"] is not None:
        assert set(result["order"]) == set(kwargs["parent"].order)
        assert result["estimated_key"] < result["original_estimated_key"]


@pytest.mark.parametrize("field,value,reason", [
    ("source", "external", "non_internal_result"),
    ("machine_id", "", "missing_resource_pair"),
    ("operator_id", None, "missing_resource_pair"),
    ("machine_id", "OTHER", "multiple_resource_pairs"),
    ("batch_id", "B1", "not_one_operation_per_batch"),
    ("op_id", 1, "result_scope_mismatch"),
    ("end_time", START, "invalid_observed_duration"),
    ("start_time", None, "invalid_result_times"),
])
def test_only_single_internal_resource_and_complete_unique_batches_are_applicable(field, value, reason):
    kwargs = _input([2, 1], [2, 3])
    setattr(kwargs["candidate"]["results"][1], field, value)
    result = build_due_date_seed(**kwargs)
    assert result["status"] == "not_applicable" and result["reason"] == reason
    assert result["order"] is None and result["probes"] == 0


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), -float("inf"), "3", 10 ** 400])
def test_missing_or_nonfinite_deadlines_are_not_applicable(value):
    kwargs = _input([1], [value])
    result = build_due_date_seed(**kwargs)
    assert result["reason"] == "missing_or_nonfinite_due_deadline_hours"
    assert result["order"] is None and result["probes"] == 0


@pytest.mark.parametrize("metric", [None, {}, True, 3])
def test_malformed_metric_records_are_explicitly_not_applicable(metric):
    kwargs = _input([1], [2])
    kwargs["metrics"][1] = metric
    result = build_due_date_seed(**kwargs)
    assert result["status"] == "not_applicable"
    assert result["reason"] == "missing_or_nonfinite_due_deadline_hours"


@pytest.mark.parametrize("kind", ["fixed", "predecessor", "successor", "parent_link", "missing_links", "failed"])
def test_fixed_precedence_missing_context_and_failed_candidates_are_rejected(kind):
    kwargs = _input([2, 1], [2, 3])
    if kind == "fixed":
        kwargs["graph_context"]["fixed_op_ids"] = {1}
    elif kind == "predecessor":
        kwargs["graph_context"]["predecessor_op_ids_by_op_id"][2] = {1}
    elif kind == "successor":
        kwargs["graph_context"]["successor_op_ids_by_op_id"][1] = {2}
    elif kind == "parent_link":
        kwargs["parent"].predecessors[2] = {1}
    elif kind == "missing_links":
        del kwargs["graph_context"]["predecessor_op_ids_by_op_id"]
    else:
        kwargs["candidate"]["summary"].failed_ops = 1
    result = build_due_date_seed(**kwargs)
    assert result["status"] == "not_applicable" and result["reason"]
    assert result["order"] is None and result["probes"] == 0


def test_mixed_timezones_are_explicitly_not_applicable():
    kwargs = _input([1], [2])
    kwargs["start_dt"] = START.replace(tzinfo=timezone.utc)
    result = build_due_date_seed(**kwargs)
    assert result["reason"] == "incompatible_start_timezones"
    assert result["order"] is None


@pytest.mark.parametrize("order", [(), (1, 1), (True, 2), (1, 3)])
def test_invalid_or_incomplete_parent_orders_are_not_repaired_by_guessing(order):
    kwargs = _input([2, 1], [2, 3])
    kwargs["parent"].order = order
    result = build_due_date_seed(**kwargs)
    assert result["status"] == "not_applicable"
    assert result["order"] is None and result["probes"] == 0


def test_identical_inputs_give_identical_complete_priority_tuples():
    kwargs = _input([9, 5, 1, 2, 2], [14, 5, 11, 14, 4], order=(5, 3, 4, 2, 1))
    assert build_due_date_seed(**kwargs) == build_due_date_seed(**kwargs)
