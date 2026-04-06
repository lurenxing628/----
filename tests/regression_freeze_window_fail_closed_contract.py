from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.freeze_window import build_freeze_window_seed


class _ExplodingScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        raise RuntimeError("boom")


class _StubSvc:
    schedule_repo = _ExplodingScheduleRepo()

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value):
        return value


def _cfg():
    return SimpleNamespace(
        freeze_window_enabled="yes",
        freeze_window_days=2,
        degradation_events=(),
        degradation_counters={},
    )


def _ops():
    return [SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal", op_type_name="工序A")]


def test_freeze_window_strict_mode_fail_closed() -> None:
    meta = {}
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            _StubSvc(),
            cfg=_cfg(),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_ops(),
            reschedulable_operations=_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", f"冻结窗口 strict_mode 未失败关闭：{exc_info.value.field!r}"


def test_freeze_window_relaxed_mode_surfaces_degraded_state() -> None:
    meta = {}
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        _StubSvc(),
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), f"降级后不应保留冻结工序：{frozen_op_ids!r}"
    assert seed_results == [], f"降级后不应保留 seed 结果：{seed_results!r}"
    assert meta.get("freeze_state") == "degraded", f"freeze_state 未标记 degraded：{meta!r}"
    assert meta.get("freeze_applied") is False, f"freeze_applied 异常：{meta!r}"
    assert meta.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], f"冻结退化原因码异常：{meta!r}"
    assert warnings and "读取上一版本排程失败" in warnings[0], f"冻结降级 warning 异常：{warnings!r}"
