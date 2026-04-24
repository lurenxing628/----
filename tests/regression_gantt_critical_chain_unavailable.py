import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

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


def test_critical_chain_unavailable_result_is_not_cached(monkeypatch) -> None:
    svc = GanttService(_DummyConn(str(REPO_ROOT / "db" / "aps.db")))

    monkeypatch.setattr(GanttService, "_CRITICAL_CHAIN_CACHE", OrderedDict())
    monkeypatch.setattr(GanttService, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(GanttService, "_CRITICAL_CHAIN_CACHE_MAX", 8)

    def _repo_raise(_version: int):
        raise RuntimeError("repo boom")

    monkeypatch.setattr(svc.schedule_repo, "list_by_version_with_details", _repo_raise)

    first = svc._get_critical_chain(77)
    assert first.get("available") is False
    assert first.get("reason") == "repo_exception"
    assert first.get("cache_hit") is False
    assert len(GanttService._CRITICAL_CHAIN_CACHE) == 0

    monkeypatch.setattr(svc.schedule_repo, "list_by_version_with_details", lambda _version: [])

    second = svc._get_critical_chain(77)
    third = svc._get_critical_chain(77)

    assert second.get("available") is True
    assert second.get("reason") in (None, "")
    assert second.get("cache_hit") is False
    assert third.get("available") is True
    assert third.get("cache_hit") is True
