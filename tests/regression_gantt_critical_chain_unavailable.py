import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from core.services.scheduler import gantt_critical_chain
from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.gantt_service import GanttService

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        assert critical_chain.get("reason") == "关键链计算异常"
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
        critical_chain={"available": False, "reason": "rows_exception", "ids": ["RAW"], "edges": [{"from": "A", "to": "B"}]},
    )
    critical_chain = data["critical_chain"]

    assert critical_chain.get("reason_code") == "rows_exception"
    assert critical_chain.get("reason") == "关键链计算异常"
    assert critical_chain.get("ids") == []
    assert critical_chain.get("edges") == []


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
