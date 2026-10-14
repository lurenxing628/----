"""正式方案与候选方案分别从正确数据源计算关键链。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, List
from unittest.mock import Mock

from core.services.scheduler.gantt.critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE


class _DummyCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _DummyConn:
    def __init__(self, db_file: str = ":memory:"):
        self._db_file = db_file

    def execute(self, sql: str, params=()):
        text = str(sql or "").strip().lower()
        if "pragma database_list" in text:
            return _DummyCursor([(0, "main", self._db_file)])
        raise RuntimeError(f"unexpected sql in test: {sql!r}")


class _DummyScheduleRepo:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def list_by_version_with_details(self, version: int):
        self.calls.append(int(version))
        return [dict(row) for row in self.rows]


def _detail_rows():
    return [
        {"op_code": "A", "machine_id": "M1", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
        {"op_code": "B", "machine_id": "M1", "start_time": "2026-05-01 09:00", "end_time": "2026-05-01 10:00"},
    ]


class _PlanQueryProbe:
    def __init__(
        self,
        rows_by_role: Dict[str, List[Dict[str, Any]]] = None,
        rows_by_resolution: Dict[tuple, List[Dict[str, Any]]] = None,
    ):
        self.rows_by_role = rows_by_role or {}
        self.rows_by_resolution = rows_by_resolution or {}
        self.calls: List[Dict[str, Any]] = []

    def list_plan_detail_rows_all(self, *, version: int, role):
        self.calls.append({"version": int(version), "role": role})
        return list(self.rows_by_role.get(str(role or ""), []))

    def list_plan_detail_rows_all_for_resolution(self, *, version: int, source_table: str, candidate_id,
                                               effective_plan_role=None, plan_ref=None):
        self.calls.append(
            {
                "version": int(version),
                "source_table": source_table,
                "candidate_id": candidate_id,
                "effective_plan_role": effective_plan_role,
                "plan_ref": plan_ref,
            }
        )
        return list(self.rows_by_resolution.get((source_table, candidate_id), []))


def _reset_provider_cache(monkeypatch) -> None:
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", OrderedDict())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", 8)
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_EPOCH", 0)


def _plan_resolution(role: str, *, candidate_id=None, source_table: str = SOURCE_SCHEDULE) -> Dict[str, Any]:
    return {
        "requested_role": role,
        "selected_role": role,
        "source_table": source_table,
        "candidate_id": candidate_id,
        "candidate_key": None,
        "status": "resolved_adopted" if role == ROLE_ADOPTED else "resolved_comparison",
        "message": "",
    }


def test_adopted_critical_chain_uses_schedule_repo(monkeypatch) -> None:
    import core.services.scheduler.gantt.critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute = Mock(wraps=provider_module.compute_critical_chain)
    monkeypatch.setattr(provider_module, "compute_critical_chain", compute)
    plan_query = _PlanQueryProbe()
    schedule_repo = _DummyScheduleRepo(_detail_rows())
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=schedule_repo, plan_query_service=plan_query)
    plan = _plan_resolution(ROLE_ADOPTED)

    result = provider.get_critical_chain(7, plan_resolution=plan)

    assert result["ids"] == ["A", "B"]
    assert result["available"] is True
    assert result["reason"] == ""
    assert result["cache_hit"] is False
    assert schedule_repo.calls == [7]
    assert compute.call_count == 1
    snapshot, version = compute.call_args[0]
    assert version == 7
    assigned_rows = snapshot.list_by_version_with_details(version)
    assert [{key: value for key, value in row.items() if key != "task_id"} for row in assigned_rows] == schedule_repo.rows
    assert all(row["task_id"].startswith("task_") and "_v7_adopted_r" in row["task_id"] for row in assigned_rows)
    assert provider.get_critical_chain(7, plan_resolution=plan)["cache_hit"] is True
    assert schedule_repo.calls == [7, 7]
    assert compute.call_count == 1

    schedule_repo.rows[1]["machine_id"] = "M2"
    changed = provider.get_critical_chain(7, plan_resolution=plan)
    assert changed["ids"] == ["B"]
    assert changed["cache_hit"] is False
    assert schedule_repo.calls == [7, 7, 7]
    assert compute.call_count == 2
    stable = provider.get_critical_chain(7, plan_resolution=plan)
    assert stable["ids"] == ["B"]
    assert stable["cache_hit"] is True
    assert schedule_repo.calls == [7, 7, 7, 7]
    assert compute.call_count == 2
    assert snapshot.rows[1]["machine_id"] == "M1"
    assert plan_query.calls == []

    schedule_repo.rows[1]["machine_id"] = "M1"
    assert provider.get_critical_chain(7, plan_resolution=plan)["cache_hit"] is True
    assert schedule_repo.calls == [7, 7, 7, 7, 7]
    assert compute.call_count == 2


def test_candidate_critical_chain_uses_full_plan_detail_rows(monkeypatch) -> None:
    import core.services.scheduler.gantt.critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    rows_seen: List[List[Dict[str, Any]]] = []

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows_seen.append(rows)
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_resolution={
            (SOURCE_CANDIDATE_ROWS, 101): [
                {
                    "op_code": "BASELINE-OP",
                    "start_time": "2026-05-01 08:00",
                    "end_time": "2026-05-01 10:00",
                }
            ]
        }
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)

    result = provider.get_critical_chain(
        7,
        plan_resolution=_plan_resolution(
            ROLE_BASELINE_BEST,
            candidate_id=101,
            source_table=SOURCE_CANDIDATE_ROWS,
        ),
    )

    assert result["ids"] == ["BASELINE-OP"]
    assert result["cache_hit"] is False
    assert plan_query.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101,
                                "effective_plan_role": ROLE_BASELINE_BEST, "plan_ref": None}]
    assert rows_seen == [
        [
            {
                "op_code": "BASELINE-OP",
                "start_time": "2026-05-01 08:00",
                "end_time": "2026-05-01 10:00",
            }
        ]
    ]


def test_cache_compares_lossless_values_in_every_returned_column(monkeypatch) -> None:
    import core.services.scheduler.gantt.critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", 16)
    compute = Mock(wraps=provider_module.compute_critical_chain)
    monkeypatch.setattr(provider_module, "compute_critical_chain", compute)
    schedule_repo = _DummyScheduleRepo(_detail_rows())
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=schedule_repo)
    values = [True, 1, 1.0, 0.0, -0.0, b"\x00\xff", float("nan"), float("inf"), float("-inf")]

    for count, value in enumerate(values, 1):
        schedule_repo.rows[0]["joined_detail"] = value
        changed = provider.get_critical_chain(7)
        assert changed["cache_hit"] is False
        assert compute.call_count == count
        # Column order has no meaning; REAL nan compares by its stored value.
        schedule_repo.rows[0] = dict(reversed(list(schedule_repo.rows[0].items())))
        if type(value) is float:
            schedule_repo.rows[0]["joined_detail"] = float.fromhex(value.hex())
        assert provider.get_critical_chain(7)["cache_hit"] is True
        assert compute.call_count == count

    schedule_repo.rows[0]["joined_detail"] = True
    restored = provider.get_critical_chain(7)
    assert restored["cache_hit"] is True
    assert restored["ids"] == ["A", "B"]
    assert len(schedule_repo.calls) == 2 * len(values) + 1


def test_cache_preserves_duplicate_task_row_order(monkeypatch) -> None:
    import core.services.scheduler.gantt.critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute = Mock(wraps=provider_module.compute_critical_chain)
    monkeypatch.setattr(provider_module, "compute_critical_chain", compute)
    first, successor = _detail_rows()
    last = dict(first, end_time="2026-05-01 11:00")
    schedule_repo = _DummyScheduleRepo([first, last, successor])
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=schedule_repo)

    initial = provider.get_critical_chain(7)
    assert initial["cache_hit"] is False
    assert initial["ids"] == ["A"]

    schedule_repo.rows = [last, first, successor]
    reordered = provider.get_critical_chain(7)
    assert reordered["cache_hit"] is False
    assert reordered["ids"] == ["A", "B"]
    schedule_repo.rows = [first, last, successor]
    restored = provider.get_critical_chain(7)
    assert restored["cache_hit"] is True
    assert restored["ids"] == ["A"]
    assert compute.call_count == 2
    assert schedule_repo.calls == [7, 7, 7]


def test_unencodable_detail_bypasses_cache_and_retains_calculation(monkeypatch) -> None:
    import core.services.scheduler.gantt.critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute = Mock(wraps=provider_module.compute_critical_chain)
    monkeypatch.setattr(provider_module, "compute_critical_chain", compute)
    schedule_repo = _DummyScheduleRepo(_detail_rows())
    schedule_repo.rows[0]["joined_detail"] = object()
    logger = Mock()
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=schedule_repo, logger=logger)

    for _ in range(2):
        result = provider.get_critical_chain(7)
        assert result["cache_hit"] is False
        assert result["available"] is True
        assert result["ids"] == ["A", "B"]
    assert compute.call_count == 2
    assert schedule_repo.calls == [7, 7]
    assert not GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE
    assert logger.warning.call_count == 2
