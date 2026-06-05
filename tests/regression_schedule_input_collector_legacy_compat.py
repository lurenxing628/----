"""回归测试：collect_schedule_run_input 强制拒绝旧式注入签名——build_algo_operations_fn/build_freeze_window_seed_fn 的 legacy 签名须抛 TypeError，未返回 BuildOutcome 也须 TypeError；空算法输入须在读冻结窗口/停机/资源池之前就以 ValidationError 暴露（reason=algo_builder_filtered_all），不得被误标成冻结窗口问题。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.schedule_input_collector import collect_schedule_run_input

# 说明：本文件保留原命名以延续审查上下文，
# 但当前约束已经从“legacy compat”收紧为“legacy signature 必须显式拒绝”。

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeSvc:
    logger = None
    op_logger = None

    def __init__(self, ops):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
        part_rows = {}
        machine_ids = set()
        operator_ids = set()
        supplier_ids = set()
        for op in ops:
            batch_id = str(op.batch_id)
            part_no = "PART-" + batch_id
            part_rows[batch_id] = part_no
            if op.machine_id:
                machine_ids.add(str(op.machine_id))
            if op.operator_id:
                operator_ids.add(str(op.operator_id))
            if op.supplier_id:
                supplier_ids.add(str(op.supplier_id))
        for part_no in sorted(set(part_rows.values())):
            self.conn.execute(
                "INSERT OR IGNORE INTO Parts(part_no, part_name) VALUES (?, ?)",
                (part_no, part_no),
            )
        for batch_id, part_no in sorted(part_rows.items()):
            self.conn.execute(
                """
                INSERT OR IGNORE INTO Batches(
                    batch_id, part_no, part_name, quantity, due_date,
                    priority, ready_status, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (batch_id, part_no, part_no, 1, "2026-01-10", "normal", "yes", "pending"),
            )
        for machine_id in sorted(machine_ids):
            self.conn.execute(
                "INSERT OR IGNORE INTO Machines(machine_id, name, status) VALUES (?, ?, ?)",
                (machine_id, machine_id, "active"),
            )
        for operator_id in sorted(operator_ids):
            self.conn.execute(
                "INSERT OR IGNORE INTO Operators(operator_id, name, status) VALUES (?, ?, ?)",
                (operator_id, operator_id, "active"),
            )
        for supplier_id in sorted(supplier_ids):
            self.conn.execute(
                "INSERT OR IGNORE INTO Suppliers(supplier_id, name, status) VALUES (?, ?, ?)",
                (supplier_id, supplier_id, "active"),
            )
        for op in ops:
            self.conn.execute(
                """
                INSERT INTO BatchOperations(
                    id, op_code, batch_id, seq, source,
                    machine_id, operator_id, supplier_id,
                    setup_hours, unit_hours, ext_days, status, op_type_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(op.id),
                    str(op.op_code),
                    str(op.batch_id),
                    int(op.seq),
                    str(op.source),
                    op.machine_id,
                    op.operator_id,
                    op.supplier_id,
                    float(op.setup_hours or 0),
                    float(op.unit_hours or 0),
                    op.ext_days,
                    str(op.status),
                    str(op.op_type_name),
                ),
            )
        self.conn.commit()
        self.history_repo = SimpleNamespace(get_latest_version=lambda: 5)
        self.op_repo = SimpleNamespace(list_by_batch=lambda _batch_id: list(ops))
        self.schedule_repo = SimpleNamespace(list_by_version_with_details=lambda _version: [])

    def _normalize_text(self, value):
        return None if value is None else str(value).strip()

    def _normalize_datetime(self, value):
        if isinstance(value, datetime):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")

    def _get_batch_or_raise(self, batch_id):
        return SimpleNamespace(batch_id=batch_id, status="pending", ready_status="yes")

    def _is_reschedulable_operation(self, op):
        return str(getattr(op, "status", "") or "").strip().lower() not in {"completed", "skipped"}


def _build_ops():
    return [
        SimpleNamespace(
            id=1,
            op_code="B001_10",
            batch_id="B001",
            seq=10,
            source="internal",
            machine_id="M1",
            operator_id="O1",
            supplier_id=None,
            setup_hours=1.0,
            unit_hours=0.0,
            ext_days=None,
            status="pending",
            op_type_name="工序A",
        )
    ]


def _strict_build_algo_operations(_svc, ops, *, strict_mode: bool, return_outcome: bool):
    assert isinstance(strict_mode, bool)
    assert return_outcome is True
    return BuildOutcome(
        value=[
            SimpleNamespace(
                id=int(op.id),
                op_code=op.op_code,
                batch_id=op.batch_id,
                seq=int(op.seq or 0),
                source=op.source,
                machine_id=op.machine_id,
                operator_id=op.operator_id,
                supplier_id=op.supplier_id,
            )
            for op in ops
        ]
    )


def test_collect_schedule_run_input_rejects_legacy_build_algo_operations_signature() -> None:
    svc = _FakeSvc(_build_ops())

    def _legacy_build_algo_operations(_svc, ops):
        return list(ops)

    with pytest.raises(TypeError, match=r"build_algo_operations_fn"):
        collect_schedule_run_input(
            svc,
            batch_ids=["B001"],
            start_dt="2026-01-01 08:00:00",
            enforce_ready=False,
            strict_mode=True,
            calendar_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            config_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            get_snapshot_with_strict_mode=lambda _cfg_svc, strict_mode: SimpleNamespace(enforce_ready_default="no"),
            build_algo_operations_fn=_legacy_build_algo_operations,
            build_freeze_window_seed_fn=lambda _svc, **kwargs: (set(), [], []),
            load_machine_downtimes_fn=lambda *_args, **_kwargs: {},
            build_resource_pool_fn=lambda *_args, **_kwargs: ({}, []),
            extend_downtime_map_for_resource_pool_fn=lambda _svc, **kwargs: kwargs.get("downtime_map") or {},
        )


def test_collect_schedule_run_input_requires_build_outcome_when_return_outcome_requested() -> None:
    svc = _FakeSvc(_build_ops())

    with pytest.raises(TypeError, match=r"BuildOutcome"):
        collect_schedule_run_input(
            svc,
            batch_ids=["B001"],
            start_dt="2026-01-01 08:00:00",
            enforce_ready=False,
            strict_mode=True,
            calendar_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            config_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            get_snapshot_with_strict_mode=lambda _cfg_svc, strict_mode: SimpleNamespace(enforce_ready_default="no"),
            build_algo_operations_fn=lambda _svc, ops, *, strict_mode, return_outcome: list(ops),
            build_freeze_window_seed_fn=lambda _svc, **kwargs: (set(), [], []),
            load_machine_downtimes_fn=lambda *_args, **_kwargs: {},
            build_resource_pool_fn=lambda *_args, **_kwargs: ({}, []),
            extend_downtime_map_for_resource_pool_fn=lambda _svc, **kwargs: kwargs.get("downtime_map") or {},
        )


def test_collect_schedule_run_input_rejects_legacy_freeze_window_signature() -> None:
    svc = _FakeSvc(_build_ops())

    def _legacy_build_freeze_window_seed(_svc, cfg):
        return set(), [], []

    with pytest.raises(TypeError, match=r"build_freeze_window_seed_fn"):
        collect_schedule_run_input(
            svc,
            batch_ids=["B001"],
            start_dt="2026-01-01 08:00:00",
            enforce_ready=False,
            strict_mode=True,
            calendar_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            config_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            get_snapshot_with_strict_mode=lambda _cfg_svc, strict_mode: SimpleNamespace(enforce_ready_default="no"),
            build_algo_operations_fn=_strict_build_algo_operations,
            build_freeze_window_seed_fn=_legacy_build_freeze_window_seed,
            load_machine_downtimes_fn=lambda *_args, **_kwargs: {},
            build_resource_pool_fn=lambda *_args, **_kwargs: ({}, []),
            extend_downtime_map_for_resource_pool_fn=lambda _svc, **kwargs: kwargs.get("downtime_map") or {},
        )


def test_collect_schedule_run_input_rejects_empty_algo_input_without_freeze_mislabel() -> None:
    svc = _FakeSvc(_build_ops())

    with pytest.raises(ValidationError) as exc_info:
        collect_schedule_run_input(
            svc,
            batch_ids=["B001"],
            start_dt="2026-01-01 08:00:00",
            enforce_ready=False,
            strict_mode=False,
            calendar_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            config_service_cls=lambda *args, **kwargs: SimpleNamespace(),
            get_snapshot_with_strict_mode=lambda _cfg_svc, strict_mode: SimpleNamespace(enforce_ready_default="no"),
            build_algo_operations_fn=lambda _svc, ops, **kwargs: BuildOutcome(value=[], empty_reason="algo_builder_filtered_all"),
            build_freeze_window_seed_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("空算法输入不应继续读取冻结窗口")),
            load_machine_downtimes_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("空算法输入不应继续加载停机数据")),
            build_resource_pool_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("空算法输入不应继续构建资源池")),
            extend_downtime_map_for_resource_pool_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("空算法输入不应继续扩展停机数据")),
        )

    message = getattr(exc_info.value, "message", str(exc_info.value))
    details = getattr(exc_info.value, "details", None) or {}
    assert "未生成可用于排产的工序输入" in message
    assert details.get("reason") == "algo_builder_filtered_all"
