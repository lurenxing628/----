"""EK real EA adoption, production HTTP routes, and isolated temporary server."""

import uuid
from contextlib import contextmanager
from threading import Thread

from flask import Blueprint, Flask, g, request, send_from_directory
from werkzeug.serving import make_server

from core.infrastructure.database import get_connection
from core.services.workbench.actual_gantt import ActualGanttService
from core.services.workbench.actual_gantt_scope import ActualGanttScope
from tests.workbench.ea_zero_duration_support import adopt, point_candidate
from web.routes.workbench.actual_gantt import register_actual_gantt_routes
from web.routes.workbench.execution import register_execution_routes
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.reports import register_report_routes
from web.routes.workbench.resources import register_resource_routes

ACTUAL = '/api/workbench/v1/actual-gantt'
FIELD = '/api/workbench/v1/execution'


def adopted(case, **options):
    candidate = point_candidate(case, **options)
    plan = adopt(case, candidate, key='ek-point-adopt-' + uuid.uuid4().hex)
    reader = ActualGanttService(case.conn)
    with reader.read_snapshot():
        data, _ = reader.workspace(ActualGanttScope(plan['plan_ref']))
    return {'candidate_ref': candidate, 'plan': plan, 'task': data['items'][0]['task']}


def app_for(case, output=None):
    app = Flask('ek-point-downstream', static_folder=None)
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
        if request.method == 'GET':
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


def read(client, path, **scope):
    response = client.get(path, query_string=scope)
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result['ok'] is True
    return result


def report(client, identity, *, quantity=1, start='2026-09-09T08:00:00', end='2026-09-09T09:30:00', hours=1.25):
    task = identity['task']
    current = read(client, FIELD + '/tasks/' + task['task_ref'], plan_ref=task['plan_ref'])['data']['task']
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


@contextmanager
def serve(app):
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        assert not thread.is_alive()
