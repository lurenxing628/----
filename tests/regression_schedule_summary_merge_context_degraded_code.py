from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationEvent
from core.services.scheduler.schedule_summary import build_result_summary


class _SummaryStubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def test_merge_context_degraded_uses_dedicated_degradation_code() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "freeze_window_days": 0, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        input_build_outcome=BuildOutcome(
            value=[],
            events=(
                DegradationEvent(
                    code="template_missing",
                    scope="scheduler.input_builder",
                    field="template",
                    message="template missing",
                ),
            ),
        ),
        warning_merge_status={
            "summary_merge_attempted": False,
            "summary_merge_failed": False,
            "summary_merge_error": None,
        },
        simulate=False,
        t0=0.0,
    )

    causes = list(result_summary_obj.get("degraded_causes") or [])
    events = list(result_summary_obj.get("degradation_events") or [])
    warnings = list(result_summary_obj.get("warnings") or [])

    assert "merge_context_degraded" in causes, causes
    assert "warning_merge_failed" not in causes, causes
    assert any(str(event.get("code") or "") == "merge_context_degraded" for event in events), events
    assert "input_fallback" not in causes, causes
    assert warnings == [], warnings


def test_merge_context_invalid_number_stays_in_merge_context_channel() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    merge_event = {
        "code": "invalid_number",
        "scope": "scheduler.input_builder",
        "field": "ext_group_total_days",
        "message": "invalid ext_group_total_days",
        "sample": "'bad-number'",
    }

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "freeze_window_days": 0, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        input_build_outcome=BuildOutcome(
            value=[SimpleNamespace(merge_context_degraded=True, merge_context_events=[merge_event])],
            events=(
                DegradationEvent(
                    code="invalid_number",
                    scope="scheduler.input_builder",
                    field="ext_group_total_days",
                    message="invalid ext_group_total_days",
                    sample="'bad-number'",
                ),
            ),
        ),
        warning_merge_status={
            "summary_merge_attempted": False,
            "summary_merge_failed": False,
            "summary_merge_error": None,
        },
        simulate=False,
        t0=0.0,
    )

    causes = list(result_summary_obj.get("degraded_causes") or [])
    algo = dict(result_summary_obj.get("algo") or {})
    warnings = list(result_summary_obj.get("warnings") or [])

    assert "merge_context_degraded" in causes, causes
    assert "input_fallback" not in causes, causes
    assert algo.get("merge_context_degraded") is True
    assert any(str(event.get("code") or "") == "invalid_number" for event in list(algo.get("merge_context_events") or []))
    assert warnings == [], warnings


def test_generic_input_fallback_stays_in_input_fallback_channel() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "freeze_window_days": 0, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        input_build_outcome=BuildOutcome(
            value=[],
            events=(
                DegradationEvent(
                    code="invalid_number",
                    scope="scheduler.input_builder",
                    field="setup_hours",
                    message="invalid setup_hours",
                    sample="'bad-number'",
                ),
            ),
        ),
        warning_merge_status={
            "summary_merge_attempted": False,
            "summary_merge_failed": False,
            "summary_merge_error": None,
        },
        simulate=False,
        t0=0.0,
    )

    causes = list(result_summary_obj.get("degraded_causes") or [])
    algo = dict(result_summary_obj.get("algo") or {})

    assert "input_fallback" in causes, causes
    assert "merge_context_degraded" not in causes, causes
    assert algo.get("merge_context_degraded") is False
    assert list(algo.get("merge_context_events") or []) == []
