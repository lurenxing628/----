"""Candidate comparison corrections (2026-09-18): plans report the mode they decoded with, a
sibling reuse leaves no stale budget signal, a failed input certification says why, and the
orchestrator reads its candidate settings from the config snapshot without private defaults.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.errors import ValidationError
from core.services.scheduler.run import schedule_orchestrator as orchestrator
from core.services.scheduler.run.optimizer_search_budget import CandidateBudgetFeedback
from core.services.scheduler.run.schedule_candidate_dedup import (
    CERTIFIED,
    UNCERTIFIED_PREFIX,
    CandidateInputLedger,
    certify_optimizer_inputs,
    optimizer_input_fingerprint,
)
from core.services.scheduler.run.schedule_candidate_persistence_models import build_candidate_model
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_candidate_summary import candidate_public_summary
from tests.algorithm.test_optimizer_shared_budget import _IMPROVED_SCORE, _REFERENCE_SCORE, _feedback_observation
from tests.candidate.test_scheduler_candidate_runner_contract import _cfg, _outcome, _schedule_input, _StepClock


def _graph_preparation(context: Any, *, override: Any = "sgs") -> SimpleNamespace:
    return SimpleNamespace(
        graph_analysis_public=None, graph_analysis_diagnostics=None, graph_ready_context=context,
        graph_dispatch_mode_override=override,
    )


def _no_graph(_schedule_input: Any) -> SimpleNamespace:
    return _graph_preparation(None, override=None)


def _prepare(context_for_weight: Any):
    def prepare_graph(schedule_input: Any) -> SimpleNamespace:
        cfg = schedule_input.cfg
        if cfg.graph_analysis_mode == "off":
            return _no_graph(schedule_input)
        return _graph_preparation(context_for_weight(cfg.graph_critical_weight))

    return prepare_graph


def _optimize_with_modes(modes: Dict[str, str]):
    def optimize(**kwargs: Any) -> SimpleNamespace:
        cfg = kwargs["cfg"]
        key = "baseline" if cfg.graph_analysis_mode == "off" else f"graph_{cfg.graph_critical_weight}"
        outcome = _outcome(key, score=(0, 0, 10), tardiness=10.0)
        if key in modes:
            outcome.dispatch_mode = modes[key]
        return outcome

    return optimize


def _compare(*, prepare_graph, optimize, **overrides: Any):
    return run_candidate_comparison(
        schedule_input=_schedule_input(cfg=_cfg(dispatch_mode="batch_order")), prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize, weight_count=3, selection_policy="score_only", clock=_StepClock([0] * 100), **overrides,
    )


def test_plan_dispatch_mode_is_the_mode_the_optimizer_decoded_with() -> None:
    outcome = _compare(
        prepare_graph=_prepare(lambda weight: {"candidate": weight}),
        optimize=_optimize_with_modes({"graph_250": "sgs", "graph_500": "sgs", "graph_750": "sgs"}),
    )
    plans = {plan.candidate_key: plan for plan in outcome.candidates}
    # The baseline outcome carries no mode: the configured mode stands. Graph tiers decoded under sgs.
    assert plans["baseline"].dispatch_mode == "batch_order"
    assert [plans[key].dispatch_mode for key in ("graph_w1_of_3", "graph_w2_of_3", "graph_w3_of_3")] == ["sgs"] * 3
    assert all(plan.dispatch_rule == "cr" for plan in outcome.candidates)
    # The persisted column follows the plan.
    row = build_candidate_model(plans["graph_w1_of_3"], version=1, roles=[], selection_reason=None, weight_count=3)
    assert row.dispatch_mode == "sgs"
    assert build_candidate_model(plans["baseline"], version=1, roles=[], selection_reason=None, weight_count=3).dispatch_mode == "batch_order"


def test_reused_plans_keep_the_twin_mode_and_are_certified() -> None:
    outcome = _compare(
        prepare_graph=_prepare(lambda _weight: {"shared": True}),
        optimize=_optimize_with_modes({"graph_250": "sgs"}),
    )
    tiers = [plan for plan in outcome.candidates if plan.candidate_key != "baseline"]
    assert outcome.reused_count == 2
    assert [plan.reused_from_candidate_key for plan in tiers] == [None, "graph_w1_of_3", "graph_w1_of_3"]
    assert [plan.dispatch_mode for plan in tiers] == ["sgs"] * 3
    assert [plan.input_certification for plan in tiers] == [CERTIFIED] * 3
    baseline = next(plan for plan in outcome.candidates if plan.candidate_key == "baseline")
    assert baseline.input_certification == ""
    assert "input_certification" not in candidate_public_summary(tiers[0])


def test_uncertified_inputs_run_their_own_search_and_report_the_reason() -> None:
    class _Logger:
        def __init__(self) -> None:
            self.warnings: List[str] = []

        def warning(self, message: str, *args: Any) -> None:
            self.warnings.append(message % args)

    logger = _Logger()
    outcome = _compare(
        prepare_graph=_prepare(lambda _weight: {"opaque": object()}),
        optimize=_optimize_with_modes({}),
        logger=logger,
    )
    tiers = [plan for plan in outcome.candidates if plan.candidate_key != "baseline"]
    assert outcome.reused_count == 0 and all(plan.reused_from_candidate_key is None for plan in tiers)
    assert all(plan.input_certification.startswith(UNCERTIFIED_PREFIX + "TypeError: ") for plan in tiers)
    # The public view carries the code only; the raw exception text stays on the plan and in the log.
    assert candidate_public_summary(tiers[0])["input_certification"] == "uncertified"
    assert len(logger.warnings) == 3 and "不能复用兄弟方案" in logger.warnings[0]


def test_certification_names_the_failure_and_the_ledger_exposes_it() -> None:
    cfg = _cfg(graph_analysis_mode="on")
    fingerprint, reason = certify_optimizer_inputs(cfg, _graph_preparation({"keys": {1: (0.0,)}}))
    assert fingerprint is not None and reason is None
    assert optimizer_input_fingerprint(cfg, _graph_preparation({"keys": {1: (0.0,)}})) == fingerprint
    assert certify_optimizer_inputs(cfg, _graph_preparation(object())) == (None, "graph_ready_context_not_mapping: object")
    none, reason = certify_optimizer_inputs(cfg, _graph_preparation({"fn": lambda: None}))
    assert none is None and reason is not None and reason.startswith("TypeError: ")
    assert optimizer_input_fingerprint(cfg, _graph_preparation(object())) is None

    ledger = CandidateInputLedger(
        schedule_input=_schedule_input(cfg=cfg), base_cfg=cfg, prepare_graph_fn=lambda _input: _graph_preparation(object()),
    )
    spec = SimpleNamespace(sequence=1, graph_enabled=True, graph_critical_weight=1, graph_impact_weight=1, graph_downstream_weight=1)
    assert ledger.certification(spec) is None
    ledger.prepare_graph_specs([spec])
    assert ledger.certification(spec) == UNCERTIFIED_PREFIX + "graph_ready_context_not_mapping: object"
    assert ledger.completed_twin(spec) is None


def test_non_improvement_is_neutral_and_a_reused_sibling_clears_the_signal() -> None:
    feedback = CandidateBudgetFeedback("min_overdue")
    feedback.observe(_feedback_observation(_IMPROVED_SCORE))
    feedback.observe(_feedback_observation(_REFERENCE_SCORE, sequence=1))
    assigned, report = feedback.allocate(12.0, remaining_candidates=3)
    assert assigned == pytest.approx(4.0)
    assert report["reason"] == "observed_no_improvement_neutral" and report["feedback_applied"] is False
    assert report["strict_improvement"] is False

    feedback.observe(_feedback_observation(_IMPROVED_SCORE[:-1] + (2.0,), sequence=2))
    feedback.observe_reused(SimpleNamespace(sequence=3, reused_from_candidate_key="graph_w2_of_3"))
    assigned, report = feedback.allocate(9.0, remaining_candidates=2)
    assert assigned == pytest.approx(4.5)
    assert report["reason"] == "reused_sibling_no_new_signal" and report["reused_count"] == 1
    assert report["reused_from"] == "graph_w2_of_3" and "strict_improvement" not in report


@pytest.mark.parametrize("name, reader", [
    ("graph_analysis_mode", orchestrator._candidate_comparison_enabled),
    ("graph_candidate_weight_count", orchestrator._candidate_weight_count),
    ("graph_selection_policy", orchestrator._candidate_selection_policy),
    ("graph_overdue_tolerance_count", orchestrator._candidate_overdue_tolerance_count),
    ("graph_tardiness_tolerance_ratio", orchestrator._candidate_tardiness_tolerance_ratio),
])
def test_orchestrator_candidate_settings_come_from_the_snapshot_without_private_defaults(name, reader) -> None:
    snapshot = _cfg()
    assert reader(snapshot) == reader(SimpleNamespace(**{name: getattr(snapshot, name)}))
    for broken in (SimpleNamespace(), SimpleNamespace(**{name: None}), SimpleNamespace(**{name: "  "})):
        with pytest.raises(ValidationError) as exc_info:
            reader(broken)
        assert exc_info.value.field == name
