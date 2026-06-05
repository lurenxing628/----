from __future__ import annotations

import json
import os
import re
from urllib.parse import unquote

from core.services.scheduler.schedule_plan_option_display import public_plan_role_options
from tests.reports_workbench_backlink_helpers import _client, _html_for, _xlsx_sheet_rows
from web.viewmodels.scheduler_reports_workbench import build_report_context


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


def _assert_context_plan_label(html: str, expected: str) -> None:
    pattern = (
        r'<span class="aps-context-label">\s*方案\s*</span>\s*'
        r'<span class="aps-context-value">\s*' + re.escape(expected) + r"\s*</span>"
    )
    assert re.search(pattern, html), html
    wrong_pattern = (
        r'<span class="aps-context-label">\s*方案\s*</span>\s*'
        r'<span class="aps-context-value">\s*正式采用方案\s*</span>'
    )
    assert not re.search(wrong_pattern, html), html


def _assert_selected_plan_option_label(html: str, expected: str) -> None:
    selected_option = re.search(
        r'<option value="adopted"[^>]*selected[^>]*>\s*(.*?)\s*</option>',
        html,
        re.S,
    )
    assert selected_option, html
    option_text = re.sub(r"\s+", "", selected_option.group(1))
    assert expected in option_text, selected_option.group(0)
    assert "正式采用方案·正式采用方案" not in re.sub(r"\s+", "", html)


def test_gantt_page_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    html = _html_for(
        client,
        "/scheduler/gantt?view=machine&version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06",
    )

    _assert_context_plan_label(html, "历史正式方案（已被新版本替代）")
    _assert_selected_plan_option_label(html, "历史正式方案（已被新版本替代）")


def test_week_plan_page_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    html = _html_for(client, "/scheduler/week-plan?version=12&plan_role=adopted&week_start=2026-05-06")

    _assert_context_plan_label(html, "历史正式方案（已被新版本替代）")
    _assert_selected_plan_option_label(html, "历史正式方案（已被新版本替代）")


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

    html = _html_for(
        client,
        "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06",
    )

    assert "这是历史正式方案，只能查看" in html
    assert "复盘正式方案" not in html
    assert "查看计划和现场实际" in html


def test_resource_dispatch_labels_superseded_adopted_option_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    html = _html_for(
        client,
        "/scheduler/resource-dispatch?version=12&plan_role=adopted"
        "&period_preset=week&query_date=2026-05-06&start_date=2026-05-06&end_date=2026-05-06",
    )

    _assert_selected_plan_option_label(html, "历史正式方案（已被新版本替代）")


def test_report_filter_option_labels_superseded_adopted_version_as_historical() -> None:
    client = _client()
    _seed_newer_executable_version(13)

    html = _html_for(client, "/reports/overdue?version=12&plan_role=adopted")

    _assert_selected_plan_option_label(html, "历史正式方案（已被新版本替代）")


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
