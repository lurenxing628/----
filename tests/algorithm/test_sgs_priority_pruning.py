"""Strict graph-order dominance preserves full SGS decisions and failure handling."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning
from core.infrastructure.errors import ValidationError
from tests._support.sgs_slot_reuse_case import make_case, make_scheduler


def _run(case, *, enabled):
    def full_scoring(*_args):
        return None

    original = GraphPriorityPruning.frontier
    # The independent native SGS reuse may already own windowed rounds. Isolate this
    # shortcut while keeping the actual scorer, calendar, and formal placement unchanged.
    with patch.object(GraphPriorityPruning, "frontier", original if enabled else full_scoring), \
            patch.object(scheduler_module, "create_native_sgs_reuse", lambda *_args, **_kwargs: None):
        scheduler = make_scheduler()
        results, summary, strategy, params = scheduler.schedule(**deepcopy(case))
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return ([vars(row) for row in results], fields, strategy, params), scheduler._last_sgs_score_cache_stats


@pytest.mark.parametrize("rule", ["slack", "cr", "atc", "atc:k=0.5"])
@pytest.mark.parametrize("window", [False, True])
def test_unique_graph_ranks_match_full_scoring_with_resources_gaps_and_horizon(rule, window):
    case = make_case(batch_count=12, ops_per_batch=5, auto=False, graph=True, window=window)
    case["dispatch_rule"] = rule
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (float(index), 0.0) for index, op in enumerate(case["operations"])}
    full, _ = _run(case, enabled=False)
    pruned, stats = _run(case, enabled=True)
    assert pruned == full
    assert stats["graph_candidates_pruned"] > 0


@pytest.mark.parametrize("kind", ["ties", "auto", "invalid_static"])
def test_unproven_inputs_keep_the_full_scoring_path(kind):
    case = make_case(batch_count=6, ops_per_batch=2, auto=kind == "auto", graph=True)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (0.0 if kind == "ties" else float(index),) for index, op in enumerate(case["operations"])}
    if kind == "invalid_static":
        # The ordinary scorer remains responsible for reporting malformed input.
        case["batches"]["B005"].due_date = "bad-date"
        case["strict_mode"] = True
        errors = []
        for enabled in (False, True):
            with pytest.raises(ValidationError) as exc:
                _run(case, enabled=enabled)
            errors.append((type(exc.value), str(exc.value)))
        assert errors[0] == errors[1]
        return
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] == 0


def test_normalized_production_dto_with_unused_merge_audit_metadata_is_supported():
    from core.services.scheduler.run.schedule_input_builder import OpForScheduleAlgo

    case = make_case(batch_count=8, ops_per_batch=3, auto=False, graph=True)
    normalized = []
    for op in case["operations"]:
        values = {name: getattr(op, name, None) for name in OpForScheduleAlgo.__dataclass_fields__}
        values.update(merge_context_degraded=False, merge_context_events=[{"test": "unused for internal work"}])
        normalized.append(OpForScheduleAlgo(**values))
    case["operations"] = normalized
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {op.id: (float(i), 0.0) for i, op in enumerate(normalized)}
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0


def test_full_graph_key_dominance_supports_tied_first_components_and_sparse_ranks():
    case = make_case(batch_count=8, ops_per_batch=3, auto=False, graph=True)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (-2.5, float(index * 7 + 100)) for index, op in enumerate(case["operations"])}
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0


def test_variable_width_graph_keys_cannot_be_compared_without_the_dynamic_suffix():
    case = make_case(batch_count=8, ops_per_batch=3, auto=False, graph=True)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: ((0.0,) if index % 2 else (0.0, 100.0)) for index, op in enumerate(case["operations"])}
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] == 0


@pytest.mark.parametrize("window", [False, True])
def test_tied_minimum_group_still_compares_every_members_dynamic_key(window):
    case = make_case(batch_count=12, ops_per_batch=5, auto=False, graph=True, window=window)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (float(op.seq),) for op in case["operations"]}
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0
