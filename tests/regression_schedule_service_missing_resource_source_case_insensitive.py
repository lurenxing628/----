import os
import sqlite3
import sys
from datetime import datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        load_schema(conn, repo_root)

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
            svc.run_schedule(batch_ids=["B001"], start_dt="2026-01-01 08:00:00", simulate=True, enforce_ready=True)
        finally:
            conn.close()

        missing = captured.get("missing_internal_resource_op_ids") or set()
        assert 1 in missing, missing
    finally:
        for attr_name, original in patched_attrs.items():
            setattr(schedule_service_mod, attr_name, original)

    print("OK")


if __name__ == "__main__":
    main()
