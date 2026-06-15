"""回归测试：守护 /reports/execution-review 现场复盘只对「正式采用方案」开放——baseline_best/未知 plan_role/模拟预览 scenario 等非正式身份会被可见拦截且禁用导出（含 /export 返回 400），不泄露原始 role；历史正式版本只读可见，资源过滤导出仍保留正式行。"""

from __future__ import annotations

import os
from typing import List
from urllib.parse import urlparse

import pytest

from core.infrastructure.database import get_connection
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.report.execution_review import ExecutionReviewMixin
from tests.web_pages.reports_workbench_backlink_helpers import (
    _assert_public_output_boundaries,
    _client,
    _href_with_text_and_fragment,
    _parser_for,
    _visible_text,
    _xlsx_text,
)


def _seed_historical_adopted_version() -> None:
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (11)")
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            SELECT op_id, machine_id, operator_id, start_time, end_time, lock_status, 11
            FROM Schedule
            WHERE version = 12
            LIMIT 1
            """
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (11, 'priority_first', 1, 1, 'success', '{}', 'pytest')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _export_links(parser) -> List[str]:
    return [
        link["href"]
        for link in parser.links
        if urlparse(link["href"]).path == "/reports/execution-review/export"
    ]


def _assert_no_adopted_continuation_links(parser) -> None:
    hrefs = [link["href"] for link in parser.links]
    assert all(urlparse(href).path != "/scheduler/resource-dispatch" for href in hrefs)
    assert all(urlparse(href).path != "/reports/execution-review" for href in hrefs)
    assert all("scenario_id=SCENARIO-RPT" not in href for href in hrefs)


class _ReviewResolution:
    def to_dict(self):
        return {"plan_identity": {"user_label": "正式采用方案"}}


class _NoFeedbackService:
    def get_execution_state_for_scopes(self, scopes):
        return {}


class _ReviewHost(ExecutionReviewMixin):
    def __init__(self) -> None:
        self.calls = []
        self.execution_feedback_service = _NoFeedbackService()

    def _resolve_plan(self, version, plan_role, scenario_id=None):
        self.calls.append(("resolve", version, plan_role, scenario_id))
        return _ReviewResolution()

    def _list_plan_rows_between(self, **kwargs):
        self.calls.append(("between", kwargs))
        return []

    def _list_plan_rows_all(self, **kwargs):
        self.calls.append(("all", kwargs))
        return []


def test_execution_review_service_hard_pins_adopted_null_scope() -> None:
    host = _ReviewHost()

    host.execution_review(
        12,
        date_from="2026-05-06",
        date_to="2026-05-06",
        resource_type="machine",
        resource_id="M-RPT",
    )
    host.execution_review(12)

    assert host.calls[0] == ("resolve", 12, ROLE_ADOPTED, None)
    assert host.calls[1][0] == "between"
    assert host.calls[1][1]["plan_role"] == ROLE_ADOPTED
    assert host.calls[1][1]["scenario_id"] is None
    assert host.calls[2] == ("resolve", 12, ROLE_ADOPTED, None)
    assert host.calls[3][0] == "all"
    assert host.calls[3][1]["plan_role"] == ROLE_ADOPTED
    assert host.calls[3][1]["scenario_id"] is None


def test_execution_review_direct_candidate_request_is_visible_blocked() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/execution-review?version=12&plan_role=baseline_best"
        "&date_from=2026-05-06&date_to=2026-05-06&batch_id=B-RPT",
    )
    visible = _visible_text(parser)

    assert "计划和现场实际只复盘正式采用方案" in visible
    assert "原算法代表方案" in visible
    assert "不能当作正式现场复盘显示" in visible
    assert "查看现场记录入口" not in visible
    assert _export_links(parser) == []
    _assert_no_adopted_continuation_links(parser)


def test_execution_review_unknown_plan_role_does_not_leak_raw_role() -> None:
    client = _client()
    resp = client.get("/reports/execution-review?version=12&plan_role=future_role")
    parser = _parser_for(client, "/reports/execution-review?version=12&plan_role=future_role")
    body = resp.get_data(as_text=True)
    visible = _visible_text(parser)

    assert resp.status_code == 200
    assert "计划和现场实际只复盘正式采用方案" in visible
    assert "未知方案身份" in visible
    assert "future_role" not in body
    assert "future_role" not in visible
    assert _export_links(parser) == []


def test_execution_review_direct_scenario_request_is_visible_blocked() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/execution-review?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT"
        "&date_from=2026-05-06&date_to=2026-05-06",
    )
    visible = _visible_text(parser)

    assert "计划和现场实际只复盘正式采用方案" in visible
    assert "模拟预览身份" in visible
    assert "B-RPT" not in visible
    assert _export_links(parser) == []
    _assert_no_adopted_continuation_links(parser)


def test_execution_review_resource_filter_export_keeps_formal_rows() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/execution-review?version=12&date_from=2026-05-06&date_to=2026-05-06"
        "&resource_type=machine&resource_id=M-RPT",
    )
    visible = _visible_text(parser)

    assert "B-RPT" in visible
    assert "B-SAME" in visible
    assert "B-OTHER" not in visible
    assert "M-OTHER" not in visible
    export_href = _href_with_text_and_fragment(
        parser,
        "导出 Excel",
        "/reports/execution-review/export",
        "resource_id=M-RPT",
    )
    export_resp = client.get(export_href)
    export_text = _xlsx_text(export_resp.data)

    assert export_resp.status_code == 200
    assert "B-RPT" in export_text
    assert "B-SAME" in export_text
    assert "B-OTHER" not in export_text
    _assert_public_output_boundaries(parser)


def test_execution_review_historical_adopted_version_is_visible_history() -> None:
    client = _client()
    _seed_historical_adopted_version()
    parser = _parser_for(client, "/reports/execution-review?version=11")
    visible = _visible_text(parser)

    assert "历史正式方案（已被新版本替代）" in visible
    assert "这个历史版本已被更新的正式排产替代，只能查看，不能写现场事实。" in visible
    assert "排产方案\n历史正式方案（已被新版本替代）" in visible
    assert "排产方案\n正式采用方案" not in visible

    export_resp = client.get("/reports/execution-review/export?version=11")
    assert export_resp.status_code == 200
    export_text = _xlsx_text(export_resp.data)

    assert "历史正式方案（已被新版本替代）" in export_text
    assert "正式采用方案" not in export_text


@pytest.mark.parametrize(
    "query, expected",
    (
        ("plan_role=baseline_best", "原算法代表方案"),
        ("plan_role=adopted&scenario_id=SCENARIO-RPT", "模拟预览身份"),
    ),
)
def test_execution_review_export_rejects_non_formal_identity(query: str, expected: str) -> None:
    client = _client()
    resp = client.get(
        "/reports/execution-review/export?version=12&date_from=2026-05-06&date_to=2026-05-06&"
        + query
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "计划和现场实际只复盘正式采用方案" in body
    assert expected in body
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in resp.content_type
