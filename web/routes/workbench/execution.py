"""Field namespace registration. Caller owns blueprint, app startup and schema."""

from flask import g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.workbench.field_workspace import FieldWorkspaceService
from core.services.workbench.field_workspace_scope import PARAMETERS, normalize_scope, page_input
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from web.routes.workbench.api_responses import api_endpoint, query_success
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def arguments():
    if set(request.args) - set(PARAMETERS) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected('invalid_input', '现场记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。', 400)
    return request.args.to_dict()


def field_context(subject, actions, state):
    return issue_write_context(subject, actions, plain_plan_facts(state))


def validate_field_context(token, subject, action, state):
    return validate_write_context(token, subject, action, plain_plan_facts(state))


def field_query(task_ref=None):
    args = arguments()
    scope = normalize_scope(args)
    number, size = page_input(args)
    if number > 1 and not args.get('snapshot_ref'):
        raise WorkbenchCommandRejected('snapshot_required', '翻页位置已失效，请回到第 1 页重新查询。', 400)
    reader = FieldWorkspaceService(g.db, context_factory=field_context)
    with reader.read_snapshot():
        cohort, state = reader.cohort(scope)
        snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, args.get('snapshot_ref'))
        if args.get('task_ref'):
            selected = reader.detail(cohort, args['task_ref'])['task']
            if args.get('operation_ref') and selected['operation_ref'] != args['operation_ref']:
                raise WorkbenchCommandRejected('constraint_conflict', '选中的工序和这条任务对不上，安排没有变化。请刷新页面后重新选择工序。')
            number = next(index for index, row in enumerate(cohort['tasks']) if row['task_ref'] == selected['task_ref']) // size + 1
        data = reader.detail(cohort, task_ref) if task_ref else reader.page(cohort, number, size)
    response = query_success(data, snapshot)
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
    g.workbench_request_key = body['request_key']
    return body


def save_report(action, ref):
    from core.services.workbench.production_report import WorkbenchProductionReportService

    body = command_body()
    service = WorkbenchProductionReportService(g.db, context_factory=field_context)
    result = service.execute(action, ref, body['input'], request_key=body['request_key'],
                             validate_context=lambda subject, operation, snapshot: validate_field_context(body['write_token'], subject, operation, snapshot))
    response = jsonify(result)
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


@api_endpoint
def field_report_void_preview(report_ref):
    from core.services.workbench.production_report import WorkbenchProductionReportService

    body = request.get_json(silent=True)
    if request.args or type(body) is not dict or set(body) != {'input'} or type(body['input']) is not dict:
        raise WorkbenchCommandRejected('invalid_input', '请填写撤销原因后重新查看影响。', 400)
    service = WorkbenchProductionReportService(g.db, context_factory=field_context)
    preview = service.preview('report_void', report_ref, body['input'])
    snapshot = bind_read_snapshot({'kind': 'report_void', 'report_ref': report_ref}, input_fingerprint(preview.pop('snapshot')))
    response = query_success(preview, snapshot)
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
