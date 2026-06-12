"""周派工单打印页契约（fusion-dispatch-print-sheet）。

钉死点：页眉字段（版本/方案身份/生成时间/范围/资源名）随段重复且在 thead 内；
page-break 段容器；备注列存在；「现场状态」零出现（4.11 纸面零现场事实）；
参数错误（group_by 非法 / day 格式非法 / day 出周）明示不静默；空行集页内
空态不 404；入口链接带全量筛选参数；警示三态（当前正式零警示由种子态覆盖，
历史正式/非正式由 plan_role_resolution 判定单测覆盖路由 helper）。
"""

from __future__ import annotations

from web.routes.domains.scheduler.scheduler_week_plan_print import _identity_warning


def _seed_week_plan(db_path: str, *, operator_id="OP1") -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 2, 'success', '{}', 'pytest')"
    )
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
    conn.execute("INSERT INTO Machines (machine_id, name) VALUES ('M1', '车床')")
    if operator_id:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, '张三')", (operator_id,))
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
    conn.execute("INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')")
    conn.execute("INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-20', 'B1', 20, '铣')")
    op1 = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
    op2 = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-20'").fetchone()[0]
    conn.execute(
        "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, version)"
        " VALUES (?, 'M1', ?, '2026-06-01 08:00:00', '2026-06-01 12:00:00', 7)",
        (op1, operator_id),
    )
    conn.execute(
        "INSERT INTO Schedule (op_id, start_time, end_time, version)"
        " VALUES (?, '2026-06-02 08:00:00', '2026-06-02 12:00:00', 7)",
        (op2,),
    )
    conn.commit()
    conn.close()


_URL = "/scheduler/week-plan/print?version=7&week_start=2026-06-01"


def test_print_page_machine_view_sheets_header_and_remark_column(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get(_URL).get_data(as_text=True)
    assert '<section class="print-sheet">' in html  # page-break 段容器
    assert "M1 车床" in html
    assert "外协/未分配" in html  # 无设备行兜底段
    assert "v7" in html and "正式采用方案" in html
    assert "2026年6月1日 08:00" in html  # 生成时间走 format_public_datetime 公开口径
    assert "2026-06-01 ～ 2026-06-07" in html
    assert "<th class=\"col-remark\"" in html and "备注" in html
    assert "现场状态" not in html  # 4.11：纸面零现场事实
    assert "window.print()" in html


def test_print_page_operator_view_unassigned_fallback(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get(_URL + "&group_by=operator").get_data(as_text=True)
    assert "OP1 张三" in html
    assert "外协/未分配" in html  # 没派人的工序入兜底段
    assert "切换为按设备视图" in html


def test_print_page_day_filter_and_header_shows_single_day(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get(_URL + "&day=2026-06-02").get_data(as_text=True)
    assert "2026-06-02（单日）" in html
    assert "M1 车床" not in html  # 6-02 只有未分配行，M1 无任务不出纸


def test_print_page_param_errors_explicit(app_client, db_env):
    _seed_week_plan(db_env)
    assert app_client.get(_URL + "&group_by=bogus").status_code == 400
    assert app_client.get(_URL + "&day=abc").status_code == 400
    assert app_client.get(_URL + "&day=2026-99-99").status_code == 400
    resp = app_client.get(_URL + "&day=2026-07-01")  # 出周
    assert resp.status_code == 400
    assert "不在所选周" in resp.get_data(as_text=True)


def test_print_page_empty_week_honest_state_not_404(app_client, db_env):
    _seed_week_plan(db_env)
    resp = app_client.get("/scheduler/week-plan/print?version=7&week_start=2026-07-06")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "没有排程记录" in html
    assert "返回周计划" in html
    assert '<section class="print-sheet">' not in html


def test_print_page_no_history_empty_state(app_client, db_env):
    # 库里零排产历史 + 不指定版本：空态走「无法生成派工单」分支（与空周文案区分）；
    # 显式指定不存在版本（version=99）继承 get_week_plan_rows 的 404 语义（与周计划页一致）
    resp = app_client.get("/scheduler/week-plan/print?week_start=2026-06-01")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "没有排产历史，无法生成派工单" in html
    assert '<section class="print-sheet">' not in html
    assert app_client.get("/scheduler/week-plan/print?version=99&week_start=2026-06-01").status_code == 404


def test_week_plan_page_print_entry_carries_full_params(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get(
        "/scheduler/week-plan?version=7&week_start=2026-06-01&batch_id=B1&resource_type=machine&resource_id=M1"
    ).get_data(as_text=True)
    assert "打印周派工单" in html
    assert "/scheduler/week-plan/print?" in html
    start = html.index("/scheduler/week-plan/print?")
    href = html[start: html.index('"', start)]
    for piece in ("version=7", "week_start=2026-06-01", "batch_id=B1", "resource_type=machine", "resource_id=M1"):
        assert piece in href, href


def test_print_page_filter_scope_label_in_header(app_client, db_env):
    _seed_week_plan(db_env)
    html = app_client.get(_URL + "&batch_id=B1&resource_type=machine&resource_id=M1").get_data(as_text=True)
    assert "仅含筛选范围：批次 B1、设备 M1" in html


def test_identity_warning_three_states():
    # 当前可执行正式方案：零警示
    assert _identity_warning({"is_current_executable_official_version": True}) == ""
    # 历史正式方案（旧 adopted 无 scenario——只看 selected_role 会漏的态）
    assert (
        _identity_warning({"is_current_executable_official_version": False, "is_superseded_by_newer_version": True})
        == "历史正式方案，已被新版本替代，不得下发执行"
    )
    # 其余非可执行态（候选/模拟预览/摘要坏）
    assert (
        _identity_warning({"is_current_executable_official_version": False})
        == "非正式方案，不得下发执行"
    )
