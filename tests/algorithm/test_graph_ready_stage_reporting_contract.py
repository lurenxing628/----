"""Graph phase stage reporting: repair stream offsets, profile stagnation exit, honest phase-skip publication."""
from __future__ import annotations

from types import SimpleNamespace

from core.services.scheduler.run.optimizer_graph_ready_feature_basis import (
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
)
from core.services.scheduler.run.optimizer_graph_ready_predecode import GraphReadyProfileSearch
from core.services.scheduler.run.optimizer_graph_ready_profiles import GRAPH_READY_PHASE, GraphReadyWeightProfile
from core.services.scheduler.run.optimizer_graph_ready_repair_neighbors import RepairNeighborhood
from core.services.scheduler.run.optimizer_graph_ready_repair_portfolio import ParentRepairPortfolio, RepairPortfolio
from core.services.scheduler.run.optimizer_graph_ready_stages import PROFILE_STAGNATION_REPEATED_OUTPUTS, ProfileStage


def _profile(basis):
    return GraphReadyWeightProfile(slug="v2_" + basis, profile_order=0, raw_weights={}, effective_weights={}, candidate_origin="o",
                                   candidate_policy="p", formula_version="graph_ready_v2", feature_basis=basis)


def _portfolio(rotation):
    order = ("B0", "B1", "B2", "B3", "B4")
    moves = tuple(("adjacent_swap", i, i + 1) for i in range(4)) + (("single_insert", 0, 4), ("single_insert", 1, 3))
    return RepairPortfolio(RepairNeighborhood(order, moves[rotation:] + moves[:rotation]), (), ())


def _labels(items):
    return [(kind, decision.batch_order, profile.feature_basis) for kind, decision, profile in items]


def test_adding_a_basis_variant_mid_visit_neither_revisits_nor_skips_decisions():
    first = ParentRepairPortfolio(((_profile(SUCCESSOR_WORKLOAD_BASIS), _portfolio(0)),))
    stream = _labels(first.profiled_decisions())
    consumed = {SUCCESSOR_WORKLOAD_BASIS: 3}
    visited, pending = stream[:3], stream[3:]
    both = first.with_variant(_profile(BATCH_WORKLOAD_BASIS), _portfolio(2))
    resumed = _labels(both.profiled_decisions(skip_by_basis=consumed))
    assert [item for item in resumed if item in visited] == [], "consumed decisions must not be yielded again"
    assert [item for item in pending if item not in resumed] == [], "unvisited decisions of the first stream must stay reachable"
    added = [(kind, decision.batch_order, BATCH_WORKLOAD_BASIS) for kind, decision in _portfolio(2).decisions()]
    assert all(item in resumed for item in added), "the new variant's whole stream is still visited"
    # The new variant's decisions interleave from its own start; the first stream continues after its prefix.
    assert resumed[0][2] == SUCCESSOR_WORKLOAD_BASIS and resumed[0] == pending[0]
    assert resumed[1][2] == BATCH_WORKLOAD_BASIS
    assert len(resumed) == both.candidate_count - 3


def _profile_stage(profile_count=10, *, cost_stopped=False, stop_reason=None):
    search = SimpleNamespace(cost_stopped=cost_stopped, can_start=lambda: not cost_stopped and stop_reason is None,
                             budget=SimpleNamespace(stop_reason=stop_reason), report={"stagnation_stop": None})
    return ProfileStage(profiles=[_profile(SUCCESSOR_WORKLOAD_BASIS)] * profile_count, search=search, pool=None, state=None,
                        order=[], strict_mode=True, base_strategy=None, dispatch_rule_cfg="slack", version=0, attempts=[],
                        improvement_trace=[], search_report_state=None, clock=lambda: 0.0, t_begin=0.0)


def test_profile_stage_stops_after_a_run_of_already_seen_outputs_and_reports_it():
    stage = _profile_stage()
    for _ in range(PROFILE_STAGNATION_REPEATED_OUTPUTS - 1):
        stage.index += 1
        stage._note_output(True)
    assert stage.available() and stage.unavailable_reason() is None
    stage._note_output(False)  # a fresh schedule resets the run
    for _ in range(PROFILE_STAGNATION_REPEATED_OUTPUTS - 1):
        stage._note_output(True)
    assert stage.available()
    stage._note_output(True)
    assert not stage.available() and stage.unavailable_reason() == "profiles_stagnated"
    assert stage.search.report["stagnation_stop"] == {
        "consecutive_repeated_outputs": PROFILE_STAGNATION_REPEATED_OUTPUTS, "unvisited_profiles": 10 - stage.index}


def test_profile_stage_names_the_estimated_decode_cost_stop_instead_of_an_empty_reason():
    stage = _profile_stage(cost_stopped=True)
    assert not stage.available() and stage.unavailable_reason() == "skipped_by_estimated_decode_cost"
    exhausted = _profile_stage(profile_count=0)
    assert exhausted.unavailable_reason() == "profiles_exhausted"
    timed_out = _profile_stage(stop_reason="time_budget")
    assert timed_out.unavailable_reason() == "time_budget"


class _ReportState:
    def __init__(self):
        self.candidate_profile = {}
        self.calls = []

    def update_candidate_profile(self, **kwargs):
        self.candidate_profile.update(kwargs)

    def mark_deadline_reached(self):
        self.calls.append("deadline")

    def mark_phase_skipped(self, phase, reason):
        self.calls.append(("skipped", phase, reason))


def _publish(profile_decodes):
    budget = SimpleNamespace(stop_reason="time_budget", profile_decodes=profile_decodes, summary=lambda: {"stop_reason": "time_budget"})
    search = GraphReadyProfileSearch(evaluate=lambda **kwargs: None, pool=None, budget=budget, profile_count=3)
    state = _ReportState()
    search.publish(attempts=[], report_state=state)
    return state.calls


def test_phase_with_decodes_that_hit_the_deadline_is_not_published_as_skipped():
    assert _publish(profile_decodes=0) == ["deadline", ("skipped", GRAPH_READY_PHASE, "time_budget")]
    assert _publish(profile_decodes=3) == ["deadline"]
