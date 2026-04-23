from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.schedule_summary import build_result_summary


class _StubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def _build_snapshot(**overrides) -> ScheduleConfigSnapshot:
    data = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }
    data.update(overrides)
    return ScheduleConfigSnapshot(**data)


def _build_summary(cfg):
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _StubSvc(),
        cfg=cfg,
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="MIN_CHANGEOVER",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids={1},
        freeze_meta={"freeze_state": "active", "freeze_applied": True, "freeze_degradation_codes": []},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        simulate=False,
        t0=0.0,
    )
    return result_summary_obj


def test_schedule_summary_normalizes_raw_cfg_into_single_snapshot() -> None:
    result_summary_obj = _build_summary(
        {
            "objective": " MIN_CHANGEOVER ",
            "auto_assign_enabled": " YES ",
            "freeze_window_enabled": " YES ",
            "freeze_window_days": " 3 ",
        }
    )

    algo = result_summary_obj.get("algo") or {}
    config_snapshot = algo.get("config_snapshot") or {}
    assert config_snapshot.get("objective") == "min_changeover"
    assert config_snapshot.get("auto_assign_enabled") == "yes"
    assert config_snapshot.get("freeze_window_enabled") == "yes"
    assert config_snapshot.get("freeze_window_days") == 3
    assert algo.get("comparison_metric") == "changeover_count"
    schema_keys = [item.get("key") for item in (algo.get("best_score_schema") or []) if isinstance(item, dict)]
    assert schema_keys[:2] == ["failed_ops", "changeover_count"]
    assert "freeze_window" in (algo.get("hard_constraints") or [])


def test_schedule_summary_dirty_snapshot_matches_raw_cfg_contract() -> None:
    raw_payload = _build_snapshot().to_dict()
    raw_payload.update(
        {
            "objective": " NOT-A-VALID-OBJECTIVE ",
            "algo_mode": " BROKEN-MODE ",
            "dispatch_mode": " UNKNOWN-MODE ",
            "dispatch_rule": " UNKNOWN-RULE ",
            "time_budget_seconds": "",
            "auto_assign_enabled": " MAYBE ",
            "freeze_window_enabled": " YES ",
            "freeze_window_days": " 3 ",
        }
    )
    raw_result = _build_summary(raw_payload)
    snapshot_result = _build_summary(
        _build_snapshot(
            objective=" NOT-A-VALID-OBJECTIVE ",
            algo_mode=" BROKEN-MODE ",
            dispatch_mode=" UNKNOWN-MODE ",
            dispatch_rule=" UNKNOWN-RULE ",
            time_budget_seconds="",
            auto_assign_enabled=" MAYBE ",
            freeze_window_enabled=" YES ",
            freeze_window_days=" 3 ",
        )
    )

    raw_algo = raw_result.get("algo") or {}
    snapshot_algo = snapshot_result.get("algo") or {}

    assert snapshot_algo.get("config_snapshot") == raw_algo.get("config_snapshot")
    assert snapshot_algo.get("comparison_metric") == raw_algo.get("comparison_metric")
    assert snapshot_algo.get("hard_constraints") == raw_algo.get("hard_constraints")
    assert (snapshot_algo.get("config_snapshot") or {}).get("auto_assign_enabled") == "no"
    assert raw_result.get("degraded_success") is True
    assert snapshot_result.get("degraded_success") is True
    assert "config_fallback" in list(raw_result.get("degraded_causes") or [])
    assert "config_fallback" in list(snapshot_result.get("degraded_causes") or [])
    raw_events = list(raw_result.get("degradation_events") or [])
    snapshot_events = list(snapshot_result.get("degradation_events") or [])
    assert any(str(event.get("field") or "") == "objective" for event in raw_events), raw_events
    assert any(str(event.get("field") or "") == "algo_mode" for event in raw_events), raw_events
    assert any(str(event.get("field") or "") == "dispatch_mode" for event in raw_events), raw_events
    assert any(str(event.get("field") or "") == "dispatch_rule" for event in raw_events), raw_events
    assert any(str(event.get("field") or "") == "time_budget_seconds" for event in raw_events), raw_events
    assert snapshot_events == raw_events
