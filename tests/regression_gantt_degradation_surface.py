from __future__ import annotations

import importlib
import json
import os
import sys
from typing import List
from unittest import mock

import pytest

from core.services.scheduler.gantt_service import GanttService


# =====================================================================
# A. bad_time_rows_surface_degraded —— 服务层直连（无 HTTP），独立函数
#    坏值构造：第二条 Schedule start_time 小时 99（非法时间）→ 被跳过
#    复用 schema_conn（:memory: + 全量 schema）+ repo_root（读 JS 静态文件）
# =====================================================================
def test_gantt_bad_time_rows_surface_degraded(schema_conn, repo_root) -> None:
    conn = schema_conn
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

    gantt_boot_js = (repo_root / "static" / "js" / "gantt_boot.js").read_text(encoding="utf-8")
    gantt_contract_js = (repo_root / "static" / "js" / "gantt_contract.js").read_text(encoding="utf-8")
    gantt_render_js = (repo_root / "static" / "js" / "gantt_render.js").read_text(encoding="utf-8")
    assert "buildDegradationMessages" in gantt_boot_js, "gantt_boot.js 未接入共享退化提示构造器"
    assert "bad_time_row_skipped" in gantt_contract_js, "gantt_contract.js 未消费 bad_time_row_skipped"
    assert "all_rows_filtered_by_invalid_time" in gantt_contract_js, "gantt_contract.js 未消费统一空原因码"
    assert "已过滤 " in gantt_contract_js, "gantt_contract.js 未提供部分过滤提示"
    assert "已过滤 \" + badTimeSkipped + \" 条开始或结束时间写法不对的排程记录。当前区间没有可显示排程" in gantt_render_js, (
        "gantt_render.js 未在坏时间全量过滤空态展示过滤条数"
    )
    assert "当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。" in gantt_render_js, (
        "gantt_render.js 未区分坏时间全量过滤空态"
    )
    assert "当前筛选条件下暂无可显示任务。" in gantt_render_js, "gantt_render.js 未区分前端筛选后的空态"


# =====================================================================
# B. calendar_load_failed_degraded —— HTTP + mock build_calendar_days，独立函数
#    复用 app_client / db_path / repo_root（B 已是标准范式）
#    安全断言：sample 中 RuntimeError / sample 字段不外泄；内部 message 不泄漏到 HTML
# =====================================================================
def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def test_gantt_calendar_load_failed_degraded(app_client, db_path, repo_root) -> None:
    from core.infrastructure.database import get_connection
    from core.services.common.build_outcome import BuildOutcome
    from core.services.common.degradation import DegradationCollector

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (3, "greedy", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()
    finally:
        conn.close()

    def _calendar_failed(*_args, **_kwargs):
        collector = DegradationCollector()
        collector.add(
            code="calendar_load_failed",
            scope="gantt.calendar_days",
            field="calendar_days",
            message="工作日历加载失败，当前不显示假期/停工背景标注。",
            sample="RuntimeError",
        )
        return BuildOutcome.from_collector([], collector, empty_reason="calendar_load_failed")

    client = app_client

    with mock.patch("core.services.scheduler.gantt_service.build_calendar_days", side_effect=_calendar_failed):
        page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=3")
        _assert_status(page_resp, "GET /scheduler/gantt")
        html = page_resp.data.decode("utf-8", errors="ignore")
        assert 'id="ganttDegradationWarning"' in html, html
        assert "工作日历加载失败，当前不显示假期/停工背景标注。" not in html, html

        data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=3")
        _assert_status(data_resp, "GET /scheduler/gantt/data")
        payload = json.loads(data_resp.data.decode("utf-8", errors="ignore") or "{}")
        assert payload.get("success") is True, payload
        data = dict(payload.get("data") or {})
        assert data.get("degraded") is True, data
        assert data.get("empty_reason") == "calendar_load_failed", data
        counters = dict(data.get("degradation_counters") or {})
        assert int(counters.get("calendar_load_failed") or 0) == 1, counters
        events = list(data.get("degradation_events") or [])
        assert any(str(evt.get("code") or "") == "calendar_load_failed" for evt in events), events
        assert "RuntimeError" not in str(events)
        assert all("sample" not in evt for evt in events if isinstance(evt, dict)), events

    gantt_boot_js = open(os.path.join(str(repo_root), "static", "js", "gantt_boot.js"), "r", encoding="utf-8").read()
    gantt_contract_js = open(os.path.join(str(repo_root), "static", "js", "gantt_contract.js"), "r", encoding="utf-8").read()
    assert "ganttDegradationWarning" in gantt_boot_js, "gantt_boot.js 未接入页面退化提示节点"
    assert "buildDegradationMessages" in gantt_boot_js, "gantt_boot.js 未接入共享退化提示构造器"
    assert "calendar_load_failed" in gantt_contract_js, "gantt_contract.js 未识别 calendar_load_failed"


# =====================================================================
# C/D. overdue_markers_summary —— HTTP，C(invalid 全降级) 与 D(partial 部分降级)
#       为故意成对的互斥镜像（degraded↔partial、超期↔已识别、降级↔部分不完整），
#       parametrize 两 case，严禁去重为一条。
#       簇内私有 helper _build_overdue_app(db_env, ...)：插种子 + create_app + 捕获 logger.warning。
# =====================================================================
def _build_overdue_app(db_env, monkeypatch, result_summary):
    """在 db_env 库上插甘特种子（含给定 result_summary），create_app 并捕获 logger.warning。

    返回 (app, client, logged)。db_env 已设好 APS_* 环境与建好库（ensure_schema）。
    """
    from core.infrastructure.database import get_connection

    conn = get_connection(db_env)
    conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备 1", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
    conn.execute("INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)", ("PART-001", "零件", "[]"))
    conn.execute(
        "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("B001", "PART-001", "零件", 1, "2026-03-08", "normal", "yes", "scheduled"),
    )
    cur = conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
    )
    lastrowid = cur.lastrowid
    assert lastrowid is not None
    op_id = int(lastrowid)
    conn.execute(
        "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (op_id, "MC001", "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "greedy", 1, 1, "success", result_summary, "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app = importlib.import_module("app").create_app()

    logged: List[str] = []

    def _fake_warning(message, *args, **_kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    return app, app.test_client(), logged


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            dict(
                result_summary="{broken json",
                expect_degraded=True,
                expect_partial=False,
                expect_message_kw="超期",
                expect_log_kw="甘特图超期标记降级",
                expect_task_overdue=None,
            ),
            id="invalid",
        ),
        pytest.param(
            dict(
                result_summary=json.dumps(
                    {"overdue_batches": [{"batch_id": "B001", "hours": 4}, {"hours": 2}, "", None]},
                    ensure_ascii=False,
                ),
                expect_degraded=False,
                expect_partial=True,
                expect_message_kw="已识别",
                expect_log_kw="甘特图超期标记部分不完整",
                expect_task_overdue=True,
            ),
            id="partial",
        ),
    ],
)
def test_gantt_overdue_markers_summary(db_env, monkeypatch, case) -> None:
    app, client, logged = _build_overdue_app(db_env, monkeypatch, case["result_summary"])

    page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=1")
    assert page_resp.status_code == 200
    page_html = page_resp.get_data(as_text=True)
    assert 'id="ganttOverdueWarning"' in page_html

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=1")
    assert data_resp.status_code == 200
    payload = json.loads(data_resp.get_data(as_text=True) or "{}")
    assert payload.get("success") is True, payload
    data = payload.get("data") or {}
    assert int(data.get("task_count") or 0) == 1
    assert data.get("overdue_markers_degraded") is case["expect_degraded"]
    assert data.get("overdue_markers_partial") is case["expect_partial"]
    assert case["expect_message_kw"] in str(data.get("overdue_markers_message") or "")
    if case["expect_task_overdue"] is not None:
        tasks = data.get("tasks") or []
        assert tasks and tasks[0].get("meta", {}).get("is_overdue") is case["expect_task_overdue"]
    assert any(case["expect_log_kw"] in item for item in logged), logged
