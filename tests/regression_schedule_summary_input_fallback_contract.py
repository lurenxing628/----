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

    @staticmethod
    def _normalize_text(value):
        return "" if value is None else str(value).strip()


def test_schedule_summary_promotes_input_fallback_to_top_level_degraded_cause() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    input_build_outcome = BuildOutcome(
        value=[],
        events=[
            DegradationEvent(
                code="invalid_number",
                scope="scheduler.input_builder",
                field="work_hours",
                message="invalid work_hours",
            )
        ],
    )

    _overdue, result_status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=11,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 2, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        input_build_outcome=input_build_outcome,
        simulate=False,
        t0=0.0,
    )

    assert result_status == "success", result_status
    causes = list(result_summary_obj.get("degraded_causes") or [])
    warnings = list(result_summary_obj.get("warnings") or [])
    degradation_events = list(result_summary_obj.get("degradation_events") or [])

    assert "input_fallback" in causes, causes
    assert "invalid_number" not in causes, causes
    assert warnings == [], warnings
    assert any(str(evt.get("code") or "") == "input_fallback" for evt in degradation_events), degradation_events
    assert any(str(evt.get("code") or "") == "invalid_number" for evt in degradation_events), degradation_events
