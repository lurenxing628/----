"""回归测试：当 result_summary 解析失败/缺失或版本被更新版本取代时，仪表盘、资源派工、执行复盘三处页面把它当作可见数据缺口(「当前排产摘要读取失败」等)而非 500，并据 plan_identity 关闭派工/写现场反馈入口；非法或越界 version 请求、缺失/非法/越界 overdue 与利用率指标都呈现「数据不足」而非伪造 0。"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Set
from urllib.parse import urlparse

from core.infrastructure.database import get_connection
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from tests._support.schedule_retirement import (
    assert_retired_scope,
    capture_schedule_context,
    initialize_read_fixture,
    projection_text,
)
from tests.web_pages.reports_workbench_backlink_helpers import _client as _fixture_client
from web.routes.dashboard import (
    _summary_overdue_count,
    _summary_payload_dict,
    _workbench_summary_parse_state,
)


def _client():
    """Use the existing real plan fixture with startup defaults already persisted."""
    client = _fixture_client()
    initialize_read_fixture(client.application)
    return client


def _replace_latest_result_summary(raw_summary: str) -> None:
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        conn.execute("UPDATE ScheduleHistory SET result_summary = ? WHERE version = 12", (raw_summary,))
        conn.commit()
    finally:
        conn.close()


def _assert_no_path_links(value, paths: Set[str]) -> None:
    """No enabled link in the actual public projection may bypass the guard."""
    if isinstance(value, dict):
        url = value.get("url") or value.get("href")
        if url and not value.get("disabled"):
            assert urlparse(url).path not in paths
        for item in value.values():
            _assert_no_path_links(item, paths)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _assert_no_path_links(item, paths)


def _dashboard_projection(client, path):
    """Keep retained summary semantics separate from non-equivalent old GETs."""
    context = capture_schedule_context(client, endpoint="dashboard.index", path=path, template="dashboard.html")
    assert_retired_scope(client, path)
    return context["workbench_summary"]


def _dashboard_text(workbench):
    """Select only the purpose-built display fields, without altering values."""
    return projection_text(workbench["hero"], workbench["risk_cards"], workbench["summary_stats"])


def _rejected_dashboard(client, path, *, status=400, message="地址里的计划编号、日期或筛选不对"):
    """The current adapter rejects bad identity/scope instead of selecting latest."""
    body = assert_retired_scope(client, path, status=status, message=message)
    assert "ValueError" not in body and "Traceback" not in body
    assert "已回到" not in body
    assert "/scheduler/gantt" not in body and "/reports/execution-review" not in body
    return body


def _assert_bad_summary_dashboard(client) -> None:
    dashboard = _dashboard_projection(
        client,
        "/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    dashboard_text = _dashboard_text(dashboard)

    assert "当前排产摘要读取失败" in dashboard_text
    assert "页面仅展示基础历史信息" in dashboard_text
    assert "超期批次需要先看" not in dashboard_text
    assert "资源负荷偏高" not in dashboard_text
    assert dashboard["latest_plan"]["version"] == "12"
    assert dashboard["latest_plan"]["can_write_feedback"] is False
    _assert_no_path_links(dashboard, {"/reports/execution-review"})


def _assert_bad_summary_dispatch(client) -> None:
    path = ("/scheduler/resource-dispatch?scope_type=machine&machine_id=M-RPT"
            "&period_preset=custom&date_from=2026-05-06&date_to=2026-05-06"
            "&version=12&plan_role=adopted&batch_id=B-RPT")
    dispatch = capture_schedule_context(
        client, endpoint="scheduler.resource_dispatch_page", path=path, template="scheduler/resource_dispatch.html",
    )
    dispatch_html = projection_text(dispatch["plan_identity"])
    assert "当前排产摘要读取失败" in dispatch_html
    assert "页面仅展示基础历史信息" in dispatch_html
    assert dispatch["filters"]["version"] == 12
    assert dispatch["plan_identity"]["can_write_feedback"] is False
    assert dispatch["execution_review_link"]["disabled"] is True
    for key in ("actual_record_url_template", "actual_template_url", "actual_import_url"):
        assert dispatch[key] is None
    assert_retired_scope(client, path)


def _assert_bad_summary_review(client) -> None:
    path = "/reports/execution-review?version=12&date_from=2026-05-06&date_to=2026-05-06"
    review = capture_schedule_context(
        client, endpoint="reports.execution_review_page", path=path, template="reports/execution_review.html",
    )
    review_text = projection_text(review["report_plan_status"])

    assert "当前排产摘要读取失败" in review_text
    assert "页面仅展示基础历史信息" in review_text
    assert "当前方案只能查看，不能写现场记录。" not in review_text
    assert review["version"] == 12
    _assert_no_path_links(review["report_links"], {"/scheduler/resource-dispatch"})
    assert_retired_scope(client, path)


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

    for path, message in (
        ("/?version=12&plan_role=bad_role", "地址里的计划类型不对"),
        ("/?version=12&plan_role=adopted&scenario_id=missing-scenario", "地址里的计划编号、日期或筛选不对"),
    ):
        text = _rejected_dashboard(client, path, message=message)
        assert "bad_role" not in text and "missing-scenario" not in text


def test_dashboard_missing_requested_version_is_visible_gap_instead_of_no_history() -> None:
    client = _client()

    text = _rejected_dashboard(client, "/?version=999", status=404, message="页面不存在或已被删除")
    assert "数据库里还没有排产历史" not in text
    assert "/scheduler/analysis" not in text


def test_dashboard_recent_schedule_metrics_do_not_turn_missing_values_into_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":"","makespan_hours":null,"machine_util_avg":""}}}'
    )

    workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
    text = _dashboard_text(workbench)

    # fusion-dashboard-cockpit：「当前查看排产」卡 recent_metrics 退役，设备利用率缺失态护卫
    # 迁到 7 格体检表「资源负荷」格——缺失值仍诚实显「数据不足」而非伪装成 0。
    assert "当前摘要里没有可安全展示的设备平均利用率" in text
    assert "拖期 0 小时" not in text
    assert "总工期 0 小时" not in text
    assert "设备利用率 0%" not in text


def test_dashboard_missing_overdue_count_is_data_gap_not_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0.4}}}'
    )

    workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
    text = _dashboard_text(workbench)

    assert "排产摘要缺少超期批次数" in text
    assert "超期批次 0" not in text
    assert "数据不足" in text
    assert workbench["summary_stats"]["overdue_count_value"] == "数据不足"


def test_dashboard_invalid_overdue_count_is_data_gap_not_zero() -> None:
    client = _client()
    for raw_count in ("null", '""', "-3"):
        _replace_latest_result_summary(
            f'{{"overdue_batches":{{"count":{raw_count}}},"algo":{{"metrics":{{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0.4}}}}}}'
        )

        workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
        text = _dashboard_text(workbench)

        assert "首页暂时不能展示准确数量" in text
        assert "超期批次 0" not in text
        assert "数据不足" in text
        assert workbench["summary_stats"]["overdue_count_value"] == "数据不足"


def test_dashboard_recent_schedule_metrics_reject_bool_utilization_without_hiding_real_zero() -> None:
    client = _client()
    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":false}}}'
    )

    workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
    text = _dashboard_text(workbench)

    # bool 利用率 → 资源负荷格诚实显「数据不足」，不伪装成 0.0%
    assert "当前摘要里没有可安全展示的设备平均利用率" in text
    assert "设备利用率 0.0%" not in text

    _replace_latest_result_summary(
        '{"overdue_batches":{"count":0},"algo":{"metrics":{"total_tardiness_hours":0,"makespan_hours":0,"machine_util_avg":0}}}'
    )
    workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
    text = _dashboard_text(workbench)

    # 真实 0 利用率 → 资源负荷格显「0.0%」而非被当成缺失（不隐藏真零）；
    # 拖期/总工期已随 recent_metrics 退役离开首页（不再断言其文案）。
    assert "0.0%" in text
    assert "当前摘要里没有可安全展示的设备平均利用率" not in text


def test_dashboard_missing_requested_version_keeps_request_gap_when_latest_summary_is_bad() -> None:
    client = _client()
    _replace_latest_result_summary("{bad-json")

    text = _rejected_dashboard(client, "/?version=999", status=404, message="页面不存在或已被删除")
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        identity = SchedulePlanQueryService(conn).resolve_plan(12, ROLE_ADOPTED).to_dict()["plan_identity"]
        assert identity["result_summary_parse_failed"] is True
        assert conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=12").fetchone()[0] == "{bad-json"
    finally:
        conn.close()
    assert "数据库里还没有排产历史" not in text


def test_dashboard_invalid_requested_version_is_visible_gap() -> None:
    client = _client()

    text = _rejected_dashboard(client, "/?version=abc")
    assert "abc" not in text
    assert "v12" not in text
    assert "数据库里还没有排产历史" not in text


def test_dashboard_invalid_version_does_not_echo_internal_token_into_visible_text() -> None:
    # ?version=op_id 等：非数字 raw 不得回显进可见文本（禁外显内部身份硬纪律）——
    # 经 plan_identity_error→data_gap evidence→hero.evidence_text 链路，回显会让 op_id 现身页面。
    client = _client()

    text = _rejected_dashboard(client, "/?version=op_id")
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
    # 非法日期不能被忽略后扩大范围，也不能回显内部字段名。
    client = _client()

    text = _rejected_dashboard(client, "/?version=12&plan_role=adopted&date_from=op_id&date_to=2026-05-06")
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

    workbench = _dashboard_projection(client, "/?version=12&plan_role=adopted")
    text = _dashboard_text(workbench)
    assert workbench["latest_plan"]["version"] == "12"
    assert workbench["latest_plan"]["is_superseded_by_newer_version"] is True
    assert workbench["latest_plan"]["can_write_feedback"] is False
    assert "现场情况" in text
    assert "今日计划或现场事实暂时读不到" in text
    assert "现场情况 暂未发现" not in text
