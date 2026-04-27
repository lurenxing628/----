from __future__ import annotations

import sqlite3
from datetime import datetime
from types import SimpleNamespace

from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot


class _SummaryContract:
    def __init__(self, payload):
        self._payload = dict(payload)

    def to_dict(self):
        return dict(self._payload)


class _Repo:
    def __init__(self, values):
        self.values = dict(values)
        self.calls = []

    def get(self, *args):
        key = tuple(args) if len(args) != 1 else args[0]
        self.calls.append(key)
        return self.values.get(key)


class _OperationRepo:
    def __init__(self, operations_by_batch):
        self.operations_by_batch = dict(operations_by_batch)
        self.calls = []

    def list_by_batch(self, batch_id):
        self.calls.append(batch_id)
        return list(self.operations_by_batch.get(batch_id) or [])


class _ConfigService:
    def __init__(self, *args, **kwargs):
        pass

    def get_snapshot(self, *, strict_mode=False):
        values = default_snapshot_values()
        values.update(
            {
                "enforce_ready_default": "no",
                "freeze_window_enabled": "no",
                "freeze_window_days": 0,
                "auto_assign_enabled": "no",
            }
        )
        return ScheduleConfigSnapshot(**values)


class _CalendarService:
    def __init__(self, *args, **kwargs):
        pass


def _external_op():
    return SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=20,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="external",
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days=2.5,
    )


def test_schedule_service_returns_merge_context_degraded_summary_without_input_fallback(monkeypatch) -> None:
    import core.services.scheduler.calendar_service as calendar_service_mod
    import core.services.scheduler.config.config_service as config_service_mod
    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.services.scheduler.schedule_service import ScheduleService
    from core.services.scheduler.schedule_summary import build_result_summary

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row

    def _stub_orchestrate(svc, *, schedule_input, simulate, strict_mode, **kwargs):
        assert schedule_input.algo_input_outcome.has_events
        assert [
            event.code
            for event in schedule_input.algo_input_outcome.events
        ] == ["external_group_missing"]
        summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[])
        _overdue, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary(
            svc,
            cfg=schedule_input.cfg,
            version=3,
            normalized_batch_ids=schedule_input.normalized_batch_ids,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            end_date=None,
            batches=schedule_input.batches,
            operations=schedule_input.operations,
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
            input_build_outcome=schedule_input.algo_input_outcome,
            simulate=simulate,
            t0=0.0,
        )
        return SimpleNamespace(
            version=3,
            results=[],
            summary=summary,
            summary_contract=_SummaryContract(result_summary_obj),
            validated_schedule_payload=SimpleNamespace(schedule_rows=[], scheduled_op_ids=set(), assigned_by_op_id={}),
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            result_status=result_status,
            result_summary_json=result_summary_json,
            result_summary_obj=result_summary_obj,
            overdue_items=[],
            time_cost_ms=time_cost_ms,
        )

    def _stub_build_freeze_window_seed(*args, **kwargs):
        return set(), [], []

    def _stub_load_machine_downtimes(*args, **kwargs):
        return {}

    def _stub_build_resource_pool(*args, **kwargs):
        return None, []

    def _stub_extend_downtime_map_for_resource_pool(*args, **kwargs):
        return kwargs["downtime_map"]

    monkeypatch.setattr(calendar_service_mod, "CalendarService", _CalendarService)
    monkeypatch.setattr(config_service_mod, "ConfigService", _ConfigService)
    monkeypatch.setattr(schedule_service_mod, "build_freeze_window_seed", _stub_build_freeze_window_seed)
    monkeypatch.setattr(schedule_service_mod, "load_machine_downtimes", _stub_load_machine_downtimes)
    monkeypatch.setattr(schedule_service_mod, "build_resource_pool", _stub_build_resource_pool)
    monkeypatch.setattr(
        schedule_service_mod,
        "extend_downtime_map_for_resource_pool",
        _stub_extend_downtime_map_for_resource_pool,
    )
    monkeypatch.setattr(schedule_service_mod, "orchestrate_schedule_run", _stub_orchestrate)
    monkeypatch.setattr(schedule_service_mod, "persist_schedule", lambda *args, **kwargs: None)

    service = ScheduleService(conn, logger=None, op_logger=None)
    service.batch_repo = _Repo(
        {
            "B001": SimpleNamespace(
                batch_id="B001",
                part_no="P001",
                status="planned",
                ready_status="yes",
                due_date=None,
            )
        }
    )
    service.op_repo = _OperationRepo({"B001": [_external_op()]})
    service.part_op_repo = _Repo({("P001", 20): SimpleNamespace(ext_group_id="G404")})
    service.group_repo = _Repo({})
    service.history_repo = SimpleNamespace(get_latest_version=lambda: 0)

    try:
        result = service.run_schedule(
            batch_ids=["B001"],
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            end_date=None,
            created_by="regression",
            simulate=False,
            enforce_ready=False,
            strict_mode=False,
        )
    finally:
        conn.close()

    assert service.op_repo.calls == ["B001"]
    assert service.part_op_repo.calls == [("P001", 20)]
    assert service.group_repo.calls == ["G404"]
    summary = result["summary"]
    assert "merge_context_degraded" in summary["degraded_causes"]
    assert "input_fallback" not in summary["degraded_causes"]
    assert summary["algo"]["merge_context_degraded"] is True
    assert [event["code"] for event in summary["algo"]["merge_context_events"]] == ["external_group_missing"]
