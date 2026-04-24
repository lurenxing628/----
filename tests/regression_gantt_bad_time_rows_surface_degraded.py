from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.services.scheduler.gantt_service import GanttService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_gantt_bad_time_rows_surface_degraded() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备 1", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("PART-001", "零件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "PART-001", "零件", 1, "2026-03-08", "normal", "yes", "scheduled"),
        )
        cur1 = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        cur2 = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-20", "B001", "P1", 20, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        assert cur1.lastrowid is not None
        assert cur2.lastrowid is not None
        op_id_valid = int(cur1.lastrowid)
        op_id_invalid = int(cur2.lastrowid)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id_valid, "MC001", "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
        )
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id_invalid, "MC001", "OP001", "2026-03-02 99:00:00", "2026-03-02 13:00:00", "locked", 1),
        )
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "greedy", 1, 2, "success", json.dumps({"overdue_batches": []}, ensure_ascii=False), "pytest"),
        )
        conn.commit()

        data = GanttService(conn, logger=None, op_logger=None).get_gantt_tasks(
            view="machine",
            week_start="2026-03-02",
            version=1,
        )
        assert int(data.get("task_count") or 0) == 1
        assert data.get("degraded") is True
        counters = data.get("degradation_counters") or {}
        assert int(counters.get("bad_time_row_skipped") or 0) == 1
        assert data.get("empty_reason") is None
        events = data.get("degradation_events") or []
        assert events and events[0].get("code") == "bad_time_row_skipped"
    finally:
        conn.close()

    gantt_boot_js = (REPO_ROOT / "static" / "js" / "gantt_boot.js").read_text(encoding="utf-8")
    gantt_contract_js = (REPO_ROOT / "static" / "js" / "gantt_contract.js").read_text(encoding="utf-8")
    gantt_render_js = (REPO_ROOT / "static" / "js" / "gantt_render.js").read_text(encoding="utf-8")
    assert "buildDegradationMessages" in gantt_boot_js, "gantt_boot.js 未接入共享退化提示构造器"
    assert "bad_time_row_skipped" in gantt_contract_js, "gantt_contract.js 未消费 bad_time_row_skipped"
    assert "all_rows_filtered_by_invalid_time" in gantt_contract_js, "gantt_contract.js 未消费统一空原因码"
    assert "已过滤 " in gantt_contract_js, "gantt_contract.js 未提供部分过滤提示"
    assert "当前区间存在时间非法的排程数据，已全部过滤，请检查排产结果。" in gantt_render_js, (
        "gantt_render.js 未区分坏时间全量过滤空态"
    )
    assert "当前筛选条件下暂无可显示任务。" in gantt_render_js, "gantt_render.js 未区分前端筛选后的空态"
