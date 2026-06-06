"""回归测试：ScheduleService.run_schedule 判定"内部工序缺资源"时，对 op.source 须大小写与首尾空白不敏感——source=" INTERNAL  " 的缺设备/人员工序仍应被识别为内部并把其 op_id 计入传给 persist_schedule 的 missing_internal_resource_op_ids。"""

from datetime import datetime
from types import SimpleNamespace


def test_schedule_service_missing_resource_source_case_insensitive(schema_conn) -> None:

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
    from core.services.scheduler.schedule_service import ScheduleService

    captured = {}

    def _stub_build_freeze_window_seed(*args, **kwargs):
        return set(), [], []

    def _stub_load_machine_downtimes(*args, **kwargs):
        return {}

    def _stub_build_resource_pool(*args, **kwargs):
        return None, []

    def _stub_extend_downtime_map_for_resource_pool(_svc, *, downtime_map, **_kw):
        return downtime_map

    def _stub_optimize_schedule(**_kwargs):
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return OptimizationOutcome(
            results=[
                SimpleNamespace(
                    op_id=1,
                    op_code="B001_01",
                    batch_id="B001",
                    seq=1,
                    machine_id="MC001",
                    operator_id="OP001",
                    start_time=datetime(2026, 1, 1, 8, 0, 0),
                    end_time=datetime(2026, 1, 1, 9, 0, 0),
                    source="internal",
                    op_type_name="A",
                )
            ],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            metrics=None,
            best_score=(0.0,),
            best_order=[],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=1,
            algo_stats={},
        )

    def _stub_build_result_summary(*args, **kwargs):
        return [], "success", {"algo": "stub"}, "{}", 0

    def _stub_persist_schedule(_svc, **kwargs):
        captured["missing_internal_resource_op_ids"] = set(kwargs.get("missing_internal_resource_op_ids") or set())
        return None

    patched_attrs = {
        "build_freeze_window_seed": schedule_service_mod.build_freeze_window_seed,
        "load_machine_downtimes": schedule_service_mod.load_machine_downtimes,
        "build_resource_pool": schedule_service_mod.build_resource_pool,
        "extend_downtime_map_for_resource_pool": schedule_service_mod.extend_downtime_map_for_resource_pool,
        "optimize_schedule": schedule_service_mod.optimize_schedule,
        "build_result_summary": schedule_service_mod.build_result_summary,
        "persist_schedule": schedule_service_mod.persist_schedule,
    }

    try:
        schedule_service_mod.build_freeze_window_seed = _stub_build_freeze_window_seed
        schedule_service_mod.load_machine_downtimes = _stub_load_machine_downtimes
        schedule_service_mod.build_resource_pool = _stub_build_resource_pool
        schedule_service_mod.extend_downtime_map_for_resource_pool = _stub_extend_downtime_map_for_resource_pool
        schedule_service_mod.optimize_schedule = _stub_optimize_schedule
        schedule_service_mod.build_result_summary = _stub_build_result_summary
        schedule_service_mod.persist_schedule = _stub_persist_schedule

        conn = schema_conn

        svc = ScheduleService(conn)
        svc._get_batch_or_raise = lambda bid: SimpleNamespace(  # type: ignore[assignment]
            batch_id=bid,
            priority="normal",
            due_date=None,
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
            part_no="P001",
        )

        class _StubOpRepo:
            def list_by_batch(self, bid: str):
                return [
                    SimpleNamespace(
                        id=1,
                        op_code=f"{bid}_01",
                        batch_id=bid,
                        seq=1,
                        source=" INTERNAL  ",
                        machine_id="",
                        operator_id="",
                        supplier_id=None,
                        setup_hours=0.0,
                        unit_hours=0.0,
                        ext_days=None,
                        status="pending",
                        op_type_id=None,
                        op_type_name="A",
                    )
                ]

        svc.op_repo = _StubOpRepo()  # type: ignore[assignment]

        try:
            svc.run_schedule(batch_ids=["B001"], start_dt="2026-01-01 08:00:00", simulate=False, enforce_ready=True)
        finally:
            conn.close()

        missing = captured.get("missing_internal_resource_op_ids") or set()
        assert 1 in missing, missing
    finally:
        for attr_name, original in patched_attrs.items():
            setattr(schedule_service_mod, attr_name, original)


