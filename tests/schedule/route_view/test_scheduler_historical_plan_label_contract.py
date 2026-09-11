"""守护被新版本替代的 adopted 方案在各页面/导出处统一显示为「历史正式方案（已被新版本替代）」：甘特图、周计划页与导出、reports 首页、资源派工、超期清单筛选项均以该历史标签替代「正式采用方案」，public_plan_role_options 不再生成重复候选标签，build_report_context 优先采用 plan_identity 的 user_label，且未知 plan_role 重定向不泄露原始 role。"""

from __future__ import annotations

import json
import os
from urllib.parse import unquote

from core.services.scheduler.schedule_plan_option_display import public_plan_role_options
from tests._support.schedule_retirement import (
    assert_retired_scope,
    capture_schedule_context,
    initialize_read_fixture,
    projection_text,
)
from tests.web_pages.reports_workbench_backlink_helpers import _client as _fixture_client
from tests.web_pages.reports_workbench_backlink_helpers import _xlsx_sheet_rows
from web.viewmodels.scheduler_reports_workbench import build_report_context


def _client():
    """Keep the existing v12 plan fixture; settle startup defaults before reads."""
    client = _fixture_client()
    initialize_read_fixture(client.application)
    return client


def _seed_newer_executable_version(version: int) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        source = conn.execute("SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 LIMIT 1").fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source["op_id"],
                source["machine_id"],
                source["operator_id"],
                "2026-05-07 08:00:00",
                "2026-05-07 12:00:00",
                "unlocked",
                version,
            ),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                "priority_first",
                1,
                1,
                "success",
                json.dumps({"algo": {"metrics": {"machine_util_avg": 0.8}}}, ensure_ascii=False),
                "pytest",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _assert_context_plan_label(context: dict, expected: str) -> None:
    """The real v12 resolution must stay historical after v13 is persisted."""
    plan = context["plan_resolution"]
    assert plan["version"] == 12 and context["version"] == 12
    assert plan["source_table"] == "schedule" and plan["scenario_id"] is None
    assert plan["user_label"] == expected
    assert plan["plan_identity"]["is_superseded_by_newer_version"] is True
    assert not plan["can_write_feedback"] and not plan["can_dispatch"]


def _assert_selected_plan_option_label(options, expected: str) -> None:
    """Inspect the actual public option values, not a removed select element."""
    selected, = [option for option in options if option["role"] == "adopted"]
    assert selected["display_text"] == expected
    assert "正式采用方案·正式采用方案" not in projection_text(options)


def test_gantt_page_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    path = "/scheduler/gantt?view=machine&version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
    context = capture_schedule_context(
        client, endpoint="scheduler.gantt_page", path=path, template="scheduler/gantt.html",
    )
    _assert_context_plan_label(context, "历史正式方案（已被新版本替代）")
    _assert_selected_plan_option_label(context["plan_role_options"], "历史正式方案（已被新版本替代）")
    assert_retired_scope(client, path, message="未忽略条件后跳转")


def test_week_plan_page_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    path = "/scheduler/week-plan?version=12&plan_role=adopted&week_start=2026-05-06"
    context = capture_schedule_context(
        client, endpoint="scheduler.week_plan_page", path=path, template="scheduler/week_plan.html",
    )
    _assert_context_plan_label(context, "历史正式方案（已被新版本替代）")
    _assert_selected_plan_option_label(context["plan_role_options"], "历史正式方案（已被新版本替代）")
    assert_retired_scope(client, path)


def test_week_plan_export_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    resp = client.get("/scheduler/week-plan/export?version=12&plan_role=adopted&week_start=2026-05-06")
    disposition = unquote(str(resp.headers.get("Content-Disposition") or ""))
    summary_rows = _xlsx_sheet_rows(resp.data, "查询摘要")
    summary = {str(row[0] or ""): str(row[1] or "") for row in summary_rows if row and row[0]}

    assert resp.status_code == 200
    assert "历史正式方案" in disposition
    assert summary["导出类型"] == "周计划导出"
    assert summary["方案"] == "历史正式方案（已被新版本替代）"
    assert "历史版本" in summary["提示"]
    assert summary["方案"] != "正式采用方案"


def test_week_plan_export_unknown_plan_role_redirect_does_not_leak_raw_role() -> None:
    client = _client()

    resp = client.get("/scheduler/week-plan/export?version=12&plan_role=future_role&week_start=2026-05-06")
    location = unquote(str(resp.headers.get("Location") or ""))

    assert resp.status_code == 302
    assert "future_role" not in location


def test_reports_index_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    path = "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
    context = capture_schedule_context(
        client, endpoint="reports.index", path=path, template="reports/index.html",
    )
    workbench = context["reports_workbench"]
    assert workbench["context"]["version"] == 12
    assert workbench["context"]["plan_role_label"] == "历史正式方案（已被新版本替代）"
    assert workbench["context"]["can_write_feedback"] is False
    public = projection_text(workbench["entry_cards"], workbench["workbench_links"])
    assert "历史版本、模拟预览和对比参考方案只能查看" in public
    assert "复盘正式方案" not in public
    assert "查看计划和现场实际" in public
    assert_retired_scope(client, path)


def test_resource_dispatch_labels_superseded_adopted_option_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    path = ("/scheduler/resource-dispatch?version=12&plan_role=adopted"
            "&period_preset=week&query_date=2026-05-06&start_date=2026-05-06&end_date=2026-05-06")
    context = capture_schedule_context(
        client, endpoint="scheduler.resource_dispatch_page", path=path, template="scheduler/resource_dispatch.html",
    )
    assert context["filters"]["version"] == 12
    assert context["filters"]["can_write_feedback"] is False
    _assert_selected_plan_option_label(context["plan_role_options"], "历史正式方案（已被新版本替代）")
    assert_retired_scope(client, path)


def test_report_filter_option_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    path = "/reports/overdue?version=12&plan_role=adopted"
    context = capture_schedule_context(
        client, endpoint="reports.overdue_page", path=path, template="reports/overdue.html",
    )
    assert context["version"] == 12
    assert context["selected_plan_role"] == "adopted"
    _assert_selected_plan_option_label(context["plan_options"], "历史正式方案（已被新版本替代）")
    body = assert_retired_scope(client, path)
    assert "/reports/overdue/export" in body


def test_public_plan_role_options_use_historical_label_without_duplicate_candidate() -> None:
    [option] = public_plan_role_options(
        {
            "is_superseded_by_newer_version": True,
            "available_roles": [
                {
                    "role": "adopted",
                    "label": "正式采用方案",
                    "source_table": "schedule",
                    "candidate_label": "正式采用方案",
                }
            ],
        }
    )

    assert option["display_text"] == "历史正式方案（已被新版本替代）"
    assert option["display_candidate_label"] == ""


def test_public_plan_role_options_uses_superseded_label_when_option_source_missing() -> None:
    [option] = public_plan_role_options(
        {
            "is_superseded_by_newer_version": True,
            "available_roles": [{"role": "adopted", "label": "正式采用方案"}],
        }
    )

    assert option["display_text"] == "历史正式方案（已被新版本替代）"


def test_report_context_prefers_plan_identity_user_label() -> None:
    context = build_report_context(
        version=12,
        plan_resolution={
            "selected_role": "adopted",
            "selected_label": "正式采用方案",
            "scenario_display_name": "容易误导的旧场景名",
            "user_label": "历史正式方案（已被新版本替代）",
        },
        date_from="2026-05-06",
        date_to="2026-05-06",
    )

    assert context["plan_role_label"] == "历史正式方案（已被新版本替代）"
