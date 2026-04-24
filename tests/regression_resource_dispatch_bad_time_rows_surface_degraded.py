from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_resource_dispatch_bad_time_rows_surface_degraded() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-OP", "装配组", "active"))
        conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-MC", "设备组", "active"))
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("OP001", "张三", "active", "TEAM-OP", ""),
        )
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("MC001", "设备 1", "active", "TEAM-MC", ""),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("PART-001", "零件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "PART-001", "零件", 1, "2026-03-08", "normal", "yes", "scheduled"),
        )
        cur = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        assert cur.lastrowid is not None
        op_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, "MC001", "OP001", "2026-03-02 99:00:00", "2026-03-02 13:00:00", "locked", 1),
        )
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "greedy", 1, 1, "success", json.dumps({"overdue_batches": []}, ensure_ascii=False), "pytest"),
        )
        conn.commit()

        payload = ResourceDispatchService(conn, logger=None, op_logger=None).get_dispatch_payload(
            scope_type="operator",
            operator_id="OP001",
            period_preset="week",
            query_date="2026-03-02",
            version=1,
        )
        summary = payload.get("summary") or {}
        assert summary.get("degraded") is True
        counters = summary.get("degradation_counters") or {}
        assert int(counters.get("bad_time_row_skipped") or 0) == 1
        events = list(summary.get("degradation_events") or [])
        assert events
        assert all("sample" not in event for event in events), events
        assert "99:00:00" not in str(events), events
        assert any("时间不合法" in str(event.get("message") or "") for event in events), events
        assert summary.get("empty_reason") == "all_rows_filtered_by_invalid_time"
        assert payload.get("detail_rows") == []
        assert payload.get("tasks") == []
        assert payload.get("calendar_rows") == []
        assert "已全部过滤" in str(payload.get("empty_message") or "")
    finally:
        conn.close()
