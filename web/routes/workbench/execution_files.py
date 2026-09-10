"""Retained original bytes and read-only preflight; one atomic ledger command."""

import hashlib
import json
from io import BytesIO

from flask import g, jsonify, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.field_report_files import FieldReportFileService
from core.services.workbench.field_report_files_codec import BYTE_LIMIT, MIME, encode_issues
from core.services.workbench.field_workspace import FieldWorkspaceService
from core.services.workbench.field_workspace_scope import normalize_scope
from web.routes.workbench.api_responses import api_endpoint, query_success
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.resource_action_context import read_endpoint, resolve_context, retain_context
from web.routes.workbench.write_context import issue_write_context, validate_write_context

from .execution import arguments, command_body, field_context, validate_field_context

PREVIEW_NAMESPACE = 'workbench-field-file-preview-v1'


@read_endpoint
def field_file_preview():
    if request.args or request.mimetype != 'multipart/form-data' or set(request.files) != {'file'} or set(request.form) != {'scope', 'snapshot_ref'} or len(request.files.getlist('file')) != 1 or any(len(request.form.getlist(key)) != 1 for key in request.form):
        raise WorkbenchCommandRejected('invalid_input', '预检须包含一个文件、原筛选和读取快照。', 400)
    content = request.files['file'].read(BYTE_LIMIT + 1)
    try:
        scope = normalize_scope(json.loads(request.form['scope']))
    except (ValueError, TypeError) as exc:
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        raise WorkbenchCommandRejected('invalid_input', '文件筛选范围不是有效 JSON。', 400) from exc
    token = request.form['snapshot_ref']
    if not token:
        raise WorkbenchCommandRejected('snapshot_required', '文件预检必须保留原读取范围。', 400)
    reader = FieldWorkspaceService(g.db)
    with reader.read_snapshot():
        cohort, state = reader.cohort(scope)
        snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, token)
        preview = FieldReportFileService(g.db).preview(content, cohort)
        document = {'preview': preview, 'read_state': state, 'read_snapshot': token}
        ref, expiry = retain_context(PREVIEW_NAMESPACE, canonical_json(document), content)
        context = field_context(ref, ['import_confirm'], preview['snapshot'])
        if not preview['can_confirm']:
            context.update(capabilities={'import_confirm': False}, blocked_reasons=[{'code': 'constraint_conflict', 'message': '预检存在问题或没有可导入记录。'}])
        public = {key: value for key, value in preview.items() if key not in ('snapshot', 'items')}
        public.update(preview_ref=ref, expires_at=expiry, write_context=context)
    response = query_success(public, snapshot)
    response.headers['Cache-Control'] = 'no-store'
    return response


@api_endpoint
def field_file_confirm():
    from core.services.workbench.production_report import WorkbenchProductionReportService

    body = command_body()
    if set(body['input']) != {'preview_ref'}:
        raise WorkbenchCommandRejected('invalid_input', '确认仅接受原文件预检引用。', 400)
    ref = body['input']['preview_ref']
    # Replay must remain possible after retained bytes and edit tokens expire.
    service = WorkbenchProductionReportService(g.db, context_factory=field_context)
    def load_items():
        document, content = resolve_context(PREVIEW_NAMESPACE, ref, 'stale_write')
        stored = json.loads(document)
        preview = stored['preview']
        if not preview['can_confirm'] or hashlib.sha256(content).hexdigest() != preview['file_sha256']:
            raise WorkbenchCommandRejected('stale_write', '原文件或可执行预检无效，未替换内容。')
        cohort, read_state = FieldWorkspaceService(g.db).cohort(preview['scope'])
        bind_read_snapshot({'kind': 'field', **cohort['scope']}, read_state, stored['read_snapshot'])
        checked = FieldReportFileService(g.db).preview(content, cohort)
        if checked['items'] != preview['items'] or checked['snapshot'] != preview['snapshot'] or not checked['can_confirm']:
            raise WorkbenchCommandRejected('stale_write', '原文件对应事实或处理内容变化，请重新预检。')
        return checked['items']

    def guard(subject, action, state):
        validate_field_context(body['write_token'], subject, 'import_confirm', state)

    response = jsonify(service.execute_import(ref, request_key=body['request_key'], load_items=load_items, validate_context=guard))
    response.headers['Cache-Control'] = 'no-store'
    return response


@read_endpoint
def field_file_errors():
    if set(request.args) != {'preview_ref'} or len(request.args.getlist('preview_ref')) != 1:
        raise WorkbenchCommandRejected('invalid_input', '下载问题清单须提供原预检引用。', 400)
    document, _ = resolve_context(PREVIEW_NAMESPACE, request.args['preview_ref'], 'snapshot_stale')
    content = encode_issues(json.loads(document)['preview']['rows'])
    response = send_file(BytesIO(content), mimetype=MIME, as_attachment=True, download_name='报工导入问题.xlsx', max_age=0)
    response.headers['Cache-Control'] = 'no-store'
    return response


def download(template):
    args = arguments()
    token = args.get('snapshot_ref')
    if not token:
        raise WorkbenchCommandRejected('snapshot_required', '下载必须提供原读取快照。', 400)
    reader = FieldWorkspaceService(g.db)
    with reader.read_snapshot():
        cohort, state = reader.cohort(normalize_scope(args))
        snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, token)
        content, count = FieldReportFileService(g.db).download(cohort, template)
    response = send_file(BytesIO(content), mimetype=MIME, as_attachment=True,
                         download_name='现场分次报工模板.xlsx' if template else '现场报工导出.xlsx', max_age=0)
    response.headers['Cache-Control'] = 'no-store'
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
