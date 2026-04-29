from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.freeze_window import build_freeze_window_seed


class _ExplodingScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        raise RuntimeError("boom")


class _CountingExplodingScheduleRepo:
    def __init__(self) -> None:
        self.calls = 0

    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        self.calls += 1
        raise RuntimeError("boom")


class _SuccessfulScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {
                "op_id": 1,
                "machine_id": "MC001",
                "operator_id": "OP001",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 10, 0, 0),
            },
        ]


class _RecordingScheduleRepo:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        self.calls.append(kwargs)
        return list(self.rows)


class _MalformedScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {"op_id": "bad", "start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 10:00:00"},
        ]


class _EmptyScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return []


class _PartiallyInvalidScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {"op_id": 1, "start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 10:00:00"},
            {"op_id": 2, "start_time": "2026-04-01 11:00:00", "end_time": "2026-04-01 10:00:00"},
        ]


class _DuplicateScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {
                "op_id": 1,
                "machine_id": "MC_A",
                "operator_id": "OP_A",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 10, 0, 0),
            },
            {
                "op_id": 1,
                "machine_id": "MC_B",
                "operator_id": "OP_B",
                "start_time": datetime(2026, 4, 1, 11, 0, 0),
                "end_time": datetime(2026, 4, 1, 12, 0, 0),
            },
        ]


class _PartialMissingPrefixScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {"op_id": 2, "start_time": "2026-04-01 09:00:00", "end_time": "2026-04-01 10:00:00"},
            {"op_id": 3, "start_time": "2026-04-01 11:00:00", "end_time": "2026-04-01 12:00:00"},
        ]


class _AllMissingPrefixScheduleRepo:
    def list_version_rows_by_op_ids_start_range(self, **kwargs):
        return [
            {"op_id": 2, "start_time": "2026-04-01 11:00:00", "end_time": "2026-04-01 12:00:00"},
        ]


class _StubSvc:
    schedule_repo: Any = _ExplodingScheduleRepo()

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value):
        return value


def _cfg(*, enabled="yes", days=2, degradation_events=()):
    return SimpleNamespace(
        freeze_window_enabled=enabled,
        freeze_window_days=days,
        degradation_events=degradation_events,
        degradation_counters={},
    )


def _ops():
    return [SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal", op_type_name="A")]


def _mixed_ops():
    return [
        SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal", op_type_name="A"),
        SimpleNamespace(id=2, op_code="B002_10", batch_id="B002", seq=10, source="internal", op_type_name="A"),
    ]


def _prefix_ops():
    return [
        SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal", op_type_name="A"),
        SimpleNamespace(id=2, op_code="B001_20", batch_id="B001", seq=20, source="internal", op_type_name="A"),
        SimpleNamespace(id=3, op_code="B002_10", batch_id="B002", seq=10, source="internal", op_type_name="A"),
    ]


def test_freeze_window_seed_uses_operations_when_reschedulable_operations_is_none() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _RecordingScheduleRepo(
        [
            {
                "op_id": 1,
                "machine_id": "MC001",
                "operator_id": "OP001",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 10, 0, 0),
            }
        ]
    )
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=None,
        strict_mode=False,
        meta=meta,
    )

    assert repo.calls[0]["op_ids"] == [1], repo.calls
    assert frozen_op_ids == {1}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [1], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "active", meta
    assert meta.get("freeze_application_status") == "applied", meta


def test_freeze_window_seed_limits_frozen_results_to_explicit_reschedulable_subset() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _RecordingScheduleRepo(
        [
            {
                "op_id": 1,
                "machine_id": "MC001",
                "operator_id": "OP001",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 10, 0, 0),
            },
            {
                "op_id": 3,
                "machine_id": "MC003",
                "operator_id": "OP003",
                "start_time": datetime(2026, 4, 1, 11, 0, 0),
                "end_time": datetime(2026, 4, 1, 12, 0, 0),
            },
        ]
    )
    svc.schedule_repo = repo
    subset = [_prefix_ops()[2]]
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_prefix_ops(),
        reschedulable_operations=subset,
        strict_mode=False,
        meta=meta,
    )

    assert repo.calls[0]["op_ids"] == [3], repo.calls
    assert frozen_op_ids == {3}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [3], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "active", meta


def test_freeze_window_seed_results_keep_fields_and_sort_by_start_time_then_op_id() -> None:
    meta = {}
    svc = _StubSvc()
    operations = [
        SimpleNamespace(id=30, op_code="B009_30", batch_id="B009", seq=30, source="internal", op_type_name="C"),
        SimpleNamespace(id=20, op_code="B009_20", batch_id="B009", seq=20, source="internal", op_type_name="B"),
        SimpleNamespace(id=10, op_code="B009_10", batch_id="B009", seq=10, source="internal", op_type_name="A"),
    ]
    repo = _RecordingScheduleRepo(
        [
            {
                "op_id": 30,
                "machine_id": "MC030",
                "operator_id": "OP030",
                "start_time": datetime(2026, 4, 1, 9, 0, 0),
                "end_time": datetime(2026, 4, 1, 10, 0, 0),
            },
            {
                "op_id": 20,
                "machine_id": "MC020",
                "operator_id": "OP020",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 9, 0, 0),
            },
            {
                "op_id": 10,
                "machine_id": "MC010",
                "operator_id": "OP010",
                "start_time": datetime(2026, 4, 1, 8, 0, 0),
                "end_time": datetime(2026, 4, 1, 8, 30, 0),
            },
        ]
    )
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=operations,
        reschedulable_operations=operations,
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == {10, 20, 30}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [10, 20, 30], seed_results
    assert warnings == [], warnings
    assert seed_results[0] == {
        "op_id": 10,
        "op_code": "B009_10",
        "batch_id": "B009",
        "seq": 10,
        "machine_id": "MC010",
        "operator_id": "OP010",
        "start_time": datetime(2026, 4, 1, 8, 0, 0),
        "end_time": datetime(2026, 4, 1, 8, 30, 0),
        "source": "internal",
        "op_type_name": "A",
    }
    assert seed_results[1]["start_time"] == datetime(2026, 4, 1, 8, 0, 0), seed_results
    assert seed_results[1]["op_id"] == 20, seed_results
    assert seed_results[2]["start_time"] == datetime(2026, 4, 1, 9, 0, 0), seed_results


def test_freeze_window_disabled_by_config_never_reads_previous_schedule() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _CountingExplodingScheduleRepo()
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(enabled="no", days=2),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=True,
        meta=meta,
    )

    assert repo.calls == 0
    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "config_disabled", meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_zero_days_is_disabled_without_warning() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _CountingExplodingScheduleRepo()
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(days=0),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=True,
        meta=meta,
    )

    assert repo.calls == 0
    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_days", meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_without_prev_version_is_disabled_without_warning() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _CountingExplodingScheduleRepo()
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=0,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=True,
        meta=meta,
    )

    assert repo.calls == 0
    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_previous_version", meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_without_reschedulable_operations_is_disabled_without_warning() -> None:
    meta = {}
    svc = _StubSvc()
    repo = _CountingExplodingScheduleRepo()
    svc.schedule_repo = repo
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=[],
        strict_mode=True,
        meta=meta,
    )

    assert repo.calls == 0
    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_reschedulable_operations", meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_successful_seed_sets_active_applied_status() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _SuccessfulScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == {1}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [1], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "active", meta
    assert meta.get("freeze_applied") is True, meta
    assert meta.get("freeze_application_status") == "applied", meta
    assert meta.get("freeze_disabled_reason") is None, meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_enabled_config_degraded_relaxed_mode_surfaces_unapplied_status() -> None:
    meta = {}
    events = ({"code": "invalid_choice", "field": "freeze_window_enabled", "message": "bad enabled", "count": 1},)
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        _StubSvc(),
        cfg=_cfg(enabled="no", days=2, degradation_events=events),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_disabled_reason") == "config_degraded", meta
    assert meta.get("freeze_application_status") == "unapplied", meta
    assert meta.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], meta
    assert warnings, warnings


def test_freeze_window_days_config_degraded_strict_mode_fail_closed() -> None:
    meta = {}
    events = ({"code": "freeze_seed_unavailable", "field": "freeze_window_days", "message": "bad days", "count": 1},)
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            _StubSvc(),
            cfg=_cfg(days=0, degradation_events=events),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_ops(),
            reschedulable_operations=_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", exc_info.value.field
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_disabled_reason") == "config_degraded", meta


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

    assert exc_info.value.field == "freeze_window", exc_info.value.field


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

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_application_status") == "unapplied", meta
    assert meta.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], meta
    assert warnings, warnings


def test_freeze_window_invalid_previous_rows_strict_mode_fail_closed() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _MalformedScheduleRepo()
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            svc,
            cfg=_cfg(),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_ops(),
            reschedulable_operations=_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", exc_info.value.field


def test_freeze_window_invalid_previous_rows_relaxed_mode_surfaces_degradation() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _MalformedScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_application_status") == "unapplied", meta
    assert meta.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], meta
    assert warnings, warnings


def test_freeze_window_duplicate_previous_rows_strict_mode_fail_closed() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _DuplicateScheduleRepo()
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            svc,
            cfg=_cfg(),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_ops(),
            reschedulable_operations=_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", exc_info.value.field
    assert meta.get("freeze_state") == "degraded", meta


def test_freeze_window_duplicate_previous_rows_relaxed_mode_does_not_pick_one() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _DuplicateScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_application_status") == "unapplied", meta
    assert warnings, warnings


def test_freeze_window_no_previous_rows_is_not_degraded() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _EmptyScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_previous_schedule_rows", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_no_previous_rows_strict_mode_is_disabled_without_warning() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _EmptyScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_ops(),
        reschedulable_operations=_ops(),
        strict_mode=True,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert warnings == [], warnings
    assert meta.get("freeze_state") == "disabled", meta
    assert meta.get("freeze_disabled_reason") == "no_previous_schedule_rows", meta
    assert meta.get("freeze_degradation_codes") == [], meta


def test_freeze_window_missing_prefix_strict_mode_fail_closed() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _PartialMissingPrefixScheduleRepo()
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            svc,
            cfg=_cfg(),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_prefix_ops(),
            reschedulable_operations=_prefix_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", exc_info.value.field
    assert meta.get("freeze_state") == "degraded", meta


def test_freeze_window_invalid_time_range_strict_mode_fail_closed() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _PartiallyInvalidScheduleRepo()
    with pytest.raises(ValidationError) as exc_info:
        build_freeze_window_seed(
            svc,
            cfg=_cfg(),
            prev_version=1,
            start_dt=datetime(2026, 4, 1, 8, 0, 0),
            operations=_mixed_ops(),
            reschedulable_operations=_mixed_ops(),
            strict_mode=True,
            meta=meta,
        )

    assert exc_info.value.field == "freeze_window", exc_info.value.field
    assert meta.get("freeze_state") == "degraded", meta


def test_freeze_window_relaxed_mode_preserves_applied_bit_under_partial_degradation() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _PartiallyInvalidScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_mixed_ops(),
        reschedulable_operations=_mixed_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == {1}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [1], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is True, meta
    assert meta.get("freeze_application_status") == "partially_applied", meta
    assert "未应用冻结窗口种子" not in str(meta.get("freeze_degradation_reason") or ""), meta
    assert meta.get("freeze_degradation_codes") == ["freeze_seed_unavailable"], meta
    assert warnings, warnings


def test_freeze_window_partial_missing_prefix_surfaces_partial_application_status() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _PartialMissingPrefixScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_prefix_ops(),
        reschedulable_operations=_prefix_ops(),
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == {3}, frozen_op_ids
    assert [item.get("op_id") for item in seed_results] == [3], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is True, meta
    assert meta.get("freeze_application_status") == "partially_applied", meta
    assert "未应用冻结窗口种子" not in str(meta.get("freeze_degradation_reason") or ""), meta
    assert warnings, warnings


def test_freeze_window_all_missing_prefix_surfaces_unapplied_status() -> None:
    meta = {}
    svc = _StubSvc()
    svc.schedule_repo = _AllMissingPrefixScheduleRepo()
    frozen_op_ids, seed_results, warnings = build_freeze_window_seed(
        svc,
        cfg=_cfg(),
        prev_version=1,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        operations=_prefix_ops()[:2],
        reschedulable_operations=_prefix_ops()[:2],
        strict_mode=False,
        meta=meta,
    )

    assert frozen_op_ids == set(), frozen_op_ids
    assert seed_results == [], seed_results
    assert meta.get("freeze_state") == "degraded", meta
    assert meta.get("freeze_applied") is False, meta
    assert meta.get("freeze_application_status") == "unapplied", meta
    assert "未应用冻结窗口种子" in str(meta.get("freeze_degradation_reason") or ""), meta
    assert warnings, warnings
