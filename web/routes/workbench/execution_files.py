"""Retained original bytes and read-only preflight; one atomic ledger command."""

from io import BytesIO

from flask import g, request, send_file

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_field_report_source import PreparedFieldReportSource
from core.services.workbench import messages
from core.services.workbench.execution.field_report_files import FieldReportFileService
from core.services.workbench.execution.field_report_files_codec import BYTE_LIMIT, MIME, decode_reports, encode_issues
from core.services.workbench.execution.field_workspace import FieldWorkspaceService
from core.services.workbench.execution.field_workspace_scope import normalize_scope
from core.shared.strict_json import load_strict_json
from web.api_responses import json_response, query_success
from web.routes.workbench.api_responses import api_endpoint
from web.routes.workbench.read_budget import PLAN_READ_SLOTS
from web.routes.workbench.read_context import bind_read_snapshot, fact_value
from web.routes.workbench.request_json import rejecter
from web.routes.workbench.resource_action_context import read_endpoint, resolve_context, retain_context
from web.routes.workbench.write_context import preview_write_context, validate_preview_confirmation

from .execution import arguments, command_body

# 报工文件弹窗：没有预检结果时按钮叫「开始预检」，出了预检结果后改为「重新预检」；换文件要点「选择文件」。
PREVIEW_NAMESPACE = 'workbench-field-file-preview-v1'


@read_endpoint
def field_file_preview():
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService

    if request.args or request.mimetype != 'multipart/form-data' or set(request.files) != {'file'} or set(request.form) != {'scope', 'snapshot_ref'} or len(request.files.getlist('file')) != 1 or any(len(request.form.getlist(key)) != 1 for key in request.form):
        raise WorkbenchCommandRejected('invalid_input', '请先选择一个文件，并确认本页数据没有过期；报工还没有写入。请刷新页面后点「开始预检」。', 400)
    content = request.files['file'].read(BYTE_LIMIT + 1)
    scope = normalize_scope(load_strict_json(request.form['scope'], on_malformed=rejecter(
        '文件导入范围读不出来，报工还没有写入。请刷新页面后重新点「开始预检」。')))
    token = request.form['snapshot_ref']
    if not token:
        raise WorkbenchCommandRejected('snapshot_required', messages.STALE, 400)
    # 文件先在读事务外解析，再排队读取整份现场范围。
    decoded = decode_reports(content)
    source = PreparedFieldReportSource.build(content, decoded)
    files = FieldReportFileService(g.db, production=WorkbenchProductionReportService(g.db))
    reader = FieldWorkspaceService(g.db, ledger=files.production.ledger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            cohort, state, _ = reader.cohort(scope)
            snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, token)
            preview, _ = files.prepare_source(source, cohort)
    document = {'preview': preview, 'read_state': fact_value(state)}
    ref, expiry = retain_context(PREVIEW_NAMESPACE, document, source, key=source.source_ref)
    context = preview_write_context(ref, expiry, ['import_confirm'])
    if not preview['can_confirm']:
        context.update(capabilities={'import_confirm': False}, blocked_reasons=[{'code': 'constraint_conflict', 'message': '文件里有问题行或没有可导入的记录，一条报工都没有写入。请修好文件后点「选择文件」重新选择，再点「开始预检」。'}])
    public = {key: value for key, value in preview.items() if key not in ('snapshot', 'items')}
    public.update(preview_ref=ref, expires_at=expiry, write_context=context)
    return query_success(public, snapshot)


@api_endpoint
def field_file_confirm():
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService

    body = command_body()
    if set(body['input']) != {'preview_ref'}:
        raise WorkbenchCommandRejected('invalid_input', '只能确认刚才预检过的那份文件，报工还没有写入。请点「重新预检」。', 400)
    ref = body['input']['preview_ref']
    # Replay must remain possible after retained bytes and edit tokens expire.
    service = WorkbenchProductionReportService(g.db)
    files = FieldReportFileService(g.db, production=service)
    reader = FieldWorkspaceService(g.db, ledger=service.ledger)

    def load_items():
        document, source = resolve_context(PREVIEW_NAMESPACE, ref, 'stale_write')
        preview = document['preview']
        if not preview['can_confirm']:
            raise WorkbenchCommandRejected('stale_write', '预检结果已过期，报工还没有写入，也没有替换任何内容。请点「重新预检」。')
        with service.ledger.read_snapshot():
            cohort, read_state, _ = reader.cohort(preview['scope'])
            if fact_value(read_state) != document['read_state']:
                raise WorkbenchCommandRejected('stale_write', '预检之后报工记录有变化，报工还没有写入。请点「重新预检」。')
            checked, prepared = files.prepare_source(source, cohort)
        if not same(checked['items'], preview['items']) or not same(checked['snapshot'], preview['snapshot']) or not checked['can_confirm']:
            raise WorkbenchCommandRejected('stale_write', '预检之后报工记录有变化，报工还没有写入。请点「重新预检」。')
        return prepared

    def guard(subject, action, state):
        # Database facts may be unchanged while the preview expires waiting for this write lock.
        resolve_context(PREVIEW_NAMESPACE, subject, 'stale_write')
        validate_preview_confirmation(body['write_token'], subject)

    # 整份现场范围和文件复核在拿写锁前的读快照里做；写锁里库没变就直接沿用，只核对并写入报工。
    return json_response(service.execute_import(ref, request_key=body['request_key'], load_items=load_items, validate_context=guard,
                                                admission=PLAN_READ_SLOTS.slot))


@read_endpoint
def field_file_errors():
    if set(request.args) != {'preview_ref'} or len(request.args.getlist('preview_ref')) != 1:
        raise WorkbenchCommandRejected('invalid_input', '预检结果已过期，没有开始下载。请点「重新预检」。', 400)
    document, _ = resolve_context(PREVIEW_NAMESPACE, request.args['preview_ref'], 'snapshot_stale')
    content = encode_issues(document['preview']['rows'])
    return send_file(BytesIO(content), mimetype=MIME, as_attachment=True, download_name='报工导入问题.xlsx', max_age=0)


def download(template):
    args = arguments()
    token = args.get('snapshot_ref')
    if not token:
        raise WorkbenchCommandRejected('snapshot_required', messages.STALE, 400)
    reader = FieldWorkspaceService(g.db)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            cohort, state, resource_codes = reader.cohort(normalize_scope(args))
            snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, token)
    # 读事务和读额度都已释放：XLSX 只用已读出的现场范围生成。
    content, count = FieldReportFileService.download(cohort, template, resource_codes=resource_codes)
    response = send_file(BytesIO(content), mimetype=MIME, as_attachment=True,
                         download_name='现场分次报工模板.xlsx' if template else '现场报工导出.xlsx', max_age=0)
    response.headers['X-Workbench-Row-Count'] = str(count)
    response.headers['X-Workbench-Snapshot-Ref'] = snapshot['snapshot_ref']
    return response


@read_endpoint
def field_file_template():
    return download(True)


@read_endpoint
def field_file_export():
    return download(False)


def register_execution_file_routes(bp):
    root = '/api/workbench/v1/execution/files/'
    for path, view, method in [('preview', field_file_preview, 'POST'), ('confirm', field_file_confirm, 'POST'),
                               ('template', field_file_template, 'GET'), ('export', field_file_export, 'GET'),
                               ('errors', field_file_errors, 'GET')]:
        bp.add_url_rule(root + path, view_func=view, methods=[method])
