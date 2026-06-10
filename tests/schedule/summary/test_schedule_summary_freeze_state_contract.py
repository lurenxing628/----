"""回归测试：build_result_summary 对冻结窗口(freeze_window)状态的 algo 投影与降级契约——freeze_state 为 active/degraded/disabled 时分别产出
freeze_application_status(applied/partially_applied/unapplied)、是否进入 hard_constraints、freeze_disabled_reason 仅 disabled 时暴露；降级统一收敛为 freeze_window_degraded 计数与结构化 degradation_event，并优先用结构化 freeze_meta 而非 warning 文本（无 meta 时回退 warning 仍能标记降级）。"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace

from tests._support.paths import REPO_ROOT_STR


def find_repo_root() -> str:
    return REPO_ROOT_STR


REPO_ROOT = find_repo_root()
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.degradation_messages import FREEZE_WINDOW_DEGRADED_MESSAGE
from core.services.scheduler.summary.schedule_summary import build_result_summary


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


_FREEZE_WINDOW_DEGRADED_EVENT = [
    ("freeze_window_degraded", "schedule.summary.freeze_window", "freeze_window", 1)
]


def _base_cfg(**overrides):
    cfg = default_snapshot_values()
    cfg.update(
        {
            "auto_assign_enabled": "no",
            "freeze_window_enabled": "yes",
            "freeze_window_days": 3,
        }
    )
    cfg.update(overrides)
    return cfg


def _degradation_event_contract(summary):
    return [
        (
            str(event.get("code") or ""),
            str(event.get("scope") or ""),
            str(event.get("field") or ""),
            int(event.get("count") or 0),
        )
        for event in (summary.get("degradation_events") or [])
        if isinstance(event, dict)
    ]


def _assert_degradation_contract(summary, *, counters, events) -> None:
    assert summary.get("degradation_counters") == counters
    assert _degradation_event_contract(summary) == events


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
        "cfg": _base_cfg(),
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
    _assert_degradation_contract(active_summary, counters={}, events=[])

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
    assert mixed_summary.get("degraded_causes") == ["freeze_window_degraded"], mixed_summary
    _assert_degradation_contract(
        mixed_summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )

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
    assert degraded_freeze.get("degradation_reason") == FREEZE_WINDOW_DEGRADED_MESSAGE, degraded_freeze
    assert degraded_freeze.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], degraded_freeze
    assert "freeze_window" not in (degraded_algo.get("hard_constraints") or []), degraded_algo
    warnings = degraded_summary.get("warnings") or []
    assert not any("freeze_window" in str(item) for item in warnings), warnings
    assert degraded_summary.get("degraded_causes") == ["freeze_window_degraded"], degraded_summary
    _assert_degradation_contract(
        degraded_summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )

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
    _assert_degradation_contract(not_applied_summary, counters={}, events=[])


def test_schedule_summary_exposes_freeze_disabled_reason_without_degradation() -> None:
    kwargs = _base_kwargs()
    kwargs.update(
        {
            "cfg": _base_cfg(freeze_window_enabled="no", freeze_window_days=0),
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "disabled",
                "freeze_applied": False,
                "freeze_disabled_reason": "config_disabled",
                "freeze_degradation_codes": [],
            },
        }
    )

    _overdue, _status, summary, _json_text, _ms = build_result_summary(**kwargs)
    algo = summary.get("algo") or {}
    freeze_window = algo.get("freeze_window") or {}

    assert freeze_window.get("freeze_disabled_reason") == "config_disabled", freeze_window
    assert not freeze_window.get("degraded"), freeze_window
    assert "freeze_window" not in (algo.get("hard_constraints") or []), algo
    _assert_degradation_contract(summary, counters={}, events=[])


def test_schedule_summary_freeze_disabled_reason_does_not_expand_warning_fallback() -> None:
    kwargs = _base_kwargs()
    kwargs["summary"].warnings = ["[freeze_window] previous schedule unavailable"]
    kwargs.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": None,
        }
    )

    _overdue, _status, summary, _json_text, _ms = build_result_summary(**kwargs)
    freeze_window = (summary.get("algo") or {}).get("freeze_window") or {}
    warnings = summary.get("warnings") or []

    assert any("freeze_window" in str(item) for item in warnings), warnings
    assert "freeze_disabled_reason" not in freeze_window, freeze_window
    assert summary.get("degraded_causes") == ["freeze_window_degraded"], summary
    _assert_degradation_contract(
        summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )


def test_schedule_summary_config_degraded_does_not_expose_disabled_reason() -> None:
    kwargs = _base_kwargs()
    kwargs.update(
        {
            "frozen_op_ids": set(),
            "freeze_meta": {
                "freeze_state": "degraded",
                "freeze_applied": False,
                "freeze_disabled_reason": "config_degraded",
                "freeze_degradation_codes": ["freeze_seed_unavailable"],
                "freeze_degradation_reason": "freeze config degraded",
            },
        }
    )

    _overdue, _status, summary, _json_text, _ms = build_result_summary(**kwargs)
    freeze_window = (summary.get("algo") or {}).get("freeze_window") or {}

    assert freeze_window.get("freeze_state") == "degraded", freeze_window
    assert "freeze_disabled_reason" not in freeze_window, freeze_window
    assert summary.get("degraded_causes") == ["freeze_window_degraded"], summary
    _assert_degradation_contract(
        summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )


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

    assert not any("freeze_window" in str(item) for item in warnings), warnings
    assert not any("冻结窗口" in str(item) for item in warnings), warnings
    assert degraded_summary.get("degraded_causes") == ["freeze_window_degraded"], degraded_summary
    _assert_degradation_contract(
        degraded_summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )


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
    assert degraded_summary.get("degraded_causes") == ["freeze_window_degraded"], degraded_summary
    _assert_degradation_contract(
        degraded_summary,
        counters={"freeze_window_degraded": 1},
        events=_FREEZE_WINDOW_DEGRADED_EVENT,
    )


def main() -> None:
    test_schedule_summary_freeze_state_controls_hard_constraints()
    print("OK")


if __name__ == "__main__":
    main()
