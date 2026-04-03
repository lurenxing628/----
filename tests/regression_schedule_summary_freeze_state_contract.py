from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace

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


def _base_kwargs():
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    return {
        "svc": _StubSvc(),
        "cfg": {"auto_assign_enabled": "no", "freeze_window_enabled": "yes", "freeze_window_days": 3},
        "version": 1,
        "normalized_batch_ids": ["B001"],
        "start_dt": datetime(2026, 4, 1, 8, 0, 0),
        "end_date": None,
        "batches": {},
        "operations": [],
        "results": [],
        "summary": summary,
        "used_strategy": SimpleNamespace(value="priority_first"),
        "used_params": {},
        "algo_mode": "greedy",
        "objective_name": "min_overdue",
        "time_budget_seconds": 20,
        "best_score": None,
        "best_metrics": None,
        "best_order": [],
        "attempts": [],
        "improvement_trace": [],
        "downtime_meta": {"downtime_load_ok": True},
        "resource_pool_meta": {},
        "simulate": False,
        "t0": time.time(),
    }


def test_schedule_summary_freeze_state_controls_hard_constraints() -> None:
    kwargs_active = _base_kwargs()
    kwargs_active.update(
        {
            "frozen_op_ids": {1},
            "freeze_meta": {
                "freeze_state": "active",
                "freeze_applied": True,
                "freeze_degradation_codes": [],
            },
        }
    )
    _overdue, _status, active_summary, _json_text, _ms = build_result_summary(**kwargs_active)
    active_algo = active_summary.get("algo") or {}
    active_freeze = active_algo.get("freeze_window") or {}
    assert active_freeze.get("freeze_state") == "active", f"freeze_state=active 未透传：{active_freeze!r}"
    assert active_freeze.get("freeze_applied") is True, f"freeze_applied 未透传：{active_freeze!r}"
    assert "freeze_window" in (active_algo.get("hard_constraints") or []), f"active 冻结窗口未进入 hard_constraints：{active_algo!r}"

    kwargs_degraded = _base_kwargs()
    kwargs_degraded.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "degraded",
                "freeze_applied": False,
                "freeze_degradation_codes": ["freeze_seed_unavailable"],
                "freeze_degradation_reason": "读取上一版本排程失败",
            },
        }
    )
    _overdue, _status, degraded_summary, _json_text, _ms = build_result_summary(**kwargs_degraded)
    degraded_algo = degraded_summary.get("algo") or {}
    degraded_freeze = degraded_algo.get("freeze_window") or {}
    assert degraded_freeze.get("freeze_state") == "degraded", f"freeze_state=degraded 未透传：{degraded_freeze!r}"
    assert degraded_freeze.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], (
        f"冻结退化原因码异常：{degraded_freeze!r}"
    )
    assert "freeze_window" not in (degraded_algo.get("hard_constraints") or []), (
        f"degraded 冻结窗口不应进入 hard_constraints：{degraded_algo!r}"
    )
    warnings = degraded_summary.get("warnings") or []
    assert any("冻结窗口" in str(item) and "未生效" in str(item) for item in warnings), f"冻结窗口退化 warning 未外显：{warnings!r}"
