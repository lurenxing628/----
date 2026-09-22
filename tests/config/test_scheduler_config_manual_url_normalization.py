"""回归测试：说明书页“本页说明”通道的参数规范化与章节截取——``_normalize_scheduler_manual_args`` 接受同源绝对 src（保留末尾问号）、从返回地址里剥掉未知 plan_role、对未登记的 page 返回 None 并给出不回显页面标识的提示；``_manual_section_map`` 按标题截到下一个同级或更高级标题为止；``_build_manual_page_view_state`` 在章节缺失或说明书不可用时退化为整本且返回地址仍指向工作台视图。"""

from __future__ import annotations

import pytest
from flask import Flask

import web.routes.workbench.manual_page as route_mod
from web.viewmodels.page_manuals_registry import manual_entry

SAMPLE_MANUAL = (
    "# 系统使用说明\n\n前言。\n\n"
    "## 0. 开头\n\n### 值班台怎么看\n\n值班台正文。\n\n"
    "## 6. 排产操作：完整指南\n\n总述。\n\n"
    "### 6.1 批次管理\n\n批次正文。\n\n#### 批次详情和补充工序\n\n详情正文。\n\n"
    "### 6.2 执行排产\n\n排产正文。\n\n"
    "```\n### 6.3 围栏里的假标题\n```\n\n"
    "## 11. 系统管理\n\n系统正文。\n\n### 6.1 批次管理\n\n重名标题。\n"
)


def _app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule("/scheduler/config/manual", endpoint="scheduler.config_manual_page", view_func=lambda: "")
    app.add_url_rule("/workbench", endpoint="workbench.index", view_func=lambda: "")
    app.add_url_rule("/workbench/trial", endpoint="workbench.trial", view_func=lambda: "")
    return app


def test_normalize_args_accepts_same_origin_absolute_src_and_flags_unregistered_page() -> None:
    with _app().test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, entry, warning = route_mod._normalize_scheduler_manual_args(
            "http://localhost/workbench?view=gantt", "bad.page"
        )
    assert safe_src == "/workbench?view=gantt"
    assert safe_page is None and entry is None
    # 页面标识是内部名，不进用户提示；提示只说明已经改开整本说明书。
    assert warning == route_mod.PAGE_NOT_REGISTERED_WARNING
    assert "bad.page" not in warning and "整本说明书" in warning


def test_normalize_args_returns_registry_entry_for_registered_view() -> None:
    with _app().test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, entry, warning = route_mod._normalize_scheduler_manual_args("/workbench?view=field", "field")
    assert safe_src == "/workbench?view=field" and safe_page == "field" and warning is None
    assert entry == manual_entry("field") and entry["view"] == "field" and entry["title"] == "现场记录"


def test_normalize_args_drops_unknown_plan_role_and_keeps_trailing_question_mark() -> None:
    with _app().test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, _entry, warning = route_mod._normalize_scheduler_manual_args(
            "/reports/execution-review?version=12&plan_role=future_role&date_from=2026-05-06", "reports"
        )
        trailing, trailing_page, _, _ = route_mod._normalize_scheduler_manual_args("http://localhost/workbench?", "gantt")
    assert safe_src == "/reports/execution-review?version=12&date_from=2026-05-06"
    assert "future_role" not in safe_src and safe_page == "reports" and warning is None
    assert trailing == "/workbench?" and trailing_page == "gantt"


def test_workbench_view_url_and_full_manual_section_url() -> None:
    with _app().test_request_context("/", base_url="http://localhost/"):
        assert route_mod._workbench_view_url("trial") == "/workbench/trial"
        assert route_mod._workbench_view_url("gantt") == "/workbench?view=gantt"
        assert route_mod._build_full_manual_section_url("/workbench?view=gantt", "") == ""
        assert route_mod._build_full_manual_section_url("", "6-4计划甘特") == "/scheduler/config/manual#6-4计划甘特"
        with_src = route_mod._build_full_manual_section_url("/workbench?view=gantt", "6-4计划甘特")
    assert with_src.startswith("/scheduler/config/manual?src=") and with_src.endswith("#6-4计划甘特")
    assert "view%3Dgantt" in with_src


def test_manual_section_map_collects_children_and_stops_at_sibling_or_parent() -> None:
    sections = route_mod._manual_section_map(SAMPLE_MANUAL)
    batches = sections["6.1 批次管理"]
    assert batches["level"] == 3 and batches["anchor"] == "6-1批次管理"
    assert batches["source"].startswith("### 6.1 批次管理\n")
    assert "批次详情和补充工序" in batches["source"] and "详情正文" in batches["source"]
    assert "6.2 执行排产" not in batches["source"] and "重名标题" not in batches["source"]
    chapter = sections["6. 排产操作：完整指南"]
    assert "批次正文" in chapter["source"] and "排产正文" in chapter["source"] and "系统正文" not in chapter["source"]
    assert "围栏里的假标题" in sections["6.2 执行排产"]["source"]
    assert "6.3 围栏里的假标题" not in sections
    assert sections["值班台怎么看"]["source"] == "### 值班台怎么看\n\n值班台正文。\n\n"
    assert "" not in sections


def test_view_state_full_mode_when_no_entry() -> None:
    state = route_mod._build_manual_page_view_state(
        entry=None, manual_text=SAMPLE_MANUAL, manual_available=True, link_src="/workbench?view=batches", back_url="/workbench?view=batches"
    )
    assert state["manual_mode"] == "full" and state["current_manual"] is None and state["related_manuals"] == []
    assert state["fallback_text"] == SAMPLE_MANUAL and state["full_manual_section_url"] == ""
    assert state["page_title"] == route_mod.FULL_MANUAL_TITLE and state["download_button_label"] == "下载说明书原文"
    assert state["back_url"] == "/workbench?view=batches" and state["back_button_label"] == "返回刚才页面"
    assert state["page_warning"] is None


def test_view_state_page_mode_extracts_section_and_related_links() -> None:
    entry = dict(manual_entry("batches"), related=("run", "dashboard"))
    with _app().test_request_context("/", base_url="http://localhost/"):
        state = route_mod._build_manual_page_view_state(
            entry=entry, manual_text=SAMPLE_MANUAL, manual_available=True, link_src="/workbench?view=batches", back_url="/workbench?view=batches"
        )
    assert state["manual_mode"] == "page" and state["page_warning"] is None
    assert state["fallback_text"].startswith("### 6.1 批次管理\n") and "6.2 执行排产" not in state["fallback_text"]
    assert state["page_title"] == "本页说明 - 批次管理" and state["download_button_label"] == "下载整本说明书"
    assert state["full_manual_section_url"].endswith("#6-1批次管理")
    current = state["current_manual"]
    assert current["view"] == current["manual_id"] == "batches" and current["anchor"] == "6-1批次管理"
    assert current["heading"] == "6.1 批次管理" and current["full_manual_label"] == route_mod.FULL_MANUAL_LABEL
    related = state["related_manuals"]
    assert [item["view"] for item in related] == ["run", "dashboard"]
    assert related[0]["title"] == "执行排产" and related[0]["url"].startswith("/scheduler/config/manual?")
    assert "page=run" in related[0]["url"] and "src=" in related[0]["url"] and related[0]["preview_sections"] == []
    assert related[0]["full_manual_section_url"].endswith("#6-2执行排产")
    assert related[1]["full_manual_section_url"].endswith("#值班台怎么看")


def test_view_state_page_mode_back_url_falls_back_to_workbench_view() -> None:
    with _app().test_request_context("/", base_url="http://localhost/"):
        state = route_mod._build_manual_page_view_state(
            entry=manual_entry("trial"), manual_text="## 6. 排产操作：完整指南\n\n### 6.6 试调排产方案\n\n正文\n",
            manual_available=True, link_src="", back_url=None
        )
        gantt = route_mod._build_manual_page_view_state(
            entry=manual_entry("gantt"), manual_text="### 6.4 计划甘特\n\n正文\n", manual_available=True, link_src="", back_url=None
        )
    assert state["manual_mode"] == "page"
    assert state["back_url"] == "/workbench/trial" and state["back_button_label"] == "返回试调排产方案"
    assert state["full_manual_section_url"] == "/scheduler/config/manual#6-6试调排产方案"
    assert gantt["back_url"] == "/workbench?view=gantt" and gantt["back_button_label"] == "返回计划甘特"


def test_view_state_degrades_to_full_when_heading_missing_or_manual_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    app = _app()
    with app.test_request_context("/", base_url="http://localhost/"):
        with caplog.at_level("WARNING"):
            missing = route_mod._build_manual_page_view_state(
                entry=manual_entry("system"), manual_text=SAMPLE_MANUAL.replace("## 11. 系统管理", "## 11. 别的标题"),
                manual_available=True, link_src="/workbench?view=system", back_url=None
            )
        unavailable = route_mod._build_manual_page_view_state(
            entry=manual_entry("system"), manual_text="找不到说明书文件，可能安装包里没带或文件被删了。请联系维护人员。",
            manual_available=False, link_src="", back_url=None
        )
    assert missing["manual_mode"] == "full" and missing["current_manual"] is None and missing["related_manuals"] == []
    assert missing["page_warning"] == route_mod.PAGE_SECTION_MISSING_WARNING
    assert missing["back_url"] == "/workbench?view=system" and missing["back_button_label"] == "返回系统管理"
    assert any("11. 系统管理" in record.getMessage() and "system" in record.getMessage() for record in caplog.records)
    assert unavailable["manual_mode"] == "full" and unavailable["page_warning"] is None
    assert unavailable["fallback_text"].startswith("找不到说明书文件") and unavailable["back_url"] == "/workbench?view=system"


def test_related_links_reject_unregistered_view() -> None:
    entry = dict(manual_entry("system"), related=("no_such_view",))
    with _app().test_request_context("/", base_url="http://localhost/"):
        with pytest.raises(ValueError, match="no_such_view"):
            route_mod._build_related_manual_links(entry, "", {})
