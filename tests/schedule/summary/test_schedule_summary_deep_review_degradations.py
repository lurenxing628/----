"""回归测试：深审发现的摘要降级口径必须可见。"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from core.services.scheduler.run.schedule_operation_log_details import dispatch_error_summary
from core.services.scheduler.summary.schedule_summary import build_result_summary
from tests.schedule.summary.test_scheduler_summary_result_summary_contract import _build_summary_for_op
from web.viewmodels.scheduler_summary_display import build_summary_display_state


def _svc() -> SimpleNamespace:
    return SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )


def test_failure_details_are_projected_to_public_errors_and_degradation_events() -> None:
    _cfg_obj, _batch, _raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    summary = SimpleNamespace(
        success=False,
        total_ops=2,
        scheduled_ops=0,
        failed_ops=2,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
        failure_details=[
            {
                "code": "dispatch_operation_exception",
                "batch_id": "B001",
                "op_id": 101,
                "op_code": "OP10",
                "seq": 1,
                "dispatch_mode": "sgs",
            },
            {
                "code": "skipped_after_batch_failure",
                "batch_id": "B001",
                "op_id": 102,
                "op_code": "OP20",
                "seq": 2,
                "failed_op_id": 101,
                "failed_op_code": "OP10",
            },
        ],
    )
    ctx = replace(ctx, results=[], summary=summary, best_metrics=None)

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _svc(),
        ctx=ctx,
    )

    public_codes = {item["code"] for item in result_summary_obj["public_error_details"]}
    assert {"dispatch_operation_exception", "skipped_after_batch_failure"} <= public_codes
    assert result_summary_obj["failure_detail_count"] == 2
    assert result_summary_obj["error_count"] == len(result_summary_obj["public_error_details"])
    assert result_summary_obj["error_count"] == len(result_summary_obj["errors"])
    assert any(
        str(event.get("code") or "") == "dispatch_failure_details"
        for event in result_summary_obj["degradation_events"]
    )


def test_summary_display_keeps_structured_public_error_messages_visible() -> None:
    display = build_summary_display_state(
        {
            "completion_status": "failed",
            "error_count": 1,
            "errors": [],
            "public_error_details": [
                {
                    "schema_version": "1.0",
                    "code": "dispatch_operation_exception",
                    "message": "工序 OP10 排产时遇到系统异常，本次没有继续安排该批次后续工序。",
                    "op_code": "OP10",
                    "op_id": 101,
                    "seq": 1,
                }
            ],
        },
        result_status="failed",
    )

    assert display["errors_display"] == ["工序 OP10 排产时遇到系统异常，本次没有继续安排该批次后续工序。"]


def test_dispatch_error_summary_keeps_total_count_when_error_details_are_sampled() -> None:
    summary = dispatch_error_summary(
        {
            "failure_detail_count": 12000,
            "public_error_details": [
                {
                    "schema_version": "1.0",
                    "code": "dispatch_operation_failed",
                    "message": "工序 OP10 没有形成有效排程，本次没有继续安排该批次后续工序。",
                    "op_code": "OP10",
                }
                for _index in range(10)
            ],
        }
    )

    assert summary["count"] == 12000
    assert summary["codes"] == {"dispatch_operation_failed": 10}


def test_invalid_hours_detail_does_not_get_deducted_as_auto_assign_failure() -> None:
    _cfg_obj, _batch, _raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    op = SimpleNamespace(
        id=101,
        batch_id="B001",
        seq=1,
        op_code="OP10",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    error_message = "工时不合法：工序 OP10 工时字段不合法：setup_hours='abc'"
    summary = SimpleNamespace(
        success=False,
        total_ops=1,
        scheduled_ops=0,
        failed_ops=1,
        warnings=[],
        errors=[error_message],
    )
    ctx = replace(
        ctx,
        operations=[op],
        results=[],
        summary=summary,
        missing_internal_resource_op_ids={101},
        scheduled_op_ids=set(),
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _svc(),
        ctx=ctx,
    )

    assert result_summary_obj["errors"] == ["工时不合法：工序 OP10"]
    assert result_summary_obj["missing_internal_resource_count"] == 1
    assert {item["op_id"] for item in result_summary_obj["missing_internal_resource_ops"]} == {101}


def test_graph_enhancement_disabled_by_cycle_is_visible_degradation() -> None:
    _cfg_obj, _batch, _raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    ctx = replace(
        ctx,
        summary=SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        graph_analysis_public={
            "mode": "on",
            "status": "available",
            "graph_enhancement_allowed": False,
            "graph_enhancement_disabled_reason": "schedule_graph_cycle",
        },
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _svc(),
        ctx=ctx,
    )

    assert result_summary_obj["degraded_success"] is True
    assert "graph_enhancement_degraded" in result_summary_obj["degraded_causes"]
    assert any(
        str(event.get("code") or "") == "graph_enhancement_degraded"
        for event in result_summary_obj["degradation_events"]
    )
