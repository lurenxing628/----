import os
import sqlite3
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace


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


def _patch_schedule_module(schedule_service_mod, captured):
    from core.services.common.build_outcome import BuildOutcome

    def _stub_build_algo_operations(_svc, ops, *, strict_mode=False, return_outcome=False):
        captured["algo_input_ids"] = [int(op.id) for op in ops]
        captured["algo_input_statuses"] = [(int(op.id), str(getattr(op, "status", "") or "").strip().lower()) for op in ops]
        algo_ops = [
            SimpleNamespace(
                id=int(op.id),
                op_code=op.op_code,
                batch_id=op.batch_id,
                seq=int(op.seq or 0),
                source=op.source,
                machine_id=op.machine_id,
                operator_id=op.operator_id,
                supplier_id=op.supplier_id,
                op_type_name=getattr(op, "op_type_name", None),
            )
            for op in ops
        ]
        if return_outcome:
            return BuildOutcome(algo_ops)
        return algo_ops

    def _stub_build_freeze_window_seed(_svc, **kwargs):
        captured["freeze_all_ids"] = [int(op.id) for op in kwargs.get("operations") or [] if getattr(op, "id", None)]
        captured["freeze_reschedulable_ids"] = [
            int(op.id) for op in kwargs.get("reschedulable_operations") or [] if getattr(op, "id", None)
        ]
        return set(), [], []

    def _stub_load_machine_downtimes(*args, **kwargs):
        return {}

    def _stub_build_resource_pool(*args, **kwargs):
        return None, []

    def _stub_extend_downtime_map_for_resource_pool(_svc, *, downtime_map, **_kw):
        return downtime_map

    def _stub_optimize_schedule(*, algo_ops_to_schedule, **_kwargs):
        captured["algo_ops_to_schedule_ids"] = [int(op.id) for op in algo_ops_to_schedule]
        override_results = captured.get("optimizer_results_override")
        if override_results is not None:
            results = list(override_results)
        else:
            base_dt = datetime(2026, 1, 1, 8, 0, 0)
            results = []
            for idx, op in enumerate(algo_ops_to_schedule):
                st = base_dt + timedelta(hours=idx)
                et = st + timedelta(hours=1)
                results.append(
                    SimpleNamespace(
                        op_id=int(op.id),
                        op_code=op.op_code,
                        batch_id=op.batch_id,
                        seq=int(op.seq or 0),
                        machine_id="MC001",
                        operator_id="OP001",
                        start_time=st,
                        end_time=et,
                        source=op.source,
                        op_type_name=getattr(op, "op_type_name", None),
                    )
                )
        summary = SimpleNamespace(
            success=True,
            total_ops=len(algo_ops_to_schedule),
            scheduled_ops=len(results),
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
        )

    def _stub_build_result_summary(*args, **kwargs):
        return [], "success", {"algo": {}}, "{}", 0

    def _stub_persist_schedule(_svc, **kwargs):
        payload = kwargs.get("validated_schedule_payload")
        captured["persist_scheduled_op_ids"] = set(getattr(payload, "scheduled_op_ids", set()) or set())
        captured["persist_reschedulable_statuses"] = [
            (int(op.id), str(getattr(op, "status", "") or "").strip().lower())
            for op in kwargs.get("reschedulable_operations") or []
            if getattr(op, "id", None)
        ]
        captured["persist_results_op_ids"] = [
            int(row.op_id) for row in getattr(payload, "schedule_rows", []) if getattr(row, "op_id", None)
        ]
        return None

    schedule_service_mod.build_algo_operations = _stub_build_algo_operations
    schedule_service_mod.build_freeze_window_seed = _stub_build_freeze_window_seed
    schedule_service_mod.load_machine_downtimes = _stub_load_machine_downtimes
    schedule_service_mod.build_resource_pool = _stub_build_resource_pool
    schedule_service_mod.extend_downtime_map_for_resource_pool = _stub_extend_downtime_map_for_resource_pool
    schedule_service_mod.optimize_schedule = _stub_optimize_schedule
    schedule_service_mod.build_result_summary = _stub_build_result_summary
    schedule_service_mod.persist_schedule = _stub_persist_schedule


def _batch_stub(batch_id: str, status: str) -> SimpleNamespace:
    return SimpleNamespace(
        batch_id=batch_id,
        status=status,
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
        part_no="P001",
    )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_service import ScheduleService

    captured = {}
    _patch_schedule_module(schedule_service_mod, captured)

    # 场景 1：completed/skipped 不进入算法输入、freeze seed 与结果集
    conn1 = _make_conn(repo_root)
    try:
        svc1 = ScheduleService(conn1)
        ops_by_batch = {
            "B001": [
                SimpleNamespace(
                    id=1,
                    op_code="B001_10",
                    batch_id="B001",
                    seq=10,
                    source="internal",
                    machine_id="",
                    operator_id="",
                    supplier_id=None,
                    setup_hours=1.0,
                    unit_hours=0.0,
                    ext_days=None,
                    status="pending",
                    op_type_name="工序A",
                ),
                SimpleNamespace(
                    id=2,
                    op_code="B001_20",
                    batch_id="B001",
                    seq=20,
                    source="internal",
                    machine_id="",
                    operator_id="",
                    supplier_id=None,
                    setup_hours=1.0,
                    unit_hours=0.0,
                    ext_days=None,
                    status="scheduled",
                    op_type_name="工序B",
                ),
                SimpleNamespace(
                    id=3,
                    op_code="B001_30",
                    batch_id="B001",
                    seq=30,
                    source="internal",
                    machine_id="",
                    operator_id="",
                    supplier_id=None,
                    setup_hours=1.0,
                    unit_hours=0.0,
                    ext_days=None,
                    status="completed",
                    op_type_name="工序C",
                ),
                SimpleNamespace(
                    id=4,
                    op_code="B001_40",
                    batch_id="B001",
                    seq=40,
                    source="external",
                    machine_id=None,
                    operator_id=None,
                    supplier_id="SUP001",
                    setup_hours=0.0,
                    unit_hours=0.0,
                    ext_days=2.0,
                    status="skipped",
                    op_type_name="外协D",
                ),
            ]
        }
        svc1._get_batch_or_raise = lambda bid: _batch_stub(bid, "pending")  # type: ignore[assignment]
        svc1.op_repo = SimpleNamespace(list_by_batch=lambda bid: list(ops_by_batch.get(bid, [])))  # type: ignore[assignment]

        ret = svc1.run_schedule(batch_ids=["B001"], start_dt="2026-01-01 08:00:00", simulate=True, enforce_ready=True)
        assert captured.get("algo_input_ids") == [1, 2], f"算法输入不应包含 completed/skipped：{captured!r}"
        assert captured.get("freeze_reschedulable_ids") == [1, 2], f"freeze seed 应与可重排集合一致：{captured!r}"
        assert captured.get("persist_scheduled_op_ids") == {1, 2}, f"persist 契约收口异常：{captured!r}"
        assert captured.get("persist_results_op_ids") == [1, 2], f"结果集不应包含 terminal op：{captured!r}"
        assert int((ret.get("summary") or {}).get("total_ops") or 0) == 2, f"total_ops 应只统计可重排工序：{ret!r}"

        # 场景 2：completed/cancelled 批次服务层 fail-fast
        captured["optimizer_results_override"] = [
            SimpleNamespace(
                op_id=1,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                machine_id="MC001",
                operator_id="OP001",
                start_time=datetime(2026, 1, 2, 8, 0, 0),
                end_time=datetime(2026, 1, 2, 9, 0, 0),
                source="internal",
                op_type_name="宸ュ簭A",
            ),
            SimpleNamespace(
                op_id=2,
                op_code="B001_20",
                batch_id="B001",
                seq=20,
                machine_id="MC001",
                operator_id="OP001",
                start_time=datetime(2026, 1, 2, 9, 0, 0),
                end_time=datetime(2026, 1, 2, 10, 0, 0),
                source="internal",
                op_type_name="宸ュ簭B",
            ),
            SimpleNamespace(
                op_id=999,
                op_code="B999_10",
                batch_id="B999",
                seq=10,
                machine_id="MC999",
                operator_id="OP999",
                start_time=datetime(2026, 1, 2, 10, 0, 0),
                end_time=datetime(2026, 1, 2, 11, 0, 0),
                source="internal",
                op_type_name="Rogue",
            ),
        ]
        captured.pop("persist_results_op_ids", None)
        rejected_out_of_scope = False
        try:
            svc1.run_schedule(batch_ids=["B001"], start_dt="2026-01-01 08:00:00", simulate=True, enforce_ready=True)
        except ValidationError as e:
            details = dict(getattr(e, "details", {}) or {})
            rejected_out_of_scope = details.get("reason") == "out_of_scope_schedule_rows"
            assert details.get("count") == 1, details
            assert details.get("sample_op_ids") == [999], details
            assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details
        assert rejected_out_of_scope, "service layer must reject optimizer results that escape reschedulable scope"
        assert "persist_results_op_ids" not in captured, captured
        captured.pop("optimizer_results_override", None)

        svc2 = ScheduleService(conn1)
        svc2._get_batch_or_raise = lambda bid: _batch_stub(bid, "completed")  # type: ignore[assignment]
        svc2.op_repo = SimpleNamespace(list_by_batch=lambda _bid: (_ for _ in ()).throw(AssertionError("completed 批次不应继续读取工序")))  # type: ignore[assignment]
        rejected_completed = False
        try:
            svc2.run_schedule(batch_ids=["B_DONE"], start_dt="2026-01-01 08:00:00", simulate=True, enforce_ready=True)
        except ValidationError as e:
            rejected_completed = "不允许排产" in str(e)
        assert rejected_completed, "completed 批次应在服务层 fail-fast"

        svc3 = ScheduleService(conn1)
        svc3._get_batch_or_raise = lambda bid: _batch_stub(bid, "cancelled")  # type: ignore[assignment]
        svc3.op_repo = SimpleNamespace(list_by_batch=lambda _bid: (_ for _ in ()).throw(AssertionError("cancelled 批次不应继续读取工序")))  # type: ignore[assignment]
        rejected_cancelled = False
        try:
            svc3.run_schedule(batch_ids=["B_CANCEL"], start_dt="2026-01-01 08:00:00", simulate=True, enforce_ready=True)
        except ValidationError as e:
            rejected_cancelled = "不允许排产" in str(e)
        assert rejected_cancelled, "cancelled 批次应在服务层 fail-fast"
    finally:
        try:
            conn1.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
