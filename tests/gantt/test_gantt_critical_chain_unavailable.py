"""回归测试：甘特图关键链（critical_chain）计算异常时对外降级可见且不泄漏内部细节。守护 repo/rows/calc 异常都返回 available=False、统一中文 reason "关键工序关系计算异常"、对应 reason_code（repo_exception/rows_exception/calc_exception），清空 ids/edges 并隐藏 debug_error/raw_rows/traceback；不可用结果不进缓存、成功结果才缓存；关键链节点标签与甘特任务公开标签一致；边时间字段缺失抛 ValueError 不静默丢边。"""

import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from core.services.scheduler import gantt_critical_chain
from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_service import GanttService
from core.services.scheduler.gantt_tasks import build_tasks
from tests._support.paths import REPO_ROOT


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


class _DummyCursor:
    def __init__(self, db_file: str):
        self._db_file = str(db_file)

    def fetchall(self):
        return [(0, "main", self._db_file)]


class _DummyConn:
    def __init__(self, db_file: str):
        self._db_file = str(db_file)

    def execute(self, sql: str):
        if "pragma database_list" not in str(sql or "").strip().lower():
            raise RuntimeError(f"unexpected sql in test: {sql!r}")
        return _DummyCursor(self._db_file)


def test_gantt_payload_surfaces_critical_chain_unavailable(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "priority_first", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()

        svc = GanttService(conn, logger=None, op_logger=None)
        monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", OrderedDict())
        monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
        monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", 8)

        def _repo_raise(_version: int):
            raise RuntimeError("repo boom")

        monkeypatch.setattr(svc.schedule_repo, "list_overlapping_with_details", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(svc.schedule_repo, "list_by_version_with_details", _repo_raise)
        monkeypatch.setattr(
            svc,
            "_overdue_batch_ids_from_history",
            lambda _version: {"ids": [], "degraded": False, "partial": False, "message": "", "reason": ""},
        )

        data = svc.get_gantt_tasks(view="machine", week_start="2026-03-02", version=1)
        critical_chain = data.get("critical_chain") or {}

        assert critical_chain.get("available") is False
        assert critical_chain.get("reason") == "关键工序关系计算异常"
        assert critical_chain.get("reason_code") == "repo_exception"
        assert critical_chain.get("ids") == []
        assert critical_chain.get("cache_hit") is False
        assert "repo boom" not in str(data)
        assert data.get("degraded") is True
        events = list(data.get("degradation_events") or ())
        assert any(str(event.get("code") or "").strip() == "critical_chain_unavailable" for event in events), events
        counters = data.get("degradation_counters") or {}
        assert int(counters.get("critical_chain_unavailable") or 0) == 1
    finally:
        conn.close()


def test_gantt_public_contract_preserves_rows_exception_reason_code() -> None:
    from core.services.scheduler.gantt_contract import build_gantt_contract

    data = build_gantt_contract(
        contract_version=1,
        view="machine",
        version=1,
        week_start="2026-03-02",
        week_end="2026-03-08",
        tasks=[],
        calendar_days=[],
        critical_chain={
            "available": False,
            "reason": "rows_exception",
            "ids": ["RAW"],
            "edges": [{"from": "A", "to": "B"}],
            "debug_error": "sqlite SECRET",
            "raw_rows": [{"internal": "row"}],
            "traceback": "internal traceback",
            "dropped_count": 3,
            "critical_chain_partial": True,
        },
    )
    critical_chain = data["critical_chain"]

    assert critical_chain.get("reason_code") == "rows_exception"
    assert critical_chain.get("reason") == "关键工序关系计算异常"
    assert critical_chain.get("ids") == []
    assert critical_chain.get("edges") == []
    assert critical_chain.get("dropped_count") == 3
    assert critical_chain.get("critical_chain_partial") is True
    assert "debug_error" not in critical_chain
    assert "raw_rows" not in critical_chain
    assert "traceback" not in critical_chain
    assert "sqlite SECRET" not in str(data)


def test_critical_chain_bad_time_rows_are_counted_without_changing_valid_chain() -> None:
    valid_rows = [
        {
            "op_id": 1,
            "op_code": "OP-A",
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 1,
            "machine_id": "MC1",
            "operator_id": "O1",
            "start_time": "2026-01-01 08:00:00",
            "end_time": "2026-01-01 09:00:00",
        },
        {
            "op_id": 2,
            "op_code": "OP-B",
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 2,
            "machine_id": "MC1",
            "operator_id": "O1",
            "start_time": "2026-01-01 09:00:00",
            "end_time": "2026-01-01 10:00:00",
        },
    ]
    bad_row = {
        "op_id": 3,
        "op_code": "OP-BAD",
        "batch_id": "B1",
        "piece_id": "P1",
        "seq": 3,
        "machine_id": "MC1",
        "operator_id": "O1",
        "start_time": "2026-01-01 99:00:00",
        "end_time": "2026-01-01 11:00:00",
    }

    baseline = gantt_critical_chain.compute_critical_chain_from_rows(valid_rows)
    with_bad_row = gantt_critical_chain.compute_critical_chain_from_rows(valid_rows + [bad_row])

    assert with_bad_row.get("available", True) is True
    assert with_bad_row["ids"] == baseline["ids"]
    assert with_bad_row["edges"] == baseline["edges"]
    assert with_bad_row["makespan_end"] == baseline["makespan_end"]
    assert with_bad_row["dropped_count"] == 1
    assert with_bad_row["critical_chain_partial"] is True
    assert baseline["dropped_count"] == 0
    assert baseline["critical_chain_partial"] is False


def test_critical_chain_all_bad_time_rows_keep_empty_result_observable() -> None:
    rows = [
        {
            "op_id": 1,
            "op_code": "OP-BAD-A",
            "start_time": "2026-01-01 99:00:00",
            "end_time": "2026-01-01 10:00:00",
        },
        {
            "op_id": 2,
            "op_code": "OP-BAD-B",
            "start_time": "2026-01-01 12:00:00",
            "end_time": "2026-01-01 11:00:00",
        },
    ]

    result = gantt_critical_chain.compute_critical_chain_from_rows(rows)

    assert result.get("available", True) is True
    assert result["ids"] == []
    assert result["edges"] == []
    assert result["edge_count"] == 0
    assert result["dropped_count"] == 2
    assert result["critical_chain_partial"] is True


def test_critical_chain_labels_match_gantt_task_public_labels_for_piece_fallback() -> None:
    rows = [
        {
            "op_id": 1,
            "batch_id": "B1",
            "piece_id": "PIECE-A",
            "machine_id": "MC1",
            "operator_id": "O1",
            "start_time": "2026-01-01 08:00:00",
            "end_time": "2026-01-01 09:00:00",
        },
        {
            "op_id": 2,
            "batch_id": "B2",
            "piece_id": "PIECE-B",
            "machine_id": "MC1",
            "operator_id": "O2",
            "start_time": "2026-01-01 09:00:00",
            "end_time": "2026-01-01 10:00:00",
        },
    ]

    wr = resolve_week_range(week_start="2026-01-01")
    tasks = build_tasks(view="machine", wr=wr, rows=rows, overdue_set=set()).value
    task_labels = {str((task.get("meta") or {}).get("task_label") or "") for task in tasks}
    critical_chain = gantt_critical_chain.compute_critical_chain_from_rows(rows)
    edge = (critical_chain.get("edges") or [])[0]

    assert task_labels == {"PIECE-A", "PIECE-B"}
    assert edge["from_label"] == "PIECE-A"
    assert edge["to_label"] == "PIECE-B"


def test_critical_chain_unavailable_result_is_not_cached(monkeypatch) -> None:
    svc = GanttService(_DummyConn(str(REPO_ROOT / "db" / "aps.db")))
    provider = GanttCriticalChainProvider(conn=svc.conn, schedule_repo=svc.schedule_repo)

    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", OrderedDict())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", 8)

    def _repo_raise(_version: int):
        raise RuntimeError("repo boom")

    monkeypatch.setattr(svc.schedule_repo, "list_by_version_with_details", _repo_raise)

    first = provider.get_critical_chain(77)
    assert first.get("available") is False
    assert first.get("reason") == "repo_exception"
    assert first.get("reason_code") == "repo_exception"
    assert first.get("cache_hit") is False
    assert len(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == 0

    monkeypatch.setattr(svc.schedule_repo, "list_by_version_with_details", lambda _version: [])

    second = provider.get_critical_chain(77)
    third = provider.get_critical_chain(77)

    assert second.get("available") is True
    assert second.get("reason") in (None, "")
    assert second.get("cache_hit") is False
    assert third.get("available") is True
    assert third.get("cache_hit") is True


def test_adopted_critical_chain_calc_exception_is_visible(monkeypatch) -> None:
    class _Repo:
        @staticmethod
        def list_by_version_with_details(_version: int):
            return [
                {
                    "op_id": 1,
                    "op_code": "OP1",
                    "batch_id": "B1",
                    "piece_id": "P1",
                    "seq": 1,
                    "machine_id": "MC1",
                    "operator_id": "O1",
                    "start_time": datetime(2026, 1, 1, 8, 0, 0),
                    "end_time": datetime(2026, 1, 1, 9, 0, 0),
                }
            ]

    def _boom(_rows):
        raise RuntimeError("critical calc boom")

    monkeypatch.setattr(gantt_critical_chain, "_compute_critical_chain_from_loaded_rows", _boom)

    result = gantt_critical_chain.compute_critical_chain(_Repo(), 1)

    assert result.get("available") is False
    assert result.get("reason") == "calc_exception"
    assert result.get("reason_code") == "calc_exception"
    assert result.get("ids") == []
    assert "critical calc boom" not in str(result)


def test_critical_chain_edge_time_errors_do_not_drop_edges_silently() -> None:
    nodes = {
        "A": {
            "id": "A",
            "start": datetime(2026, 1, 1, 8, 0, 0),
            "end": datetime(2026, 1, 1, 9, 0, 0),
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 1,
            "machine_id": "MC1",
            "operator_id": "O1",
        },
        "B": {
            "id": "B",
            "start": None,
            "end": datetime(2026, 1, 1, 10, 0, 0),
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 2,
            "machine_id": "MC1",
            "operator_id": "O1",
        },
    }

    proc_prev = {"B": "A"}
    mach_prev = {"B": "A"}
    op_prev = {}

    try:
        gantt_critical_chain._choose_control_prev(nodes, proc_prev=proc_prev, mach_prev=mach_prev, op_prev=op_prev)
    except ValueError as exc:
        assert "时间字段缺失" in str(exc)
    else:
        raise AssertionError("关键链边时间异常不应静默当成没有前驱边")
