"""Field namespace registration. Caller owns blueprint, app startup and schema."""

from flask import g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.field_workspace import FieldWorkspaceService
from core.services.workbench.field_workspace_scope import PARAMETERS, normalize_scope, page_input
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from web.routes.workbench.api_responses import api_endpoint, query_success
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def arguments():
    if set(request.args) - set(PARAMETERS) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected('invalid_input', '现场查询含未知或重复参数。', 400)
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
        raise WorkbenchCommandRejected('snapshot_required', '翻页必须保留原读取快照。', 400)
    reader = FieldWorkspaceService(g.db, context_factory=field_context)
    with reader.read_snapshot():
        cohort, state = reader.cohort(scope)
        snapshot = bind_read_snapshot({'kind': 'field', **cohort['scope']}, state, args.get('snapshot_ref'))
        if args.get('task_ref'):
            selected = reader.detail(cohort, args['task_ref'])['task']
            if args.get('operation_ref') and selected['operation_ref'] != args['operation_ref']:
                raise WorkbenchCommandRejected('constraint_conflict', '来源工序与原任务不匹配，未改指安排。')
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
        raise WorkbenchCommandRejected('invalid_input', '保存须提供明确 JSON 请求。', 400)
    body = request.get_json()
    if type(body) is not dict or set(body) != {'input', 'request_key', 'write_token'} or type(body['input']) is not dict:
        raise WorkbenchCommandRejected('invalid_input', '保存请求合同不完整或包含未知字段。', 400)
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


def register_execution_routes(bp):
    from .execution_files import register_execution_file_routes

    root = '/api/workbench/v1/execution'
    for path, view, method in [('/tasks', field_tasks, 'GET'), ('/tasks/<task_ref>', field_task, 'GET'),
                               ('/tasks/<task_ref>/reports', field_report_create, 'POST'),
                               ('/reports/<report_ref>/supplement', field_report_supplement, 'POST'),
                               ('/reports/<report_ref>/correct', field_report_correct, 'POST')]:
        bp.add_url_rule(root + path, view_func=view, methods=[method])
    register_execution_file_routes(bp)
