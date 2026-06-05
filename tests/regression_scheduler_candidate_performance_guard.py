"""回归测试（性能护栏）：SchedulePlanQueryService.list_plan_roles 不扫描 ScheduleCandidateRows 明细；get_plan_time_span 对 adopted/baseline_best 各只发一条 MIN/MAX 时间跨度查询且分别命中 idx_schedule_version_time 与 idx_schedule_candidate_rows_version_candidate_time 索引、返回值稳定；ScheduleCandidateRepository.delete_without_schedule_history 级联清理孤儿候选而不误删 ScheduleHistory/Schedule。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable, List

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _detail_text(rows: Iterable[Any]) -> str:
    parts: List[str] = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            parts.append(str(row["detail"]))
        else:
            parts.append(str(row[-1]))
    return "\n".join(parts)


def _assert_traced_query_uses_index(conn: sqlite3.Connection, sql: str, index_name: str) -> None:
    statement = " ".join(str(sql).strip().rstrip(";").split())
    plan = conn.execute("EXPLAIN QUERY PLAN " + statement).fetchall()
    detail = _detail_text(plan)
    assert index_name in detail, detail


def _traced_time_span_queries(conn: sqlite3.Connection, call: Callable[[], Any]) -> List[str]:
    sql_log: List[str] = []
    conn.set_trace_callback(sql_log.append)
    try:
        call()
    finally:
        conn.set_trace_callback(None)
    return [
        sql
        for sql in sql_log
        if "SELECT MIN(start_time)" in sql and "MAX(end_time)" in sql
    ]


def _seed_plan_rows(conn: sqlite3.Connection, *, row_count: int = 1000) -> int:
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('P001', '零件')")
    conn.execute(
        """
        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, status)
        VALUES ('B001', 'P001', '零件', 1, '2026-05-20', 'normal', 'pending')
        """
    )
    conn.executemany(
        """
        INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name, source, status)
        VALUES (?, ?, 'B001', ?, '车削', 'internal', 'pending')
        """,
        [(idx, f"OP{idx:04d}", idx) for idx in range(1, row_count + 1)],
    )
    conn.execute(
        """
        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 1, ?, 'success', '{}', 'pytest')
        """,
        (row_count,),
    )
    conn.executemany(
        """
        INSERT INTO Schedule(op_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, ?, 'unlocked', 1)
        """,
        [
            (
                idx,
                f"2026-05-{1 + ((idx - 1) % 20):02d} 08:00:00",
                f"2026-05-{1 + ((idx - 1) % 20):02d} 09:00:00",
            )
            for idx in range(1, row_count + 1)
        ],
    )
    adopted_id = conn.execute(
        """
        INSERT INTO ScheduleCandidate(
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (1, 'graph_w1_of_5', '重点工序优先方案 1/5', 'critical_chain', 'completed', 'yes', 'no')
        """
    ).lastrowid
    baseline_id = conn.execute(
        """
        INSERT INTO ScheduleCandidate(
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (1, 'baseline', '原算法方案', 'baseline', 'completed', 'no', 'yes')
        """
    ).lastrowid
    assert adopted_id is not None and baseline_id is not None
    conn.executemany(
        """
        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time, lock_status)
        VALUES (1, ?, ?, ?, ?, 'unlocked')
        """,
        [
            (
                int(baseline_id),
                idx,
                f"2026-05-{1 + ((idx - 1) % 20):02d} 10:00:00",
                f"2026-05-{1 + ((idx - 1) % 20):02d} 11:00:00",
            )
            for idx in range(1, row_count + 1)
        ],
    )
    conn.executemany(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (1, ?, ?, ?)
        """,
        [
            ("adopted", int(adopted_id), "schedule"),
            ("baseline_best", int(baseline_id), "candidate_rows"),
            ("critical_best", int(adopted_id), "schedule"),
        ],
    )
    conn.commit()
    return int(baseline_id)


def _seed_orphan_candidate(conn: sqlite3.Connection) -> int:
    candidate_id = conn.execute(
        """
        INSERT INTO ScheduleCandidate(
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (99, 'baseline', '原算法方案', 'baseline', 'completed', 'no', 'yes')
        """
    ).lastrowid
    assert candidate_id is not None
    conn.execute(
        """
        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time)
        VALUES (99, ?, 1, '2026-05-01 08:00:00', '2026-05-01 09:00:00')
        """,
        (int(candidate_id),),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (99, 'baseline_best', ?, 'candidate_rows')
        """,
        (int(candidate_id),),
    )
    conn.commit()
    return int(candidate_id)


def test_list_plan_roles_does_not_scan_candidate_rows_details(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_plan_rows(conn)
        sql_log: List[str] = []
        conn.set_trace_callback(sql_log.append)
        try:
            roles = SchedulePlanQueryService(conn).list_plan_roles(1)
        finally:
            conn.set_trace_callback(None)

        assert [role.role for role in roles] == ["adopted", "baseline_best", "critical_best"]
        assert not any("ScheduleCandidateRows" in sql for sql in sql_log), sql_log
    finally:
        conn.close()


def test_plan_time_span_queries_use_version_time_indexes(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_plan_rows(conn)
        svc = SchedulePlanQueryService(conn)
        adopted_queries = _traced_time_span_queries(conn, lambda: svc.get_plan_time_span(1, "adopted"))
        baseline_queries = _traced_time_span_queries(conn, lambda: svc.get_plan_time_span(1, "baseline_best"))
        assert len(adopted_queries) == 1
        assert len(baseline_queries) == 1
        assert "FROM Schedule " in adopted_queries[0] or "FROM Schedule\n" in adopted_queries[0]
        assert "FROM ScheduleCandidateRows" in baseline_queries[0]
        _assert_traced_query_uses_index(conn, adopted_queries[0], "idx_schedule_version_time")
        _assert_traced_query_uses_index(conn, baseline_queries[0], "idx_schedule_candidate_rows_version_candidate_time")
    finally:
        conn.close()


def test_plan_time_span_expected_values_are_stable(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        baseline_id = _seed_plan_rows(conn)
        svc = SchedulePlanQueryService(conn)
        assert baseline_id > 0
        assert svc.get_plan_time_span(1, "adopted") == {
            "version": 1,
            "start_time": "2026-05-01 08:00:00",
            "end_time": "2026-05-20 09:00:00",
        }
        assert svc.get_plan_time_span(1, "baseline_best") == {
            "version": 1,
            "start_time": "2026-05-01 10:00:00",
            "end_time": "2026-05-20 11:00:00",
        }
    finally:
        conn.close()


def test_candidate_orphan_cleanup_cascades_without_deleting_schedule_history(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_plan_rows(conn)
        _seed_orphan_candidate(conn)

        removed = ScheduleCandidateRepository(conn).delete_without_schedule_history()
        conn.commit()

        assert removed == 1
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version=99").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateRows WHERE version=99").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateSelection WHERE version=99").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory WHERE version=1").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=1").fetchone()[0] == 1000
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version=1").fetchone()[0] == 2
    finally:
        conn.close()
