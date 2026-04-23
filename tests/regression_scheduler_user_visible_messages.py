from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_summary import build_result_summary
from web.routes.domains.scheduler import scheduler_config as scheduler_config_route

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_schedule_params_normalization_warnings_are_user_facing_chinese() -> None:
    result = resolve_schedule_params(
        config={},
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params=None,
        start_dt="not-a-datetime",
        end_date="not-a-date",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},
        strict_mode=False,
    )

    assert result.warnings
    assert any("无法解析" in item for item in result.warnings), result.warnings
    assert all("could not be parsed" not in item for item in result.warnings), result.warnings
    assert all("was normalized" not in item for item in result.warnings), result.warnings


def test_scheduler_manual_missing_base_dir_message_is_user_facing_chinese() -> None:
    app = Flask(__name__)

    with app.app_context():
        text, mtime = scheduler_config_route._load_manual_text_and_mtime(None, [])

    assert mtime is None
    assert "运行配置缺失" in text
    assert "Runtime config missing" not in text


def test_schedule_params_validation_message_uses_chinese_field_label() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config={},
            strategy=SortStrategy.PRIORITY_FIRST,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode="bad-mode",
            dispatch_rule="slack",
            resource_pool={},
            strict_mode=False,
        )

    message = str(exc_info.value)
    assert "派工方式" in message, message
    assert "dispatch_mode" not in message, message


def test_scheduler_run_degraded_success_message_is_user_facing_chinese() -> None:
    route_source = (REPO_ROOT / "web/routes/domains/scheduler/scheduler_run.py").read_text(encoding="utf-8")
    presenter_source = (REPO_ROOT / "web/viewmodels/scheduler_degradation_presenter.py").read_text(encoding="utf-8")

    assert "primary_degradation" in route_source
    assert "degraded_success" not in route_source
    assert "本次排产已成功，但存在内部降级/兼容修补。" in presenter_source
    assert "本次排产部分完成，且存在内部降级/兼容修补。" in presenter_source
    assert "本次排产失败，且存在内部降级/兼容修补。" in presenter_source


class _SummaryStubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def test_schedule_summary_seed_result_warning_no_longer_surfaces_degraded_success_story() -> None:
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
        simulate=False,
        t0=0.0,
        algo_stats={"fallback_counts": {"optimizer_seed_result_invalid_count": 2}, "param_fallbacks": {}},
    )

    warnings = list(result_summary_obj.get("warnings") or [])
    assert not any("seed_results 中有" in item for item in warnings), warnings
    assert not any("有效子集继续计算" in item for item in warnings), warnings


def test_schedule_summary_top_level_degraded_causes_include_business_degradations() -> None:
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
        cfg={"freeze_window_enabled": "yes", "freeze_window_days": 3, "auto_assign_enabled": "yes"},
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
        freeze_meta={"freeze_state": "degraded", "freeze_degradation_reason": "freeze degraded"},
        downtime_meta={"downtime_load_ok": False, "downtime_load_error": "downtime degraded"},
        resource_pool_meta={
            "resource_pool_attempted": True,
            "resource_pool_build_ok": False,
            "resource_pool_build_error": "pool degraded",
        },
        simulate=False,
        t0=0.0,
        warning_merge_status={
            "summary_merge_attempted": True,
            "summary_merge_failed": True,
            "summary_merge_error": "summary.warnings broken: readonly list",
        },
        algo_stats={"fallback_counts": {"optimizer_seed_result_invalid_count": 1}, "param_fallbacks": {}},
    )

    causes = list(result_summary_obj.get("degraded_causes") or [])
    events = list(result_summary_obj.get("degradation_events") or [])
    warning_pipeline = dict((result_summary_obj.get("algo") or {}).get("warning_pipeline") or {})
    assert result_summary_obj.get("degraded_success") is True
    assert "freeze_window_degraded" in causes, causes
    assert "downtime_avoid_degraded" in causes, causes
    assert "resource_pool_degraded" in causes, causes
    assert "summary_merge_failed" in causes, causes
    assert warning_pipeline.get("summary_merge_error") == "summary_warnings_assignment_failed", warning_pipeline
    summary_merge_event = next(evt for evt in events if str(evt.get("code") or "") == "summary_merge_failed")
    assert "summary.warnings broken" not in str(summary_merge_event.get("message") or ""), summary_merge_event
    assert "summary.warnings broken" not in str(result_summary_obj), result_summary_obj
