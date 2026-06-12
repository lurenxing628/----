"""周计划增强页面契约（fusion-week-plan-enrich）：列渲染/汇总条/空周升级/Excel 列。

钉死点：现场状态列出现在预览表与 Excel；每日汇总条含容量来源明示文案；
空周+版本有计划行 → 升级文案+跳转链接（URL 带日期与版本身份）；
无计划行版本 → 现有文案零跳转；禁直调 calculations.capacity_hours（grep 钉死）。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_week_plan(db_path: str, *, with_schedule: bool = True) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 1, 'success', '{}', 'pytest')"
    )
    if with_schedule:
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
        conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
        conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')"
        )
        op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, version)"
            " VALUES (?, '2026-06-01 08:00:00', '2026-06-01 12:00:00', 7)",
            (op_id,),
        )
    conn.commit()
    conn.close()


def test_week_plan_renders_execution_status_column_and_daily_summary(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get("/scheduler/week-plan?version=7&week_start=2026-06-01").get_data(as_text=True)
    assert "现场状态" in html
    assert "待开工" in html  # 无事实工序的缺省态
    # 每日汇总条 + 4.6 容量来源明示
    assert "2026-06-01：计划 4 小时" in html
    assert "容量按全局工作日历估算，未按单台设备/单人细分" in html


def test_week_plan_empty_week_upgraded_hint_with_jump_link(app_client, db_env):
    _seed_week_plan(db_env)
    # 看一个没有排程的周：升级文案告知计划所在区间 + 跳转链接
    html = app_client.get("/scheduler/week-plan?version=7&week_start=2026-07-06").get_data(as_text=True)
    assert "这个版本的计划在 2026-06-01 ～ 2026-06-01" in html
    assert "跳到计划区间" in html
    assert "week_start=2026-06-01" in html  # 链接带计划区间日期


def test_week_plan_empty_week_no_plan_rows_keeps_plain_message(app_client, db_env):
    _seed_week_plan(db_env, with_schedule=False)  # 有历史但无计划行（失败/模拟）
    html = app_client.get("/scheduler/week-plan?version=7&week_start=2026-07-06").get_data(as_text=True)
    assert "暂无数据" in html
    assert "跳到计划区间" not in html


def test_week_plan_export_contains_execution_status_column(app_client, db_env):
    from openpyxl import load_workbook

    _seed_week_plan(db_env)
    resp = app_client.get("/scheduler/week-plan/export?version=7&week_start=2026-06-01")
    assert resp.status_code == 200
    wb = load_workbook(BytesIO(resp.data))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers == ["日期", "批次号", "图号", "工序", "设备", "人员", "时段", "现场状态"]
    assert ws.cell(row=2, column=8).value == "待开工"
    # 导出不含每日合计行（合计是页面阅读辅助，不破坏导出行语义）
    all_values = [str(c.value or "") for row in ws.iter_rows() for c in row]
    assert not any("容量" in v for v in all_values)


def test_no_direct_capacity_hours_call_in_week_plan_chain():
    # 4.6 红线：周计划链路禁直调 calculations.capacity_hours（midnight 采样错归属）
    for rel in (
        "core/services/scheduler/week_plan_daily_summary.py",
        "core/services/scheduler/gantt_week_plan.py",
        "web/routes/domains/scheduler/scheduler_week_plan.py",
        "web/routes/domains/scheduler/scheduler_week_plan_preview.py",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "capacity_hours(" not in text.replace("_capacity_hours_at_noon(", ""), rel
