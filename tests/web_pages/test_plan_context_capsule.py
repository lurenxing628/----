"""壳层计划上下文胶囊契约（fusion-plan-context-capsule，4.2）。

钉死点：合同四类边界（_UNSET 未喂参「-」/ 喂 None 空串走词表缺失态 / 正常值 /
坏值）；builder 无 version 零渲染；history_row_capsule_fields 查不到诚实降级
（有意行为防误修）；URL fallback 不查库补；6 发布点喂参落点实证；dashboard
muted 行去重后版本号归胶囊单点。
"""

from __future__ import annotations

from html.parser import HTMLParser

from web.viewmodels.plan_context_capsule import build_plan_context_capsule, history_row_capsule_fields
from web.viewmodels.scheduler_workbench_links import build_workbench_plan_context

# ---------- 合同四类边界（design 验收场景 1） ----------


def test_contract_unset_renders_dash():
    context = build_workbench_plan_context(version=7, plan_role="adopted")
    assert context["generated_at_label"] == "-"
    assert context["strategy_label"] == "-"


def test_contract_fed_none_or_empty_uses_vocabulary_missing_state():
    # 喂了 None/空串 ≠ 未喂参：旧历史行缺失值要诚实显示，不伪装成「无上下文」
    context = build_workbench_plan_context(version=7, plan_role="adopted", generated_at=None, strategy=None)
    assert context["generated_at_label"] == "-"  # format_public_datetime 空值口径
    assert context["strategy_label"] == "旧历史未记录"  # 词表单源缺失态
    context2 = build_workbench_plan_context(version=7, plan_role="adopted", generated_at="", strategy="")
    assert context2["strategy_label"] == "旧历史未记录"


def test_contract_normal_and_bad_values():
    context = build_workbench_plan_context(
        version=7, plan_role="adopted", generated_at="2026-06-01 08:00:00", strategy="weighted"
    )
    assert context["generated_at_label"] == "2026年6月1日 08:00"
    assert context["strategy_label"] == "综合优先级和交期"
    bad = build_workbench_plan_context(
        version=7, plan_role="adopted", generated_at="not-a-time", strategy="future_strategy"
    )
    assert bad["generated_at_label"] == "时间记录异常"
    assert bad["strategy_label"] == "历史记录异常"  # 词表单源未知态（不造第三套文案）


# ---------- builder ----------


def test_capsule_none_without_version():
    assert build_plan_context_capsule(build_workbench_plan_context()) is None
    assert build_plan_context_capsule({}) is None


def test_capsule_full_shape():
    context = build_workbench_plan_context(
        version=7,
        plan_role="adopted",
        date_from="2026-06-01",
        date_to="2026-06-05",
        generated_at="2026-06-01 08:00:00",
        strategy="weighted",
    )
    capsule = build_plan_context_capsule(context)
    assert capsule == {
        "version_label": "v7",
        "plan_role_label": "正式采用方案",
        "generated_at_label": "2026年6月1日 08:00",
        "strategy_label": "综合优先级和交期",
        "date_range_label": "2026-06-01 ～ 2026-06-05",
    }


def test_capsule_missing_fields_render_dash():
    capsule = build_plan_context_capsule(build_workbench_plan_context(version=9, plan_role="adopted"))
    assert capsule is not None
    assert capsule["generated_at_label"] == "-"
    assert capsule["strategy_label"] == "-"
    assert capsule["date_range_label"] == "-"


# ---------- history_row_capsule_fields（公共取数） ----------

_ROWS = [
    {"version": 7, "schedule_time": "2026-06-01 08:00:00", "strategy": "weighted"},
    {"version": 8, "schedule_time": None, "strategy": ""},
]


def test_capsule_fields_found_returns_raw_values():
    assert history_row_capsule_fields(_ROWS, 7) == {
        "generated_at": "2026-06-01 08:00:00",
        "strategy": "weighted",
    }
    # 行存在但值缺失：返回缺失值本身（喂进合同走词表缺失态，不是 _UNSET）
    assert history_row_capsule_fields(_ROWS, 8) == {"generated_at": None, "strategy": ""}


def test_capsule_fields_not_found_is_honest_degradation():
    # 查不到（如 limit-30 外旧版本）→ 空 dict → 胶囊「-」。这是有意降级不是漏查：
    # 胶囊是上下文回显，不为它另发查询（防后人误修成查库补数据）
    assert history_row_capsule_fields(_ROWS, 99) == {}
    assert history_row_capsule_fields(None, 7) == {}
    assert history_row_capsule_fields(_ROWS, "abc") == {}


# ---------- 页面契约（真应用渲染） ----------


def _seed_history(db_path: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
    conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')"
    )
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
    conn.execute(
        "INSERT INTO Schedule (op_id, start_time, end_time, version)"
        " VALUES (?, '2026-06-01 08:00:00', '2026-06-05 18:00:00', 7)",
        (op_id,),
    )
    conn.commit()
    conn.close()


def _capsule_html(html: str) -> str:
    assert 'class="aps-plan-capsule"' in html, "胶囊容器未渲染"
    start = html.index('class="aps-plan-capsule"')
    return html[start : html.index("</div>", start)]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        # 跳过 WorkbenchLink 导航面包屑（.aps-dashboard-action-context）——它含「v7，方案身份，日期」
        # 是链接去向上下文（item#11 全站契约），不是「版本展示字段」，不参与正文唯一性判定
        cls = dict(attrs).get("class") or ""
        if self._skip_depth or "aps-dashboard-action-context" in cls:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = str(data or "").strip()
        if text:
            self.parts.append(text)


def _visible_text_excluding_breadcrumb(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return "\n".join(parser.parts)


def test_dashboard_capsule_fed_and_chrome_deduped(app_client, db_env):
    _seed_history(db_env)
    html = app_client.get("/").get_data(as_text=True)
    capsule = _capsule_html(html)
    # 喂参落点实证：第二次发布（latest_plan_context 构造处）喂参未被覆盖
    assert "v7" in capsule
    assert "2026年6月1日 08:00" in capsule
    assert "综合优先级和交期" in capsule
    # 去重实证：今日待处理 muted 行不再渲染 version_label·plan_role_label
    assert "今日待处理" in html
    workbench_start = html.index("今日待处理")
    muted_section = html[workbench_start : workbench_start + 600]
    assert "v7 ·" not in muted_section
    # 4.2 阶段二正文唯一性：版本号作为独立展示字段只剩壳层胶囊一处——删 stat-grid 版本卡
    # （label「当前查看版本」）+ risk latest_version 卡（label「当前计划」）+「当前查看排产」卡。
    assert "当前查看版本" not in html
    assert "当前查看排产" not in html
    # 剔除胶囊与链接面包屑后，正文可见文本无第二处版本号
    body_visible = _visible_text_excluding_breadcrumb(html.replace(capsule, ""))
    assert "v7" not in body_visible


def test_gantt_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    capsule = _capsule_html(app_client.get("/scheduler/gantt?version=7").get_data(as_text=True))
    assert "v7" in capsule
    assert "2026年6月1日 08:00" in capsule


def test_analysis_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    capsule = _capsule_html(app_client.get("/scheduler/analysis?version=7").get_data(as_text=True))
    assert "2026年6月1日 08:00" in capsule


def test_week_plan_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    capsule = _capsule_html(app_client.get("/scheduler/week-plan?version=7").get_data(as_text=True))
    assert "2026年6月1日 08:00" in capsule


def test_reports_capsule_fed(app_client, db_env):
    # reports 多入口共用 _publish_report_context：抽超期页做页面断言，
    # 公共取数由 history_row_capsule_fields 单测覆盖
    _seed_history(db_env)
    capsule = _capsule_html(app_client.get("/reports/overdue?version=7").get_data(as_text=True))
    assert "2026年6月1日 08:00" in capsule


def _seed_two_versions(db_path: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    # v7 旧版本（早时间/weighted）、v8 最新版本（晚时间/greedy）
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (8, '2026-06-10 09:00:00', 'greedy', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
    conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')"
    )
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
    for version, start, end in (
        (7, "2026-06-01 08:00:00", "2026-06-05 18:00:00"),
        (8, "2026-06-10 09:00:00", "2026-06-12 18:00:00"),
    ):
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, version) VALUES (?, ?, ?, ?)",
            (op_id, start, end, version),
        )
    conn.commit()
    conn.close()


def test_reports_index_old_version_capsule_shows_that_version(app_client, db_env):
    # #6：报表首页带旧版本号（非最新 v7，最新是 v8）时，胶囊须回显 v7 的生成时间/策略，
    # 而非因原 limit=1 只取最新版导致显示「-」。
    _seed_two_versions(db_env)
    html = app_client.get("/reports/?version=7").get_data(as_text=True)
    capsule = _capsule_html(html)
    assert "v7" in capsule
    assert "2026年6月1日 08:00" in capsule  # v7 的生成时间
    assert "综合优先级和交期" in capsule  # weighted → v7 策略
    assert "2026年6月10日 09:00" not in capsule  # 不是最新 v8 的时间


def test_resource_dispatch_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    capsule = _capsule_html(app_client.get("/scheduler/resource-dispatch?version=7").get_data(as_text=True))
    assert "2026年6月1日 08:00" in capsule


def test_basic_data_page_renders_no_capsule(app_client, db_env):
    _seed_history(db_env)
    html = app_client.get("/material/materials").get_data(as_text=True)
    assert 'class="aps-plan-capsule"' not in html


def test_url_fallback_renders_base_fields_without_query(app_client, db_env):
    # 无发布点页面带 ?version=N：胶囊渲染基础字段，generated_at/strategy 为「-」
    # （URL 不含此信息，不查库补——胶囊是回显不是查询入口）
    _seed_history(db_env)
    html = app_client.get("/system/history?version=7").get_data(as_text=True)
    capsule = _capsule_html(html)
    assert "v7" in capsule
    assert "2026年6月1日 08:00" not in capsule
