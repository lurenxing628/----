from __future__ import annotations

import json
import os
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from tests.web_pages.reports_workbench_backlink_helpers import (
    INTERNAL_VISIBLE_TOKENS,
    _assert_public_output_boundaries,
    _client,
    _href_with_text,
    _href_with_text_and_class,
    _href_with_text_and_fragment,
    _html_for,
    _parser_for,
    _query,
    _visible_text,
)

# ---------------------------------------------------------------------------
# 合并体：workbench/首页/报表行 链接跳转时的上下文透传契约。
# 由 P5.1 MERGE 簇合并而来（方案 B：只合 flow + report_row，first_round 保持独立）。
# 共用 reports_workbench_backlink_helpers._client()（v1 UI + reports 种子，非 conftest app_client）。
# 去重仅限唯一逐字完全相同的无副作用 helper `_assert_query_values`（原 flow:22 / report_row:13，留一份）。
# ---------------------------------------------------------------------------


# 共享 helper（原两文件逐字相同，去重保留一份）
def _assert_query_values(query: Dict[str, List[str]], expected: Dict[str, str]) -> None:
    for key, value in expected.items():
        assert query[key] == [value], (key, query)


# ===========================================================================
# 迁入自 tests/regression_aps_workbench_flow_contract.py
# （4 个 test + 其本地 helper；含 ★B-6 / R57-PINNED）
# ===========================================================================


def _target_parser(client, href: str):
    return _parser_for(client, href)


def _target_visible(client, href: str) -> str:
    return _visible_text(_target_parser(client, href))


def _assert_public_visible_text(text: str) -> None:
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in text


def _public_page_surface(parser) -> str:
    return "\n".join(parser.visible_parts + parser.public_attribute_parts)


def _assert_no_execution_review_links(parser) -> None:
    assert not [
        link
        for link in parser.links
        if urlparse(link["href"]).path == "/reports/execution-review"
    ]


def _assert_read_only_home_gap(visible: str, public_surface: str) -> None:
    for text in ("当前排产摘要为空", "当前查看方案没有可用的首页摘要内容", "超期批次", "数据不足"):
        assert text in visible
    for text in ("超期批次 0", "超期批次需要先看", "资源负荷偏高", "设备利用率", "80.0%"):
        assert text not in visible
    for text in ("最新排产", "当前正式采用方案", "当前排产风险概览"):
        assert text not in public_surface


def _assert_home_workspace_links_keep_context(parser, expected_by_label: Dict[str, Dict[str, str]]) -> None:
    seen = set()
    for link in parser.links:
        expected = expected_by_label.get(link["text"])
        if expected is not None:
            _assert_query_values(_query(link["href"]), expected)
            seen.add(link["text"])
    assert seen == set(expected_by_label)


def _assert_home_link_keeps_context(parser, expected_query: Dict[str, str]) -> None:
    home_href = _href_with_text_and_class(parser, "首页值班台", "/", "aps-workbench-nav-link")
    _assert_query_values(_query(home_href), expected_query)


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


def test_workbench_main_flow_from_home_keeps_context_and_reaches_first_version_pages() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    visible = _visible_text(parser)

    assert "计划工作台" in visible
    assert "首页值班台" in visible
    assert "今日待处理" in visible
    _assert_public_visible_text(visible)
    _assert_public_output_boundaries(parser)
    _assert_home_workspace_links_keep_context(
        parser,
        {
            "设备甘特图": {
                "version": "12",
                "plan_role": "adopted",
                "start_date": "2026-05-06",
                "end_date": "2026-05-06",
            },
            "资源排班": {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
            },
            "报表中心": {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
            },
            "周计划": {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
            },
        },
    )

    expectations = (
        (
            "查看超期清单",
            "/reports/overdue",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
            "超期",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
        (
            "排产分析",
            "/scheduler/analysis",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
            "排产分析",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
        (
            "设备甘特图",
            "/scheduler/gantt",
            {
                "version": "12",
                "plan_role": "adopted",
                "view": "machine",
                "start_date": "2026-05-06",
                "end_date": "2026-05-06",
                "gantt_batch": "B-RPT",
                "gantt_resource": "M-RPT",
            },
            "甘特图",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
        (
            "人员甘特图",
            "/scheduler/gantt",
            {
                "version": "12",
                "plan_role": "adopted",
                "view": "operator",
                "start_date": "2026-05-06",
                "end_date": "2026-05-06",
                "gantt_batch": "B-RPT",
            },
            "甘特图",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
            },
        ),
        (
            "资源派工",
            "/scheduler/resource-dispatch",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "period_preset": "custom",
                "scope_type": "machine",
                "scope_id": "M-RPT",
                "machine_id": "M-RPT",
                "batch_id": "B-RPT",
            },
            "资源排班",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
        (
            "计划和现场实际",
            "/reports/execution-review",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
            "正式采用方案",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
        (
            "查看资源负荷",
            "/reports/utilization",
            {
                "version": "12",
                "plan_role": "adopted",
                "start_date": "2026-05-06",
                "end_date": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
            "资源负荷",
            {
                "version": "12",
                "plan_role": "adopted",
                "date_from": "2026-05-06",
                "date_to": "2026-05-06",
                "batch_id": "B-RPT",
                "resource_type": "machine",
                "resource_id": "M-RPT",
            },
        ),
    )
    for label, path, expected_query, expected_text, expected_home_query in expectations:
        href = _href_with_text(parser, label, path)
        query = _query(href)
        _assert_query_values(query, expected_query)
        target_parser = _target_parser(client, href)
        target_text = _visible_text(target_parser)
        assert expected_text in target_text
        _assert_public_visible_text(target_text)
        _assert_public_output_boundaries(target_parser)
        _assert_home_link_keeps_context(target_parser, expected_home_query)


# ★B-6 / R57-PINNED — 非 adopted（plan_role=baseline_best）复盘入口被有意禁用，
# 且首页链接逐字透传非 adopted 的 plan_role（绝不改写成 adopted）。
# 整函数原样搬入：:346/:347/:352/:353/:354/:355 透传断言禁去重、禁与主流程 adopted 同义合并。
def test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese() -> None:
    client = _client()
    path = (
        "/scheduler/analysis?version=12&plan_role=baseline_best"
        "&date_from=2026-05-06&date_to=2026-05-06"
    )
    html = _html_for(client, path)
    parser = _parser_for(client, path)
    visible = _visible_text(parser)

    _assert_no_execution_review_links(parser)
    assert 'aria-disabled="true"' in html
    assert "计划和现场实际只复盘正式采用方案" in html
    _assert_public_visible_text(visible)

    home_href = _href_with_text_and_class(parser, "首页值班台", "/", "aps-workbench-nav-link")
    home_query = parse_qs(urlparse(home_href).query)
    assert home_query["version"] == ["12"]
    assert home_query["plan_role"] == ["baseline_best"]
    assert home_query["date_from"] == ["2026-05-06"]
    assert home_query["date_to"] == ["2026-05-06"]

    home_html = _html_for(client, home_href)
    home_parser = _parser_for(client, home_href)
    _assert_no_execution_review_links(home_parser)
    assert "计划和现场实际只复盘正式采用方案" in home_html


def test_workbench_scenario_preview_home_entry_is_read_only_and_does_not_use_current_summary() -> None:
    client = _client()
    analysis = _parser_for(
        client,
        "/scheduler/analysis?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT"
        "&date_from=2026-05-06&date_to=2026-05-06&batch_id=B-RPT"
        "&resource_type=machine&resource_id=M-RPT",
    )
    home_href = _href_with_text_and_class(analysis, "首页值班台", "/", "aps-workbench-nav-link")
    html = _html_for(client, home_href)
    parser = _parser_for(client, home_href)
    visible = _visible_text(parser)
    public_surface = _public_page_surface(parser)

    assert "测试模拟方案" in visible
    _assert_read_only_home_gap(visible, public_surface)
    _assert_no_execution_review_links(parser)
    assert "计划和现场实际只复盘正式采用方案" in html
    _assert_public_visible_text(visible)
    _assert_public_output_boundaries(parser)

    analysis_query = _query(_href_with_text(parser, "排产分析", "/scheduler/analysis"))
    _assert_query_values(
        analysis_query,
        {
            "version": "12",
            "plan_role": "adopted",
            "scenario_id": "SCENARIO-RPT",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "resource_type": "machine",
            "resource_id": "M-RPT",
        },
    )


def test_workbench_superseded_adopted_home_entry_keeps_guardrail() -> None:
    client = _client()
    _seed_newer_executable_version(13)
    analysis = _parser_for(
        client,
        "/scheduler/analysis?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    home_href = _href_with_text_and_class(analysis, "首页值班台", "/", "aps-workbench-nav-link")
    home_query = _query(home_href)

    _assert_query_values(
        home_query,
        {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "resource_type": "machine",
            "resource_id": "M-RPT",
        },
    )

    home_html = _html_for(client, home_href)
    home_parser = _parser_for(client, home_href)
    visible = _visible_text(home_parser)
    public_surface = _public_page_surface(home_parser)

    assert "历史正式方案（已被新版本替代）" in visible
    _assert_read_only_home_gap(visible, public_surface)
    _assert_public_output_boundaries(home_parser)
    _assert_no_execution_review_links(home_parser)
    assert "这是历史正式方案，只能查看" in home_html


# ===========================================================================
# 迁入自 tests/regression_aps_workbench_report_row_links_contract.py
# （1 个 public test + 2 私有 helper；其本地 _assert_query_values 与上方逐字相同已去重）
# ===========================================================================


def test_workbench_report_rows_keep_batch_and_resource_context_when_returning_to_action_pages() -> None:
    client = _client()

    _assert_overdue_row_workbench_links(client)
    _assert_utilization_row_workbench_links(client)


def _assert_overdue_row_workbench_links(client) -> None:
    overdue = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    gantt = _query(_href_with_text_and_fragment(overdue, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    dispatch = _query(_href_with_text_and_fragment(overdue, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))

    _assert_query_values(
        gantt,
        {
            "version": "12",
            "plan_role": "adopted",
            "start_date": "2026-05-06",
            "end_date": "2026-05-06",
            "gantt_batch": "B-RPT",
            "gantt_resource": "M-RPT",
        },
    )
    _assert_query_values(
        dispatch,
        {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "scope_type": "machine",
            "machine_id": "M-RPT",
        },
    )


def _assert_utilization_row_workbench_links(client) -> None:
    utilization = _parser_for(
        client,
        "/reports/utilization?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=operator&resource_id=O-RPT",
    )
    row_dispatch = _query(
        _href_with_text_and_fragment(utilization, "查看资源排班", "/scheduler/resource-dispatch", "operator_id=O-RPT")
    )
    row_gantt = _query(_href_with_text_and_fragment(utilization, "定位甘特", "/scheduler/gantt", "gantt_resource=O-RPT"))

    _assert_query_values(
        row_dispatch,
        {
            "version": "12",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "scope_type": "operator",
            "operator_id": "O-RPT",
        },
    )
    _assert_query_values(
        row_gantt,
        {
            "start_date": "2026-05-06",
            "end_date": "2026-05-06",
            "view": "operator",
            "gantt_resource": "O-RPT",
        },
    )
