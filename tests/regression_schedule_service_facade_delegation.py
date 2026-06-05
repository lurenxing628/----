"""守护 ScheduleService 作为门面的委派契约：__init__ 公开签名保持 (self, conn, logger=None, op_logger=None)、仓储 bundle 别名与 _repos 同源、Repository 各取数方法保留命名行返回类型；并验证 _run_schedule_impl 把入参原样转交 collect_schedule_run_input/orchestrate_schedule_run/persist_schedule，对外只暴露 summary_contract（而非裸 summary）拼成的结果字典。"""

import inspect
import os
import sqlite3
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import List, Optional, get_type_hints

from data.repositories.schedule_repo import ScheduleRepository
from data.repositories.schedule_rows import (
    ScheduleDetailRow,
    ScheduleDispatchRow,
    ScheduleSeedRow,
    ScheduleTimeSpanRow,
)


def test_schedule_service_constructor_keeps_public_signature_contract() -> None:
    from core.services.scheduler.schedule_service import ScheduleService

    signature = inspect.signature(ScheduleService.__init__)
    params = list(signature.parameters.values())

    assert [param.name for param in params] == ["self", "conn", "logger", "op_logger"]
    assert params[1].default is inspect.Signature.empty
    assert params[2].default is None
    assert params[3].default is None


def test_schedule_repository_dict_rows_have_named_return_contracts() -> None:
    assert get_type_hints(ScheduleRepository.get_version_time_span)["return"] == Optional[ScheduleTimeSpanRow]
    assert (
        get_type_hints(ScheduleRepository.list_version_rows_by_op_ids_start_range)["return"]
        == List[ScheduleSeedRow]
    )
    assert get_type_hints(ScheduleRepository.list_overlapping_with_details)["return"] == List[ScheduleDetailRow]
    assert get_type_hints(ScheduleRepository.list_by_version_with_details)["return"] == List[ScheduleDetailRow]
    assert (
        get_type_hints(ScheduleRepository.list_dispatch_rows_with_resource_context)["return"]
        == List[ScheduleDispatchRow]
    )


def test_schedule_service_repository_bundle_aliases_stay_in_sync() -> None:
    from core.services.scheduler.schedule_service import ScheduleService

    service = ScheduleService(object(), logger=None, op_logger=None)
    repos = getattr(service, "_repos")

    for attr in (
        "batch_repo",
        "op_repo",
        "part_op_repo",
        "group_repo",
        "machine_repo",
        "operator_repo",
        "operator_machine_repo",
        "supplier_repo",
        "schedule_repo",
        "history_repo",
    ):
        assert getattr(service, attr) is getattr(repos, attr)


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found")


class _SummaryContract:
    def __init__(self, payload):
        self._payload = dict(payload)

    def to_dict(self):
        return dict(self._payload)


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.services.scheduler.schedule_service import ScheduleService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row

    captured = {}
    collected = SimpleNamespace(
        cfg=SimpleNamespace(),
        normalized_batch_ids=["B001"],
        created_by_text="regression",
        batches={"B001": SimpleNamespace(batch_id="B001")},
        operations=[SimpleNamespace(id=1)],
        reschedulable_operations=[SimpleNamespace(id=1)],
        reschedulable_op_ids={1},
        missing_internal_resource_op_ids={1},
        frozen_op_ids={2},
    )
    validated_schedule_payload = SimpleNamespace(
        schedule_rows=[SimpleNamespace(op_id=1)],
        scheduled_op_ids={1},
        assigned_by_op_id={1: {"machine_id": "MC001", "operator_id": "OP001"}},
    )
    orchestrated = SimpleNamespace(
        version=7,
        results=[SimpleNamespace(op_id=1)],
        summary=SimpleNamespace(
            success=False,
            total_ops=999,
            scheduled_ops=998,
            failed_ops=997,
            warnings=["do not use raw summary shape"],
            errors=["do not use raw summary shape"],
            duration_seconds=999.0,
        ),
        summary_contract=_SummaryContract(
            {
                "success": True,
                "total_ops": 1,
                "scheduled_ops": 1,
                "failed_ops": 0,
                "warnings": ["w1"],
                "errors": [],
                "duration_seconds": 0.0,
                "degradation_events": [],
                "degradation_counters": {},
                "degraded_success": False,
                "degraded_causes": [],
                "error_count": 0,
                "errors_sample": [],
                "summary_schema_version": "1.2",
                "algo": {
                    "comparison_metric": "weighted_tardiness_hours",
                    "best_score_schema": [
                        {"key": "failed_ops"},
                        {"key": "weighted_tardiness_hours"},
                    ],
                    "config_snapshot": {
                        "objective": "min_weighted_tardiness",
                        "auto_assign_enabled": "yes",
                    },
                },
                "counts": {
                    "op_count": 1,
                    "total_ops": 1,
                    "scheduled_ops": 1,
                    "failed_ops": 0,
                },
            }
        ),
        validated_schedule_payload=validated_schedule_payload,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "fifo"},
        result_status="simulated",
        result_summary_json="{}",
        result_summary_obj={"algo": {}},
        overdue_items=[{"batch_id": "B001"}],
        time_cost_ms=12,
    )

    original_collect = getattr(schedule_service_mod, "collect_schedule_run_input", None)
    original_orchestrate = getattr(schedule_service_mod, "orchestrate_schedule_run", None)
    original_persist = schedule_service_mod.persist_schedule

    def _stub_collect(svc, **kwargs):
        captured["collect_svc"] = svc
        captured["collect_kwargs"] = dict(kwargs or {})
        return collected

    def _stub_orchestrate(svc, *, schedule_input, simulate, strict_mode, **kwargs):
        captured["orchestrate_svc"] = svc
        captured["orchestrate_schedule_input"] = schedule_input
        captured["orchestrate_simulate"] = simulate
        captured["orchestrate_strict_mode"] = strict_mode
        captured["orchestrate_kwargs"] = dict(kwargs or {})
        return orchestrated

    def _stub_persist(svc, **kwargs):
        captured["persist_svc"] = svc
        captured["persist_kwargs"] = dict(kwargs or {})
        return None

    schedule_service_mod.collect_schedule_run_input = _stub_collect
    schedule_service_mod.orchestrate_schedule_run = _stub_orchestrate
    schedule_service_mod.persist_schedule = _stub_persist
    try:
        svc = ScheduleService(conn, logger=None, op_logger=None)
        result = svc._run_schedule_impl(
            batch_ids=["B001"],
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            created_by="regression",
            simulate=True,
            enforce_ready=False,
            strict_mode=True,
        )
    finally:
        if original_collect is None:
            delattr(schedule_service_mod, "collect_schedule_run_input")
        else:
            schedule_service_mod.collect_schedule_run_input = original_collect
        if original_orchestrate is None:
            delattr(schedule_service_mod, "orchestrate_schedule_run")
        else:
            schedule_service_mod.orchestrate_schedule_run = original_orchestrate
        schedule_service_mod.persist_schedule = original_persist
        conn.close()

    assert captured.get("collect_svc") is svc, captured
    assert captured.get("collect_kwargs", {}).get("batch_ids") == ["B001"], captured
    assert captured.get("collect_kwargs", {}).get("simulate") is True, captured
    assert captured.get("collect_kwargs", {}).get("strict_mode") is True, captured

    assert captured.get("orchestrate_svc") is svc, captured
    assert captured.get("orchestrate_schedule_input") is collected, captured
    assert captured.get("orchestrate_simulate") is True, captured
    assert captured.get("orchestrate_strict_mode") is True, captured

    persist_kwargs = captured.get("persist_kwargs") or {}
    assert persist_kwargs.get("version") == 7, persist_kwargs
    assert persist_kwargs.get("normalized_batch_ids") == ["B001"], persist_kwargs
    assert persist_kwargs.get("created_by") == "regression", persist_kwargs
    assert persist_kwargs.get("frozen_op_ids") == {2}, persist_kwargs
    assert persist_kwargs.get("result_status") == "simulated", persist_kwargs
    assert persist_kwargs.get("time_cost_ms") == 12, persist_kwargs
    assert persist_kwargs.get("validated_schedule_payload") is validated_schedule_payload, persist_kwargs
    assert "has_actionable_schedule" not in persist_kwargs, persist_kwargs

    assert result == {
        "is_simulation": True,
        "version": 7,
        "strategy": "priority_first",
        "strategy_params": {"dispatch": "fifo"},
        "result_status": "simulated",
        "summary": {
            "success": True,
            "total_ops": 1,
            "scheduled_ops": 1,
            "failed_ops": 0,
            "warnings": ["w1"],
            "errors": [],
            "duration_seconds": 0.0,
            "degradation_events": [],
            "degradation_counters": {},
            "degraded_success": False,
            "degraded_causes": [],
            "error_count": 0,
            "errors_sample": [],
            "summary_schema_version": "1.2",
            "algo": {
                "comparison_metric": "weighted_tardiness_hours",
                "best_score_schema": [
                    {"key": "failed_ops"},
                    {"key": "weighted_tardiness_hours"},
                ],
                "config_snapshot": {
                    "objective": "min_weighted_tardiness",
                    "auto_assign_enabled": "yes",
                },
            },
            "counts": {
                "op_count": 1,
                "total_ops": 1,
                "scheduled_ops": 1,
                "failed_ops": 0,
            },
        },
        "overdue_batches": [{"batch_id": "B001"}],
        "time_cost_ms": 12,
    }, result

    print("OK")


if __name__ == "__main__":
    main()
