"""Contracts for the graph-ready iterated greedy stage (destroy, park, best re-insertion by real SGS decode).

The stage shares time with profiles and elite repair, respects wall clock and its own decode cap,
and decodes complete topological operation orders through the
same formal evaluator, and accepts into the incumbent only strictly better, previously unseen
outputs. Configuration errors fail loudly even when no search time is left.
"""

from __future__ import annotations

import json
import random

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy as ig
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_contract import (
    IG_PHASE,
    IteratedGreedyLimits,
    iterated_greedy_public_message,
    new_iterated_greedy_report,
    resolve_iterated_greedy_limits,
)
from core.services.scheduler.run.optimizer_graph_ready_stage_scheduler import ROTATION_POLICY
from tests._support.optimizer_graph_ready_benchmark import BenchmarkClock
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case, smtwt_repair_context

IG_ORIGIN = "graph_ready_v2_iterated_greedy"


def _ig_calls(result):
    return [call for call in result["calls"]
            if call["strategy_params"]["graph_ready_profile"]["candidate_origin"] == IG_ORIGIN]


# ---- limits -------------------------------------------------------------------------------------------------------

def test_limits_follow_the_repair_switch_and_keep_independent_hard_caps():
    limits = resolve_iterated_greedy_limits({"graph_ready_optimization": {}}, enabled=True)
    assert limits == IteratedGreedyLimits(
        enabled=True, destruction_size=3, max_destruction_size=6, insertion_window=6, max_iterations=200,
        max_decodes=400, time_budget_ms=None, generators=("time_window", "resource_window", "tardy_random"),
        checkpoint_count=8, pool_size=3, stagnation_iterations=10, temperature_ratio_start=0.1, temperature_ratio_end=0.001)
    assert resolve_iterated_greedy_limits(None, enabled=False).enabled is False
    assert resolve_iterated_greedy_limits({"graph_ready_optimization": {"iterated_greedy": {"enabled": True}}}, enabled=False).enabled is False
    custom = resolve_iterated_greedy_limits({"graph_ready_optimization": {"iterated_greedy": {
        "destruction_size": 99, "max_destruction_size": 40, "insertion_window": 4, "time_budget_ms": 250,
        "generators": ["tardy_random"], "checkpoint_count": 0, "pool_size": 1, "stagnation_iterations": 2,
        "temperature_ratio_start": 0.5, "temperature_ratio_end": 0.5}}}, enabled=True)
    # The initial size is capped by the (capped) maximum; a single generator and no checkpoints are legal.
    assert custom.destruction_size == 12 and custom.max_destruction_size == 12 and custom.insertion_window == 4
    assert custom.time_budget_ms == 250
    assert custom.generators == ("tardy_random",) and custom.checkpoint_count == 0 and custom.pool_size == 1
    assert custom.stagnation_iterations == 2 and custom.temperature_ratio_start == custom.temperature_ratio_end == 0.5


@pytest.mark.parametrize("raw", [
    {"unknown": 1}, {"enabled": "yes"}, {"destruction_size": 0}, {"insertion_window": True}, {"max_decodes": -1},
    {"time_budget_ms": 0}, {"time_share": 0.3}, {"worse_acceptance": 0.1},
    {"max_destruction_size": 0}, {"generators": []}, {"generators": "time_window"}, {"generators": ["time_window", "time_window"]},
    {"generators": ["unknown"]}, {"checkpoint_count": -1}, {"checkpoint_count": True}, {"pool_size": 0},
    {"stagnation_iterations": 0}, {"temperature_ratio_start": 0.0}, {"temperature_ratio_start": 1.5},
    {"due_date_seed": "yes"},
    {"temperature_ratio_end": 0.5}, {"temperature_ratio_end": 0.0},
    "not-a-dict",
])
def test_invalid_config_fails_loud(raw):
    with pytest.raises(ValidationError) as excinfo:
        resolve_iterated_greedy_limits({"graph_ready_optimization": {"iterated_greedy": raw}}, enabled=True)
    assert excinfo.value.field == "graph_ready_iterated_greedy"
    assert excinfo.value.details["reason"] == "graph_ready_bad_iterated_greedy_config"


def test_report_and_public_message_cover_every_status():
    report = new_iterated_greedy_report(IteratedGreedyLimits(), objective_name="min_overdue")
    assert report["phase"] == IG_PHASE and report["status"] == "not_run" and report["decodes"] == 0
    for status in ("not_run", "skipped_no_parent", "skipped_by_budget", "strict_improvement", "no_strict_improvement"):
        report["status"] = status
        assert "不构成最优性证明" in iterated_greedy_public_message(report)


# ---- pure helpers ---------------------------------------------------------------------------------------------------

def _parent(order, predecessors=None, successors=None):
    ops = list(order)
    return ig._Parent(tuple(ops), ("B",), (), {op: set(predecessors.get(op, ())) for op in ops} if predecessors else {op: set() for op in ops},
                      {op: set(successors.get(op, ())) for op in ops} if successors else {op: set() for op in ops})


def test_insertion_positions_stay_inside_the_precedence_window_nearest_first():
    parent = _parent(range(1, 10), predecessors={5: {2}}, successors={5: {8}})
    without = [1, 2, 3, 4, 6, 7, 8, 9]
    positions = ig._insertion_positions(without, 5, parent=parent, anchor=4, window=6)
    # Allowed ranks are after op 2 (index 1) and before op 8 (index 6): 2..6, nearest to the anchor first.
    assert positions == [4, 3, 5, 2, 6]
    assert ig._insertion_positions(without, 5, parent=parent, anchor=0, window=2) == [2, 3]
    free = _parent(range(1, 10))
    assert ig._insertion_positions(without, 5, parent=free, anchor=4, window=3) == [4, 3, 5]
    # Power-of-two probes first (4, 3, 5, 2, 6, 0, 8), then the remaining ranks nearest-first.
    assert ig._insertion_positions(without, 5, parent=free, anchor=4, window=32) == [4, 3, 5, 2, 6, 0, 8, 1, 7]
    cyclic = _parent(range(1, 10), predecessors={5: {8}}, successors={5: {2}})
    with pytest.raises(ValidationError) as excinfo:
        ig._insertion_positions(without, 5, parent=cyclic, anchor=4, window=6)
    assert excinfo.value.details["reason"] == "graph_ready_ig_cyclic_order"


def test_parking_puts_a_removed_operation_just_before_its_first_successor():
    assert ig._latest_rank([1, 2, 3, 4], 9, successors={3}) == 2
    assert ig._latest_rank([1, 2, 3, 4], 9, successors=set()) == 4
    assert ig._latest_rank([1, 2, 3, 4], 9, successors={7}) == 4


def test_parking_keeps_precedence_when_a_removed_operation_and_its_successor_are_both_removed():
    # Chain 1 -> 2 -> 3 -> 4 next to independent 5, 6; removing 2 and 3 together must keep 2 ahead of 3
    # and both between 1 and 4 (this order crashed the end-to-end matrix before successors-first parking).
    successors = {1: {2}, 2: {3}, 3: {4}, 4: set(), 5: set(), 6: set()}
    predecessors = {1: set(), 2: {1}, 3: {2}, 4: {3}, 5: set(), 6: set()}
    order = (1, 5, 2, 3, 6, 4)
    parked = ig._park(order, {2, 3}, successors=successors)
    position = {op: index for index, op in enumerate(parked)}
    assert sorted(parked) == [1, 2, 3, 4, 5, 6]
    assert position[1] < position[2] < position[3] < position[4]
    parent = ig._Parent(order, ("B",), (), predecessors, successors)
    for op in (2, 3):
        without = [item for item in parked if item != op]
        positions = ig._insertion_positions(without, op, parent=parent, anchor=order.index(op), window=8)
        assert positions, "the window must exist for every parked operation"
        for pos in positions:
            trial = without[:pos] + [op] + without[pos:]
            where = {item: index for index, item in enumerate(trial)}
            assert all(where[p] < where[o] for o, ps in predecessors.items() for p in ps)
    # Removing a whole chain in one go parks it in order at the end.
    assert ig._park((1, 2, 3, 4), {1, 2, 3, 4}, successors=successors)[:4] == [1, 2, 3, 4]


def test_destroy_prefers_tardy_or_critical_operations_and_never_empties_the_order():
    rnd = random.Random(3)
    order = tuple(range(1, 11))
    signals = {op: 0.0 for op in order}
    signals.update({4: 5.0, 7: 2.0, 9: 1e-3})
    removed = ig._destroy(order, rnd=rnd, size=4, signals=signals)
    assert len(removed) == len(set(removed)) == 4
    assert removed[0] == 4 and removed[1] == 7
    assert ig._destroy((1,), rnd=rnd, size=3, signals={}) == ()
    assert len(ig._destroy((1, 2), rnd=rnd, size=3, signals={})) == 1


# ---- production path --------------------------------------------------------------------------------------------------

def test_disabled_stage_reports_not_run_and_adds_no_decode():
    result = run_production_repair_case(clock=BenchmarkClock(), iterated_greedy={"enabled": False})
    report = result["iterated_greedy"]
    assert report["status"] == "not_run" and report["decodes"] == 0 and report["enabled"] is False
    assert _ig_calls(result) == []
    assert {"phase": IG_PHASE, "reason": "not_run"} in result["state"].skipped_phases
    assert "迭代贪心未启用" in result["state"].candidate_profile["message"]


def test_decoder_that_rejects_every_decision_stops_the_stage_without_retrying_orders():
    from core.services.scheduler.run.optimizer_graph_ready_candidates import evaluate_graph_ready_candidate

    rejected = []

    def schedule(scheduler, **kwargs):
        origin = kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"]
        if origin == IG_ORIGIN:
            rejected.append(tuple(sorted(kwargs["graph_ready_context"]["graph_priority_key_by_op_id"].items())))
            raise ValidationError("controlled decode failure", field="schedule")
        from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
        return _schedule_with_scheduler(scheduler, **kwargs)

    result = run_production_repair_case(clock=lambda: 0.0, schedule_fn=schedule, strict_mode=False)
    report = result["iterated_greedy"]
    # The walk starts by decoding the parent's own order; when the decoder rejects even that, the stage stops there.
    assert report["stop_reason"] in {"parent_order_rejected", "decoder_rejections", "search_space_exhausted"}
    assert report["status"] == "no_strict_improvement"
    assert report["decodes"] == len(rejected) == len(set(rejected)) >= 1, "a rejected decision must not be decoded twice"
    assert report["rejected_by_reason"] and sum(report["rejected_by_reason"].values()) == report["decodes"]
    assert result["best"]["candidate_origin"] != IG_ORIGIN
    with pytest.raises(ValidationError, match="controlled decode failure"):
        run_production_repair_case(clock=lambda: 0.0, schedule_fn=schedule, strict_mode=True)


def test_rotation_starts_no_decode_after_the_shared_deadline():
    now = [0.0]

    def clock():
        return now[0]

    starts = []

    def schedule(scheduler, **kwargs):
        from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
        starts.append(now[0])
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += 0.3
        return result

    result = run_production_repair_case(clock=clock, schedule_fn=schedule, time_budget_seconds=1.0)
    report = result["iterated_greedy"]
    assert all(start < 1.0 for start in starts)
    assert report["decodes"] == len(_ig_calls(result))
    assert tuple(result["best"]["score"]) <= tuple(result["baseline"]["score"])
    assert report["stop_reason"] == "time_budget"
    assert _ig_calls(result) == []


def test_real_decode_walk_on_smtwt_graph_case_is_complete_topological_and_accounted():
    case = smtwt_repair_context(size=40, index=2)
    repair_only = run_production_repair_case(case=case, clock=BenchmarkClock(), time_budget_seconds=1000,
                                             iterated_greedy={"enabled": False})
    case = smtwt_repair_context(size=40, index=2)
    result = run_production_repair_case(case=case, clock=BenchmarkClock(), time_budget_seconds=1000,
                                        iterated_greedy={"max_decodes": 120, "max_iterations": 40})
    report = result["iterated_greedy"]
    calls = _ig_calls(result)
    assert report["status"] == "strict_improvement" and report["improvements"] > 0
    assert report["decodes"] == len(calls) == 120 and report["stop_reason"] == "decode_budget"
    assert report["iterations"] > 0 and report["walk_accepted"] > 0
    assert tuple(result["best"]["score"]) < tuple(repair_only["best"]["score"])
    assert result["best"]["candidate_origin"] == IG_ORIGIN
    assert result["best"]["mutable_scope"]["scope"] == "graph_ready_iterated_greedy"
    assert result["best"]["mutable_scope"]["candidate_policy"] == "iterated_greedy"
    assert result["state"].best_origin == IG_ORIGIN
    # Every decode carried a complete, topological operation order for the mutable scope.
    mutable = {int(op.id) for op in case["operations"]}
    predecessors = case["graph_context"]["predecessor_op_ids_by_op_id"]
    decisions = set()
    for call in calls:
        keys = call["graph_ready_context"]["graph_priority_key_by_op_id"]
        assert set(keys) == mutable
        order = sorted(mutable, key=lambda op_id: keys[op_id])
        position = {op_id: index for index, op_id in enumerate(order)}
        assert all(position[parent] < position[op_id] for op_id in order for parent in predecessors.get(op_id, ()) if parent in mutable)
        decisions.add((tuple(order), tuple(call["batch_order_override"]), json.dumps(call["strategy_params"], sort_keys=True)))
    # Proving resumed trials and capturing checkpoints for a full trial are separately accounted.
    checkpoints = report["checkpoints"]
    assert checkpoints["resumed_decodes"] > 0 and checkpoints["picks_saved"] > 0
    assert checkpoints["equivalence_checks"] > 0
    assert len(decisions) == len(calls) - checkpoints["equivalence_checks"] - report["reference_capture_decodes"], \
        "a repeated full decision must be a reported verification or reference capture"
    resumed = [call for call in calls if call.get("decode_resume") is not None]
    assert len(resumed) == checkpoints["resumed_decodes"]
    assert all(call.get("decode_checkpoints") is None for call in resumed)
    assert report["parent_order_score"] is not None and report["parent_order_consistent"] in (True, False)
    assert sum(item["calls"] for item in report["generators"].values()) == report["iterations"] + report["interrupted_iterations"]
    assert report["interrupted_iterations"] <= 1
    # Accounting: every IG decode is one evaluated candidate; repair and profile counts are untouched.
    assert result["state"].evaluated_candidates == len(result["calls"]) + 1
    assert result["repair"]["repair_evaluated_candidates"] == repair_only["repair"]["repair_evaluated_candidates"]
    assert result["repair"].get("repair_time_ceiling_reason") is None
    summary = next(attempt for attempt in result["attempts"] if attempt.get("tag") == IG_PHASE)
    assert summary["iterated_greedy"] is result["state"].candidate_profile["graph_ready_optimization"]["iterated_greedy"] or \
        summary["iterated_greedy"]["decodes"] == report["decodes"]
    assert "已采纳严格更优方案" in result["state"].candidate_profile["message"]


@pytest.mark.parametrize("budget,ig_decodes", [(3.0, 0), (4.0, 1)])
def test_rotation_gives_the_stage_time_alongside_repair_instead_of_leftovers(budget, ig_decodes):
    # Real SGS with one logical second per decode. The v1 anchor costs one extra bootstrap
    # decode before v2 supplies the parent needed for repair, so all three starts require four.
    from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler

    now, starts = [0.0], []

    def schedule(scheduler, **kwargs):
        starts.append((now[0], kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"]))
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += 1.0
        return result

    case = smtwt_repair_context(size=40, index=0)
    result = run_production_repair_case(case=case, clock=lambda: now[0], schedule_fn=schedule, time_budget_seconds=budget)
    assert starts == [(0.0, "graph_ready_base"), (1.0, "graph_ready_v2_generated"),
                      (2.0, "graph_ready_v2_repaired"), (3.0, IG_ORIGIN)][:int(budget)]
    efficiency = next(attempt["profile_efficiency"] for attempt in result["attempts"] if "profile_efficiency" in attempt)
    assert efficiency["rotation_policy"] == ROTATION_POLICY
    assert efficiency["stage_order"] == ["profiles", "elite_repair", "iterated_greedy"]
    assert set(efficiency["stage_time_ms"]) == set(efficiency["stage_tasks"]) == set(efficiency["stage_order"])
    for name in ("profiles", "elite_repair"):
        assert efficiency["stage_startup"][name] == {"status": "task_started", "reason": None}
    assert efficiency["stage_startup"]["iterated_greedy"] == (
        {"status": "task_started", "reason": None} if ig_decodes else {"status": "skipped", "reason": "time_budget"})
    assert efficiency["profile_decodes"] == 2
    assert result["repair"]["repair_evaluated_candidates"] == 1
    assert result["iterated_greedy"]["decodes"] == ig_decodes
    assert now[0] == budget
    assert result["repair"].get("repair_time_ceiling_reason") is None
