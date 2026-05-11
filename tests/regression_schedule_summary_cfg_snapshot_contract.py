from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.schedule_summary import build_result_summary


class _StubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def _build_cfg(**overrides):
    data = default_snapshot_values()
    data.update(overrides)
    return data


def _build_snapshot(**overrides) -> ScheduleConfigSnapshot:
    return ScheduleConfigSnapshot(**_build_cfg(**overrides))


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
        _build_cfg(
            objective=" MIN_CHANGEOVER ",
            auto_assign_enabled=" YES ",
            freeze_window_enabled=" YES ",
            freeze_window_days=" 3 ",
        )
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
    assert result_summary_obj.get("degraded_success") is False
    assert result_summary_obj.get("degraded_causes") == []
    assert result_summary_obj.get("degradation_counters") == {}
    assert _degradation_event_contract(result_summary_obj) == []


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
    assert snapshot_events == raw_events
    assert raw_result.get("degradation_counters") == {
        "invalid_choice": 5,
        "blank_required": 1,
        "config_fallback": 1,
    }
    assert snapshot_result.get("degradation_counters") == raw_result.get("degradation_counters")
    assert _degradation_event_contract(raw_result) == [
        ("invalid_choice", "scheduler.summary", "dispatch_mode", 1),
        ("invalid_choice", "scheduler.summary", "dispatch_rule", 1),
        ("invalid_choice", "scheduler.summary", "auto_assign_enabled", 1),
        ("invalid_choice", "scheduler.summary", "algo_mode", 1),
        ("blank_required", "scheduler.summary", "time_budget_seconds", 1),
        ("invalid_choice", "scheduler.summary", "objective", 1),
        ("config_fallback", "schedule.summary.config_snapshot", "config_snapshot", 1),
    ]
