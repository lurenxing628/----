from __future__ import annotations

from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from tests.reports_workbench_backlink_helpers import (
    INTERNAL_VISIBLE_TOKENS,
    _client,
    _href_with_text,
    _href_with_text_and_class,
    _href_with_text_and_fragment,
    _html_for,
    _parser_for,
    _query,
    _visible_text,
)


def _assert_query_values(query: Dict[str, List[str]], expected: Dict[str, str]) -> None:
    for key, value in expected.items():
        assert query[key] == [value], (key, query)


def _target_visible(client, href: str) -> str:
    resp = client.get(href)
    assert resp.status_code == 200, href
    parser = _parser_for(client, href)
    return _visible_text(parser)


def _assert_public_visible_text(text: str) -> None:
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in text


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

    expectations = (
        ("查看超期清单", "/reports/overdue", {"version": "12", "plan_role": "adopted", "batch_id": "B-RPT"}, "超期"),
        ("排产分析", "/scheduler/analysis", {"version": "12", "plan_role": "adopted"}, "排产分析"),
        ("设备甘特图", "/scheduler/gantt", {"version": "12", "plan_role": "adopted", "view": "machine"}, "甘特图"),
        ("人员甘特图", "/scheduler/gantt", {"version": "12", "plan_role": "adopted", "view": "operator"}, "甘特图"),
        ("资源派工", "/scheduler/resource-dispatch", {"version": "12", "plan_role": "adopted", "scope_type": "machine"}, "资源排班"),
        ("计划和现场实际", "/reports/execution-review", {"version": "12", "plan_role": "adopted", "batch_id": "B-RPT"}, "正式采用方案"),
        ("查看资源负荷", "/reports/utilization", {"version": "12", "plan_role": "adopted", "resource_type": "machine"}, "资源负荷"),
    )
    for label, path, expected_query, expected_text in expectations:
        href = _href_with_text(parser, label, path)
        query = _query(href)
        _assert_query_values(query, expected_query)
        target_text = _target_visible(client, href)
        assert expected_text in target_text
        _assert_public_visible_text(target_text)


def test_workbench_report_rows_keep_batch_and_resource_context_when_returning_to_action_pages() -> None:
    client = _client()
    overdue = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    gantt = _query(_href_with_text_and_fragment(overdue, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    dispatch = _query(_href_with_text_and_fragment(overdue, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))

    assert gantt["version"] == ["12"]
    assert gantt["plan_role"] == ["adopted"]
    assert gantt["gantt_batch"] == ["B-RPT"]
    assert gantt["gantt_resource"] == ["M-RPT"]
    assert dispatch["version"] == ["12"]
    assert dispatch["plan_role"] == ["adopted"]
    assert dispatch["batch_id"] == ["B-RPT"]
    assert dispatch["scope_type"] == ["machine"]
    assert dispatch["machine_id"] == ["M-RPT"]

    utilization = _parser_for(
        client,
        "/reports/utilization?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=operator&resource_id=O-RPT",
    )
    row_dispatch = _query(
        _href_with_text_and_fragment(utilization, "查看资源排班", "/scheduler/resource-dispatch", "operator_id=O-RPT")
    )
    row_gantt = _query(_href_with_text_and_fragment(utilization, "定位甘特", "/scheduler/gantt", "gantt_resource=O-RPT"))

    assert row_dispatch["version"] == ["12"]
    assert row_dispatch["scope_type"] == ["operator"]
    assert row_dispatch["operator_id"] == ["O-RPT"]
    assert row_gantt["view"] == ["operator"]
    assert row_gantt["gantt_resource"] == ["O-RPT"]


def test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese() -> None:
    client = _client()
    path = (
        "/scheduler/analysis?version=12&plan_role=baseline_best"
        "&date_from=2026-05-06&date_to=2026-05-06"
    )
    html = _html_for(client, path)
    parser = _parser_for(client, path)
    visible = _visible_text(parser)

    assert not [
        link
        for link in parser.links
        if urlparse(link["href"]).path == "/reports/execution-review"
    ]
    assert 'aria-disabled="true"' in html
    assert "计划和现场实际只复盘正式采用方案" in html
    _assert_public_visible_text(visible)

    home_href = _href_with_text_and_class(parser, "首页值班台", "/", "aps-workbench-nav-link")
    home_query = parse_qs(urlparse(home_href).query)
    assert home_query["version"] == ["12"]
    assert home_query["plan_role"] == ["baseline_best"]
