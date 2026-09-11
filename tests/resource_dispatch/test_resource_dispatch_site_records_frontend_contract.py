"""回归测试：资源派工"现场记录"页面与前端脚本的契约——可写场景渲染填实际/导入Excel/查看记录入口与 data-actual-* URL 及反馈人输入；只读/历史/场景预览/无 plan 上下文场景必须隐藏写 URL 和 execution-review 链接（避免 href="None"），_execution_review_link 按 plan_role/版本守卫禁用复盘；且不出现"执行事实补录/事件底座"等旧术语。"""

from __future__ import annotations

from io import BytesIO

import openpyxl

from tests._support.legacy_report_contract import (
    IDENTITY_UNAVAILABLE,
    RETIRED_SCOPE,
    assert_rejected,
    assert_retired,
    get_unchanged,
)
from tests.operation_execution.operation_execution_feedback_test_support import (
    _build_app,
    _current_query,
)


def test_resource_dispatch_page_has_site_records_words_and_excel_entries(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    query = _current_query()
    response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
    assert_retired(response, public=("2", "正式采用方案", "人员"))
    data_response = get_unchanged(client, "/scheduler/resource-dispatch/execution/data?" + query, db_path)
    assert data_response.status_code == 200
    data = data_response.get_json()["data"]
    assert data["can_write_feedback"] is True
    actions = {item["action"]: item for item in data["tasks"][0]["available_actions"]}
    assert actions["fill_actual"]["label"] == "填写实际情况"
    assert actions["view_records"]["label"] == "查看现场记录"
    assert actions["fill_actual"]["enabled"] is True
    template = get_unchanged(client, "/scheduler/resource-dispatch/execution/actual-template?" + query, db_path)
    assert template.status_code == 200
    assert template.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    workbook = openpyxl.load_workbook(BytesIO(template.data))
    try:
        assert workbook.sheetnames and "B1" in str(list(workbook.active.values))
    finally:
        workbook.close()
    rules = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
    assert "POST" in rules["/scheduler/resource-dispatch/execution/import"]
    assert "POST" in rules["/scheduler/resource-dispatch/execution/tasks/<task_key>/actual"]


def test_resource_dispatch_actual_record_url_uses_normalized_filters_when_query_date_missing(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    query = ("scope_type=operator&operator_id=O1&period_preset=custom"
             "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted")
    response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
    assert_retired(response, public=("2", "正式采用方案", "2026-05-01 至 2026-05-07", "人员"))
    data_response = get_unchanged(client, "/scheduler/resource-dispatch/data?" + query, db_path)
    assert data_response.status_code == 200
    filters = data_response.get_json()["data"]["filters"]
    assert filters["query_date"] == "2026-05-01"
    assert filters["start_date"] == "2026-05-01" and filters["end_date"] == "2026-05-07"
    assert filters["scope_id"] == "O1" and filters["version"] == 2


def test_resource_dispatch_read_only_page_does_not_emit_actual_write_urls(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    query = ("scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
             "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best")
    response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
    assert_retired(response, public=("2", "原算法代表方案"))
    payload = get_unchanged(client, "/scheduler/resource-dispatch/execution/data?" + query, db_path).get_json()
    assert payload["success"] is True and payload["data"]["can_write_feedback"] is False
    assert "不能填写现场记录" in payload["data"]["disabled_reason"]
    assert all(action["action"] != "fill_actual" for task in payload["data"]["tasks"] for action in task["available_actions"])
    template = get_unchanged(client, "/scheduler/resource-dispatch/execution/actual-template?" + query, db_path)
    assert template.status_code == 409 and template.get_json()["success"] is False
    assert template.get_json()["error"]["message"] == "当前不是最新正式采用方案，不能填写现场记录。"


def test_resource_dispatch_unqueryable_write_page_does_not_render_none_links(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    query = ("scope_type=team&period_preset=week&query_date=2026-05-01"
             "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted")
    response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
    assert_rejected(response, forbidden=('href="None"', 'href=""', "data-actual-record-url-template="))
    template = get_unchanged(client, "/scheduler/resource-dispatch/execution/actual-template?" + query, db_path)
    assert template.status_code == 400 and template.get_json()["success"] is False


def test_resource_dispatch_history_can_review_but_scenario_pages_do_not_emit_review_or_write_urls(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    queries = (
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-30&date_to=2026-05-06&version=1&plan_role=adopted",
        _current_query() + "&scenario_id=scenario-plain",
    )
    for query in queries:
        response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
        assert_retired(response, message=IDENTITY_UNAVAILABLE if "scenario_id=" in query else RETIRED_SCOPE)
        payload = get_unchanged(client, "/scheduler/resource-dispatch/execution/data?" + query, db_path).get_json()
        assert payload["success"] is True and payload["data"]["can_write_feedback"] is False
        template = get_unchanged(client, "/scheduler/resource-dispatch/execution/actual-template?" + query, db_path)
        assert template.status_code == 409 and template.get_json()["success"] is False
        assert template.get_json()["error"]["message"] == "当前不是最新正式采用方案，不能填写现场记录。"
    history = get_unchanged(client, "/reports/execution-review/export?version=1&date_from=2026-04-30&date_to=2026-05-06", db_path)
    assert history.status_code == 200
    blocked = get_unchanged(client, "/reports/execution-review/export?version=2&scenario_id=scenario-plain&date_from=2026-05-01&date_to=2026-05-07", db_path)
    assert blocked.status_code == 400
    assert "只复盘正式采用方案" in blocked.get_data(as_text=True)


def test_resource_dispatch_invalid_plan_context_token_is_blocked_without_default_page(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")
    query = (
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
        "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted"
        "&plan_context_token=bad-token"
    )

    page_resp = client.get(f"/scheduler/resource-dispatch?{query}")
    page_body = page_resp.get_data(as_text=True)

    assert page_resp.status_code == 400
    assert_rejected(page_resp, forbidden=("bad-token", "scenario_id"))
    assert "data-actual-record-url-template=" not in page_body
    assert "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual" not in page_body

    data_resp = client.get(f"/scheduler/resource-dispatch/data?{query}", headers={"Accept": "application/json"})
    data_payload = data_resp.get_json()

    assert data_resp.status_code == 400
    assert data_payload["success"] is False
    assert data_payload["error"]["message"] == "方案预览入口已失效，请刷新页面后重试。"
    assert "scenario_id" not in str(data_payload)

    export_resp = client.get(f"/scheduler/resource-dispatch/export?{query}")
    export_body = export_resp.get_data(as_text=True)

    assert export_resp.status_code == 400
    assert "方案预览入口已失效" in export_body
    assert export_resp.location is None


def test_resource_dispatch_execution_entry_rejects_incomplete_plan_context(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    page_resp = client.get("/scheduler/resource-dispatch?version=2")
    page_body = page_resp.get_data(as_text=True)

    assert_retired(page_resp, public=("2", "正式采用方案"))
    assert 'data-execution-url=' not in page_body
    assert "data-actual-record-url-template=" not in page_body
    assert "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual" not in page_body

    data_resp = client.get("/scheduler/resource-dispatch/execution/data?version=2")
    payload = data_resp.get_json()

    assert data_resp.status_code == 400
    assert payload["success"] is False
    details = payload["error"]["details"]
    assert "field" not in details
    assert "missing_fields" not in details
    assert details["field_label"] == "计划上下文"
    assert "方案" in details["missing_field_labels"]
    assert "日期范围" in details["missing_field_labels"]
    assert "范围类型" in details["missing_field_labels"]
    assert "开始日期" in details["missing_field_labels"]
    assert "结束日期" in details["missing_field_labels"]


def test_execution_review_link_keeps_server_side_guard_fields() -> None:
    from web.routes.domains.scheduler.scheduler_resource_dispatch import _execution_review_link

    base_filters = {
        "version": 2,
        "plan_role": "adopted",
        "start_date": "2026-05-01",
        "end_date": "2026-05-07",
        "batch_id": "B-001",
        "query_date": "2026-05-01",
        "period_preset": "week",
        "scope_type": "operator",
        "operator_id": "O1",
        "is_current_executable_official_version": True,
        "source_table": "schedule",
        "schedule_result_status": "success",
        "detail_saved": True,
        "is_official_plan": True,
        "is_preview_plan": False,
        "is_simulation_plan": False,
        "can_write_feedback": True,
        "can_dispatch": True,
    }
    blocked_fields = [
        {"effective_plan_role": "baseline_best"},
        {"requested_plan_role": "baseline_best"},
        {"is_scenario_preview": True},
        {"is_comparison": True},
        {"schedule_result_status": "partial"},
        {"detail_saved": False},
        {"is_simulation_plan": True},
    ]

    for override in blocked_fields:
        link = _execution_review_link(dict(base_filters, **override), dict(base_filters, **override))
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]

    historical_link = _execution_review_link(
        dict(base_filters, is_superseded_by_newer_version=True),
        dict(base_filters, is_superseded_by_newer_version=True),
    )
    assert historical_link["disabled"] is False
    assert "plan_role=adopted" in historical_link["url"]

    link = _execution_review_link(base_filters, base_filters)
    assert link["disabled"] is False
    assert "batch_id=B-001" in link["url"]

    read_only_link = _execution_review_link(
        dict(base_filters, can_write_feedback=False, can_dispatch=False),
        dict(base_filters, can_write_feedback=False, can_dispatch=False),
    )
    assert read_only_link["disabled"] is False
    assert "plan_role=adopted" in read_only_link["url"]
    assert "scenario_id" not in read_only_link["url"]


def test_resource_dispatch_request_kwargs_preserve_batch_id(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    from web.routes.domains.scheduler.scheduler_resource_dispatch_query import _request_kwargs

    with app.test_request_context(
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=O1"
        "&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted&batch_id=B-001"
        "&date_from=2026-05-01&date_to=2026-05-07"
    ):
        kwargs = _request_kwargs()
        assert kwargs["batch_id"] == "B-001"
        assert kwargs["start_date"] == "2026-05-01"
        assert kwargs["end_date"] == "2026-05-07"
