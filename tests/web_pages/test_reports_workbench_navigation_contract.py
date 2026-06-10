"""回归测试：报表/排产页顶部导航的链接构造契约——build_scheduler_navigation_links 等始终透传 plan_role/batch_id/资源筛选与 back_to 上下文，不再回吐已下线的 plan_id，设备甘特图与人员甘特图之间不串线 gantt_resource，被新版本替代的正式方案禁用「计划和现场实际」入口（显示历史正式方案只读提示），上下文不全时导航降级为 disabled，且 scheduler_nav 宏只用 Python 链接构造器、不在模板里读 request.args/url_for。"""

from __future__ import annotations

import json
import os

from tests.web_pages.reports_workbench_backlink_helpers import (
    REPO_ROOT,
    _client,
    _href_with_text,
    _href_with_text_and_class,
    _input_values,
    _parser_for,
    _query,
    _xlsx_text,
)


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


def test_top_navigation_uses_shared_guardrails_for_partial_context() -> None:
    app = _client().application
    from web.navigation_context import (
        build_report_navigation_links,
        build_workbench_navigation_links,
    )

    with app.test_request_context("/reports/utilization?version=12&plan_role=adopted"):
        report_links = {item["label"]: item for item in build_report_navigation_links()}
        workbench_links = {item["label"]: item for item in build_workbench_navigation_links()}

    assert report_links["超期清单"]["disabled"]
    assert report_links["超期清单"]["url"] == ""
    assert "日期范围" in report_links["超期清单"]["disabled_reason"]
    assert workbench_links["报表中心"]["disabled"]
    assert workbench_links["报表中心"]["url"] == ""
    assert "日期范围" in workbench_links["报表中心"]["disabled_reason"]


def test_report_top_navigation_uses_resolved_version_span_context() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/overdue?version=12&plan_role=adopted")

    for text, path in (
        ("报表中心", "/reports/"),
        ("资源负荷与利用率", "/reports/utilization"),
        ("计划和现场实际", "/reports/execution-review"),
        ("停机影响统计", "/reports/downtime"),
    ):
        query = _query(_href_with_text(parser, text, path))
        assert query["version"] == ["12"]
        assert query["plan_role"] == ["adopted"]
        if path in {"/reports/utilization", "/reports/downtime"}:
            assert query["start_date"] == ["2026-05-06"]
            assert query["end_date"] == ["2026-05-06"]
        else:
            assert query["date_from"] == ["2026-05-06"]
            assert query["date_to"] == ["2026-05-06"]


def test_overdue_delay_diagnosis_gantt_action_keeps_filter_context() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT"
        "&back_to=%2Fscheduler%2Fresource-dispatch%3Fscope_type%3Dmachine",
    )

    query = _query(_href_with_text(parser, "查看甘特图", "/scheduler/gantt"))
    assert query["version"] == ["12"]
    assert query["plan_role"] == ["adopted"]
    assert query["start_date"] == ["2026-05-06"]
    assert query["end_date"] == ["2026-05-06"]
    assert query["gantt_batch"] == ["B-RPT"]
    assert query["view"] == ["machine"]
    assert query["gantt_resource"] == ["M-RPT"]
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


def test_scheduler_analysis_route_disables_execution_review_for_superseded_plan() -> None:
    client = _client()
    _seed_newer_executable_version(13)
    parser = _parser_for(
        client,
        "/scheduler/analysis?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-07",
    )

    assert "这是历史正式方案，只能查看" in " ".join(parser.visible_parts + parser.public_attribute_parts)
    assert not any(
        item["href"].startswith("/reports/execution-review")
        for item in parser.links
    )


def test_scheduler_pages_keep_back_to_after_publishing_navigation_context() -> None:
    client = _client()
    encoded_back_to = "%2Fscheduler%2Fresource-dispatch%3Fscope_type%3Dmachine"
    for url, text, path in (
        (f"/scheduler/analysis?version=12&back_to={encoded_back_to}", "首页值班台", "/"),
        (f"/scheduler/gantt?view=machine&version=12&back_to={encoded_back_to}", "报表中心", "/reports/"),
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


def test_gantt_data_scope_filters_are_applied_by_backend() -> None:
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

    assert batch_ids == {"B-RPT"}
    assert machine_ids == {"M-RPT"}
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


def test_scheduler_navigation_publish_keeps_plan_guard_fields() -> None:
    app = _client().application
    from web.navigation_context import build_report_navigation_links, current_workbench_navigation_context
    from web.routes.domains.scheduler.scheduler_navigation_publish import (
        publish_analysis_navigation_context,
        publish_gantt_navigation_context,
        publish_week_plan_navigation_context,
    )

    superseded_plan = dict(
        requested_role="adopted", selected_role="adopted",
        is_scenario_preview=False, is_comparison=False, is_official=True, is_preview=False,
        is_superseded_by_newer_version=True, is_current_executable_official_version=False,
        can_dispatch=True, can_write_feedback=True,
    )
    expected_guard_fields = dict(
        requested_plan_role="adopted", effective_plan_role="adopted",
        plan_role_status="resolved_adopted", is_scenario_preview=False, is_comparison=False,
        is_superseded_by_newer_version=True, is_official_plan=True, is_preview_plan=False,
        is_current_executable_official_version=False, can_dispatch=True, can_write_feedback=True,
    )

    with app.test_request_context("/scheduler/analysis"):
        context = publish_analysis_navigation_context(
            version=12,
            plan_resolution=superseded_plan,
            date_from="2026-05-06",
            date_to="2026-05-07",
            resource_context={},
        )
        links = {item["label"]: item for item in build_report_navigation_links()}

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields
        assert links["计划和现场实际"]["disabled"] is True
        assert links["计划和现场实际"]["url"] == ""
        assert "历史正式方案" in links["计划和现场实际"]["disabled_reason"]

    with app.test_request_context("/scheduler/gantt"):
        context = publish_gantt_navigation_context(
            version=12,
            plan_resolution=dict(superseded_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            view="machine",
            gantt_resource="M-RPT",
        )

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields
        assert current_workbench_navigation_context()["resource_type"] == "machine"
        assert current_workbench_navigation_context()["resource_id"] == "M-RPT"

    with app.test_request_context("/scheduler/week-plan"):
        context = publish_week_plan_navigation_context(
            version=12,
            plan_resolution=dict(superseded_plan),
            fallback_scenario_id=None,
            date_from="2026-05-06",
            date_to="2026-05-07",
        )

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields


def test_scheduler_navigation_publish_accepts_navigation_context_plan_role_shape() -> None:
    app = _client().application
    from web.navigation_context import (
        build_report_navigation_links,
        build_scheduler_navigation_links,
        current_workbench_navigation_context,
    )
    from web.routes.domains.scheduler.scheduler_navigation_publish import (
        publish_analysis_navigation_context,
        publish_gantt_navigation_context,
        publish_week_plan_navigation_context,
    )
    from web.routes.domains.scheduler.scheduler_week_plan_query import week_plan_export_url

    navigation_shape_plan = dict(
        requested_plan_role="baseline_best",
        effective_plan_role="baseline_best",
        plan_role_status="resolved_candidate",
        can_dispatch=False,
        can_write_feedback=False,
    )

    with app.test_request_context("/scheduler/analysis"):
        publish_analysis_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            resource_context={},
        )
        current_context = current_workbench_navigation_context()
        report_links = {item["label"]: item for item in build_report_navigation_links()}

        assert current_context["plan_role"] == "baseline_best"
        assert current_context["requested_plan_role"] == "baseline_best"
        assert _query(report_links["超期清单"]["url"])["plan_role"] == ["baseline_best"]

    with app.test_request_context("/scheduler/gantt"):
        publish_gantt_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            view="machine",
            gantt_resource="M-RPT",
        )
        current_context = current_workbench_navigation_context()
        scheduler_links = {item["label"]: item for item in build_scheduler_navigation_links()}

        assert current_context["plan_role"] == "baseline_best"
        assert _query(scheduler_links["排产优化分析"]["url"])["plan_role"] == ["baseline_best"]

    with app.test_request_context("/scheduler/week-plan"):
        publish_week_plan_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            fallback_scenario_id=None,
            date_from="2026-05-06",
            date_to="2026-05-07",
        )
        current_context = current_workbench_navigation_context()
        export_url = week_plan_export_url(
            version=12,
            week_start="2026-05-06",
            plan_resolution=dict(navigation_shape_plan),
        )

        assert current_context["plan_role"] == "baseline_best"
        assert export_url is not None
        assert _query(export_url)["plan_role"] == ["baseline_best"]


def test_scheduler_pages_selected_plan_role_use_core_contract() -> None:
    from core.services.scheduler.schedule_result_view_context import selected_plan_role as core_selected_plan_role
    from web.routes.domains.scheduler.scheduler_gantt import selected_plan_role as gantt_selected_plan_role
    from web.routes.domains.scheduler.scheduler_week_plan import selected_plan_role as week_selected_plan_role

    for plan_resolution in (
        {"selected_role": "baseline_best"},
        {"selected_role": None},
        {"selected_role": ""},
        {},
        None,
    ):
        assert gantt_selected_plan_role(plan_resolution) == core_selected_plan_role(plan_resolution)
        assert week_selected_plan_role(plan_resolution) == core_selected_plan_role(plan_resolution)


def test_scheduler_navigation_rejects_conflicting_resource_aliases() -> None:
    client = _client()

    response = client.get(
        "/scheduler/gantt?view=machine&version=12&start_date=2026-05-06&end_date=2026-05-06"
        "&machine_id=M-RPT&operator_id=O-RPT"
    )

    assert response.status_code == 400
    assert "资源筛选同时包含设备和人员" in response.get_data(as_text=True)


def test_week_plan_rejects_scope_type_without_scope_id() -> None:
    client = _client()

    for path in ("/scheduler/week-plan", "/scheduler/week-plan/export"):
        response = client.get(f"{path}?version=12&week_start=2026-05-06&scope_type=machine")
        assert response.status_code == 400
        assert "资源筛选类型是设备，但缺少设备编号" in response.get_data(as_text=True)
