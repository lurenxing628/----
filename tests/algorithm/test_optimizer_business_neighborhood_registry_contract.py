"""回归测试：optimizer 业务邻域注册表合同（roadmap item 7）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_neighborhood_moves import (
    BOTTLENECK_MACHINE,
    BUSINESS_NEIGHBORHOODS,
    CHANGEOVER_BLOCK,
    CRITICAL_CHAIN,
    RESOURCE_ALTERNATIVE,
    TARDY_WINDOW,
    TIME_WINDOW,
)
from core.services.scheduler.run.optimizer_neighborhood_registry import (
    build_neighborhood_move,
    registered_neighborhoods,
    validate_neighborhood_name,
)
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


class _Rnd:
    def sample(self, seq: Any, n: int) -> List[int]:
        return [0, 1][:n]

    def randrange(self, n: int) -> int:
        return 0

    def randint(self, a: int, b: int) -> int:
        return a

    def random(self) -> float:
        return 0.1


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        current = self._now
        self._now += 0.02
        return current


def _result(
    op_id: int,
    *,
    batch_id: str,
    start_offset: int,
    machine_id: str = "MC-1",
    op_type_name: str = "cut",
) -> ScheduleResult:
    start = _START + timedelta(hours=start_offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-{op_id}",
        batch_id=batch_id,
        seq=10,
        machine_id=machine_id,
        operator_id="OP-1",
        start_time=start,
        end_time=start + timedelta(hours=1),
        op_type_name=op_type_name,
    )


def _summary(*, failed_ops: int = 0, total_ops: int = 2) -> ScheduleSummary:
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=total_ops,
        scheduled_ops=max(total_ops - failed_ops, 0),
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _metrics() -> ScheduleMetrics:
    return ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=2.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )


def _score(metrics: ScheduleMetrics, *, failed_ops: int = 0) -> List[float]:
    return [float(failed_ops)] + [float(item) for item in objective_score(_OBJECTIVE, metrics)]


def _candidate(
    *,
    order: List[str],
    results: List[ScheduleResult],
    mutable_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metrics = _metrics()
    candidate = {
        "results": list(results),
        "summary": _summary(total_ops=len(results)),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {"priority_weight": 0.4, "due_weight": 0.5},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": list(order),
        "metrics": metrics,
        "score": tuple(_score(metrics)),
        "algo_stats": {"fallback_counts": {}, "param_fallbacks": {}},
    }
    if mutable_scope is not None:
        candidate["mutable_scope"] = dict(mutable_scope)
    return candidate


def _best_candidate() -> Dict[str, Any]:
    return _candidate(
        order=["B1", "B2"],
        results=[
            _result(1, batch_id="B1", start_offset=0),
            _result(2, batch_id="B2", start_offset=2),
        ],
    )


def test_registry_exposes_six_business_neighborhoods_and_rejects_unknown() -> None:
    assert BUSINESS_NEIGHBORHOODS == (
        CRITICAL_CHAIN,
        TARDY_WINDOW,
        BOTTLENECK_MACHINE,
        CHANGEOVER_BLOCK,
        RESOURCE_ALTERNATIVE,
        TIME_WINDOW,
    )
    assert registered_neighborhoods() == BUSINESS_NEIGHBORHOODS

    with pytest.raises(ValidationError) as exc_info:
        validate_neighborhood_name("teleport")

    assert exc_info.value.field == "neighborhood"
    with pytest.raises(ValidationError):
        validate_neighborhood_name("swap")


def test_noop_neighbor_is_reported_honestly_and_not_improvement() -> None:
    move = build_neighborhood_move(
        TARDY_WINDOW,
        order=["B1", "B2"],
        results=[],
        batches={},
        resource_pool=None,
        rnd=_Rnd(),
    )
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=7,
        time_budget_seconds=1,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
    )
    state.mark_neighborhood_move(move.to_report_dict())
    state.mark_candidate_rejected(reason=move.candidate_rejected)

    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])

    assert move.noop is True
    assert move.candidate_rejected == "noop_neighbor"
    assert report["neighborhood_summary"][TARDY_WINDOW]["noop"] == 1
    assert report["neighborhood_summary"][TARDY_WINDOW]["effective"] == 0
    assert report["improved"] is False


def test_illegal_neighborhood_move_payload_fails_loud() -> None:
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=7,
        time_budget_seconds=1,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
    )

    with pytest.raises(ValidationError) as exc_info:
        state.mark_neighborhood_move(
            {
                "neighborhood_name": "teleport",
                "move_kind": "move_batch",
                "input_scope": "batch_order",
            }
        )

    assert exc_info.value.field == "neighborhood_move"


def test_fallback_neighbor_records_reason_in_trace_and_summary() -> None:
    move = build_neighborhood_move(
        CHANGEOVER_BLOCK,
        order=["B1", "B2"],
        results=[
            _result(1, batch_id="B1", start_offset=0, op_type_name="cut"),
            _result(2, batch_id="B2", start_offset=2, op_type_name="cut"),
        ],
        batches={},
        resource_pool=None,
        rnd=_Rnd(),
    )
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=7,
        time_budget_seconds=1,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
    )
    state.mark_neighborhood_move(move.to_report_dict())
    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])

    assert move.fallback_used is True
    assert move.fallback_reason == "changeover_block_missing"
    assert report["neighborhood_summary"][CHANGEOVER_BLOCK]["fallback"] == 1
    report_move = report["neighborhood_moves"][0]
    assert report_move["name"] == CHANGEOVER_BLOCK
    assert report_move["scope"] == "batch_order"
    assert report_move["selected_batch_ids"] == ["B1", "B2"]
    assert report_move["selected_operation_ids"] == []
    assert report_move["selected_machine_ids"] == []
    assert report_move["reason"] == "critical_path"
    assert report_move["fallback_reason"] == "changeover_block_missing"


def test_decision_fingerprint_changes_but_output_fingerprint_still_collapses_same_decoded_output() -> None:
    results = [
        _result(1, batch_id="B1", start_offset=0),
        _result(2, batch_id="B2", start_offset=1),
    ]
    first = _candidate(
        order=["B1", "B2"],
        results=results,
        mutable_scope={"scope": "batch_order", "neighborhood_name": CRITICAL_CHAIN},
    )
    second = _candidate(
        order=["B1", "B2"],
        results=results,
        mutable_scope={"scope": "batch_order", "neighborhood_name": TARDY_WINDOW},
    )

    first_fp = build_candidate_fingerprint(first, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    second_fp = build_candidate_fingerprint(second, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())

    assert first_fp.decision_fingerprint != second_fp.decision_fingerprint
    assert first_fp.output_fingerprint == second_fp.output_fingerprint


def test_local_search_business_neighborhood_still_goes_through_sgs_decode_and_report() -> None:
    best = _best_candidate()
    state = OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=11,
        time_budget_seconds=1,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only", "neighborhoods": [CRITICAL_CHAIN]},
    )
    state.mark_candidate_accepted(best, origin="multi_start")
    schedule_calls: List[List[str]] = []

    def _schedule_fn(*args: Any, **kwargs: Any):
        schedule_calls.append(list(kwargs.get("batch_order_override") or []))
        return list(best["results"]), _summary(failed_ops=1), kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    returned = run_local_search(
        algo_mode="improve",
        best=best,
        version=11,
        time_budget_seconds=1,
        deadline=1000.0,
        scheduler=SimpleNamespace(_last_algo_stats={"fallback_counts": {}, "param_fallbacks": {}}),
        algo_ops_to_schedule=[],
        batches={
            "B1": SimpleNamespace(batch_id="B1", due_date="2026-01-04"),
            "B2": SimpleNamespace(batch_id="B2", due_date="2026-01-04"),
        },
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=_OBJECTIVE,
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=False,
        clock=_Clock(),
        rng_factory=lambda _seed: _Rnd(),
        schedule_fn=_schedule_fn,
        search_report_state=state,
        neighborhoods=(CRITICAL_CHAIN,),
    )

    report = state.finalize(runtime_ms=20, attempts=[], improvement_trace=[])
    assert returned is best
    assert schedule_calls == [["B2", "B1"]]
    assert report["neighborhood_summary"][CRITICAL_CHAIN]["effective"] == 1
    assert report["evaluated_candidates"] == 2
    assert report["accepted_candidates"] == 1
    assert report["improved"] is False


def test_resource_alternative_changes_decision_without_batch_order_change() -> None:
    move = build_neighborhood_move(
        RESOURCE_ALTERNATIVE,
        order=["B1", "B2"],
        results=[],
        batches={},
        resource_pool={
            "operators_by_machine": {"MC-1": ["OP-1", "OP-2"]},
            "pair_rank": {("OP-1", "MC-1"): 1, ("OP-2", "MC-1"): 2},
        },
        rnd=_Rnd(),
    )

    assert move.noop is False
    assert list(move.batch_order) == ["B1", "B2"]
    assert move.input_scope == "resource_pool"
    assert move.changed_decision_count == 1
    assert move.decision_key[0] == RESOURCE_ALTERNATIVE


def test_public_projection_keeps_neighborhood_summary_safe_and_raw_moves_diagnostic_only() -> None:
    public, diagnostics = project_search_report(
        {
            "candidate_profile": {
                "profile": "grasp_ig",
                "enabled": True,
                "seed": 42,
                "configured_time_budget_seconds": 5,
                "effective_time_budget_seconds": 5,
                "configured_max_iterations": 100,
                "effective_max_iterations": 200,
                "system_limit_applied": True,
                "system_limit_reason": "iteration_floor",
                "candidate_strategy_families": ["multi_start", "grasp", "iterated_greedy"],
                "neighborhoods": list(BUSINESS_NEIGHBORHOODS),
            },
            "neighborhood_summary": {
                CRITICAL_CHAIN: {"attempted": 2, "effective": 1, "noop": 1, "fallback": 0, "rejected": 1},
                "op:SECRET": {"attempted": 99},
            },
            "neighborhood_moves": [
                {
                    "neighborhood_name": CRITICAL_CHAIN,
                    "move_kind": "pull_latest_chain_batch",
                    "diagnostics": {"op_id": "op:SECRET", "machine_id": "MC-SECRET"},
                }
            ],
            "initial_fingerprint": "internal-op:SECRET",
            "best_fingerprint": "hash-secret",
            "improved": False,
        }
    )

    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert public["profile_public"]["neighborhoods"] == list(BUSINESS_NEIGHBORHOODS)
    assert public["neighborhood_summary"][CRITICAL_CHAIN]["attempted"] == 2
    assert "neighborhood_moves" not in public
    assert "op:SECRET" not in public_text
    assert "machine_id" not in public_text
    assert "fingerprint" not in public_text
    assert diagnostics["neighborhood_moves"][0]["diagnostics"]["op_id"] == "op:SECRET"
    assert diagnostics["initial_fingerprint"] == "internal-op:SECRET"
