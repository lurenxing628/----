"""EK real EA adoption, production HTTP routes, and isolated temporary server."""

import uuid
from datetime import datetime

from flask import Blueprint, Flask, g, request, send_from_directory

from core.infrastructure.database import get_connection
from core.services.workbench.execution.actual_gantt import ActualGanttService
from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope
from tests.workbench.ea_zero_duration_support import adopt, point_candidate
from web.routes.workbench.actual_gantt import register_actual_gantt_routes
from web.routes.workbench.execution import register_execution_routes
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.reports import register_report_routes
from web.routes.workbench.resources import register_resource_routes
from web.runtime_host import install_wall_clock

ACTUAL = '/api/workbench/v1/actual-gantt'
FIELD = '/api/workbench/v1/execution'
# Actual-Gantt and field reads are POSTs; like GETs they run on a query-only connection.
READS = {'ek_point_routes.' + name for name in ('actual_gantt_workspace', 'actual_gantt_export', 'field_tasks', 'field_task',
                                                 'field_file_template', 'field_file_export')}


def adopted(case, **options):
    candidate = point_candidate(case, **options)
    plan = adopt(case, candidate, key='ek-point-adopt-' + uuid.uuid4().hex)
    reader = ActualGanttService(case.conn)
    with reader.read_snapshot() as gantt_scope:
        data, _ = reader.workspace(gantt_scope, ActualGanttScope(plan['plan_ref']), full_workspace=True)
    return {'candidate_ref': candidate, 'plan': plan, 'task': data['items'][0]['task']}


def app_for(case, output=None):
    app = Flask('ek-point-downstream', static_folder=None)
    install_wall_clock(app, datetime.now)
    app.config.update(TESTING=True, DATABASE_PATH=str(case.path))
    bp = Blueprint('ek_point_routes', __name__)
    register_actual_gantt_routes(bp)
    register_execution_routes(bp)
    register_plan_read_routes(bp)
    register_report_routes(bp)
    register_resource_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def bind():
        g.db = get_connection(str(case.path))
        if request.method == 'GET' or request.endpoint in READS:
            g.db.execute('PRAGMA query_only=ON')

    @app.teardown_request
    def close(error):
        g.db.close()

    if output is not None:
        @app.route('/')
        def index():
            return send_from_directory(str(output), 'index.html')

        @app.route('/assets/<path:name>')
        def assets(name):
            return send_from_directory(str(output), name)

    return app


def _success(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result['ok'] is True
    return result


def read(client, path, **scope):
    return _success(client.get(path, query_string=scope))


def read_body(client, path, **scope):
    """Actual-Gantt and field reads carry their scope in a JSON body."""
    return _success(client.post(path, json=scope))


def report(client, identity, *, quantity=1, start='2026-09-09T08:00:00', end='2026-09-09T09:30:00', hours=1.25):
    task = identity['task']
    current = read_body(client, FIELD + '/tasks/' + task['task_ref'], plan_ref=task['plan_ref'])['data']['task']
    values = {'completed_quantity': quantity, 'actual_start': start, 'actual_end': end,
              'effective_processing_hours': hours, 'actual_machine_ref': task['machine_ref'],
              'actual_operator_ref': task['operator_ref'], 'remark': 'EK real report',
              'source': 'manual', 'declared_operator': 'EK test'}
    response = client.post(FIELD + '/tasks/' + task['task_ref'] + '/reports', json={
        'request_key': 'ek-report-' + uuid.uuid4().hex,
        'write_token': current['execution']['write_context']['write_token'], 'input': values})
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result['ok'] is True, result
    return result['data']['rows'][0]
