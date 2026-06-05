"""回归测试：资源派工"现场记录"页面与前端脚本的契约——可写场景渲染填实际/导入Excel/查看记录入口与 data-actual-* URL 及反馈人输入；只读/历史/场景预览/无 plan 上下文场景必须隐藏写 URL 和 execution-review 链接（避免 href="None"），_execution_review_link 按 plan_role/版本守卫禁用复盘；前端走 available_actions 契约、内联实际记录表单（不预填只读时间）与一键导入，且不出现"执行事实补录/事件底座"等旧术语。"""

from __future__ import annotations

from typing import Tuple

from tests.operation_execution_feedback_test_support import (
    RESOURCE_DISPATCH_TEMPLATE,
    UI_CONTRACT_CSS,
    _build_app,
    _current_query,
    read_resource_dispatch_script_bundle,
)
from tests.resource_dispatch_frontend_support import (
    RESOURCE_DISPATCH_CSS,
    extract_js_function,
)


def _assert_contains_all(text: str, values: Tuple[str, ...]) -> None:
    for value in values:
        assert value in text


def _assert_contains_none(text: str, values: Tuple[str, ...]) -> None:
    for value in values:
        assert value not in text


def test_resource_dispatch_page_has_site_records_words_and_excel_entries(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(f"/scheduler/resource-dispatch?{_current_query()}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    source = read_resource_dispatch_script_bundle()
    page_contract = body + "\n" + source
    _assert_contains_all(
        page_contract,
        ("现场记录", "填写实际情况", "导入实际情况 Excel", "下载填写模板", "查看计划和实际", "查看现场记录"),
    )
    _assert_contains_all(
        body,
        (
            "data-execution-url=",
            "data-actual-record-url-template=",
            "data-actual-template-url=",
            "data-actual-import-url=",
            'data-actual-record-url-template="/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual?',
            'data-actual-template-url="/scheduler/resource-dispatch/execution/actual-template?',
            'data-actual-import-url="/scheduler/resource-dispatch/execution/import?',
            'href="/reports/execution-review?version=2',
            "plan_role=adopted",
            "query_date=2026-05-01",
            "period_preset=week",
            "scope_type=operator",
            "scope_id=O1",
            'id="rdExecutionCreatedBy"',
            "反馈人",
            'id="rdExecutionCreatedBy" class="w-180" autocomplete="off" placeholder="可不填"',
        ),
    )
    _assert_contains_none(
        body,
        (
            "data-actual-import-preview-url=",
            "data-actual-import-confirm-url=",
        ),
    )
    _assert_contains_none(
        body,
        (
            "执行事实补录",
            "执行事件",
            "事件底座",
            "生产事实",
            "事实台账",
            "执行状态读模型",
            "这些记录来自人工填写或 Excel 导入，不代表设备自动采集",
            "请先填写反馈人",
            "暂停生产",
            "预览导入",
            "确认写入",
            "检查 Excel",
        ),
    )


def test_resource_dispatch_actual_record_url_uses_normalized_filters_when_query_date_missing(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=custom"
        "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-actual-record-url-template="/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual?' in body
    assert "query_date=2026-05-01" in body
    assert "start_date=2026-05-01" in body
    assert "end_date=2026-05-07" in body


def test_resource_dispatch_read_only_page_does_not_emit_actual_write_urls(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
        "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "只能查看" in body
    assert "不能写现场记录" in body
    assert 'href="/reports/execution-review' not in body
    for attr in (
        "data-actual-record-url-template=",
        "data-actual-template-url=",
        "data-actual-import-url=",
    ):
        assert attr not in body
    for forbidden in (
        "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual",
        "/scheduler/resource-dispatch/execution/actual-template?",
        "/scheduler/resource-dispatch/execution/import?",
        'id="rdExecutionCreatedBy"',
        'id="rdActualImportSubmit"',
    ):
        assert forbidden not in body


def test_resource_dispatch_unqueryable_write_page_does_not_render_none_links(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=team&period_preset=week&query_date=2026-05-01"
        "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'href="None"' not in body
    assert 'href=""' not in body
    assert 'data-actual-record-url-template=' not in body
    assert 'data-actual-template-url=' not in body
    assert 'data-actual-import-url=' not in body
    assert "下载填写模板" in body
    assert "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual" not in body
    assert "/scheduler/resource-dispatch/execution/actual-template?" not in body
    assert "/scheduler/resource-dispatch/execution/import?" not in body


def test_resource_dispatch_history_and_scenario_pages_do_not_emit_review_or_write_urls(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    readonly_urls = [
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-30&date_to=2026-05-06&version=1&plan_role=adopted",
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted&scenario_id=scenario-plain",
    ]

    for url in readonly_urls:
        resp = client.get(url)
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert 'href="/reports/execution-review' not in body
        for attr in (
            "data-actual-record-url-template=",
            "data-actual-template-url=",
            "data-actual-import-url=",
        ):
            assert attr not in body
        for forbidden in (
            "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual",
            "/scheduler/resource-dispatch/execution/actual-template?",
            "/scheduler/resource-dispatch/execution/import?",
            'id="rdExecutionCreatedBy"',
            'id="rdActualImportSubmit"',
        ):
            assert forbidden not in body


def test_resource_dispatch_execution_entry_rejects_incomplete_plan_context(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    page_resp = client.get("/scheduler/resource-dispatch?version=2")
    page_body = page_resp.get_data(as_text=True)

    assert page_resp.status_code == 200
    assert 'data-execution-url=""' in page_body
    assert "data-actual-record-url-template=" not in page_body
    assert "/scheduler/resource-dispatch/execution/tasks/__TASK_KEY__/actual" not in page_body

    data_resp = client.get("/scheduler/resource-dispatch/execution/data?version=2")
    payload = data_resp.get_json()

    assert data_resp.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["details"]["field"] == "plan_identity"
    assert "plan_role" in payload["error"]["details"]["missing_fields"]
    assert "period_preset" in payload["error"]["details"]["missing_fields"]
    assert "scope_type" in payload["error"]["details"]["missing_fields"]


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
        "can_write_feedback": True,
        "can_dispatch": True,
    }
    blocked_fields = [
        {"effective_plan_role": "baseline_best"},
        {"requested_plan_role": "baseline_best"},
        {"is_scenario_preview": True},
        {"is_current_executable_official_version": False},
        {"is_comparison": True},
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
    assert historical_link["disabled"] is True
    assert historical_link["url"] == ""
    assert "这是历史正式方案，只能查看" in historical_link["disabled_reason"]

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


def test_resource_dispatch_frontend_uses_actual_record_form_and_one_click_import() -> None:
    source = read_resource_dispatch_script_bundle()
    template = RESOURCE_DISPATCH_TEMPLATE.read_text(encoding="utf-8")
    css = UI_CONTRACT_CSS.read_text(encoding="utf-8")
    page_css = RESOURCE_DISPATCH_CSS.read_text(encoding="utf-8")

    _assert_contains_all(
        source,
        (
            "bindExecutionActionClicks",
            "postExecutionAction",
            "executionCreatedBy",
            "rdExecutionCreatedBy",
            "payload.created_by = createdBy",
            "payload.feedback_person = createdBy",
            "renderActualInlineForm",
            "inlineActualPayload",
        ),
    )
    _assert_contains_none(source, ("window.confirm", "window.prompt"))
    # 已记录的实际开工/完工只读展示，不预填进可编辑输入框（否则补完工会被后端整单拒绝）。
    _assert_contains_all(
        source,
        (
            "aps-execution-inline-readonly",
            "已记录，不可修改",
            "填写实际情况",
            "实际开工时间",
            "实际完工时间",
            "暂停开始时间",
            "暂停结束时间",
            "暂停时长分钟",
            "异常时间",
            "异常说明",
            "异常原因",
            "严重程度",
            "最近异常",
            "影响设备",
            "影响人员",
            "现场状态",
            "紧急异常，请计划员尽快处理。",
        ),
    )
    _assert_contains_none(
        source,
        (
            'aps-actual-start-time" value="',
            'aps-actual-finish-time" value="',
            "report-exception",
            "影响设备编号",
            "影响人员工号",
            "payload.suggest_reschedule",
        ),
    )
    _assert_contains_all(
        source,
        (
            "rdActualImportSubmit",
            "submitActualImport",
            "正在导入实际情况",
            "导入结果",
            "<th>工作表</th>",
            "可导入",
            "空白行",
            "renderActualImportResult",
        ),
    )
    _assert_contains_none(source, ("导入检查结果", "<th>Sheet</th>", "待检查", "将新增", "将跳过"))
    _assert_contains_all(
        source,
        (
            "aps-execution-record-item",
            "aps-execution-record-grid",
            "actualRecordUrlTemplate",
            "actualRecordUrl(taskKey)",
            'if (path.indexOf("?") >= 0) return path;',
            "path + query",
            "当前方案不能填写实际情况。",
            "loadExecutionRecords",
            "renderExecutionRecords",
            "/events",
            "aps-execution-events",
            "aps-execution-records",
            "normalizedUnavailableReasonTexts",
            "statusUnavailableReasonSummary",
            'actions.join("、")',
            'method: "POST"',
            'data-task-key="',
            'data-state-key="',
            'data-machine-id="',
            'data-operator-id="',
            'const base = "/scheduler/resource-dispatch/execution/tasks/" + encodeURIComponent(taskKey) + "/events";',
            "idempotency_key",
        ),
    )
    _assert_contains_none(
        source,
        (
            "requested_plan_role: identity.requested_plan_role",
            "effective_plan_role: identity.effective_plan_role",
            "source_table: identity.source_table",
            "scenario_id: identity.scenario_id",
            "__OP_ID__",
            'data-op-id="',
            'data-schedule-id="',
            'data-batch-id="',
            'data-state-revision="',
            '"schedule_id="',
            '"batch_id="',
            "expected_state_revision",
            '"start", "pause", "resume", "finish", "report_exception"',
            'map(escapeHtml).join("；")',
            "第一版",
            "请先填写反馈人",
            "填写暂停反馈",
            "填写继续生产反馈",
            "填写异常反馈",
            "暂停生产",
            "这些记录来自人工填写或 Excel 导入，不代表设备自动采集",
            "执行事实补录",
            "执行事件",
            "事件底座",
            "生产事实",
            "事实台账",
            "执行状态读模型",
        ),
    )
    _assert_contains_all(
        css,
        (
            "aps-execution-record-item",
            "aps-execution-record-wide",
            "aps-execution-inline-form",
            "aps-execution-inline-field-wide",
            "resize: vertical",
            "background: var(--ui-surface-muted",
        ),
    )
    _assert_contains_none(css, ("--ui-bg-subtle",))
    _assert_contains_all(page_css, ("aps-resource-lane-tabs", "aps-execution-bulk-maintenance"))
    _assert_contains_all(template, ('id="rdExecutionCreatedBy"', "反馈人", "现场状态", "最近异常", "影响资源"))
    _assert_contains_none(template, ("required",))


def test_resource_dispatch_execution_buttons_follow_available_actions_contract() -> None:
    source = read_resource_dispatch_script_bundle()
    render_actions = extract_js_function(source, "renderExecutionActions")

    assert 'executionAction(actions, "fill_actual")' in render_actions
    assert 'executionAction(actions, "view_records")' in render_actions
    assert "if (fillAction)" in render_actions
    assert "fillAction.enabled === true" in render_actions
    assert "viewAction && viewAction.enabled === true" in render_actions
    assert "trim(fillAction.label)" in render_actions
    assert "viewAction && viewAction.label" in render_actions
    assert "viewAction && viewAction.disabled_reason" in render_actions
    assert 'recordsDisabledAttr = opId ? "" : " disabled"' not in render_actions
    assert 'recordsTitleAttr = opId ? ""' not in render_actions


def test_manual_actual_save_refreshes_dispatch_views_after_updating_task_card() -> None:
    source = read_resource_dispatch_script_bundle()
    post_action = extract_js_function(source, "postExecutionAction")

    assert "replaceExecutionTask(responsePayload.data && responsePayload.data.task_card);" in post_action
    assert "loadData();" in post_action
    assert post_action.index("replaceExecutionTask(") < post_action.index("loadData();")
