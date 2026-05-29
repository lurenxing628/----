from __future__ import annotations

from tests.operation_execution_feedback_test_support import (
    RESOURCE_DISPATCH_JS,
    RESOURCE_DISPATCH_TEMPLATE,
    UI_CONTRACT_CSS,
    _build_app,
)


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
    source = RESOURCE_DISPATCH_JS.read_text(encoding="utf-8")
    page_contract = body + "\n" + source
    for expected in ("现场记录", "填写实际情况", "导入实际情况 Excel", "下载填写模板", "查看计划和实际"):
        assert expected in page_contract
    assert "data-execution-url=" in body
    assert "data-actual-template-url=" in body
    assert "data-actual-import-url=" in body
    assert 'data-actual-template-url="/scheduler/resource-dispatch/execution/actual-template?' in body
    assert 'data-actual-import-url="/scheduler/resource-dispatch/execution/import?' in body
    assert "data-actual-import-preview-url=" not in body
    assert "data-actual-import-confirm-url=" not in body
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


def test_resource_dispatch_frontend_uses_actual_record_form_and_one_click_import() -> None:
    source = RESOURCE_DISPATCH_JS.read_text(encoding="utf-8")
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
    assert "待检查" not in source
    assert "将新增" not in source
    assert "将跳过" not in source
    assert "可导入" in source
    assert "空白行" in source
    assert "renderActualImportResult" in source
    assert "aps-execution-record-item" in source
    assert "aps-execution-record-grid" in source
    assert "/actual" in source
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
    assert "/scheduler/resource-dispatch/execution/" in source
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
