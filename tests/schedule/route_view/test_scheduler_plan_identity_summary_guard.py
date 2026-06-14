"""回归测试：当 result_summary 解析失败/缺失或版本被更新版本取代时，仪表盘、资源派工、执行复盘三处页面把它当作可见数据缺口(「当前排产摘要读取失败」等)而非 500，并据 plan_identity 关闭派工/写现场反馈入口；非法或越界 version 请求、缺失/非法/越界 overdue 与利用率指标都呈现「数据不足」而非伪造 0。"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Set
from urllib.parse import urlparse

from core.infrastructure.database import get_connection
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from tests.web_pages.reports_workbench_backlink_helpers import (
    _client,
    _html_for,
    _parser_for,
    _visible_text,
)
from web.routes.dashboard import (
    _summary_overdue_count,
    _summary_payload_dict,
    _workbench_summary_parse_state,
)


def _replace_latest_result_summary(raw_summary: str) -> None:
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        conn.execute("UPDATE ScheduleHistory SET result_summary = ? WHERE version = 12", (raw_summary,))
        conn.commit()
    finally:
        conn.close()


def _assert_no_path_links(parser, paths: Set[str]) -> None:
    assert not [
        link
        for link in parser.links
        if urlparse(link["href"]).path in paths
    ]


def _assert_bad_summary_dashboard(client) -> None:
    dashboard = _parser_for(
        client,
        "/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    dashboard_text = _visible_text(dashboard)

    assert "当前排产摘要读取失败" in dashboard_text
    assert "页面仅展示基础历史信息" in dashboard_text
    assert "超期批次需要先看" not in dashboard_text
    assert "资源负荷偏高" not in dashboard_text
    _assert_no_path_links(dashboard, {"/reports/execution-review"})


def _assert_bad_summary_dispatch(client) -> None:
    dispatch_html = _html_for(
        client,
        "/scheduler/resource-dispatch?scope_type=machine&machine_id=M-RPT"
        "&period_preset=custom&date_from=2026-05-06&date_to=2026-05-06"
        "&version=12&plan_role=adopted&batch_id=B-RPT",
    )

    assert "当前排产摘要读取失败" in dispatch_html
    assert "页面仅展示基础历史信息" in dispatch_html
    assert 'href="/reports/execution-review' not in dispatch_html
    assert "data-actual-record-url-template=" not in dispatch_html
    assert "data-actual-template-url=" not in dispatch_html
    assert "data-actual-import-url=" not in dispatch_html


def _assert_bad_summary_review(client) -> None:
    review = _parser_for(
        client,
        "/reports/execution-review?version=12&date_from=2026-05-06&date_to=2026-05-06",
    )
    review_text = _visible_text(review)

    assert "当前排产摘要读取失败" in review_text
    assert "页面仅展示基础历史信息" in review_text
    assert "当前方案只能查看，不能写现场记录。" not in review_text
    assert "查看现场记录入口" not in review_text
    assert not [
        link
        for link in review.links
        if link["text"] == "查看现场记录入口"
        and urlparse(link["href"]).path == "/scheduler/resource-dispatch"
    ]


def test_dashboard_preparsed_summary_still_obeys_plan_identity_guardrail() -> None:
    history = SimpleNamespace(
        version=12,
        result_summary={
            "overdue_batches": {"count": 3},
            "algo": {"metrics": {"machine_util_avg": 0.91}},
        },
    )
    context = {
        "requested_plan_role": "baseline_best",
        "effective_plan_role": "baseline_best",
        "source_table": "candidate_rows",
        "is_current_executable_official_version": False,
    }

    parse_state = _workbench_summary_parse_state(history, context, summary_matches_identity=False)

    assert parse_state == {"parse_failed": False}
    assert _summary_payload_dict(parse_state) is None


def test_bad_current_result_summary_is_visible_gap_and_blocks_feedback_urls() -> None:
    client = _client()
    _replace_latest_result_summary("{bad-json")

    _assert_bad_summary_dashboard(client)
    _assert_bad_summary_dispatch(client)
    _assert_bad_summary_review(client)


def test_bad_newer_summary_does_not_promote_previous_official_version() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 ORDER BY id LIMIT 1"
        ).fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (row[0], row[1], row[2], "2026-05-07 08:00:00", "2026-05-07 12:00:00", "unlocked", 13),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (13, "priority_first", 1, 1, "success", "{bad-json", "pytest"),
        )
        conn.commit()

        service = SchedulePlanQueryService(conn)
        latest = service.resolve_plan(13, ROLE_ADOPTED).to_dict()["plan_identity"]
        previous = service.resolve_plan(12, ROLE_ADOPTED).to_dict()["plan_identity"]

        assert latest["result_summary_parse_failed"] is True
        assert latest["is_current_executable_official_version"] is False
        assert latest["can_write_feedback"] is False
        assert previous["is_superseded_by_newer_version"] is True
        assert previous["is_current_executable_official_version"] is False
        assert previous["can_write_feedback"] is False
    finally:
        conn.close()


def test_blocked_or_missing_summary_history_is_not_current_writable_official_plan() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 ORDER BY id LIMIT 1"
        ).fetchone()
        for version, result_status, result_summary in (
            (13, "blocked", "{}",),
            (14, "success", None,),
        ):
            conn.execute(
                """
                INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[2], "2026-05-07 08:00:00", "2026-05-07 12:00:00", "unlocked", version),
            )
            conn.execute(
                """
                INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (version, "priority_first", 1, 1, result_status, result_summary, "pytest"),
            )
            conn.commit()

            latest = SchedulePlanQueryService(conn).resolve_plan(version, ROLE_ADOPTED).to_dict()["plan_identity"]

            assert latest["source_row_id"] is not None
            assert latest["is_current_executable_version"] is True
            assert latest["is_current_executable_official_version"] is False
            assert latest["can_dispatch"] is False
            assert latest["can_write_feedback"] is False
            if result_summary is None:
                assert latest["result_summary_parse_failed"] is True
                assert latest["result_summary_parse_reason"] == "排产摘要缺失"
    finally:
        conn.close()


def test_empty_schedule_detail_history_is_not_current_writable_official_plan() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (13, "priority_first", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()

        service = SchedulePlanQueryService(conn)
        latest = service.resolve_plan(13, ROLE_ADOPTED).to_dict()["plan_identity"]
        previous = service.resolve_plan(12, ROLE_ADOPTED).to_dict()["plan_identity"]

        assert latest["source_table"] == "schedule"
        assert latest["source_row_id"] is None
        assert latest["is_official"] is True
        assert latest["is_current_executable_version"] is True
        assert latest["is_current_executable_official_version"] is False
        assert latest["can_dispatch"] is False
        assert latest["can_write_feedback"] is False
        assert latest["detail_saved"] is False
        assert previous["is_superseded_by_newer_version"] is True
        assert previous["is_current_executable_official_version"] is False
        assert previous["can_write_feedback"] is False
    finally:
        conn.close()


def test_dashboard_invalid_plan_identity_is_visible_gap_instead_of_500() -> None:
    client = _client()

    for path in (
        "/?version=12&plan_role=bad_role",
        "/?version=12&plan_role=adopted&scenario_id=missing-scenario",
    ):
        parser = _parser_for(client, path)
        text = _visible_text(parser)

        assert "计划工作台" in text
        assert "当前请求不可用" in text
        assert "已回到正式采用方案" in text
        assert "ValueError" not in text
        assert not [
            link
            for link in parser.links
            if urlparse(link["href"]).path in {"/reports/execution-review", "/scheduler/resource-dispatch", "/scheduler/gantt"}
        ]


def test_dashboard_missing_requested_version_is_visible_gap_instead_of_no_history() -> None:
    client = _client()

    parser = _parser_for(client, "/?version=999")
    text = _visible_text(parser)
    analysis_links = [
        link["href"]
        for link in parser.links
        if link["href"].startswith("/scheduler/analysis")
    ]

    assert "计划工作台" in text
    assert "当前请求不可用" in text
    assert "请求的排产版本 v999 不存在" in text
    assert "已回到最新排产版本" in text
    assert "数据库里还没有排产历史" not in text
    assert analysis_links
    assert any("version=12" in href for href in analysis_links)
    assert not any("version=999" in href for href in analysis_links)
    assert not [
        link
        for link in parser.links
        if urlparse(link["href"]).path in {"/reports/execution-review", "/scheduler/resource-dispatch", "/scheduler/gantt"}
    ]


def test_dashboard_recent_schedule_metrics_do_not_turn_missing_values_into_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":"","makespan_hours":null,"machine_util_avg":""}}}'
    )

    parser = _parser_for(client, "/?version=12&plan_role=adopted")
    text = _visible_text(parser)

    # fusion-dashboard-cockpit：「当前查看排产」卡 recent_metrics 退役，设备利用率缺失态护卫
    # 迁到 6 格体检表「资源负荷」格——缺失值仍诚实显「数据不足」而非伪装成 0。
    assert "当前摘要里没有可安全展示的设备平均利用率" in text
    assert "拖期 0 小时" not in text
    assert "总工期 0 小时" not in text
    assert "设备利用率 0%" not in text


def test_dashboard_missing_overdue_count_is_data_gap_not_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0.4}}}'
    )

    parser = _parser_for(client, "/?version=12&plan_role=adopted")
    text = _visible_text(parser)

    assert "排产摘要缺少超期批次数" in text
    assert "超期批次 0" not in text
    assert "数据不足" in text


def test_dashboard_invalid_overdue_count_is_data_gap_not_zero() -> None:
    client = _client()
    for raw_count in ("null", '""', "-3"):
        _replace_latest_result_summary(
            f'{{"overdue_batches":{{"count":{raw_count}}},"algo":{{"metrics":{{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0.4}}}}}}'
        )

        parser = _parser_for(client, "/?version=12&plan_role=adopted")
        text = _visible_text(parser)

        assert "首页暂时不能展示准确数量" in text
        assert "超期批次 0" not in text
        assert "数据不足" in text


def test_dashboard_recent_schedule_metrics_reject_bool_utilization_without_hiding_real_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":false}}}'
    )

    parser = _parser_for(client, "/?version=12&plan_role=adopted")
    text = _visible_text(parser)

    # bool 利用率 → 资源负荷格诚实显「数据不足」，不伪装成 0.0%
    assert "当前摘要里没有可安全展示的设备平均利用率" in text
    assert "设备利用率 0.0%" not in text

    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0}}}'
    )
    parser = _parser_for(client, "/?version=12&plan_role=adopted")
    text = _visible_text(parser)

    # 真实 0 利用率 → 资源负荷格显「0.0%」而非被当成缺失（不隐藏真零）；
    # 拖期/总工期已随 recent_metrics 退役离开首页（不再断言其文案）。
    assert "0.0%" in text
    assert "当前摘要里没有可安全展示的设备平均利用率" not in text


def test_dashboard_missing_requested_version_keeps_request_gap_when_latest_summary_is_bad() -> None:
    client = _client()
    _replace_latest_result_summary("{bad-json")

    parser = _parser_for(client, "/?version=999")
    text = _visible_text(parser)

    assert "当前请求不可用" in text
    assert "请求的排产版本 v999 不存在" in text
    assert "当前排产摘要读取失败" in text
    assert "数据库里还没有排产历史" not in text


def test_dashboard_invalid_requested_version_is_visible_gap() -> None:
    client = _client()

    parser = _parser_for(client, "/?version=abc")
    text = _visible_text(parser)

    assert "当前请求不可用" in text
    # 非数字版本不回显原始 raw（避免 ?version=op_id 把内部字段名渲染进可见文本）：用通用文案，
    # raw 本身不出现在页面；用户仍能从回退胶囊看到实际生效的 v12。
    assert "请求的排产版本不是有效数字" in text
    assert "abc" not in text
    # 版本回显从被删 stat-grid「当前查看版本」卡迁到壳层胶囊（回退最新版本 v12）
    assert "v12" in text
    assert "数据库里还没有排产历史" not in text


def test_dashboard_invalid_version_does_not_echo_internal_token_into_visible_text() -> None:
    # ?version=op_id 等：非数字 raw 不得回显进可见文本（禁外显内部身份硬纪律）——
    # 经 plan_identity_error→data_gap evidence→hero.evidence_text 链路，回显会让 op_id 现身页面。
    client = _client()

    parser = _parser_for(client, "/?version=op_id")
    text = _visible_text(parser)

    assert "当前请求不可用" in text
    assert "请求的排产版本不是有效数字" in text
    assert "op_id" not in text  # 内部字段名不得因回显用户输入而外显


def test_summary_overdue_count_flags_count_items_inconsistency() -> None:
    # count < len(items)：摘要内部不一致（count 是 items 全量/上界，不应小于明细数）→ 报错（不可信），
    # 不让 count=0 把 items 里的真超期批次掩盖成「0/正常」（严禁伪造降级掩盖坏值）。
    count, error = _summary_overdue_count(
        {"overdue_batches": {"count": 0, "items": [{"batch_id": "B1"}]}}
    )
    assert count == 0 and "不一致" in error
    # 一致（count>=len）放行，无 items 不误判
    assert _summary_overdue_count({"overdue_batches": {"count": 3, "items": [{"batch_id": "B1"}]}}) == (3, "")
    assert _summary_overdue_count({"overdue_batches": {"count": 0}}) == (0, "")
    # unicode 数字 '²'（isdigit 为真但 int() 抛）→ 报「不是整数」降级，不冒泡崩溃
    bad_count, bad_error = _summary_overdue_count({"overdue_batches": {"count": "²"}})
    assert bad_count == 0 and "不是整数" in bad_error


def test_dashboard_invalid_date_arg_does_not_echo_internal_token_into_visible_text() -> None:
    # ?date_from=op_id 等非法日期形字段：不得经 WorkbenchLink context_summary（"date_from ～ date_to"）
    # 渲染进可见文本（禁外显内部身份）。非法日期在路由入口 _valid_date_arg 被丢弃。
    client = _client()

    parser = _parser_for(client, "/?version=12&plan_role=adopted&date_from=op_id&date_to=2026-05-06")
    text = _visible_text(parser)

    assert "执行排产" in text  # 页面正常渲染（非空兜底，避免空断言假绿）
    assert "op_id" not in text


def test_dashboard_superseded_official_plan_does_not_fake_empty_site_facts() -> None:
    client = _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 ORDER BY id LIMIT 1"
        ).fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (row[0], row[1], row[2], "2026-05-07 08:00:00", "2026-05-07 12:00:00", "unlocked", 13),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                13,
                "priority_first",
                1,
                1,
                "success",
                '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0.2}}}',
                "pytest",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    parser = _parser_for(client, "/?version=12&plan_role=adopted")
    text = _visible_text(parser)

    # 版本回显归胶囊（v12），不再有 stat-grid「当前查看版本」卡
    assert "v12" in text
    assert "v13" not in text
    assert "现场情况" in text
    assert "今日计划或现场事实暂时读不到" in text
    assert "现场情况 暂未发现" not in text
