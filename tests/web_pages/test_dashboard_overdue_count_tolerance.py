"""回归测试：首页“超期批次”统计卡片对脏 result_summary 容错——当 overdue_batches.count 是非整数（如 "2.9"）时显示“数据不足”并提示“排产摘要里的超期批次数不是整数”，绝不把脏值泄漏或伪装成 0；overdue_batches 为 list 结构时仍能正确数出超期数为 1。"""

from __future__ import annotations

import json

from tests._support.gantt_retirement import _business_state
from tests._support.workbench_web_contract import canonical_boot
from web.routes.dashboard import _summary_overdue_count


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def test_dashboard_overdue_count_tolerance(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "priority_first",
                0,
                0,
                "success",
                '{"overdue_batches":{"count":"2.9","items":[]}}',
                "reg",
            ),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P1", "测试零件"))
        conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES (?, ?, ?)", ("B1", "P1", 1))
        op_cursor = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES (?, ?, ?, ?)",
            ("OP1", "B1", 10, "测试工序"),
        )
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?)",
            (op_cursor.lastrowid, "2026-05-06 08:00:00", "2026-05-06 10:00:00", "unlocked", 2),
        )
        conn.commit()
    finally:
        conn.close()

    canonical_boot(app_client, "/", "dashboard", {})
    before = _business_state(app_client)
    conn = get_connection(db_path)
    try:
        raw = conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=1").fetchone()[0]
    finally:
        conn.close()
    count, error = _summary_overdue_count(json.loads(raw))
    assert count == 0 and error == "排产摘要里的超期批次数不是整数，首页暂时不能展示准确数量。"
    resp = app_client.get("/api/workbench/v1/dashboard")
    _assert_status(resp, "GET dashboard API")
    html = resp.get_data(as_text=True)
    if "Internal Server Error" in html or "Traceback" in html:
        raise RuntimeError("脏数据容错失败：首页出现错误页内容")
    if "2.9" in html:
        raise RuntimeError("脏数据容错失败：脏值泄漏到首页展示")
    data = resp.get_json()["data"]
    assert data["plan"] is None
    assert data["categories"]["delivery"]["risk_count"] is None
    assert data["categories"]["delivery"]["issues"]
    assert _business_state(app_client) == before

    # 追加历史 list 结构，首页应兼容并展示正确数量
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "priority_first",
                0,
                0,
                "success",
                '{"overdue_batches":[{"batch_id":"B1"}]}',
                "reg",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    before = _business_state(app_client)
    conn = get_connection(db_path)
    try:
        raw = conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=2").fetchone()[0]
    finally:
        conn.close()
    assert _summary_overdue_count(json.loads(raw)) == (1, "")
    resp2 = app_client.get("/api/workbench/v1/dashboard")
    _assert_status(resp2, "GET dashboard API (retained list summary)")
    data = resp2.get_json()["data"]
    assert data["plan"]["version"] == 2
    # This fixture has no due date: a legacy count must not become evidence of a current delivery risk.
    assert data["categories"]["delivery"]["risk_count"] is None
    assert data["categories"]["delivery"]["evaluation_gaps"]
    assert _business_state(app_client) == before
