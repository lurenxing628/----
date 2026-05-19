from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import core.services.scheduler.run.schedule_candidate_runner as runner
from core.algorithms import ScheduleResult
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.run.schedule_candidate_health import HEALTH_BETTER, HEALTH_UNAVAILABLE
from core.services.scheduler.run.schedule_candidate_runner import (
    CANDIDATE_STATUS_COMPLETED,
    CANDIDATE_STATUS_FAILED,
    CANDIDATE_STATUS_SKIPPED,
    run_candidate_comparison,
)


def _cfg(**overrides) -> ScheduleConfigSnapshot:
    data = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "sgs",
        "dispatch_rule": "cr",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "improve",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_debug_export": "no",
    }
    data.update(overrides)
    return ScheduleConfigSnapshot(**data)


def _schedule_input(**overrides) -> SimpleNamespace:
    data = {
        "cal_svc": SimpleNamespace(),
        "cfg_svc": SimpleNamespace(
            VALID_STRATEGIES=("priority_first", "weighted", "fifo"),
            VALID_DISPATCH_MODES=("sgs", "batch_order"),
            VALID_DISPATCH_RULES=("cr", "atc", "slack"),
            VALID_OBJECTIVES=("min_overdue", "min_tardiness"),
            VALID_ALGO_MODES=("greedy", "improve"),
        ),
        "cfg": _cfg(),
        "algo_ops_to_schedule": [],
        "batches": {},
        "start_dt_norm": datetime(2026, 5, 1, 8, 0, 0),
        "end_date_norm": None,
        "downtime_map": {},
        "seed_results": [],
        "resource_pool": None,
        "optimizer_seed_version": 12,
        "readiness_gate_enabled": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _result(op_id: int, start_hour: int, end_hour: int) -> ScheduleResult:
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id="B1",
        seq=op_id,
        start_time=datetime(2026, 5, 1, start_hour, 0, 0),
        end_time=datetime(2026, 5, 1, end_hour, 0, 0),
    )


def _outcome(candidate_key: str, *, score, results=None, tardiness: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        results=list(results or [_result(1, 8, 10), _result(2, 10, 12)]),
        summary=SimpleNamespace(failed_ops=int(score[0]), warnings=[], errors=[]),
        metrics=SimpleNamespace(overdue_count=int(score[1]), total_tardiness_hours=float(tardiness)),
        best_score=tuple(score),
        best_order=[candidate_key],
        attempts=[],
        improvement_trace=[],
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
    )


class _StepClock:
    def __init__(self, values):
        self._values = list(values)

    def __call__(self):
        if self._values:
            return float(self._values.pop(0))
        return 999.0


def test_candidate_comparison_honors_strict_mode_for_runtime_config(monkeypatch) -> None:
    calls = []

    def fake_ensure_snapshot(cfg, *, strict_mode, source="scheduler.runtime_config"):
        calls.append((strict_mode, source))
        return cfg

    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    monkeypatch.setattr(runner, "ensure_schedule_config_snapshot", fake_ensure_snapshot)

    runner.run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        strict_mode=True,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    assert calls
    assert calls[0][0] is True


def test_candidate_runner_runs_baseline_first_and_passes_graph_context_to_critical_candidates() -> None:
    prepare_calls = []
    optimize_calls = []

    def prepare_graph(schedule_input):
        prepare_calls.append(schedule_input.cfg)
        if schedule_input.cfg.graph_analysis_mode == "off":
            return SimpleNamespace(
                graph_analysis_public=None,
                graph_analysis_diagnostics=None,
                graph_ready_context=None,
                graph_dispatch_mode_override=None,
            )
        return SimpleNamespace(
            graph_analysis_public={"status": "available"},
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context={"candidate": schedule_input.cfg.graph_critical_weight},
            graph_dispatch_mode_override="sgs",
        )

    def optimize(**kwargs):
        optimize_calls.append(kwargs)
        key = "baseline" if kwargs["cfg"].graph_analysis_mode == "off" else f"graph_{kwargs['cfg'].graph_critical_weight}"
        return _outcome(key, score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    assert [candidate.candidate_key for candidate in outcome.candidates] == [
        "baseline",
        "graph_w1_of_3",
        "graph_w2_of_3",
        "graph_w3_of_3",
    ]
    assert [candidate.status for candidate in outcome.candidates] == [CANDIDATE_STATUS_COMPLETED] * 4
    assert prepare_calls[0].graph_analysis_mode == "off"
    assert [cfg.graph_analysis_mode for cfg in prepare_calls[1:]] == ["on", "on", "on"]
    assert optimize_calls[0]["graph_ready_context"] is None
    assert optimize_calls[1]["graph_ready_context"] == {"candidate": 250}
    assert optimize_calls[1]["graph_dispatch_mode_override"] == "sgs"


def test_candidate_runner_uses_graph_health_context_for_critical_health() -> None:
    def prepare_graph(schedule_input):
        if schedule_input.cfg.graph_analysis_mode == "off":
            return SimpleNamespace(
                graph_analysis_public=None,
                graph_analysis_diagnostics=None,
                graph_health_context=None,
                graph_ready_context=None,
                graph_dispatch_mode_override=None,
            )
        return SimpleNamespace(
            graph_analysis_public={"status": "available"},
            graph_analysis_diagnostics={
                "critical_path_sample": ["op:1"],
                "critical_path_count": 2,
                "critical_path_truncated": True,
            },
            graph_health_context={
                "critical_path_op_ids": [1, 2],
                "top_impact_op_ids": [1, 2],
            },
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        if kwargs["cfg"].graph_analysis_mode == "off":
            return _outcome(
                "baseline",
                score=(0, 0, 10),
                results=[_result(1, 8, 10), _result(2, 11, 13)],
            )
        return _outcome(
            "critical",
            score=(0, 0, 10),
            results=[_result(1, 8, 9), _result(2, 9, 11)],
        )

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    critical = next(candidate for candidate in outcome.candidates if candidate.kind == "critical_chain")
    assert critical.health is not None
    assert critical.health.state == HEALTH_BETTER


def test_candidate_runner_health_uses_private_health_context_not_diagnostics_samples() -> None:
    def prepare_graph(schedule_input):
        if schedule_input.cfg.graph_analysis_mode == "off":
            return SimpleNamespace(
                graph_analysis_public=None,
                graph_analysis_diagnostics=None,
                graph_health_context=None,
                graph_ready_context=None,
                graph_dispatch_mode_override=None,
            )
        return SimpleNamespace(
            graph_analysis_public={"status": "available", "critical_path_op_ids": [999]},
            graph_analysis_diagnostics={
                "critical_path_sample": ["op:999"],
                "graph_score_sample": [{"op_id": 999, "impact_count": 999}],
                "node_metrics_sample": [{"node_id": "op:999", "impact_count": 999}],
            },
            graph_health_context={
                "critical_path_op_ids": [1, 2],
                "top_impact_op_ids": [1, 2],
            },
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        if kwargs["cfg"].graph_analysis_mode == "off":
            return _outcome(
                "baseline",
                score=(0, 0, 10),
                results=[_result(1, 8, 10), _result(2, 11, 13)],
            )
        return _outcome(
            "critical",
            score=(0, 0, 10),
            results=[_result(1, 8, 9), _result(2, 9, 11)],
        )

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    critical = next(candidate for candidate in outcome.candidates if candidate.kind == "critical_chain")
    assert critical.health is not None
    assert critical.health.state == HEALTH_BETTER
    assert critical.health.critical_chain_node_count == 2
    assert critical.health.top_impact_op_count == 2


def test_candidate_runner_health_does_not_fall_back_to_diagnostics_sample() -> None:
    def prepare_graph(schedule_input):
        if schedule_input.cfg.graph_analysis_mode == "off":
            return SimpleNamespace(
                graph_analysis_public=None,
                graph_analysis_diagnostics=None,
                graph_health_context=None,
                graph_ready_context=None,
                graph_dispatch_mode_override=None,
            )
        return SimpleNamespace(
            graph_analysis_public={"status": "available"},
            graph_analysis_diagnostics={
                "critical_path_sample": ["op:1", "op:2"],
                "critical_path_count": 2,
            },
            graph_health_context=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        return _outcome(
            "baseline" if kwargs["cfg"].graph_analysis_mode == "off" else "critical",
            score=(0, 0, 10),
            results=[_result(1, 8, 10), _result(2, 10, 12)],
        )

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    critical = next(candidate for candidate in outcome.candidates if candidate.kind == "critical_chain")
    assert critical.health is not None
    assert critical.health.state == HEALTH_UNAVAILABLE
    assert critical.health.reason_code == "critical_path_unavailable"
    assert critical.health.critical_chain_node_count == 0
    assert critical.health.top_impact_op_count == 0


def test_candidate_trial_mode_locks_sort_dispatch_mode_and_dispatch_rule_to_current_values() -> None:
    seen = []

    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        cfg_svc = kwargs["cfg_svc"]
        cfg = kwargs["cfg"]
        seen.append(
            (
                cfg.algo_mode,
                tuple(cfg_svc.VALID_STRATEGIES),
                tuple(cfg_svc.VALID_DISPATCH_MODES),
                tuple(cfg_svc.VALID_DISPATCH_RULES),
                tuple(cfg_svc.VALID_ALGO_MODES),
            )
        )
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    assert seen
    assert set(seen) == {
        (
            "greedy",
            ("priority_first",),
            ("sgs",),
            ("cr",),
            ("greedy",),
        )
    }


def test_candidate_runner_skips_not_started_candidates_after_global_deadline() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        return _outcome("baseline", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        run_time_budget_seconds=1,
        selection_policy="score_only",
        clock=_StepClock([0, 0, 2, 2, 2, 2, 2]),
    )

    assert outcome.completed_count == 1
    assert outcome.skipped_count == 3
    assert outcome.time_budget_reached is True
    assert [candidate.status for candidate in outcome.candidates[1:]] == [CANDIDATE_STATUS_SKIPPED] * 3


def test_candidate_runner_records_single_candidate_failure_and_continues() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        if kwargs["cfg"].graph_critical_weight == 250:
            raise runner.CandidateTrialFailure("candidate failed")
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    outcome = run_candidate_comparison(
        schedule_input=_schedule_input(),
        prepare_graph_fn=prepare_graph,
        optimize_schedule_fn=optimize,
        weight_count=3,
        selection_policy="score_only",
        clock=_StepClock([0] * 100),
    )

    assert outcome.failed_count == 1
    assert outcome.completed_count == 3
    assert outcome.candidates[1].status == CANDIDATE_STATUS_FAILED
    assert "candidate failed" in str(outcome.candidates[1].failure_reason)


def test_candidate_runner_raises_validation_error_instead_of_selecting_baseline() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        if kwargs["cfg"].graph_analysis_mode == "on":
            raise ValidationError("图 ready 队列上下文无效。", field="graph_ready_context")
        return _outcome("baseline", score=(0, 0, 10), tardiness=10.0)

    with pytest.raises(ValidationError) as exc_info:
        run_candidate_comparison(
            schedule_input=_schedule_input(),
            prepare_graph_fn=prepare_graph,
            optimize_schedule_fn=optimize,
            weight_count=3,
            selection_policy="score_only",
            clock=_StepClock([0] * 100),
        )

    assert exc_info.value.field == "graph_ready_context"


def test_candidate_runner_propagates_unexpected_contract_errors() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        raise TypeError("optimizer contract broken")

    with pytest.raises(TypeError, match="optimizer contract broken"):
        run_candidate_comparison(
            schedule_input=_schedule_input(),
            prepare_graph_fn=prepare_graph,
            optimize_schedule_fn=optimize,
            strict_mode=True,
            weight_count=3,
            selection_policy="score_only",
            clock=_StepClock([0] * 100),
        )


def test_candidate_runner_propagates_runtime_contract_errors() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics={"critical_path_sample": ["op:1", "op:2"]},
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        raise RuntimeError("graph ready context contract broken")

    with pytest.raises(RuntimeError, match="graph ready context contract broken"):
        run_candidate_comparison(
            schedule_input=_schedule_input(),
            prepare_graph_fn=prepare_graph,
            optimize_schedule_fn=optimize,
            strict_mode=True,
            weight_count=3,
            selection_policy="score_only",
            clock=_StepClock([0] * 100),
        )


def test_candidate_runner_fails_when_every_candidate_failed() -> None:
    def prepare_graph(schedule_input):
        return SimpleNamespace(
            graph_analysis_public=None,
            graph_analysis_diagnostics=None,
            graph_ready_context=None,
            graph_dispatch_mode_override=None,
        )

    def optimize(**kwargs):
        raise runner.CandidateTrialFailure("all failed")

    with pytest.raises(ValidationError) as exc_info:
        run_candidate_comparison(
            schedule_input=_schedule_input(),
            prepare_graph_fn=prepare_graph,
            optimize_schedule_fn=optimize,
            weight_count=3,
            selection_policy="score_only",
            clock=_StepClock([0] * 100),
        )

    assert exc_info.value.field == "candidate_selection"
