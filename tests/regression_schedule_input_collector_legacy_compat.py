from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.schedule_input_collector import collect_schedule_run_input

# 说明：本文件保留原命名以延续审查上下文，
# 但当前约束已经从“legacy compat”收紧为“legacy signature 必须显式拒绝”。


class _FakeSvc:
    conn = None
    logger = None
    op_logger = None

    def __init__(self, ops):
        self.history_repo = SimpleNamespace(get_latest_version=lambda: 5)
        self.op_repo = SimpleNamespace(list_by_batch=lambda _batch_id: list(ops))

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
