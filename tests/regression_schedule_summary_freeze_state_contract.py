from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found")


REPO_ROOT = find_repo_root()
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

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
    assert active_freeze.get("freeze_state") == "active", active_freeze
    assert active_freeze.get("freeze_applied") is True, active_freeze
    assert "freeze_window" in (active_algo.get("hard_constraints") or []), active_algo

    kwargs_mixed = _base_kwargs()
    kwargs_mixed.update(
        {
            "frozen_op_ids": {1},
            "freeze_meta": {
                "freeze_state": "degraded",
                "freeze_applied": True,
                "freeze_degradation_codes": ["freeze_seed_unavailable"],
                "freeze_degradation_reason": "partial freeze window seed unavailable",
            },
        }
    )
    _overdue, _status, mixed_summary, _json_text, _ms = build_result_summary(**kwargs_mixed)
    mixed_algo = mixed_summary.get("algo") or {}
    mixed_freeze = mixed_algo.get("freeze_window") or {}
    assert mixed_freeze.get("freeze_state") == "degraded", mixed_freeze
    assert mixed_freeze.get("freeze_applied") is True, mixed_freeze
    assert mixed_freeze.get("freeze_application_status") == "partially_applied", mixed_freeze
    assert "未应用冻结窗口种子" not in str(mixed_freeze.get("degradation_reason") or ""), mixed_freeze
    assert mixed_freeze.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], mixed_freeze
    assert "freeze_window" in (mixed_algo.get("hard_constraints") or []), mixed_algo

    kwargs_degraded = _base_kwargs()
    kwargs_degraded.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "degraded",
                "freeze_applied": False,
                "freeze_degradation_codes": ["freeze_seed_unavailable"],
                "freeze_degradation_reason": "failed to read previous schedule",
            },
        }
    )
    _overdue, _status, degraded_summary, _json_text, _ms = build_result_summary(**kwargs_degraded)
    degraded_algo = degraded_summary.get("algo") or {}
    degraded_freeze = degraded_algo.get("freeze_window") or {}
    assert degraded_freeze.get("freeze_state") == "degraded", degraded_freeze
    assert degraded_freeze.get("freeze_application_status") == "unapplied", degraded_freeze
    assert "未应用冻结窗口种子" in str(degraded_freeze.get("degradation_reason") or ""), degraded_freeze
    assert degraded_freeze.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], degraded_freeze
    assert "freeze_window" not in (degraded_algo.get("hard_constraints") or []), degraded_algo
    warnings = degraded_summary.get("warnings") or []
    assert not any("freeze_window" in str(item) for item in warnings), warnings
    assert any(
        str(item.get("code") or "") == "freeze_window_degraded"
        for item in (degraded_summary.get("degradation_events") or [])
        if isinstance(item, dict)
    ), degraded_summary.get("degradation_events")

    kwargs_not_applied = _base_kwargs()
    kwargs_not_applied.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "active",
                "freeze_applied": False,
                "freeze_degradation_codes": [],
            },
        }
    )
    _overdue, _status, not_applied_summary, _json_text, _ms = build_result_summary(**kwargs_not_applied)
    not_applied_algo = not_applied_summary.get("algo") or {}
    not_applied_freeze = not_applied_algo.get("freeze_window") or {}
    assert not_applied_freeze.get("freeze_state") in (None, "disabled"), not_applied_freeze
    assert not_applied_freeze.get("freeze_applied") in (None, False), not_applied_freeze
    assert "freeze_window" not in (not_applied_algo.get("hard_constraints") or []), not_applied_algo


def test_schedule_summary_freeze_degradation_prefers_structured_event_over_warning_text() -> None:
    kwargs = _base_kwargs()
    kwargs["summary"].warnings = ["[freeze_window] previous schedule unavailable"]
    kwargs.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "degraded",
                "freeze_applied": False,
                "freeze_degradation_codes": ["freeze_seed_unavailable"],
                "freeze_degradation_reason": "previous schedule unavailable",
            },
        }
    )

    _overdue, _status, degraded_summary, _json_text, _ms = build_result_summary(**kwargs)
    warnings = degraded_summary.get("warnings") or []
    degradation_events = degraded_summary.get("degradation_events") or []

    assert not any("freeze_window" in str(item) for item in warnings), warnings
    assert not any("冻结窗口" in str(item) for item in warnings), warnings
    assert any(str(item.get("code") or "") == "freeze_window_degraded" for item in degradation_events), degradation_events


def test_schedule_summary_freeze_warning_fallback_survives_without_freeze_meta() -> None:
    kwargs = _base_kwargs()
    kwargs["summary"].warnings = ["[freeze_window] previous schedule unavailable"]
    kwargs.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": None,
        }
    )

    _overdue, _status, degraded_summary, _json_text, _ms = build_result_summary(**kwargs)
    warnings = degraded_summary.get("warnings") or []

    assert any("freeze_window" in str(item) for item in warnings), warnings


def main() -> None:
    test_schedule_summary_freeze_state_controls_hard_constraints()
    print("OK")


if __name__ == "__main__":
    main()
