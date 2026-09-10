"""合同测试：freeze_state=disabled 时 freeze_disabled_reason 必须非空（audit 2026-07-20 A15）。

此前唯一一条断档路径：冻结窗开启、上一版窗内有行、但命中工序 seq 全部 <=0
（freeze_window_prefixes.max_seq_by_batch 跳过 seq<=0），_apply_freeze_prefixes
返回空集且不置 degraded，收尾直接置 disabled 却不补 reason——与"没开冻结"在
诊断字段上难以区分。本文件锁两件事：
1. 全 seq<=0 场景落 disabled 且 reason=no_freezable_prefix（strict/relaxed 一致，静默不告警）；
2. 枚举全部 6 条 disabled 终态路径，逐条断言 reason 非空且取值符合口径。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, List

import pytest

from core.services.scheduler.freeze_window import build_freeze_window_seed


class _RowsScheduleRepo:
    def __init__(self, rows: List[dict]):
        self._rows = rows

    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return list(self._rows)


class _StubSvc:
    def __init__(self, rows: List[dict]):
        self.schedule_repo = _RowsScheduleRepo(rows)

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value):
        return value


def _cfg(*, enabled: str = "yes", days: int = 2, degradation_events=()) -> SimpleNamespace:
    return SimpleNamespace(
        freeze_window_enabled=enabled,
        freeze_window_days=days,
        degradation_events=degradation_events,
        degradation_counters={},
    )


def _op(op_id: int, *, seq: int, batch_id: str = "B001") -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        op_code=f"{batch_id}_{op_id:02d}",
        batch_id=batch_id,
        seq=seq,
        source="internal",
        op_type_name="A",
    )


def _row(op_id: int) -> dict:
    return {
        "op_id": op_id,
        "machine_id": "MC001",
        "operator_id": "OP001",
        "start_time": datetime(2026, 4, 1, 8, 0, 0),
        "end_time": datetime(2026, 4, 1, 10, 0, 0),
    }


def _build(
    *,
    cfg: SimpleNamespace,
    prev_version: int,
    operations: List[Any],
    rows: List[dict],
    strict_mode: bool = False,
):
    meta: dict = {}
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        _StubSvc(rows),
        cfg=cfg,
        prev_version=prev_version,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=operations,
        strict_mode=strict_mode,
        meta=meta,
    )
    return frozen_op_ids, seed_results, warnings, meta


@pytest.mark.parametrize("strict_mode", [False, True])
def test_all_rows_seq_non_positive_disabled_with_no_freezable_prefix_reason(strict_mode: bool) -> None:
    """上一版窗内有行但命中工序 seq 全 <=0：disabled 必须带 no_freezable_prefix 原因。"""
    frozen_op_ids, seed_results, warnings, meta = _build(
        cfg=_cfg(),
        prev_version=3,
        operations=[_op(1, seq=0), _op(2, seq=0)],
        rows=[_row(1), _row(2)],
        strict_mode=strict_mode,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_freezable_prefix", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_application_status") is None, meta
    assert list(meta.get("freeze_degradation_codes") or []) == [], meta
    # 与"没开冻结"可区分：配置回显仍为开启态。
    assert meta.get("freeze_enabled") is True, meta
    assert int(meta.get("freeze_days") or 0) == 2, meta


def test_negative_seq_rows_also_fall_into_no_freezable_prefix() -> None:
    frozen_op_ids, _seed_results, _warnings, meta = _build(
        cfg=_cfg(),
        prev_version=3,
        operations=[_op(1, seq=-5)],
        rows=[_row(1)],
    )
    assert frozen_op_ids == set()
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_freezable_prefix", meta


def _disabled_scenarios():
    return [
        pytest.param(
            dict(cfg=_cfg(enabled="no"), prev_version=3, operations=[_op(1, seq=10)], rows=[_row(1)]),
            "config_disabled",
            id="config_disabled",
        ),
        pytest.param(
            dict(cfg=_cfg(days=0), prev_version=3, operations=[_op(1, seq=10)], rows=[_row(1)]),
            "no_days",
            id="no_days",
        ),
        pytest.param(
            dict(cfg=_cfg(), prev_version=0, operations=[_op(1, seq=10)], rows=[_row(1)]),
            "no_previous_version",
            id="no_previous_version",
        ),
        pytest.param(
            dict(cfg=_cfg(), prev_version=3, operations=[], rows=[_row(1)]),
            "no_reschedulable_operations",
            id="no_reschedulable_operations",
        ),
        pytest.param(
            dict(cfg=_cfg(), prev_version=3, operations=[_op(1, seq=10)], rows=[]),
            "no_previous_schedule_rows",
            id="no_previous_schedule_rows",
        ),
        pytest.param(
            dict(cfg=_cfg(), prev_version=3, operations=[_op(1, seq=0)], rows=[_row(1)]),
            "no_freezable_prefix",
            id="no_freezable_prefix",
        ),
    ]


@pytest.mark.parametrize("build_kwargs, expected_reason", _disabled_scenarios())
def test_every_disabled_path_carries_non_empty_reason(build_kwargs: dict, expected_reason: str) -> None:
    """口径不变量：freeze_state=disabled ⇒ freeze_disabled_reason 非空，且取值符合各路径口径。"""
    frozen_op_ids, seed_results, _warnings, meta = _build(**build_kwargs)

    assert frozen_op_ids == set(), (expected_reason, frozen_op_ids)
    assert seed_results == [], (expected_reason, seed_results)
    assert meta.get("freeze_state") == "disabled", (expected_reason, meta)
    reason = meta.get("freeze_disabled_reason")
    assert isinstance(reason, str) and reason.strip(), (expected_reason, meta)
    assert reason == expected_reason, (expected_reason, meta)
