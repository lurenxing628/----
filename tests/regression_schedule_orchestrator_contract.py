"""回归测试：orchestrate_schedule_run 编排契约——空结果先抛 no_actionable_schedule_rows 且不分配版本/不建 summary，越界 op 抛 out_of_scope_schedule_rows、混入非法行抛 invalid_schedule_rows（均在版本分配前失败）；正常路径才分配版本、合并 optimizer/freeze 警告、构造 SummaryBuildContext，并校验 _build_summary_contract 对计数非法/类整数('2.0')值的归一与降级事件。"""

import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, cast


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


def _base_input() -> Any:
    from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot

    return SimpleNamespace(
        cfg=ScheduleConfigSnapshot(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            ready_weight=0.1,
            holiday_default_efficiency=0.8,
            enforce_ready_default="no",
            prefer_primary_skill="no",
            dispatch_mode="sgs",
            dispatch_rule="cr",
            auto_assign_enabled="no",
            auto_assign_persist="yes",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="improve",
            time_budget_seconds=20,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
            graph_analysis_mode="off",
            graph_block_on_cycle="no",
            graph_critical_weight=500,
            graph_impact_weight=10,
            graph_debug_export="no",
        ),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops_to_schedule=[SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal")],
        batches={"B001": SimpleNamespace(batch_id="B001")},
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        operations=[SimpleNamespace(id=1, batch_id="B001")],
        reschedulable_operations=[SimpleNamespace(id=1, source="internal")],
        reschedulable_op_ids={1},
        normalized_batch_ids=["B001"],
        freeze_meta={"loaded": True},
        algo_input_outcome=SimpleNamespace(value=[], counters={}),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=["freeze warning"],
        frozen_op_ids=set(),
        t0=0.0,
        optimizer_seed_version=6,
        run_label="schedule",
        prev_version=5,
        created_by_text="tester",
        missing_internal_resource_op_ids=set(),
    )


def test_schedule_orchestrator_contract() -> None:

    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
    from core.services.scheduler.run.schedule_orchestrator import _build_summary_contract
    from core.services.scheduler.schedule_orchestrator import orchestrate_schedule_run
    from core.services.scheduler.schedule_service import ScheduleService
    from core.services.scheduler.schedule_summary_types import SummaryBuildContext

    def _optimizer_outcome(**kwargs):
        return OptimizationOutcome(
            results=list(kwargs.get("results") or []),
            summary=kwargs.get("summary"),
            used_strategy=cast(Any, kwargs.get("used_strategy")),
            used_params=dict(kwargs.get("used_params") or {}),
            metrics=kwargs.get("metrics"),
            best_score=tuple(kwargs.get("best_score") or ()),
            best_order=list(kwargs.get("best_order") or []),
            attempts=list(kwargs.get("attempts") or []),
            improvement_trace=list(kwargs.get("improvement_trace") or []),
            algo_mode=str(kwargs.get("algo_mode") or ""),
            objective_name=str(kwargs.get("objective_name") or ""),
            time_budget_seconds=int(kwargs.get("time_budget_seconds") or 0),
            algo_stats=dict(kwargs.get("algo_stats") or {}),
        )

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    svc = ScheduleService(conn, logger=None, op_logger=None)

    captured_empty: Dict[str, Any] = {"allocate_calls": 0}

    def _unexpected_allocate_next_version():
        captured_empty["allocate_calls"] += 1
        raise AssertionError("empty results must not allocate version")

    svc.history_repo.allocate_next_version = _unexpected_allocate_next_version  # type: ignore[assignment]

    def _stub_optimize_empty(**kwargs):
        captured_empty["optimize_strict_mode"] = kwargs.get("strict_mode")
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=0,
            failed_ops=1,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return _optimizer_outcome(
            results=[],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            metrics=None,
            best_score=(0.0,),
            best_order=[],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=1,
            algo_stats={},
        )

    rejected = False
    try:
        orchestrate_schedule_run(
            svc,
            schedule_input=_base_input(),
            simulate=False,
            strict_mode=True,
            optimize_schedule_fn=_stub_optimize_empty,
            build_result_summary_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("empty results must not build summary")
            ),
        )
    except ValidationError as exc:
        rejected = getattr(exc, "details", {}).get("reason") == "no_actionable_schedule_rows"
    assert rejected, "empty results must raise no_actionable_schedule_rows"
    assert captured_empty.get("allocate_calls") == 0, captured_empty
    assert captured_empty.get("optimize_strict_mode") is True, captured_empty

    captured_ok: Dict[str, Any] = {"allocate_calls": 0}

    def _allocate_next_version():
        captured_ok["allocate_calls"] += 1
        return 7

    svc.history_repo.allocate_next_version = _allocate_next_version  # type: ignore[assignment]

    valid_result = SimpleNamespace(
        op_id=1,
        op_code="B001_10",
        batch_id="B001",
        seq=10,
        machine_id="MC001",
        operator_id="OP001",
        start_time=_make_dt(0),
        end_time=_make_dt(1),
        source="internal",
        op_type_name="A",
    )

    def _stub_optimize_ok(**kwargs):
        captured_ok["optimize_strict_mode"] = kwargs.get("strict_mode")
        captured_ok["readiness_gate_enabled"] = kwargs.get("readiness_gate_enabled")
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=["optimizer warning"],
            errors=[],
            duration_seconds=0.0,
        )
        return _optimizer_outcome(
            results=[valid_result],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={"dispatch": "fifo"},
            metrics={"makespan": 1},
            best_score=(0.0,),
            best_order=["B001"],
            attempts=[{"score": [0.0]}],
            improvement_trace=[{"score": [0.0]}],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=3,
            algo_stats={"fallback_counts": {"x": 1}},
        )

    def _stub_build_result_summary(_svc, **kwargs):
        captured_ok["summary_kwargs"] = dict(kwargs or {})
        return [{"batch_id": "B001"}], "success", {"algo": {"ok": 1}}, '{"algo":{"ok":1}}', 34

    collected = _base_input()
    outcome = orchestrate_schedule_run(
        svc,
        schedule_input=collected,
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=_stub_optimize_ok,
        build_result_summary_fn=_stub_build_result_summary,
    )

    assert captured_ok.get("allocate_calls") == 1, captured_ok
    assert captured_ok.get("optimize_strict_mode") is True, captured_ok
    assert captured_ok.get("readiness_gate_enabled") is True, captured_ok
    assert outcome.version == 7, outcome
    assert outcome.result_status == "success", outcome
    assert outcome.time_cost_ms == 34, outcome
    assert outcome.algo_warnings == ["freeze warning"], outcome
    assert list(outcome.summary.warnings) == ["optimizer warning", "freeze warning"], outcome.summary.warnings
    assert outcome.validated_schedule_payload.scheduled_op_ids == {1}, outcome.validated_schedule_payload
    assert len(outcome.validated_schedule_payload.schedule_rows) == 1, outcome.validated_schedule_payload
    assert outcome.validated_schedule_payload.schedule_rows[0].op_id == 1, outcome.validated_schedule_payload
    assert outcome.validated_schedule_payload.assigned_by_op_id == {1: {"machine_id": "MC001", "operator_id": "OP001"}}
    assert outcome.summary_contract.to_dict() == {
        "success": True,
        "total_ops": 1,
        "scheduled_ops": 1,
        "failed_ops": 0,
        "warnings": ["optimizer warning", "freeze warning"],
        "errors": [],
        "duration_seconds": 0.0,
        "degraded_success": False,
        "degraded_causes": [],
        "degradation_events": [],
        "degradation_counters": {},
        "error_count": 0,
        "errors_sample": [],
        "counts": {
            "op_count": 1,
            "total_ops": 1,
            "scheduled_ops": 1,
            "failed_ops": 0,
        },
        "algo": {"ok": 1},
    }
    fallback_contract = _build_summary_contract(
        SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        result_summary_obj={
            "warnings": ["persisted warning"],
            "degraded_success": True,
            "degraded_causes": ["summary_merge_failed"],
        },
    )
    assert fallback_contract.to_dict() == {
        "success": True,
        "total_ops": 1,
        "scheduled_ops": 1,
        "failed_ops": 0,
        "warnings": ["persisted warning"],
        "errors": [],
        "duration_seconds": 0.0,
        "degraded_success": True,
        "degraded_causes": ["summary_merge_failed"],
        "degradation_events": [],
        "degradation_counters": {},
        "error_count": 0,
        "errors_sample": [],
        "counts": {
            "op_count": 1,
            "total_ops": 1,
            "scheduled_ops": 1,
            "failed_ops": 0,
        },
    }

    bad_count_contract = _build_summary_contract(
        SimpleNamespace(
            success=True,
            total_ops="bad",
            scheduled_ops=True,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        result_summary_obj={},
    ).to_dict()
    assert bool(bad_count_contract.get("summary_count_parse_failed")), bad_count_contract
    assert int(bad_count_contract.get("error_count") or 0) > 0, bad_count_contract
    assert bad_count_contract["counts"]["total_ops"] == 0, bad_count_contract
    assert bad_count_contract["counts"]["scheduled_ops"] == 0, bad_count_contract
    assert any("数量记录异常" in item for item in list(bad_count_contract.get("warnings") or [])), bad_count_contract
    assert any(
        str(event.get("code") or "") == "summary_count_parse_failed"
        for event in list(bad_count_contract.get("degradation_events") or [])
    ), bad_count_contract

    integer_like_contract = _build_summary_contract(
        SimpleNamespace(
            success=True,
            total_ops="2.0",
            scheduled_ops=1.0,
            failed_ops="0",
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        result_summary_obj={},
    ).to_dict()
    assert integer_like_contract["counts"]["total_ops"] == 2, integer_like_contract
    assert integer_like_contract["counts"]["scheduled_ops"] == 1, integer_like_contract
    assert not integer_like_contract.get("summary_count_parse_failed"), integer_like_contract

    summary_kwargs = captured_ok.get("summary_kwargs") or {}
    summary_ctx = summary_kwargs.get("ctx")
    assert isinstance(summary_ctx, SummaryBuildContext), summary_kwargs
    assert summary_ctx.version == 7, summary_ctx
    assert summary_ctx.simulate is True, summary_ctx
    assert summary_ctx.algo_warnings == ["freeze warning"], summary_ctx
    assert summary_ctx.warning_merge_status == {
        "summary_merge_attempted": True,
        "summary_merge_failed": False,
        "summary_merge_error": None,
    }, summary_ctx
    assert summary_ctx.readiness_gate_enabled is True, summary_ctx
    assert summary_ctx.input_build_outcome is collected.algo_input_outcome, summary_ctx

    captured_invalid: Dict[str, Any] = {"allocate_calls": 0}

    def _should_not_allocate_for_invalid():
        captured_invalid["allocate_calls"] += 1
        raise AssertionError("invalid in-scope results must fail before version allocation")

    svc.history_repo.allocate_next_version = _should_not_allocate_for_invalid  # type: ignore[assignment]

    def _stub_optimize_mixed(**kwargs):
        captured_invalid["optimize_strict_mode"] = kwargs.get("strict_mode")
        summary = SimpleNamespace(
            success=False,
            total_ops=2,
            scheduled_ops=2,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        invalid_result = SimpleNamespace(
            op_id=1,
            op_code="B001_10",
            batch_id="B001",
            seq=10,
            machine_id="MC001",
            operator_id="OP001",
            start_time=_make_dt(2),
            end_time=_make_dt(2),
            source="internal",
            op_type_name="A",
        )
        return _optimizer_outcome(
            results=[valid_result, invalid_result],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            metrics=None,
            best_score=(0.0,),
            best_order=[],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=1,
            algo_stats={},
        )

    invalid_rejected = False
    try:
        orchestrate_schedule_run(
            svc,
            schedule_input=collected,
            simulate=False,
            strict_mode=True,
            optimize_schedule_fn=_stub_optimize_mixed,
            build_result_summary_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("invalid results must not build summary")
            ),
        )
    except ValidationError as exc:
        invalid_rejected = getattr(exc, "details", {}).get("reason") == "invalid_schedule_rows"
        errors = list((getattr(exc, "details", {}) or {}).get("validation_errors") or [])
        assert errors, exc
    assert invalid_rejected, "mixed valid and invalid in-scope rows must fail with invalid_schedule_rows"
    assert captured_invalid.get("allocate_calls") == 0, captured_invalid
    assert captured_invalid.get("optimize_strict_mode") is True, captured_invalid

    captured_out_of_scope: Dict[str, Any] = {"allocate_calls": 0, "summary_calls": 0}

    def _should_not_allocate_for_out_of_scope():
        captured_out_of_scope["allocate_calls"] += 1
        raise AssertionError("out-of-scope results must fail before version allocation")

    svc.history_repo.allocate_next_version = _should_not_allocate_for_out_of_scope  # type: ignore[assignment]

    def _stub_optimize_out_of_scope(**kwargs):
        captured_out_of_scope["optimize_strict_mode"] = kwargs.get("strict_mode")
        summary = SimpleNamespace(
            success=False,
            total_ops=2,
            scheduled_ops=2,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        rogue_result = SimpleNamespace(
            op_id=999,
            op_code="B999_10",
            batch_id="B999",
            seq=10,
            machine_id="MC999",
            operator_id="OP999",
            start_time=_make_dt(3),
            end_time=_make_dt(4),
            source="internal",
            op_type_name="Rogue",
        )
        return _optimizer_outcome(
            results=[valid_result, rogue_result],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            metrics=None,
            best_score=(0.0,),
            best_order=[],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=1,
            algo_stats={},
        )

    out_of_scope_rejected = False
    try:
        orchestrate_schedule_run(
            svc,
            schedule_input=collected,
            simulate=False,
            strict_mode=True,
            optimize_schedule_fn=_stub_optimize_out_of_scope,
            build_result_summary_fn=lambda *_args, **_kwargs: captured_out_of_scope.__setitem__(
                "summary_calls",
                int(captured_out_of_scope.get("summary_calls") or 0) + 1,
            ),
        )
    except ValidationError as exc:
        details = dict(getattr(exc, "details", {}) or {})
        out_of_scope_rejected = details.get("reason") == "out_of_scope_schedule_rows"
        assert details.get("count") == 1, details
        assert details.get("sample_op_ids") == [999], details
        assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details
    assert out_of_scope_rejected, "out-of-scope rows must fail with out_of_scope_schedule_rows"
    assert captured_out_of_scope.get("allocate_calls") == 0, captured_out_of_scope
    assert captured_out_of_scope.get("summary_calls") == 0, captured_out_of_scope
    assert captured_out_of_scope.get("optimize_strict_mode") is True, captured_out_of_scope

    conn.close()


