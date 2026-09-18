"""Unique ready priorities avoid whole-frontier scans without changing native results."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from core.algorithms.greedy.dispatch import sgs
from core.algorithms.greedy.dispatch import sgs_decode_acceleration as acceleration
from tests._support.sgs_slot_reuse_case import make_case, make_scheduler


def _run(case, enabled):
    collected = []
    original_collect = sgs._collect_candidates

    def collect(**kwargs):
        collected.append(True)
        return original_collect(**kwargs)

    queue = acceleration.make_priority_queue if enabled else lambda *_args: None
    with patch.object(acceleration, "make_priority_queue", queue), patch.object(sgs, "_collect_candidates", collect):
        scheduler = make_scheduler()
        results, summary, strategy, params = scheduler.schedule(**deepcopy(case))
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return ([vars(row) for row in results], fields, strategy, params), len(collected)


@pytest.mark.parametrize("rule", ["slack", "cr", "atc", "atc:k=0.5"])
def test_unique_ready_queue_matches_scanning_with_shared_resources(rule):
    case = make_case(batch_count=32, ops_per_batch=5, auto=False, graph=True)
    case["dispatch_rule"] = rule
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (float(i), 0.0) for i, op in enumerate(case["operations"])}
    expected, old_scans = _run(case, False)
    actual, new_scans = _run(case, True)
    assert actual == expected
    assert new_scans < old_scans / 2


@pytest.mark.parametrize("rule", ["slack", "atc"])
def test_certified_auto_assign_operations_use_the_unique_ready_queue(rule):
    # Auto-assign operations with a statically eligible pool are certified like fixed resources
    # (decision 2026-09-19 graph-priority-pruning-auto-assign); the head still gets the real probe.
    case = make_case(batch_count=32, ops_per_batch=5, auto=True, graph=True)
    case["dispatch_rule"] = rule
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (float(i), 0.0) for i, op in enumerate(case["operations"])}
    expected, old_scans = _run(case, False)
    actual, new_scans = _run(case, True)
    assert actual == expected
    assert new_scans < old_scans / 2


@pytest.mark.parametrize("variant", ["horizon", "ties", "auto_ties"])
def test_infeasible_heads_and_unproven_inputs_keep_original_outcomes(variant):
    tied = variant in ("ties", "auto_ties")
    case = make_case(batch_count=32, ops_per_batch=5, auto=variant == "auto_ties", graph=True, window=variant == "horizon")
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (0.0 if tied else float(i),) for i, op in enumerate(case["operations"])}
    expected, old_scans = _run(case, False)
    actual, new_scans = _run(case, True)
    assert actual == expected
    if tied:
        # Tied keys keep the whole-frontier scan for auto-assign operations too.
        assert new_scans == old_scans
