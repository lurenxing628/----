from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, List

import pytest

import core.services.scheduler.resource_pool_builder as builder_mod


class _StubSvc:
    conn = object()
    logger = None

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value: Any):
        if isinstance(value, datetime):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")


class _RepoRows:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def list_active_after(self, machine_id: str, _start_str: str):
        if machine_id == "MC_BAD":
            raise RuntimeError("downtime query failed")
        if machine_id == "MC_OK":
            return [
                SimpleNamespace(start_time="2026-01-01 12:00:00", end_time="2026-01-01 13:00:00"),
                SimpleNamespace(start_time="2026-01-01 09:00:00", end_time="2026-01-01 10:00:00"),
                SimpleNamespace(start_time="2026-01-01 11:00:00", end_time="2026-01-01 10:30:00"),
            ]
        return []


class _RepoAlwaysFails:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def list_active_after(self, _machine_id: str, _start_str: str):
        raise RuntimeError("downtime query failed")


def _patch_repo(monkeypatch: pytest.MonkeyPatch, repo_cls) -> None:
    monkeypatch.setattr(builder_mod, "MachineDowntimeRepository", repo_cls)


def test_build_resource_pool_disabled_sets_attempted_false() -> None:
    meta = {}

    resource_pool, warnings = builder_mod.build_resource_pool(
        _StubSvc(),
        cfg=SimpleNamespace(auto_assign_enabled="no"),
        algo_ops=[],
        meta=meta,
    )

    assert resource_pool is None
    assert warnings == []
    assert meta == {
        "resource_pool_attempted": False,
        "resource_pool_build_ok": None,
        "resource_pool_build_error": None,
    }


def test_build_resource_pool_success_filters_active_matching_resources() -> None:
    svc = _StubSvc()
    svc.machine_repo = SimpleNamespace(
        list=lambda status: [
            SimpleNamespace(machine_id="MC_1", op_type_id="OT_A"),
            SimpleNamespace(machine_id="MC_2", op_type_id="OT_B"),
        ]
    )
    svc.operator_repo = SimpleNamespace(
        list=lambda status: [
            SimpleNamespace(operator_id="OP_1"),
        ]
    )
    svc.operator_machine_repo = SimpleNamespace(
        list_simple_rows=lambda: [
            {"operator_id": "OP_1", "machine_id": "MC_1", "is_primary": "yes", "skill_level": "expert"},
            {"operator_id": "OP_2", "machine_id": "MC_1", "is_primary": "yes", "skill_level": "expert"},
            {"operator_id": "OP_1", "machine_id": "MC_2", "is_primary": "yes", "skill_level": "expert"},
        ]
    )
    meta = {}

    resource_pool, warnings = builder_mod.build_resource_pool(
        svc,
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        algo_ops=[SimpleNamespace(source="internal", op_type_id="OT_A")],
        meta=meta,
    )

    assert warnings == []
    assert meta["resource_pool_attempted"] is True
    assert meta["resource_pool_build_ok"] is True
    assert resource_pool["machines_by_op_type"] == {"OT_A": ["MC_1"]}
    assert resource_pool["operators_by_machine"] == {"MC_1": ["OP_1"], "MC_2": ["OP_1"]}
    assert resource_pool["machines_by_operator"] == {"OP_1": ["MC_1", "MC_2"]}


def test_build_resource_pool_failure_sets_public_warning_and_meta() -> None:
    svc = _StubSvc()
    svc.machine_repo = SimpleNamespace(list=lambda status: (_ for _ in ()).throw(RuntimeError("db down")))
    meta = {}

    resource_pool, warnings = builder_mod.build_resource_pool(
        svc,
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        algo_ops=[],
        meta=meta,
    )

    assert resource_pool is None
    assert meta["resource_pool_attempted"] is True
    assert meta["resource_pool_build_ok"] is False
    assert meta["resource_pool_build_error"] == builder_mod.RESOURCE_POOL_BUILD_FAILED_MESSAGE
    assert warnings == ["自动分配资源池构建失败，已降级为不自动分配（请查看日志）。"]


def test_load_machine_downtimes_success_sorts_intervals_and_sets_meta_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.load_machine_downtimes(
        _StubSvc(),
        algo_ops=[
            SimpleNamespace(source="internal", machine_id="MC_OK"),
            SimpleNamespace(source="internal", machine_id="MC_OK"),
            SimpleNamespace(source="external", machine_id="MC_BAD"),
        ],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert warnings == []
    assert meta["downtime_load_ok"] is True
    assert meta["downtime_load_error"] is None
    assert downtime_map == {
        "MC_OK": [
            (datetime(2026, 1, 1, 9, 0, 0), datetime(2026, 1, 1, 10, 0, 0)),
            (datetime(2026, 1, 1, 12, 0, 0), datetime(2026, 1, 1, 13, 0, 0)),
        ]
    }


def test_load_machine_downtimes_no_records_is_ok_without_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.load_machine_downtimes(
        _StubSvc(),
        algo_ops=[SimpleNamespace(source="internal", machine_id="MC_EMPTY")],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert downtime_map == {}
    assert warnings == []
    assert meta["downtime_load_ok"] is True
    assert meta["downtime_load_error"] is None


def test_load_machine_downtimes_partial_failure_preserves_successful_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.load_machine_downtimes(
        _StubSvc(),
        algo_ops=[
            SimpleNamespace(source="internal", machine_id="MC_OK"),
            SimpleNamespace(source="internal", machine_id="MC_BAD"),
        ],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert "MC_OK" in downtime_map
    assert "MC_BAD" not in downtime_map
    assert meta["downtime_load_ok"] is False
    expected_error = "部分设备停机区间加载失败（1 台，如：MC_BAD），这些设备已降级为忽略停机约束"
    assert meta["downtime_load_error"] == expected_error
    assert meta["downtime_partial_fail_count"] == 1
    assert meta["downtime_partial_fail_machines_sample"] == ["MC_BAD"]
    assert warnings == [f"【停机】{expected_error}"]


def test_load_machine_downtimes_all_query_failures_use_partial_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoAlwaysFails)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.load_machine_downtimes(
        _StubSvc(),
        algo_ops=[
            SimpleNamespace(source="internal", machine_id="MC_A"),
            SimpleNamespace(source="internal", machine_id="MC_B"),
        ],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    expected_error = "部分设备停机区间加载失败（2 台，如：MC_A、MC_B），这些设备已降级为忽略停机约束"
    assert downtime_map == {}
    assert meta["downtime_load_ok"] is False
    assert meta["downtime_load_error"] == expected_error
    assert meta["downtime_partial_fail_count"] == 2
    assert meta["downtime_partial_fail_machines_sample"] == ["MC_A", "MC_B"]
    assert warnings == [f"【停机】{expected_error}"]


def test_load_machine_downtimes_repo_failure_sets_public_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenRepo:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("repo init failed")

    _patch_repo(monkeypatch, _BrokenRepo)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.load_machine_downtimes(
        _StubSvc(),
        algo_ops=[SimpleNamespace(source="internal", machine_id="MC_OK")],
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert downtime_map == {}
    assert meta["downtime_load_ok"] is False
    assert meta["downtime_load_error"] == builder_mod.DOWNTIME_LOAD_FAILED_MESSAGE
    assert warnings == [f"【停机】{builder_mod.DOWNTIME_LOAD_FAILED_MESSAGE}"]


def test_extend_downtime_map_disabled_does_not_mark_attempted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {}
    existing = {"MC_OK": [(datetime(2026, 1, 1, 9, 0, 0), datetime(2026, 1, 1, 10, 0, 0))]}

    result = builder_mod.extend_downtime_map_for_resource_pool(
        _StubSvc(),
        cfg=SimpleNamespace(auto_assign_enabled="no"),
        resource_pool={"operators_by_machine": {"MC_EMPTY": ["OP_1"]}},
        downtime_map=existing,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=[],
        meta=meta,
    )

    assert result is existing
    assert meta == {}


def test_extend_downtime_map_candidate_without_records_is_ok_without_empty_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {}
    warnings: List[str] = []

    downtime_map = builder_mod.extend_downtime_map_for_resource_pool(
        _StubSvc(),
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        resource_pool={"operators_by_machine": {"MC_EMPTY": ["OP_1"]}},
        downtime_map={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert downtime_map == {}
    assert warnings == []
    assert meta["downtime_extend_attempted"] is True
    assert meta["downtime_extend_ok"] is True
    assert meta["downtime_extend_error"] is None


def test_extend_downtime_map_partial_failure_preserves_successful_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, _RepoRows)
    meta = {"downtime_load_ok": True, "downtime_load_error": None}
    warnings: List[str] = []

    downtime_map = builder_mod.extend_downtime_map_for_resource_pool(
        _StubSvc(),
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        resource_pool={"operators_by_machine": {"MC_OK": ["OP_1"], "MC_BAD": ["OP_2"]}},
        downtime_map={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert "MC_OK" in downtime_map
    assert "MC_BAD" not in downtime_map
    assert meta["downtime_extend_ok"] is False
    assert meta["downtime_extend_partial_fail_count"] == 1
    assert meta["downtime_extend_partial_fail_machines_sample"] == ["MC_BAD"]
    assert any("MC_BAD" in item for item in warnings)


def test_extend_downtime_map_repo_failure_preserves_existing_map_and_sets_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenRepo:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("repo init failed")

    _patch_repo(monkeypatch, _BrokenRepo)
    existing = {
        "MC_EXISTING": [
            (datetime(2026, 1, 1, 9, 0, 0), datetime(2026, 1, 1, 10, 0, 0)),
        ]
    }
    expected = {"MC_EXISTING": list(existing["MC_EXISTING"])}
    meta = {}
    warnings: List[str] = []

    result = builder_mod.extend_downtime_map_for_resource_pool(
        _StubSvc(),
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        resource_pool={"operators_by_machine": {"MC_NEW": ["OP_1"]}},
        downtime_map=existing,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        warnings=warnings,
        meta=meta,
    )

    assert result is existing
    assert result == expected
    assert meta["downtime_extend_attempted"] is True
    assert meta["downtime_extend_ok"] is False
    assert meta["downtime_extend_error"] == builder_mod.DOWNTIME_EXTEND_FAILED_MESSAGE
    assert warnings == [f"【停机】{builder_mod.DOWNTIME_EXTEND_FAILED_MESSAGE}"]
