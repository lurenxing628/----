"""Strict graph-order dominance preserves full SGS decisions and failure handling."""

from copy import deepcopy
from typing import Any, Dict
from unittest.mock import patch

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.auto_assign import eligible_auto_assign_resources
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning
from core.infrastructure.errors import ValidationError
from tests._support.sgs_slot_reuse_case import MemoryCalendar, make_case, make_scheduler


def _run(case, *, enabled, scheduler_factory=make_scheduler):
    def full_scoring(*_args):
        return None

    original = GraphPriorityPruning.frontier
    # The independent native SGS reuse may already own windowed rounds. Isolate this
    # shortcut while keeping the actual scorer, calendar, and formal placement unchanged.
    with patch.object(GraphPriorityPruning, "frontier", original if enabled else full_scoring), \
            patch.object(scheduler_module, "create_native_sgs_reuse", lambda *_args, **_kwargs: None):
        scheduler = scheduler_factory()
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


@pytest.mark.parametrize("kind", ["ties", "invalid_static"])
def test_unproven_inputs_keep_the_full_scoring_path(kind):
    case = make_case(batch_count=6, ops_per_batch=2, auto=False, graph=True)
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


def _unique_keys(case):
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        op.id: (float(index), 0.0) for index, op in enumerate(case["operations"])}
    return case


@pytest.mark.parametrize("rule", ["slack", "cr", "atc", "atc:k=0.5"])
@pytest.mark.parametrize("window", [False, True])
def test_auto_assign_operations_prune_exactly_like_fixed_resources(rule, window):
    # The probe only chooses the pair and the feasibility penalty; both sit behind the graph key.
    case = _unique_keys(make_case(batch_count=12, ops_per_batch=5, auto=True, graph=True, window=window))
    case["dispatch_rule"] = rule
    full, _ = _run(case, enabled=False)
    pruned, stats = _run(case, enabled=True)
    assert pruned == full
    assert stats["graph_candidates_pruned"] > 0 and stats["pair_hits"] > 0


def test_auto_assign_tied_minimum_group_still_compares_every_member():
    case = make_case(batch_count=12, ops_per_batch=5, auto=True, graph=True)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {op.id: (float(op.seq),) for op in case["operations"]}
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0


def test_auto_assign_piece_scope_prunes_against_predecessor_completion():
    case = _unique_keys(make_case(batch_count=12, ops_per_batch=4, auto=True, graph=True))
    case["graph_ready_context"]["piece_scope"] = True
    for op in case["operations"]:
        op.piece_id = op.batch_id + "-P1"
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0


def test_auto_assign_production_dto_is_supported():
    from core.services.scheduler.run.schedule_input_builder import OpForScheduleAlgo

    case = _unique_keys(make_case(batch_count=8, ops_per_batch=3, auto=True, graph=True))
    normalized = []
    for op in case["operations"]:
        values: Dict[str, Any] = {name: getattr(op, name, None) for name in OpForScheduleAlgo.__dataclass_fields__}
        normalized.append(OpForScheduleAlgo(**values))
    case["operations"] = normalized
    full, _ = _run(case, enabled=False)
    actual, stats = _run(case, enabled=True)
    assert actual == full and stats["graph_candidates_pruned"] > 0


def _assignment_disabled_scheduler():
    return GreedyScheduler(calendar_service=MemoryCalendar(), config_service={"auto_assign_enabled": "no"})


@pytest.mark.parametrize("kind", ["no_machines_for_type", "no_operators_for_type", "assignment_disabled", "no_pool"])
def test_auto_assign_without_static_eligibility_keeps_the_full_path_and_first_error(kind):
    case = _unique_keys(make_case(batch_count=6, ops_per_batch=2, auto=True, graph=True))
    factory = make_scheduler
    if kind == "no_machines_for_type":
        case["resource_pool"]["machines_by_op_type"].pop("T1")
    elif kind == "no_operators_for_type":
        for machine_id in case["resource_pool"]["machines_by_op_type"]["T1"]:
            case["resource_pool"]["operators_by_machine"][machine_id] = []
    elif kind == "assignment_disabled":
        factory = _assignment_disabled_scheduler
    else:
        case["resource_pool"] = None
    errors = []
    for enabled in (False, True):
        with pytest.raises(ValidationError) as exc:
            _run(case, enabled=enabled, scheduler_factory=factory)
        errors.append((type(exc.value), str(exc.value), exc.value.field))
    assert errors[0] == errors[1]


def _pruning_for(case, *, pool):
    from core.algorithms.greedy.dispatch.sgs_graph import _prepare_graph_ready_state

    operations, batches = case["operations"], case["batches"]
    ops_by_batch = {}
    for op in operations:
        ops_by_batch.setdefault(op.batch_id, []).append(op)
    graph = _prepare_graph_ready_state(case["graph_ready_context"], ops_by_batch=ops_by_batch)
    hours = {op.id: float(op.setup_hours + op.unit_hours) for op in operations}
    return GraphPriorityPruning(graph, batches, hours, strict_mode=True, resource_pool=pool,
                                eligible_resources=eligible_auto_assign_resources)


def test_certification_reports_fixed_resources_only_when_every_operation_names_both():
    fixed = _unique_keys(make_case(batch_count=4, ops_per_batch=2, auto=False, graph=True))
    auto = _unique_keys(make_case(batch_count=4, ops_per_batch=2, auto=True, graph=True))
    fixed_pruning = _pruning_for(fixed, pool=None)
    assert fixed_pruning.supported and fixed_pruning.fixed_resources
    auto_pruning = _pruning_for(auto, pool=auto["resource_pool"])
    assert auto_pruning.supported and not auto_pruning.fixed_resources
    assert not _pruning_for(auto, pool=None).supported
    auto["resource_pool"]["machines_by_op_type"].pop("T2")
    assert not _pruning_for(auto, pool=auto["resource_pool"]).supported

