"""回归测试：报表/排产页顶部导航的链接构造契约——build_scheduler_navigation_links 等始终透传 plan_role/batch_id/资源筛选与 back_to 上下文，不再回吐已下线的 plan_id，设备甘特图与人员甘特图之间不串线 gantt_resource，被新版本替代的正式方案禁用「计划和现场实际」入口（显示历史正式方案只读提示），上下文不全时导航降级为 disabled，且 scheduler_nav 宏只用 Python 链接构造器、不在模板里读 request.args/url_for。"""

from __future__ import annotations

import base64
import json
import os

from tests.web_pages.reports_workbench_backlink_helpers import (
    REPO_ROOT,
    _client,
    _href_with_text,
    _href_with_text_and_class,
    _href_with_text_and_fragment,
    _input_values,
    _parser_for,
    _query,
    _xlsx_text,
)


def _decode_urlsafe_first_segment(token: str) -> str:
    first = str(token or "").split(".", 1)[0]
    padded = first + ("=" * (-len(first) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")


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


def _seed_superseded_adopted_version(version: int) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        source = conn.execute("SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 LIMIT 1").fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source["op_id"], source["machine_id"], source["operator_id"], "2026-05-05 08:00:00", "2026-05-05 12:00:00", "unlocked", version),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version, "priority_first", 1, 1, "success", json.dumps({"algo": {"metrics": {}}}, ensure_ascii=False), "pytest"),
        )
        conn.commit()
    finally:
        conn.close()


def test_execution_review_navigation_keeps_formal_plan_role() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/execution-review?version=12&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )

    for text, path in (
        ("报表中心", "/reports/"),
        ("超期清单", "/reports/overdue"),
        ("资源负荷与利用率", "/reports/utilization"),
        ("停机影响统计", "/reports/downtime"),
    ):
        query = _query(_href_with_text(parser, text, path))
        assert query["plan_role"] == ["adopted"]
        assert query["batch_id"] == ["B-RPT"]
        assert query["resource_type"] == ["machine"]
        assert query["resource_id"] == ["M-RPT"]


def test_report_navigation_drops_plan_id_and_keeps_return_context() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/utilization?version=12&plan_id=PLAN-RPT&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06&batch_id=B-RPT"
        "&resource_type=operator&resource_id=O-RPT"
        "&back_to=%2Fscheduler%2Fresource-dispatch%3Fscope_type%3Doperator",
    )

    for text, path in (
        ("报表中心", "/reports/"),
        ("超期清单", "/reports/overdue"),
        ("计划和现场实际", "/reports/execution-review"),
        ("导出 Excel", "/reports/utilization/export"),
    ):
        query = _query(_href_with_text(parser, text, path))
        assert "plan_id" not in query
        assert query["back_to"] == ["/scheduler/resource-dispatch?scope_type=operator"]

    hidden_inputs = _input_values(parser)
    assert "plan_id" not in hidden_inputs
    assert hidden_inputs["back_to"] == ["/scheduler/resource-dispatch?scope_type=operator"]


def test_execution_review_marks_superseded_adopted_version_as_history() -> None:
    client = _client()
    _seed_superseded_adopted_version(5)

    parser = _parser_for(client, "/reports/execution-review?version=5&date_from=2026-05-05&date_to=2026-05-05")
    visible = " ".join(parser.visible_parts)

    assert "历史正式方案" in visible
    assert "已被更新的正式排产替代" in visible
    assert "不能写现场事实" in visible


def test_scheduler_nav_template_uses_python_link_builder() -> None:
    source = (REPO_ROOT / "templates" / "components" / "ui_macros.html").read_text(encoding="utf-8")
    macro = source.split("{% macro scheduler_nav", 1)[1].split("{% endmacro %}", 1)[0]

    assert "build_scheduler_navigation_links(active)" in macro
    assert "request.args.get" not in macro
    assert "url_for(" not in macro


def test_all_nav_specs_have_nonempty_plain_url() -> None:
    from web.viewmodels.scheduler_navigation_links import build_scheduler_navigation_links

    links = build_scheduler_navigation_links({})

    assert [item["url"] for item in links] == [
        "/scheduler/",
        "/scheduler/batches",
        "/scheduler/config",
        "/scheduler/resource-dispatch",
        "/scheduler/gantt?view=machine",
        "/scheduler/gantt?view=operator",
        "/scheduler/analysis",
        "/scheduler/week-plan",
        "/scheduler/calendar",
    ]
    assert all(item["url"] for item in links)


def test_scheduler_navigation_does_not_cross_wire_gantt_resource_between_views() -> None:
    app = _client().application
    from web.navigation_context import build_scheduler_navigation_links

    with app.test_request_context(
        "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&resource_type=machine&resource_id=M-RPT"
    ):
        links = {item["label"]: item["url"] for item in build_scheduler_navigation_links()}

    machine_query = _query(links["设备甘特图"])
    operator_query = _query(links["人员甘特图"])
    assert machine_query["view"] == ["machine"]
    assert machine_query["gantt_resource"] == ["M-RPT"]
    assert operator_query["view"] == ["operator"]
    assert "gantt_resource" not in operator_query

    with app.test_request_context(
        "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&resource_type=operator&resource_id=O-RPT"
    ):
        links = {item["label"]: item["url"] for item in build_scheduler_navigation_links()}

    machine_query = _query(links["设备甘特图"])
    operator_query = _query(links["人员甘特图"])
    assert machine_query["view"] == ["machine"]
    assert "gantt_resource" not in machine_query
    assert operator_query["view"] == ["operator"]
    assert operator_query["gantt_resource"] == ["O-RPT"]


def test_scheduler_navigation_uses_opaque_plan_context_token_for_preview() -> None:
    app = _client().application
    from web.navigation_context import build_scheduler_navigation_links

    with app.test_request_context(
        "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&scenario_id=SC-SECRET"
    ):
        links = {item["label"]: item["url"] for item in build_scheduler_navigation_links()}

    for label in ("资源排班", "设备甘特图", "人员甘特图", "周计划"):
        url = links[label]
        query = _query(url)
        assert "scenario_id" not in query, (label, url)
        assert query.get("plan_context_token"), (label, url)
        token = query["plan_context_token"][0]
        assert "SC-SECRET" not in token
        assert "SC-SECRET" not in _decode_urlsafe_first_segment(token)


def test_workbench_links_use_public_plan_context_token_from_context() -> None:
    from web.viewmodels.scheduler_workbench_links import build_workbench_link, build_workbench_plan_context

    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        scenario_id="SC-SECRET",
        plan_context_token="opaque-public-token",
        date_from="2026-05-06",
        date_to="2026-05-07",
        query_date="2026-05-06",
        period_preset="week",
        batch_id="B-RPT",
        resource_type="machine",
        resource_id="M-RPT",
    )
    for target, kwargs in (
        ("dashboard", {}),
        ("analysis", {}),
        ("gantt", {"view": "machine"}),
        ("week_plan", {}),
        ("resource_dispatch", {}),
        ("overdue_report", {}),
        ("utilization_report", {}),
        ("downtime_report", {}),
        ("reports_index", {}),
    ):
        link = build_workbench_link(context, target, **kwargs)
        query = _query(link["url"])
        assert "scenario_id" not in query, (target, link["url"])
        assert query.get("plan_context_token") == ["opaque-public-token"], (target, link["url"])
        assert "SC-SECRET" not in link["url"]


def test_top_navigation_uses_shared_guardrails_for_partial_context() -> None:
    app = _client().application
    from web.navigation_context import (
        build_report_navigation_links,
        build_workbench_navigation_links,
    )

    with app.test_request_context("/reports/utilization?version=12&plan_role=adopted"):
        report_links = {item["label"]: item for item in build_report_navigation_links()}
        workbench_links = {item["label"]: item for item in build_workbench_navigation_links()}

    assert report_links["超期清单"]["disabled"] is False
    assert report_links["超期清单"]["url"]
    assert workbench_links["报表中心"]["disabled"]
    assert workbench_links["报表中心"]["url"] == ""
    assert "日期范围" in workbench_links["报表中心"]["disabled_reason"]


def test_report_top_navigation_uses_resolved_version_span_context() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/overdue?version=12&plan_role=adopted")

    overdue = _query(_href_with_text(parser, "超期清单", "/reports/overdue"))
    assert overdue["version"] == ["12"]
    assert overdue["plan_role"] == ["adopted"]
    for key in ("date_from", "date_to", "start_date", "end_date", "query_date", "period_preset"):
        assert key not in overdue


def test_overdue_delay_diagnosis_gantt_action_keeps_filter_context() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT"
        "&back_to=%2Fscheduler%2Fresource-dispatch%3Fscope_type%3Dmachine",
    )

    query = _query(_href_with_text_and_fragment(parser, "查看为什么晚了", "/reports/overdue", "batch_id=B-RPT"))
    assert query["version"] == ["12"]
    assert query["plan_role"] == ["adopted"]
    assert query["batch_id"] == ["B-RPT"]
    assert query["resource_type"] == ["machine"]
    assert query["resource_id"] == ["M-RPT"]
    assert "date_from" not in query and "date_to" not in query
    assert query["back_to"] == ["/scheduler/resource-dispatch?scope_type=machine"]


def test_scheduler_version_only_pages_keep_navigation_clickable() -> None:
    client = _client()
    for url in (
        "/scheduler/gantt?view=machine&version=12",
        "/scheduler/analysis?version=12",
        "/scheduler/resource-dispatch?version=12",
    ):
        parser = _parser_for(client, url)
        query = _query(_href_with_text_and_class(parser, "首页值班台", "/", "aps-workbench-nav-link"))
        assert query["version"] == ["12"]


def test_scheduler_version_only_non_adopted_context_uses_guardrails() -> None:
    client = _client()
    parser = _parser_for(client, "/scheduler/analysis?version=12&plan_role=baseline_best")

    execution_review_links = [
        item
        for item in parser.links
        if item["text"] == "计划和现场实际" and item["href"].startswith("/reports/execution-review")
    ]
    assert execution_review_links == []


def test_scheduler_analysis_route_keeps_execution_review_disabled_for_superseded_success_plan() -> None:
    client = _client()
    _seed_newer_executable_version(13)
    parser = _parser_for(
        client,
        "/scheduler/analysis?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-07",
    )

    execution_review_links = [
        item["href"]
        for item in parser.links
        if "计划和现场实际" in item["text"] and item["href"].startswith("/reports/execution-review")
    ]
    assert execution_review_links == []


def test_scheduler_pages_keep_back_to_after_publishing_navigation_context() -> None:
    client = _client()
    encoded_back_to = "%2Fscheduler%2Fresource-dispatch%3Fscope_type%3Dmachine"
    for url, text, path in (
        (f"/scheduler/analysis?version=12&back_to={encoded_back_to}", "首页值班台", "/"),
        (f"/scheduler/gantt?view=machine&version=12&back_to={encoded_back_to}", "首页值班台", "/"),
        (f"/scheduler/resource-dispatch?version=12&back_to={encoded_back_to}", "首页值班台", "/"),
        (f"/scheduler/week-plan?version=12&back_to={encoded_back_to}", "报表中心", "/reports/"),
    ):
        parser = _parser_for(client, url)
        query = _query(_href_with_text(parser, text, path))
        assert query["back_to"] == ["/scheduler/resource-dispatch?scope_type=machine"]


def test_scheduler_pages_keep_batch_and_resource_after_publishing_navigation_context() -> None:
    client = _client()
    page_cases = (
        (
            "/scheduler/gantt?view=machine&version=12&start_date=2026-05-06&end_date=2026-05-06"
            "&gantt_batch=B-RPT&gantt_resource=M-RPT",
            "报表中心",
            "/reports/",
            {"batch_id": ["B-RPT"], "resource_type": ["machine"], "resource_id": ["M-RPT"]},
        ),
        (
            "/scheduler/analysis?version=12&date_from=2026-05-06&date_to=2026-05-06"
            "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
            "资源排班",
            "/scheduler/resource-dispatch",
            {"batch_id": ["B-RPT"], "scope_type": ["machine"], "scope_id": ["M-RPT"], "machine_id": ["M-RPT"]},
        ),
        (
            "/scheduler/week-plan?version=12&week_start=2026-05-06"
            "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
            "报表中心",
            "/reports/",
            {"batch_id": ["B-RPT"], "resource_type": ["machine"], "resource_id": ["M-RPT"]},
        ),
    )

    for source_url, link_text, link_path, expected in page_cases:
        parser = _parser_for(client, source_url)
        query = _query(_href_with_text(parser, link_text, link_path))

        for key, value in expected.items():
            assert query[key] == value


def test_gantt_data_endpoint_returns_full_scope_ignoring_view_filters() -> None:
    # finding-08：甘特数据接口恒返回全量，不按 gantt_batch/gantt_resource 后端预筛——批次/
    # 资源筛选是纯前端查看态（页面 URL 种子化 filterBatch/filterResource + applyFilters
    # 客户端过滤），后端预筛会让「清筛选」回不到全量、负荷条带与当前视图割裂。
    # 「带 scope 进入即聚焦」由前端种子化保留，「scope 跨导航持续」由下一个用例（页面
    # 导航链接/表单仍带 scope）覆盖；本用例钉死数据接口本身全量。
    client = _client()
    response = client.get(
        "/scheduler/gantt/data?view=machine&version=12&start_date=2026-05-06&end_date=2026-05-06"
        "&gantt_batch=B-RPT&gantt_resource=M-RPT"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    tasks = data["tasks"]
    task_ids = {str(task.get("id") or "") for task in tasks}
    batch_ids = {str((task.get("meta") or {}).get("batch_id") or "") for task in tasks}
    machine_ids = {str((task.get("meta") or {}).get("machine_id") or "") for task in tasks}

    # 尽管 URL 带 gantt_batch=B-RPT&gantt_resource=M-RPT，数据接口仍返回全量：
    # 范围外批次 B-OTHER 与设备 M-OTHER 都在，证明后端未按 scope 裁剪。
    assert "B-OTHER" in batch_ids, "数据接口不应按 gantt_batch 裁剪（B-OTHER 应仍在）"
    assert "M-OTHER" in machine_ids, "数据接口不应按 gantt_resource 裁剪（M-OTHER 应仍在）"
    assert {"B-RPT", "B-SAME"}.issubset(batch_ids)
    assert data["task_count"] == len(tasks)
    assert set((data.get("critical_chain") or {}).get("ids") or []).issubset(task_ids)


def test_gantt_page_controls_keep_scope_filters_for_followup_actions() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/scheduler/gantt?view=machine&version=12&start_date=2026-05-06&end_date=2026-05-06"
        "&gantt_batch=B-RPT&gantt_resource=M-RPT",
    )

    machine_query = _query(_href_with_text(parser, "设备视图", "/scheduler/gantt"))
    operator_query = _query(_href_with_text(parser, "人员视图", "/scheduler/gantt"))
    assert machine_query["gantt_batch"] == ["B-RPT"]
    assert machine_query["gantt_resource"] == ["M-RPT"]
    assert operator_query["gantt_batch"] == ["B-RPT"]
    assert "gantt_resource" not in operator_query

    for text in ("上周", "回到本周", "下周"):
        query = _query(_href_with_text(parser, text, "/scheduler/gantt"))
        assert query["gantt_batch"] == ["B-RPT"]
        assert query["gantt_resource"] == ["M-RPT"]

    hidden_inputs = _input_values(parser)
    assert hidden_inputs["gantt_batch"] == ["B-RPT"]
    assert hidden_inputs["gantt_resource"] == ["M-RPT"]


def test_week_plan_preview_and_export_scope_filters_are_applied_by_backend() -> None:
    client = _client()
    path = (
        "/scheduler/week-plan?version=12&week_start=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT"
    )
    parser = _parser_for(client, path)
    visible_text = "\n".join(parser.visible_parts)

    assert "B-RPT" in visible_text
    assert "B-OTHER" not in visible_text
    assert "B-SAME" not in visible_text

    hidden_inputs = _input_values(parser)
    assert hidden_inputs["batch_id"] == ["B-RPT"]
    assert hidden_inputs["resource_type"] == ["machine"]
    assert hidden_inputs["resource_id"] == ["M-RPT"]

    export_href = _href_with_text(parser, "导出周计划表.xlsx", "/scheduler/week-plan/export")
    export_query = _query(export_href)
    assert export_query["batch_id"] == ["B-RPT"]
    assert export_query["resource_type"] == ["machine"]
    assert export_query["resource_id"] == ["M-RPT"]

    export_response = client.get(export_href)
    assert export_response.status_code == 200
    workbook_text = _xlsx_text(export_response.data)
    assert "B-RPT" in workbook_text
    assert "B-OTHER" not in workbook_text
    assert "B-SAME" not in workbook_text
