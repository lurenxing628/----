"""Native reuse must preserve outputs, mutations, callback visibility and formal placement."""

import cProfile
import pstats
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple, cast
from unittest.mock import patch

import pytest

from core.algorithm_contracts.dispatch_rules import DispatchRule
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_reuse, sgs_reuse_scope
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch import sgs, sgs_scoring
from core.algorithms.greedy.run_context import ScheduleRunContext
from core.errors import ValidationError
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from tests._support.busy_block_case import BASE, native_calendar


def _case(count, *, shared_machine=False, shared_operator=False, namespace=False) -> Tuple[List[Any], Dict[str, Any]]:
    operations = [BatchOperation(
        id=index + 1, op_code="OP" + str(index), batch_id="B" + str(index), seq=1,
        machine_id="M0" if shared_machine else "M" + str(index),
        operator_id="O0" if shared_operator else "O" + str(index),
        setup_hours=0.25, unit_hours=0.75, op_type_name="TURN",
    ) for index in range(count)]
    batches = {op.batch_id: Batch(batch_id=op.batch_id, part_no="P", quantity=1, due_date="2026-09-30")
               for op in operations}
    if namespace:
        operations = [SimpleNamespace(**vars(op)) for op in operations]
        batches = {key: SimpleNamespace(**vars(value)) for key, value in batches.items()}
    return operations, batches


def _run(operations, batches, *, enabled, scheduler_type=scheduler_module.GreedyScheduler, **options):
    factory = scheduler_module.create_native_sgs_reuse if enabled else lambda *args: None
    with native_calendar() as calendar, patch.object(scheduler_module, "create_native_sgs_reuse", factory):
        scheduler = scheduler_type(calendar)
        profile = cProfile.Profile()
        profile.enable()
        results, summary, strategy, params = scheduler.schedule(
            operations, batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack", **options)
        profile.disable()
        counts = {}
        for (_, _, name), stat in cast(Any, pstats.Stats(profile)).stats.items():
            if name in ("_score_candidate", "estimate_internal_slot"):
                counts[name] = counts.get(name, 0) + stat[1]
        fields = vars(summary).copy()
        fields.pop("duration_seconds")
        return (results, fields, strategy, params), counts


@pytest.mark.parametrize("count", [10, 30])
@pytest.mark.parametrize("namespace", [False, True])
def test_disjoint_native_resources_score_once_and_reuse_formal_estimate(count, namespace):
    operations, batches = _case(count, namespace=namespace)
    before = deepcopy((operations, batches))
    legacy, old = _run(operations, batches, enabled=False)
    actual, new = _run(operations, batches, enabled=True)
    assert actual == legacy
    assert (operations, batches) == before
    # Without the certificate the witness cache still scores each disjoint candidate once and hands the
    # scoring estimate to formal placement, so both paths estimate every operation exactly once.
    assert old["_score_candidate"] == new["_score_candidate"] == count
    assert old["estimate_internal_slot"] == new["estimate_internal_slot"] == count
    assert current_sgs_reuse() is None


@pytest.mark.parametrize("machine,operator", [(True, False), (False, True), (True, True)])
def test_shared_resource_scores_invalidate_and_results_match(machine, operator):
    operations, batches = _case(8, shared_machine=machine, shared_operator=operator)
    legacy, old = _run(operations, batches, enabled=False)
    actual, new = _run(operations, batches, enabled=True)
    assert actual == legacy
    assert new["_score_candidate"] == old["_score_candidate"] == 36
    # Shared resources invalidate every peer each round; the selected candidate's scoring estimate is
    # still handed to formal placement, so no extra estimate is spent there.
    assert new["estimate_internal_slot"] == old["estimate_internal_slot"] == 36


def test_scheduler_subclass_keeps_results_and_falls_back_to_the_witness_cache():
    class Customized(scheduler_module.GreedyScheduler):
        pass
    operations, batches = _case(8)
    old, _ = _run(operations, batches, enabled=False, scheduler_type=Customized)
    actual, counts = _run(operations, batches, enabled=True, scheduler_type=Customized)
    assert actual == old
    # The certificate refuses a subclass; fixed-resource scoring never touches scheduler methods, so the
    # witness cache still serves every unchanged candidate and hands its estimate to formal placement.
    assert counts == {"_score_candidate": 8, "estimate_internal_slot": 8}


@pytest.mark.parametrize("scope", ["score_function", "calendar_method", "callback"])
def test_instrumented_native_functions_are_observable_every_round(scope):
    operations, batches = _case(5)
    seen = []
    if scope == "score_function":
        original = sgs._score_candidate
        def wrapped(*args, **kwargs):
            seen.append("score")
            return original(*args, **kwargs)
        with patch.object(sgs, "_score_candidate", wrapped):
            _, counts = _run(operations, batches, enabled=True)
        assert len(seen) == counts["_score_candidate"] == 15
    else:
        with native_calendar() as calendar:
            scheduler = scheduler_module.GreedyScheduler(calendar)
            owner, name = (calendar, "get_efficiency") if scope == "calendar_method" else (scheduler, "_schedule_internal")
            original = getattr(owner, name)
            def method_wrapper(*args, **kwargs):
                seen.append(name)
                return original(*args, **kwargs)
            setattr(owner, name, method_wrapper)
            scheduler.schedule(operations, batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")
        # An instrumented calendar disables the certificate; the witness cache then estimates each
        # disjoint candidate once and formal placement reuses that estimate.
        assert len(seen) == 5


def _direct_reuse(calendar):
    operations, batches = _case(2)
    scheduler = scheduler_module.GreedyScheduler(calendar)
    ctx = ScheduleRunContext.from_legacy_scheduler(scheduler)
    state = ScheduleRunState(base_time=BASE)
    reuse = scheduler_module.create_native_sgs_reuse(
        scheduler, ctx, state, operations, batches, scheduler_module._NATIVE_SGS_SCHEDULER_GUARD,
        scheduler_module._NATIVE_SGS_CONTEXT_GUARD)
    assert reuse is not None
    inputs: Dict[str, Any] = dict(op=operations[1], batch=batches["B1"], batch_id="B1", batch_order={"B0": 0, "B1": 1},
                  graph_state=None, end_dt_exclusive=None, machine_downtimes={}, dispatch_rule=DispatchRule.SLACK,
                  strict_mode=True, avg_proc_hours=1.0, total_hours_by_op_id={2: 1.0})
    def score():
        return sgs._score_candidate(ctx, state, inputs["op"], inputs["batch"], inputs["batch_id"],
                                    inputs["batch_order"], inputs["dispatch_rule"], inputs["end_dt_exclusive"],
                                    inputs["machine_downtimes"], False, None, inputs["strict_mode"],
                                    inputs["avg_proc_hours"], inputs["total_hours_by_op_id"], inputs["graph_state"])
    return reuse, inputs, score


@pytest.mark.parametrize("mutation", ["due", "priority", "prev_end", "machine", "operator", "downtime", "policy", "policy_clear", "graph"])
def test_same_length_native_content_changes_force_real_rescore(mutation):
    with native_calendar() as calendar:
        reuse, inputs, score = _direct_reuse(calendar)
        assert reuse is not None
        calls = []
        def observed():
            calls.append(1)
            return score()
        with sgs_reuse_scope(reuse):
            reuse.begin_round()
            first = reuse.score(observed, inputs)
            reuse.begin_round()
            assert reuse.score(observed, inputs) == first
            assert len(calls) == 1
            if mutation == "due":
                inputs["batch"].due_date = "2026-09-29"
            elif mutation == "priority":
                inputs["batch"].priority = "urgent"
            elif mutation == "prev_end":
                reuse.state.batch_progress["B1"] = BASE + timedelta(hours=2)
            elif mutation in ("machine", "operator"):
                mapping = reuse.state.machine_timeline if mutation == "machine" else reuse.state.operator_timeline
                key = "M1" if mutation == "machine" else "O1"
                mapping[key] = [(BASE, BASE + timedelta(hours=1))]
                mapping[key][0] = (BASE, BASE + timedelta(hours=2))
            elif mutation == "downtime":
                inputs["machine_downtimes"]["M1"] = [(BASE, BASE + timedelta(hours=2))]
            elif mutation == "policy":
                policy = next(value for key, value in calendar._engine._policy_cache.items() if key[0] == "O1")
                policy.efficiency = 0.5
            elif mutation == "policy_clear":
                calendar._engine.clear_policy_cache()
            else:
                inputs["graph_state"] = {"score_enabled": True, "graph_priority_key_by_op_id": {2: (3.0,)}}
            reuse.begin_round()
            actual = reuse.score(observed, inputs)
            assert len(calls) == 2
            assert actual == score()


def test_invalid_date_errors_remain_in_original_candidate_order():
    operations, batches = _case(3)
    batches["B1"].due_date = "invalid"
    batches["B2"].due_date = "also-invalid"
    with native_calendar() as calendar:
        reuse, inputs, score = _direct_reuse(calendar)
        inputs["batch"].due_date = "invalid"
        with sgs_reuse_scope(reuse):
            reuse.begin_round()
            for _ in range(2):
                with pytest.raises(ValidationError) as caught:
                    reuse.score(score, inputs)
                assert caught.value.field == "due_date"
            assert not reuse.entries


def test_due_date_cache_is_bounded_and_does_not_cache_invalid_input():
    sgs_scoring._DUE_TEXT_CACHE.clear()
    for day in range(4100):
        value = (BASE + timedelta(days=day)).date().isoformat()
        parsed = sgs_scoring._parse_due_date(value, strict_mode=True)
        assert parsed is not None and parsed.isoformat() == value
    assert len(sgs_scoring._DUE_TEXT_CACHE) == 4096
    for _ in range(2):
        assert sgs_scoring._parse_due_date("invalid", strict_mode=False) is None
    assert (False, "invalid") not in sgs_scoring._DUE_TEXT_CACHE


def test_owned_segment_certificate_override_cannot_hide_same_length_mutation():
    with native_calendar() as calendar:
        reuse, inputs, score = _direct_reuse(calendar)
        reuse.state.machine_timeline["M1"] = [(BASE, BASE + timedelta(hours=1))]
        segments = reuse.state.machine_timeline["M1"]
        with sgs_reuse_scope(reuse):
            reuse.begin_round()
            first = reuse.score(score, inputs)
            certificate = segments.certificate()
            segments.certificate = lambda: certificate
            segments[0] = (BASE, BASE + timedelta(hours=2))
            reuse.begin_round()
            actual = reuse.score(score, inputs)
            assert actual == score()
            assert actual != first


@pytest.mark.parametrize("kind", ["timeline", "type_state"])
def test_inherited_dict_get_override_keeps_original_due_date_error_first(kind):
    with native_calendar() as calendar:
        reuse, inputs, score = _direct_reuse(calendar)
        inputs["batch"].due_date = "invalid"
        mapping = reuse.state.machine_timeline if kind == "timeline" else reuse.state.last_op_type_by_machine
        def failing_get(*args):
            raise RuntimeError("custom get")
        mapping.get = failing_get
        assert not reuse.supported()
        with sgs_reuse_scope(reuse):
            reuse.begin_round()
            with pytest.raises(ValidationError) as caught:
                reuse.score(score, inputs)
            assert caught.value.field == "due_date"


@pytest.mark.parametrize("name", ["_scoring_resources", "_estimate_scoring_slot", "_scoring_total_hours"])
def test_scoring_helper_overrides_remain_visible_on_every_candidate(name):
    operations, batches = _case(5)
    original = getattr(sgs_scoring, name)
    with patch.object(sgs_scoring, name, wraps=original) as observed:
        _, counts = _run(operations, batches, enabled=True)
    assert counts["_score_candidate"] == observed.call_count == 15


def test_decode_counter_is_monotonic_without_changing_native_methods():
    operations, batches = _case(5)
    with native_calendar() as calendar:
        scheduler = scheduler_module.GreedyScheduler(calendar)
        for expected in (1, 2):
            scheduler.schedule(operations, batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")
            assert scheduler._decode_invocations == expected
            assert scheduler._last_sgs_reuse_stats["hits"] == 10


def test_context_originals_are_fixed_before_first_reuse_construction(monkeypatch):
    operations, batches = _case(5)
    original = ScheduleRunContext.schedule_internal
    calls = []
    def overridden(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(ScheduleRunContext, "schedule_internal", overridden)
    actual, counts = _run(operations, batches, enabled=True)
    assert actual[1]["scheduled_ops"] == 5
    assert len(calls) == 5
    assert counts == {"_score_candidate": 5, "estimate_internal_slot": 5}
