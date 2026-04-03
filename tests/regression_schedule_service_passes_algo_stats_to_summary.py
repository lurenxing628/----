import os
import sqlite3
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _make_conn(repo_root: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)
    return conn


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.services.scheduler.schedule_service import ScheduleService

    captured = {}

    def _stub_build_algo_operations(_svc, ops):
        return [
            SimpleNamespace(
                id=int(op.id),
                op_code=op.op_code,
                batch_id=op.batch_id,
                seq=int(op.seq or 0),
                source=op.source,
                machine_id=getattr(op, "machine_id", None),
                operator_id=getattr(op, "operator_id", None),
                supplier_id=getattr(op, "supplier_id", None),
                op_type_name=getattr(op, "op_type_name", None),
            )
            for op in ops
        ]

    def _stub_build_freeze_window_seed(_svc, **_kwargs):
        return set(), [], []

    def _stub_load_machine_downtimes(*_args, **_kwargs):
        return {}

    def _stub_build_resource_pool(*_args, **_kwargs):
        return None, []

    def _stub_extend_downtime_map_for_resource_pool(_svc, *, downtime_map, **_kw):
        return downtime_map

    def _stub_optimize_schedule(**_kwargs):
        captured["optimize_strict_mode"] = _kwargs.get("strict_mode")
        results = [
            SimpleNamespace(
                op_id=1,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                machine_id="MC001",
                operator_id="OP001",
                start_time=datetime(2026, 4, 1, 8, 0, 0),
                end_time=datetime(2026, 4, 1, 9, 0, 0),
                source="internal",
                op_type_name="工序A",
            )
        ]
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return SimpleNamespace(
            results=results,
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
            algo_stats={
                "fallback_counts": {"seed_duplicate_dropped_count": 2},
                "param_fallbacks": {"dispatch_rule_defaulted_count": 1},
            },
        )

    def _stub_build_result_summary(*args, **kwargs):
        captured["algo_stats"] = kwargs.get("algo_stats")
        return [], "simulated", {"algo": {}}, "{}", 0

    original_build_algo_operations = schedule_service_mod.build_algo_operations
    original_build_freeze_window_seed = schedule_service_mod.build_freeze_window_seed
    original_load_machine_downtimes = schedule_service_mod.load_machine_downtimes
    original_build_resource_pool = schedule_service_mod.build_resource_pool
    original_extend_downtime_map_for_resource_pool = schedule_service_mod.extend_downtime_map_for_resource_pool
    original_optimize_schedule = schedule_service_mod.optimize_schedule
    original_build_result_summary = schedule_service_mod.build_result_summary
    original_persist_schedule = schedule_service_mod.persist_schedule

    schedule_service_mod.build_algo_operations = _stub_build_algo_operations
    schedule_service_mod.build_freeze_window_seed = _stub_build_freeze_window_seed
    schedule_service_mod.load_machine_downtimes = _stub_load_machine_downtimes
    schedule_service_mod.build_resource_pool = _stub_build_resource_pool
    schedule_service_mod.extend_downtime_map_for_resource_pool = _stub_extend_downtime_map_for_resource_pool
    schedule_service_mod.optimize_schedule = _stub_optimize_schedule
    schedule_service_mod.build_result_summary = _stub_build_result_summary
    schedule_service_mod.persist_schedule = lambda *_args, **_kwargs: None

    conn = _make_conn(repo_root)
    try:
        svc = ScheduleService(conn)
        batch_repo = cast(Any, svc.batch_repo)
        batch_repo.get = lambda batch_id: SimpleNamespace(
            batch_id=batch_id,
            status="pending",
            priority="normal",
            due_date=None,
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
            part_no="P001",
        )
        op_repo = cast(Any, svc.op_repo)
        op_repo.list_by_batch = lambda batch_id: [
            SimpleNamespace(
                id=1,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                source="internal",
                machine_id="MC001",
                operator_id="OP001",
                supplier_id=None,
                setup_hours=1.0,
                unit_hours=0.0,
                ext_days=None,
                status="pending",
                op_type_name="工序A",
            )
        ]

        result = svc.run_schedule(
            batch_ids=["B001"],
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            simulate=True,
            strict_mode=True,
        )
    finally:
        schedule_service_mod.build_algo_operations = original_build_algo_operations
        schedule_service_mod.build_freeze_window_seed = original_build_freeze_window_seed
        schedule_service_mod.load_machine_downtimes = original_load_machine_downtimes
        schedule_service_mod.build_resource_pool = original_build_resource_pool
        schedule_service_mod.extend_downtime_map_for_resource_pool = original_extend_downtime_map_for_resource_pool
        schedule_service_mod.optimize_schedule = original_optimize_schedule
        schedule_service_mod.build_result_summary = original_build_result_summary
        schedule_service_mod.persist_schedule = original_persist_schedule
        conn.close()

    assert isinstance(result, dict), f"run_schedule 应返回 dict，实际：{type(result)!r}"
    assert result.get("result_status") == "simulated", f"run_schedule 返回异常：{result.get('result_status')!r}"
    algo_stats = captured.get("algo_stats") or {}
    assert int((algo_stats.get("fallback_counts") or {}).get("seed_duplicate_dropped_count") or 0) == 2, (
        f"ScheduleService 未透传 fallback_counts：{algo_stats!r}"
    )
    assert int((algo_stats.get("param_fallbacks") or {}).get("dispatch_rule_defaulted_count") or 0) == 1, (
        f"ScheduleService 未透传 param_fallbacks：{algo_stats!r}"
    )
    assert captured.get("optimize_strict_mode") is True, f"ScheduleService 未向 optimize_schedule 透传 strict_mode：{captured!r}"

    print("OK")


if __name__ == "__main__":
    main()
