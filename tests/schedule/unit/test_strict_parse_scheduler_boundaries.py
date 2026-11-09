"""排产算法准备严格日期契约、风险摘要纯函数与候选指标精度边界回归。"""

from __future__ import annotations

import time
from datetime import date, datetime
from unittest.mock import patch

import pytest

from core.algorithm_contracts import date_parsers
from core.algorithm_contracts.date_parsers import require_optional_date, require_optional_datetime
from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics
from core.algorithms.evaluation_completion import BatchCompletion, due_display_text
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.errors import ValidationError
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext
from core.services.scheduler.run.schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import BusinessObjectiveSelectionResult
from core.services.scheduler.run.schedule_candidate_summary import (
    candidate_comparison_public_summary,
    candidate_metrics_summary,
)
from core.services.scheduler.summary.due_risk_items import build_incomplete_batch_items
from core.services.scheduler.summary.schedule_summary import build_result_summary
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.optimizer_graph_ready_benchmark import ContinuousCalendar
from tests._support.schedule_decode import config_snapshot, production_session


def test_require_optional_date_and_datetime_enforce_zero_padded_local_iso() -> None:
    assert require_optional_date(None, field="due_date") is None
    assert require_optional_date(date(2026, 5, 20), field="due_date") == date(2026, 5, 20)
    assert require_optional_date("2026-05-20", field="due_date") == date(2026, 5, 20)

    for bad_date in (
        "",
        "   ",
        " 2026-05-20 ",
        "2026/05/20",
        "2026-5-2",
        "20260520",
        "2026-05-20 08:00:00",
        datetime(2026, 5, 20, 8, 0, 0),
        "2026-02-29",
        True,
    ):
        with pytest.raises(ValidationError) as exc_info:
            require_optional_date(bad_date, field="due_date")
        assert exc_info.value.field == "due_date"

    assert require_optional_datetime(None, field="created_at") is None
    now_val = datetime(2026, 5, 20, 8, 30, 15)
    assert require_optional_datetime(now_val, field="created_at") == now_val
    assert require_optional_datetime(date(2026, 5, 20), field="created_at") == datetime(2026, 5, 20, 0, 0, 0)
    assert require_optional_datetime("2026-05-20", field="created_at") == datetime(2026, 5, 20, 0, 0, 0)
    assert require_optional_datetime("2026-05-20 08:30", field="created_at") == datetime(2026, 5, 20, 8, 30, 0)
    assert require_optional_datetime("2026-05-20T08:30", field="created_at") == datetime(2026, 5, 20, 8, 30, 0)
    # SQLite CURRENT_TIMESTAMP space-separated format and 1..6 fractional digits:
    assert require_optional_datetime("2026-05-20 08:30:15", field="created_at") == now_val
    assert require_optional_datetime("2026-05-20 08:30:15.5", field="created_at") == datetime(
        2026, 5, 20, 8, 30, 15, 500000
    )
    assert require_optional_datetime("2026-05-20T08:30:15.123456", field="created_at") == datetime(
        2026, 5, 20, 8, 30, 15, 123456
    )

    for bad_dt in (
        "",
        "   ",
        " 2026-05-20 08:30:15 ",
        "2026/05/20 08:30:15",
        "2026-5-20 08:30:15",
        "2026-05-20 8:30:15",
        "20260520T083015",
        "2026-05-20T08:30:15Z",
        "2026-05-20T08:30:15+08:00",
        "2026-05-20 08:30:15.1234567",
        "2026-05-20 24:00",
        "2026-05-20T24:00:00",
        "2026-02-29 08:30:15",
        123,
    ):
        with pytest.raises(ValidationError) as dt_exc:
            require_optional_datetime(bad_dt, field="created_at")
        assert dt_exc.value.field == "created_at"


def test_native_preparation_caches_due_dates_for_piece_batches_and_preserves_validity_probe() -> None:
    scheduler = GreedyScheduler(ContinuousCalendar(), config_snapshot(auto_assign_enabled="no"))
    batches = {
        "B1": make_batch(batch_id="B1", quantity=2, due_date="2026-05-25", created_at="2026-05-01 09:15:00"),
        "B2": make_batch(batch_id="B2", quantity=1, due_date="2026-05-20", created_at="2026-05-01 08:00:00"),
    }
    piece_op = make_algo_op(id=1, batch_id="B1", piece_id="P1", seq=10, machine_id="M1", operator_id="O1")
    prep = production_session(scheduler, operations=[piece_op], batches=batches).native_preparation

    piece_batch = prep.operation_batch(piece_op, batches["B1"])
    assert piece_batch is not batches["B1"] and piece_batch.quantity == 1

    with patch.object(date_parsers, "parse_date", wraps=date_parsers.parse_date) as spy:
        assert prep.due_date_for_batch("B1") == date(2026, 5, 25)
        assert prep.due_date_for_batch("B1") == date(2026, 5, 25)
        assert prep.batch_order(start_dt=datetime(2026, 5, 1, 8, 0), strategy=SortStrategy.FIFO) == ("B2", "B1")
    assert spy.call_count == 2

    invalid_batches = {"B_BAD": make_batch(batch_id="B_BAD", due_date="2026/05/20")}
    bad_prep = production_session(
        scheduler,
        operations=[make_algo_op(id=2, batch_id="B_BAD", seq=10, machine_id="M1", operator_id="O1")],
        batches=invalid_batches,
    ).native_preparation
    assert bad_prep.all_batch_due_dates_valid() is False
    with pytest.raises(ValidationError) as due_exc:
        bad_prep.batch_order(start_dt=datetime(2026, 5, 1, 8, 0), strategy=SortStrategy.DUE_DATE_FIRST)
    assert due_exc.value.field == "due_date"


def test_summary_warnings_are_pure_and_due_display_distinguishes_none_empty_and_datetime() -> None:
    assert due_display_text(None) is None
    assert due_display_text("") == ""
    assert due_display_text("  2026-05-20  ") == "  2026-05-20  "
    assert due_display_text(date(2026, 5, 20)) == "2026-05-20"
    assert due_display_text(datetime(2026, 5, 20, 14, 30)) == "2026-05-20 14:30:00"

    batches = {
        "B_EMPTY": make_batch(batch_id="B_EMPTY", due_date=""),
        "B_NONE": make_batch(batch_id="B_NONE", due_date=None),
        "B_UNSCHED": make_batch(batch_id="B_UNSCHED", due_date="2026-05-25"),
    }
    results = [
        ScheduleResult(
            op_id=1,
            op_code="OP1",
            batch_id="B_EMPTY",
            seq=10,
            machine_id="M1",
            operator_id="O1",
            start_time=datetime(2026, 5, 20, 8, 0),
            end_time=datetime(2026, 5, 20, 9, 0),
            source="internal",
        ),
        ScheduleResult(
            op_id=2,
            op_code="OP2",
            batch_id="B_NONE",
            seq=10,
            machine_id="M1",
            operator_id="O1",
            start_time=datetime(2026, 5, 20, 9, 0),
            end_time=datetime(2026, 5, 20, 10, 0),
            source="internal",
        ),
    ]
    failures = [
        {"batch_id": "B_EMPTY", "code": "missing_internal_resource", "op_id": 11, "op_code": "OP1B", "seq": 20},
        {"batch_id": "B_NONE", "code": "missing_internal_resource", "op_id": 22, "op_code": "OP2B", "seq": 20},
    ]
    incomplete_items = build_incomplete_batch_items(
        incomplete_batch_ids={"B_EMPTY", "B_NONE"},
        batches=batches,
        finish_by_batch={"B_EMPTY": datetime(2026, 5, 20, 9, 0), "B_NONE": datetime(2026, 5, 20, 10, 0)},
        results=results,
        failure_details=failures,
    )
    by_batch = {row["batch_id"]: row["due_date"] for row in incomplete_items}
    assert by_batch == {"B_EMPTY": "", "B_NONE": None}

    ops = [
        make_algo_op(id=1, batch_id="B_EMPTY", seq=10),
        make_algo_op(id=11, batch_id="B_EMPTY", seq=20),
        make_algo_op(id=2, batch_id="B_NONE", seq=10),
        make_algo_op(id=22, batch_id="B_NONE", seq=20),
        make_algo_op(id=3, batch_id="B_UNSCHED", seq=10),
    ]
    metrics = compute_metrics(
        results, batches, expected_operations=ops, seed_occupancies_by_op_id={}, failure_details=failures
    )
    original_warnings = ["基础提醒"]
    summary = ScheduleSummary(
        success=False,
        total_ops=5,
        scheduled_ops=2,
        failed_ops=3,
        warnings=list(original_warnings),
        errors=[],
        duration_seconds=0.1,
        failure_details=failures,
    )
    cfg = snapshot_from_values(
        dict(default_snapshot_values(), freeze_window_enabled="no", auto_assign_enabled="no", freeze_window_days=0)
    )
    with pytest.raises(TypeError):
        SummaryBuildContext(  # type: ignore[call-arg]
            cfg=cfg,
            version=1,
            normalized_batch_ids=list(batches),
            start_dt=datetime(2026, 5, 20, 8, 0),
            end_date=None,
            batches=batches,
            operations=[],
            results=results,
            summary=summary,
            used_strategy=SortStrategy.PRIORITY_FIRST,
            used_params={},
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=5,
            best_score=(3.0,),
            best_metrics=metrics,
            frozen_op_ids=set(),
            scheduled_op_ids={1, 2},
            freeze_meta={"freeze_enabled": False, "freeze_days": 0, "freeze_state": "disabled", "freeze_applied": False},
            missing_internal_resource_op_ids=set(),
        )

    ctx = SummaryBuildContext(
        cfg=cfg,
        version=1,
        normalized_batch_ids=list(batches),
        start_dt=datetime(2026, 5, 20, 8, 0),
        end_date=date(2026, 5, 30),
        batches=batches,
        operations=[],
        results=results,
        summary=summary,
        used_strategy=SortStrategy.PRIORITY_FIRST,
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(3.0,),
        best_metrics=metrics,
        frozen_op_ids=set(),
        scheduled_op_ids={1, 2},
        freeze_meta={"freeze_enabled": False, "freeze_days": 0, "freeze_state": "disabled", "freeze_applied": False},
        missing_internal_resource_op_ids=set(),
        t0=time.monotonic() + 5.0,
    )
    out = build_result_summary(ctx=ctx)
    assert summary.warnings == original_warnings
    assert out["end_date"] == "2026-05-30"
    assert out["time_cost_ms"] == 0
    assert out["warnings"][0] == "基础提醒"
    assert "存在 1 个批次交期写法不对" in out["warnings"][1]
    assert "存在 1 个批次未形成完工结果" in out["warnings"][2]


def test_candidate_metrics_summary_preserves_four_decimal_rounding_without_unified_process_copy() -> None:
    completion = BatchCompletion(
        expected_operation_count=1,
        missing_operation_count=0,
        unexpected_result_count=0,
        complete_batch_count=1,
        incomplete_batch_ids=(),
        partial_batch_ids=(),
        failure_detail_count=0,
        failure_batch_ids=(),
    )
    metrics = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=1.2345678,
        weighted_tardiness_hours=2.3456789,
        makespan_hours=8.9876543,
        changeover_count=2,
        completion=completion,
    )
    scope = {
        "scheduled_operation_ids": [1],
        "complete_batch_ids": ["B1"],
        "objective_scope": "all_batches",
        "components_known": True,
        "is_complete": True,
    }
    plan = CandidatePlan(
        candidate_key="cand_1",
        sequence=1,
        label="方案 1",
        kind="primary",
        status="complete",
        generation_policy_version="unified_search_v1",
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        dispatch_mode="sgs",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_downstream_weight=1,
        results=[],
        summary=ScheduleSummary(
            success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[], duration_seconds=0.1
        ),
        used_strategy=SortStrategy.PRIORITY_FIRST,
        used_params={"dispatch_rule": "slack"},
        score=(0.0, 1.0, 1.2345678, 8.9876543, 2.0),
        metrics=metrics,
        algo_stats={},
        graph_analysis_public=None,
        graph_analysis_diagnostics=None,
        representative_objectives=["min_overdue"],
        evaluations={
            "min_overdue": {
                "score": [0.0, 1.0, 1.2346, 8.9877, 2.0],
                "scoring_scope": scope,
            }
        },
        origin={"stage": "multi_start"},
        first_found_elapsed_ms=12,
        search_evidence_ref={"entry_id": 1},
    )
    assert candidate_metrics_summary(plan) == {
        "failed_ops": 0,
        "overdue_count": 1,
        "total_tardiness_hours": 1.2346,
        "weighted_tardiness_hours": 2.3457,
        "makespan_hours": 8.9877,
        "changeover_count": 2,
    }
    selection = BusinessObjectiveSelectionResult(
        selected_candidate_key="cand_1",
        selected_plan=plan,
        primary_objective="min_overdue",
        target_objectives=("min_overdue",),
        objective_winners={"min_overdue": "cand_1"},
        objective_winner_reasons={"min_overdue": None},
        objective_field_order={"min_overdue": ["failed_ops", "overdue_count", "total_tardiness_hours"]},
        selected_score=plan.score,
        scoring_scope=scope,
        reason_code="primary_objective_best_found",
        evidence_state="verified",
    )
    outcome = CandidateComparisonOutcome(
        generation_policy_version="unified_search_v1",
        primary_objective="min_overdue",
        target_objectives=["min_overdue"],
        candidates=[plan],
        selection=selection,
        time_budget_reached=False,
        run_time_budget_seconds=5,
        unified_process={"events": [{"event_type": "heavy"}]},
    )
    public = candidate_comparison_public_summary(outcome)
    assert "unified_process" not in public
    assert public["candidates"][0]["metrics"]["total_tardiness_hours"] == 1.2346
