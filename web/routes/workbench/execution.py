"""Field namespace registration. Caller owns blueprint, app startup and schema."""

from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES
from core.services.workbench.execution.field_workspace import FieldWorkspaceService
from core.services.workbench.execution.field_workspace_scope import PARAMETERS, normalize_scope, page_input
from web.api_responses import json_response, query_success
from web.routes.workbench.api_responses import api_endpoint, read_endpoint
from web.routes.workbench.read_budget import PLAN_READ_SLOTS
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def arguments():
    if set(request.args) - set(PARAMETERS) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected('invalid_input', '现场记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。', 400)
    return request.args.to_dict()


def field_query(task_ref=None):
    args = arguments()
    scope = normalize_scope(args)
    number, size = page_input(args)
    reader = FieldWorkspaceService(g.db, context_factory=issue_write_context)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            cohort, state, _ = reader.cohort(scope)
    # 读事务已结束：定位页码、给这一页签发报工令牌只用已算好的范围，不再占着读锁。
    snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, args.get('snapshot_ref'))
    if args.get('task_ref'):
        # 定位页码只在已算好的范围里查，不签报工令牌；令牌由下面 page() 给这一页签发一次。
        index = next((index for index, row in enumerate(cohort['tasks']) if row['task_ref'] == args['task_ref']), None)
        if index is None:
            raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
        if args.get('operation_ref') and cohort['tasks'][index]['operation_ref'] != args['operation_ref']:
            raise WorkbenchCommandRejected('constraint_conflict', '选中的工序和这条任务对不上，安排没有变化。请刷新页面后重新选择工序。')
        if task_ref is None:
            number = index // size + 1
    data = reader.detail(cohort, task_ref) if task_ref else reader.page(cohort, number, size)
    response = query_success(data, snapshot, byte_limit=MAX_PLAN_RESPONSE_BYTES)
    response.headers['Cache-Control'] = 'no-store'
    return response


@api_endpoint
def field_tasks():
    return field_query()


@api_endpoint
def field_task(task_ref):
    return field_query(task_ref)


def command_body():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected('invalid_input', '提交的内容格式不正确，报工还没有保存。请刷新页面后重新填写。', 400)
    body = request.get_json()
    if type(body) is not dict or set(body) != {'input', 'request_key', 'write_token'} or type(body['input']) is not dict:
        raise WorkbenchCommandRejected('invalid_input', '提交的内容不完整或有多余项，报工还没有保存。请刷新页面后重新填写。', 400)
    validate_request_key(body['request_key'])
    g.workbench_request_key = body['request_key']
    return body


def save_report(action, ref):
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService

    body = command_body()
    service = WorkbenchProductionReportService(g.db)
    result = service.execute(action, ref, body['input'], request_key=body['request_key'],
                             validate_context=lambda subject, operation, snapshot: validate_write_context(body['write_token'], subject, operation, snapshot))
    response = json_response(result)
    response.headers['Cache-Control'] = 'no-store'
    return response


@api_endpoint
def field_report_create(task_ref):
    return save_report('create', task_ref)


@api_endpoint
def field_report_supplement(report_ref):
    return save_report('supplement', report_ref)


@api_endpoint
def field_report_correct(report_ref):
    return save_report('correct', report_ref)


@api_endpoint
def field_report_void(report_ref):
    return save_report('report_void', report_ref)


@read_endpoint
def field_report_void_preview(report_ref):
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService

    body = request.get_json(silent=True)
    if request.args or type(body) is not dict or set(body) != {'input'} or type(body['input']) is not dict:
        raise WorkbenchCommandRejected('invalid_input', '请填写撤销原因后重新查看影响。', 400)
    service = WorkbenchProductionReportService(g.db, context_factory=issue_write_context)
    preview = service.preview('report_void', report_ref, body['input'])
    snapshot = bind_read_snapshot({'kind': 'report_void', 'report_ref': report_ref}, preview.pop('snapshot'))
    response = query_success(preview, snapshot, byte_limit=MAX_PLAN_RESPONSE_BYTES)
    response.headers['Cache-Control'] = 'no-store'
    return response


def register_execution_routes(bp):
    from .execution_files import register_execution_file_routes

    root = '/api/workbench/v1/execution'
    for path, view, method in [('/tasks', field_tasks, 'GET'), ('/tasks/<task_ref>', field_task, 'GET'),
                               ('/tasks/<task_ref>/reports', field_report_create, 'POST'),
                               ('/reports/<report_ref>/supplement', field_report_supplement, 'POST'),
                               ('/reports/<report_ref>/correct', field_report_correct, 'POST'),
                               ('/reports/<report_ref>/void-preview', field_report_void_preview, 'POST'),
                               ('/reports/<report_ref>/void', field_report_void, 'POST')]:
        bp.add_url_rule(root + path, view_func=view, methods=[method])
    register_execution_file_routes(bp)
