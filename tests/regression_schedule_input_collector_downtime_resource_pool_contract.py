from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from types import SimpleNamespace

from core.models.enums import SourceType
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.resource_pool_builder import (
    build_resource_pool,
    extend_downtime_map_for_resource_pool,
    load_machine_downtimes,
)
from core.services.scheduler.schedule_input_collector import collect_schedule_run_input
from core.services.scheduler.schedule_service import ScheduleService


def _load_schema(conn: sqlite3.Connection) -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()


def _insert_fixture(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('P001', '测试零件')")
    conn.execute("INSERT INTO OpTypes(op_type_id, name, category) VALUES ('OT_A', '工序A', 'internal')")
    conn.executemany(
        "INSERT INTO Machines(machine_id, name, op_type_id, status) VALUES (?, ?, ?, 'active')",
        [("MC_FIXED", "固定设备", "OT_A"), ("MC_POOL", "候选设备", "OT_A")],
    )
    conn.execute("INSERT INTO Operators(operator_id, name, status) VALUES ('OP_FIXED', '固定人员', 'active')")
    conn.execute("INSERT INTO Operators(operator_id, name, status) VALUES ('OP_POOL', '候选人员', 'active')")
    conn.execute(
        "INSERT INTO OperatorMachine(operator_id, machine_id, skill_level, is_primary) VALUES ('OP_POOL', 'MC_POOL', 'expert', 'yes')"
    )
    conn.execute("INSERT INTO Batches(batch_id, part_no, quantity, ready_status, status) VALUES ('B001', 'P001', 1, 'yes', 'pending')")
    conn.execute(
        """
        INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, setup_hours, unit_hours, status)
        VALUES ('B001_10', 'B001', 10, 'OT_A', '工序A', 'internal', 'MC_FIXED', 'OP_FIXED', 1, 0, 'pending')
        """
    )
    conn.executemany(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES (?, ?, ?, 'active')
        """,
        [
            ("MC_FIXED", "2026-01-01 09:00:00", "2026-01-01 10:00:00"),
            ("MC_POOL", "2026-01-01 11:00:00", "2026-01-01 12:00:00"),
        ],
    )
    conn.commit()


def _build_algo_operations(_svc, ops, *, strict_mode: bool, return_outcome: bool):
    assert strict_mode is False
    assert return_outcome is True
    return BuildOutcome(
        value=[
            SimpleNamespace(
                id=int(op.id),
                op_code=str(op.op_code),
                batch_id=str(op.batch_id),
                seq=int(op.seq),
                source=SourceType.INTERNAL.value,
                machine_id=str(op.machine_id or ""),
                operator_id=str(op.operator_id or ""),
                supplier_id=None,
                setup_hours=float(op.setup_hours or 0),
                unit_hours=float(op.unit_hours or 0),
                op_type_id=str(op.op_type_id or ""),
                op_type_name=str(op.op_type_name or ""),
            )
            for op in ops
        ]
    )


def test_collector_extends_downtime_map_for_resource_pool_candidates() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _load_schema(conn)
    _insert_fixture(conn)
    svc = ScheduleService(conn)

    try:
        collected = collect_schedule_run_input(
            svc,
            batch_ids=["B001"],
            start_dt="2026-01-01 08:00:00",
            enforce_ready=False,
            strict_mode=False,
            calendar_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            config_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            get_snapshot_with_strict_mode=lambda _cfg_svc, strict_mode: SimpleNamespace(
                enforce_ready_default="no",
                auto_assign_enabled="yes",
                freeze_window_enabled="no",
                freeze_window_days=0,
            ),
            build_algo_operations_fn=_build_algo_operations,
            build_freeze_window_seed_fn=lambda _svc, **_kwargs: (set(), [], []),
            load_machine_downtimes_fn=load_machine_downtimes,
            build_resource_pool_fn=build_resource_pool,
            extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
        )
    finally:
        conn.close()

    assert sorted(collected.downtime_map) == ["MC_FIXED", "MC_POOL"]
    assert collected.downtime_map["MC_FIXED"] == [(datetime(2026, 1, 1, 9, 0, 0), datetime(2026, 1, 1, 10, 0, 0))]
    assert collected.downtime_map["MC_POOL"] == [(datetime(2026, 1, 1, 11, 0, 0), datetime(2026, 1, 1, 12, 0, 0))]
    assert collected.downtime_meta["downtime_load_ok"] is True
    assert collected.downtime_meta["downtime_extend_attempted"] is True
    assert collected.downtime_meta["downtime_extend_ok"] is True
