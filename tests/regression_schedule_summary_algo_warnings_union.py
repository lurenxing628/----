from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.services.scheduler.schedule_summary import build_result_summary


class _StubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        return str(value)


def _build_summary(*, freeze_meta, algo_warnings):
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    return build_result_summary(
        _StubSvc(),
        cfg={"auto_assign_enabled": "yes", "freeze_window_enabled": "yes", "freeze_window_days": 3},
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
        freeze_meta=freeze_meta,
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={
            "resource_pool_attempted": True,
            "resource_pool_build_ok": False,
            "resource_pool_build_error": "pool boom",
        },
        algo_warnings=list(algo_warnings),
        warning_merge_status={
            "summary_merge_attempted": True,
            "summary_merge_failed": True,
            "summary_merge_error": "summary_warnings_assignment_failed",
        },
        simulate=False,
        t0=time.time(),
    )


def test_schedule_summary_prefers_freeze_meta_as_primary_fact_source() -> None:
    _overdue, result_status, result_summary_obj, _json_text, _ms = _build_summary(
        freeze_meta={
            "freeze_state": "degraded",
            "freeze_applied": False,
            "freeze_degradation_codes": ["freeze_seed_unavailable"],
            "freeze_degradation_reason": "freeze meta degraded",
        },
        algo_warnings=[
            "[freeze_window] legacy warning text that should not win",
            "自动分配资源池构建失败，已降级为不自动分配（请查看日志）。",
        ],
    )

    assert result_status == "success", result_status
    warnings = list(result_summary_obj.get("warnings") or [])
    assert any("自动分配资源池构建失败" in item for item in warnings), warnings

    algo = result_summary_obj.get("algo") or {}
    freeze_window = algo.get("freeze_window") or {}
    resource_pool = algo.get("resource_pool") or {}
    warning_pipeline = algo.get("warning_pipeline") or {}

    assert bool(freeze_window.get("degraded")), freeze_window
    assert freeze_window.get("degradation_reason") == "freeze meta degraded", freeze_window
    assert bool(resource_pool.get("degraded")), resource_pool
    assert "pool boom" in str(resource_pool.get("degradation_reason") or ""), resource_pool
    assert bool(warning_pipeline.get("summary_merge_failed")), warning_pipeline
    assert warning_pipeline.get("summary_merge_error") == "summary_warnings_assignment_failed", warning_pipeline
    assert int(warning_pipeline.get("algo_warning_count") or 0) == 2, warning_pipeline
    assert bool(result_summary_obj.get("degraded_success")), result_summary_obj

    causes = list(result_summary_obj.get("degraded_causes") or [])
    assert "summary_merge_failed" in causes, result_summary_obj
    assert "freeze_window_degraded" in causes, result_summary_obj
    assert "resource_pool_degraded" in causes, result_summary_obj

    degradation_counters = dict(result_summary_obj.get("degradation_counters") or {})
    assert int(degradation_counters.get("freeze_window_degraded") or 0) == 1, degradation_counters
    assert int(degradation_counters.get("resource_pool_degraded") or 0) == 1, degradation_counters


def test_schedule_summary_keeps_narrow_freeze_warning_compat_when_meta_missing() -> None:
    _overdue, _result_status, result_summary_obj, _json_text, _ms = _build_summary(
        freeze_meta=None,
        algo_warnings=[
            "[freeze_window] fallback warning path",
            "自动分配资源池构建失败，已降级为不自动分配（请查看日志）。",
        ],
    )

    freeze_window = ((result_summary_obj.get("algo") or {}).get("freeze_window") or {})
    assert bool(freeze_window.get("degraded")), freeze_window
    assert "[freeze_window] fallback warning path" in str(freeze_window.get("degradation_reason") or ""), freeze_window
