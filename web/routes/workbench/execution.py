"""Field namespace registration. Caller owns blueprint, app startup and schema."""

from flask import current_app, g

from core.models.workbench_load_limits import MAX_WINDOW_RESPONSE_BYTES
from core.services.workbench.execution.field_workspace import FieldWorkspaceService
from core.services.workbench.execution.field_workspace_scope import normalize_scope, page_input
from core.shared.key_sets import keys_conform
from web.api_responses import json_response, query_success
from web.routes.workbench.api_responses import api_endpoint, read_endpoint
from web.routes.workbench.read_budget import PLAN_READ_SLOTS
from web.routes.workbench.read_context import bind_read_snapshot, current_snapshot_time, read_snapshot_time
from web.routes.workbench.write_context import issue_write_context, validate_write_context
from web.runtime_host import wall_clock

from .execution_files import register_execution_file_routes
from .execution_request import field_command, field_read
from .request_json import BodyTexts, read_json_body, rejecter

_VOID_PREVIEW_REJECTED = '请填写撤销原因后重新查看影响。'
_VOID_PREVIEW = BodyTexts(transport=_VOID_PREVIEW_REJECTED, malformed=_VOID_PREVIEW_REJECTED,
                          incomplete=_VOID_PREVIEW_REJECTED)


def field_query(task_ref=None):
    args = field_read()
    scope = normalize_scope(args)
    number, size = page_input(args)
    locate_task_ref = args.get('task_ref')
    locate_operation_ref = args.get('operation_ref')
    token = args.get('snapshot_ref')
    as_of, binding = read_snapshot_time(token)
    reader = FieldWorkspaceService(g.db, context_factory=issue_write_context)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot() as ws_scope:
            read_state = reader.prepare_read(ws_scope, scope)
            snapshot = bind_read_snapshot({'kind': 'field', **read_state.effective_scope}, read_state.state, token,
                                          as_of=as_of, binding=binding)
            data = (
                reader.detail(
                    ws_scope,
                    read_state,
                    task_ref,
                    locate_task_ref=locate_task_ref,
                    locate_operation_ref=locate_operation_ref,
                )
                if task_ref
                else reader.page(
                    ws_scope,
                    read_state,
                    number,
                    size,
                    locate_task_ref=locate_task_ref,
                    locate_operation_ref=locate_operation_ref,
                )
            )
    return query_success(data, snapshot, byte_limit=MAX_WINDOW_RESPONSE_BYTES)


@read_endpoint
def field_tasks():
    return field_query()


@read_endpoint
def field_task(task_ref):
    return field_query(task_ref)


def save_report(action, ref):
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService

    body = field_command()
    service = WorkbenchProductionReportService(g.db, clock=wall_clock(current_app))
    result = service.execute(action, ref, body['input'], request_key=body['request_key'],
                             validate_context=lambda subject, operation, snapshot: validate_write_context(body['write_token'], subject, operation, snapshot))
    return json_response(result)


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

    body = read_json_body(_VOID_PREVIEW)
    if not keys_conform(body, ('input',)) or type(body['input']) is not dict:
        rejecter(_VOID_PREVIEW_REJECTED)()
    now = current_snapshot_time()
    service = WorkbenchProductionReportService(g.db, clock=wall_clock(current_app), context_factory=issue_write_context)
    preview = service.preview_void(report_ref, body['input'], now=now)
    snapshot = bind_read_snapshot({'kind': 'report_void', 'report_ref': report_ref}, preview.pop('snapshot'), as_of=now)
    return query_success(preview, snapshot, byte_limit=MAX_WINDOW_RESPONSE_BYTES)


def register_execution_routes(bp):
    root = '/api/workbench/v1/execution'
    for path, view, method in [('/tasks', field_tasks, 'POST'), ('/tasks/<task_ref>', field_task, 'POST'),
                               ('/tasks/<task_ref>/reports', field_report_create, 'POST'),
                               ('/reports/<report_ref>/supplement', field_report_supplement, 'POST'),
                               ('/reports/<report_ref>/correct', field_report_correct, 'POST'),
                               ('/reports/<report_ref>/void-preview', field_report_void_preview, 'POST'),
                               ('/reports/<report_ref>/void', field_report_void, 'POST')]:
        bp.add_url_rule(root + path, view_func=view, methods=[method])
    register_execution_file_routes(bp)
