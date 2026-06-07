"""回归测试：ScheduleService.run_schedule 在冻结窗口内无可调整工序时短路——构建算法输入并读取冻结窗口后即抛 ValidationError（区分排产/模拟措辞），绝不继续加载停机区间、构建资源池、扩展停机映射、调用优化器、进入持久化或分配新版本号。"""

import os
import sqlite3
from types import SimpleNamespace

from tests._support.paths import REPO_ROOT, REPO_ROOT_STR

SCHEMA_PATH = str(REPO_ROOT / "schema.sql")


def load_schema(conn: sqlite3.Connection) -> None:
    schema_path = SCHEMA_PATH
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn)
    return conn


def _batch_stub(batch_id: str, status: str = "pending") -> SimpleNamespace:
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
        part_name="测试件",
    )


def _reschedulable_ops(batch_id: str):
    return [
        SimpleNamespace(
            id=11,
            op_code=f"{batch_id}_10",
            batch_id=batch_id,
            seq=10,
            source="internal",
            machine_id="",
            operator_id="",
            supplier_id=None,
            setup_hours=1.0,
            unit_hours=0.0,
            ext_days=None,
            status="pending",
            op_type_id="OT_A",
            op_type_name="工序A",
        ),
        SimpleNamespace(
            id=12,
            op_code=f"{batch_id}_20",
            batch_id=batch_id,
            seq=20,
            source="internal",
            machine_id="",
            operator_id="",
            supplier_id=None,
            setup_hours=1.0,
            unit_hours=0.0,
            ext_days=None,
            status="scheduled",
            op_type_id="OT_B",
            op_type_name="工序B",
        ),
    ]


def _run_case(
    ScheduleService,
    ValidationError,
    *,
    captured,
    simulate: bool,
    expected_message: str,
) -> None:
    conn = _make_conn()
    try:
        svc = ScheduleService(conn)
        svc._get_batch_or_raise = lambda bid: _batch_stub(bid, "pending")  # type: ignore[assignment]
        svc.op_repo = SimpleNamespace(list_by_batch=lambda _bid: list(_reschedulable_ops("B_FROZEN")))  # type: ignore[assignment]

        def _unexpected_allocate_next_version():
            captured["allocate_next_version_calls"] = captured.get("allocate_next_version_calls", 0) + 1
            raise AssertionError("冻结后全空场景不应分配新版本号")

        svc.history_repo.allocate_next_version = _unexpected_allocate_next_version  # type: ignore[assignment]

        try:
            svc.run_schedule(
                batch_ids=["B_FROZEN"],
                start_dt="2026-01-01 08:00:00",
                simulate=simulate,
                enforce_ready=True,
            )
            raise RuntimeError("冻结后全空场景应抛出 ValidationError")
        except ValidationError as exc:
            message = getattr(exc, "message", str(exc))
            assert expected_message in message, f"冻结后全空提示异常：{message!r}"

        assert captured.get("build_algo_operations_calls", 0) == 1, f"应先构建算法输入：{captured!r}"
        assert captured.get("build_freeze_window_seed_calls", 0) == 1, f"应读取冻结窗口：{captured!r}"
        assert captured.get("load_machine_downtimes_calls", 0) == 0, f"冻结后全空不应继续加载停机区间：{captured!r}"
        assert captured.get("build_resource_pool_calls", 0) == 0, f"冻结后全空不应继续构建资源池：{captured!r}"
        assert captured.get("extend_downtime_map_calls", 0) == 0, f"冻结后全空不应继续扩展停机区间：{captured!r}"
        assert captured.get("optimize_schedule_calls", 0) == 0, f"冻结后全空不应调用优化器：{captured!r}"
        assert captured.get("persist_schedule_calls", 0) == 0, f"冻结后全空不应进入持久化：{captured!r}"
        assert captured.get("allocate_next_version_calls", 0) == 0, f"冻结后全空不应分配版本号：{captured!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_schedule_service_all_frozen_short_circuit() -> None:

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.infrastructure.errors import ValidationError
    from core.services.common.build_outcome import BuildOutcome
    from core.services.scheduler.schedule_service import ScheduleService

    captured = {}
    original_build_algo_operations = schedule_service_mod.build_algo_operations
    original_build_freeze_window_seed = schedule_service_mod.build_freeze_window_seed
    original_load_machine_downtimes = schedule_service_mod.load_machine_downtimes
    original_build_resource_pool = schedule_service_mod.build_resource_pool
    original_extend_downtime_map = schedule_service_mod.extend_downtime_map_for_resource_pool
    original_optimize_schedule = schedule_service_mod.optimize_schedule
    original_persist_schedule = schedule_service_mod.persist_schedule

    def _stub_build_algo_operations(_svc, ops, *, strict_mode=False, return_outcome=False):
        captured["build_algo_operations_calls"] = captured.get("build_algo_operations_calls", 0) + 1
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
                op_type_id=getattr(op, "op_type_id", None),
                op_type_name=getattr(op, "op_type_name", None),
            )
            for op in ops
        ]
        if return_outcome:
            return BuildOutcome(algo_ops)
        return algo_ops

    def _stub_build_freeze_window_seed(_svc, **kwargs):
        captured["build_freeze_window_seed_calls"] = captured.get("build_freeze_window_seed_calls", 0) + 1
        frozen_ids = {
            int(op.id)
            for op in kwargs.get("reschedulable_operations") or []
            if getattr(op, "id", None) and int(getattr(op, "id", 0) or 0) > 0
        }
        return frozen_ids, [], []

    def _unexpected_load_machine_downtimes(*_args, **_kwargs):
        captured["load_machine_downtimes_calls"] = captured.get("load_machine_downtimes_calls", 0) + 1
        raise AssertionError("冻结后全空场景不应继续加载停机区间")

    def _unexpected_build_resource_pool(*_args, **_kwargs):
        captured["build_resource_pool_calls"] = captured.get("build_resource_pool_calls", 0) + 1
        raise AssertionError("冻结后全空场景不应继续构建资源池")

    def _unexpected_extend_downtime_map(*_args, **_kwargs):
        captured["extend_downtime_map_calls"] = captured.get("extend_downtime_map_calls", 0) + 1
        raise AssertionError("冻结后全空场景不应继续扩展停机区间")

    def _unexpected_optimize_schedule(*_args, **_kwargs):
        captured["optimize_schedule_calls"] = captured.get("optimize_schedule_calls", 0) + 1
        raise AssertionError("冻结后全空场景不应调用优化器")

    def _unexpected_persist_schedule(*_args, **_kwargs):
        captured["persist_schedule_calls"] = captured.get("persist_schedule_calls", 0) + 1
        raise AssertionError("冻结后全空场景不应进入持久化")

    schedule_service_mod.build_algo_operations = _stub_build_algo_operations
    schedule_service_mod.build_freeze_window_seed = _stub_build_freeze_window_seed
    schedule_service_mod.load_machine_downtimes = _unexpected_load_machine_downtimes
    schedule_service_mod.build_resource_pool = _unexpected_build_resource_pool
    schedule_service_mod.extend_downtime_map_for_resource_pool = _unexpected_extend_downtime_map
    schedule_service_mod.optimize_schedule = _unexpected_optimize_schedule
    schedule_service_mod.persist_schedule = _unexpected_persist_schedule
    try:
        captured.clear()
        _run_case(
            ScheduleService,
            ValidationError,
            captured=captured,
            simulate=False,
            expected_message="冻结窗口内无可调整工序，本次未执行排产。",
        )

        captured.clear()
        _run_case(
            ScheduleService,
            ValidationError,
            captured=captured,
            simulate=True,
            expected_message="冻结窗口内无可调整工序，本次未执行模拟排产。",
        )
    finally:
        schedule_service_mod.build_algo_operations = original_build_algo_operations
        schedule_service_mod.build_freeze_window_seed = original_build_freeze_window_seed
        schedule_service_mod.load_machine_downtimes = original_load_machine_downtimes
        schedule_service_mod.build_resource_pool = original_build_resource_pool
        schedule_service_mod.extend_downtime_map_for_resource_pool = original_extend_downtime_map
        schedule_service_mod.optimize_schedule = original_optimize_schedule
        schedule_service_mod.persist_schedule = original_persist_schedule


