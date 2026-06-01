from __future__ import annotations

from tests.operation_execution_feedback_test_support import (
    RESOURCE_DISPATCH_TEMPLATE,
    UI_CONTRACT_CSS,
    _build_app,
    read_resource_dispatch_script_bundle,
)
from tests.resource_dispatch_frontend_support import extract_js_function


def test_resource_dispatch_page_has_site_records_words_and_excel_entries(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    source = read_resource_dispatch_script_bundle()
    page_contract = body + "\n" + source
    for expected in ("现场记录", "填写实际情况", "导入实际情况 Excel", "下载填写模板", "查看计划和实际"):
        assert expected in page_contract
    assert "data-execution-url=" in body
    assert "data-actual-record-url-template=" in body
    assert "data-actual-template-url=" in body
    assert "data-actual-import-url=" in body
    assert 'data-actual-record-url-template="/scheduler/resource-dispatch/execution/__OP_ID__/actual"' in body
    assert 'data-actual-template-url="/scheduler/resource-dispatch/execution/actual-template?' in body
    assert 'data-actual-import-url="/scheduler/resource-dispatch/execution/import?' in body
    assert "data-actual-import-preview-url=" not in body
    assert "data-actual-import-confirm-url=" not in body
    assert 'href="/reports/execution-review?version=2' in body
    assert "plan_role=adopted" in body
    assert "query_date=2026-05-01" in body
    assert "period_preset=week" in body
    assert "scope_type=operator" in body
    assert "scope_id=O1" in body
    assert 'id="rdExecutionCreatedBy"' in body
    assert "反馈人" in body
    assert 'id="rdExecutionCreatedBy" class="w-180" autocomplete="off" placeholder="可不填"' in body
    for forbidden in (
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
    ):
        assert forbidden not in body


def test_resource_dispatch_read_only_page_does_not_emit_actual_write_urls(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=baseline_best"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "只能查看" in body
    assert "不能提交现场反馈" in body
    assert 'href="/reports/execution-review' not in body
    for forbidden in (
        "/scheduler/resource-dispatch/execution/__OP_ID__/actual",
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
        "/scheduler/resource-dispatch?scope_type=team&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'href="None"' not in body
    assert 'href=""' not in body
    assert 'data-actual-record-url-template=""' in body
    assert 'data-actual-template-url=""' in body
    assert 'data-actual-import-url=""' in body
    assert "下载填写模板" in body
    assert "/scheduler/resource-dispatch/execution/__OP_ID__/actual" not in body
    assert "/scheduler/resource-dispatch/execution/actual-template?" not in body
    assert "/scheduler/resource-dispatch/execution/import?" not in body


def test_resource_dispatch_history_and_scenario_pages_do_not_emit_review_or_write_urls(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

    monkeypatch.setattr(rd_routes, "_export_url", lambda _filters: "")

    readonly_urls = [
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&version=1&plan_role=adopted",
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted&scenario_id=scenario-plain",
    ]

    for url in readonly_urls:
        resp = client.get(url)
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert 'href="/reports/execution-review' not in body
        for forbidden in (
            "/scheduler/resource-dispatch/execution/__OP_ID__/actual",
            "/scheduler/resource-dispatch/execution/actual-template?",
            "/scheduler/resource-dispatch/execution/import?",
            'id="rdExecutionCreatedBy"',
            'id="rdActualImportSubmit"',
        ):
            assert forbidden not in body


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
        "can_write_feedback": True,
        "can_dispatch": True,
    }
    blocked_fields = [
        {"effective_plan_role": "baseline_best"},
        {"requested_plan_role": "baseline_best"},
        {"is_scenario_preview": True},
        {"is_superseded_by_newer_version": True},
        {"is_comparison": True},
    ]

    for override in blocked_fields:
        link = _execution_review_link(dict(base_filters, **override), dict(base_filters, **override))
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]

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

    assert "bindExecutionActionClicks" in source
    assert "postExecutionAction" in source
    assert "executionCreatedBy" in source
    assert "rdExecutionCreatedBy" in source
    assert "payload.created_by = createdBy" in source
    assert "payload.feedback_person = createdBy" in source
    assert "window.confirm" not in source
    assert "window.prompt" not in source
    assert "renderActualInlineForm" in source
    assert "inlineActualPayload" in source
    # 已记录的实际开工/完工只读展示，不预填进可编辑输入框（否则补完工会被后端整单拒绝）。
    assert "aps-execution-inline-readonly" in source
    assert "已记录，不可修改" in source
    assert 'aps-actual-start-time" value="' not in source
    assert 'aps-actual-finish-time" value="' not in source
    assert "填写实际情况" in source
    assert "实际开工时间" in source
    assert "实际完工时间" in source
    assert "暂停开始时间" in source
    assert "暂停结束时间" in source
    assert "暂停时长分钟" in source
    assert "异常时间" in source
    assert "异常说明" in source
    assert "异常原因" in source
    assert "严重程度" in source
    assert "report-exception" not in source
    assert "影响设备编号" not in source
    assert "影响人员工号" not in source
    assert "payload.suggest_reschedule" not in source
    assert "最近异常" in source
    assert "影响设备" in source
    assert "影响人员" in source
    assert "现场状态" in source
    assert "紧急异常，请计划员尽快处理。" in source
    assert "rdActualImportSubmit" in source
    assert "submitActualImport" in source
    assert "正在导入实际情况" in source
    assert "导入结果" in source
    assert "导入检查结果" not in source
    assert "<th>工作表</th>" in source
    assert "<th>Sheet</th>" not in source
    assert "待检查" not in source
    assert "将新增" not in source
    assert "将跳过" not in source
    assert "可导入" in source
    assert "空白行" in source
    assert "renderActualImportResult" in source
    assert "aps-execution-record-item" in source
    assert "aps-execution-record-grid" in source
    assert "actualRecordUrlTemplate" in source
    assert "actualRecordUrl(opId)" in source
    assert "path + query" in source
    assert "requested_plan_role: identity.requested_plan_role" not in source
    assert "effective_plan_role: identity.effective_plan_role" not in source
    assert "source_table: identity.source_table" not in source
    assert "scenario_id: identity.scenario_id" not in source
    assert "当前方案不能填写实际情况。" in source
    assert "loadExecutionRecords" in source
    assert "renderExecutionRecords" in source
    assert "/events" in source
    assert "aps-execution-events" in source
    assert "aps-execution-records" in source
    assert "aps-execution-record-item" in css
    assert "aps-execution-record-wide" in css
    assert "aps-execution-inline-form" in css
    assert "aps-execution-inline-field-wide" in css
    assert "resize: vertical" in css
    assert "background: var(--ui-surface-muted" in css
    assert "--ui-bg-subtle" not in css
    assert "normalizedUnavailableReasonTexts" in source
    assert "statusUnavailableReasonSummary" in source
    assert '"start", "pause", "resume", "finish", "report_exception"' not in source
    assert 'actions.join("、")' in source
    assert 'map(escapeHtml).join("；")' not in source
    assert "第一版" not in source
    assert 'id="rdExecutionCreatedBy"' in template
    assert "required" not in template
    assert "反馈人" in template
    assert "现场状态" in template
    assert "最近异常" in template
    assert "影响资源" in template
    assert 'method: "POST"' in source
    assert 'data-op-id="' in source
    assert 'data-state-revision="' in source
    assert 'data-machine-id="' in source
    assert 'data-operator-id="' in source
    assert 'const base = "/scheduler/resource-dispatch/execution/" + encodeURIComponent(opId) + "/events";' in source
    assert "idempotency_key" in source
    for forbidden in (
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
    ):
        assert forbidden not in source


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
