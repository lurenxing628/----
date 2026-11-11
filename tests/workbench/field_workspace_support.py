"""AK-only Flask fixture, backed exclusively by pytest's temporary SQLite path."""

import json
import sqlite3
import uuid
from io import BytesIO

import pytest
from flask import Blueprint, Flask, g, request

from tests.workbench.execution_ledger_support import ledger_case as _ledger_fixture
from web.routes.workbench.commands import register_command_routes
from web.routes.workbench.execution import register_execution_routes
from web.routes.workbench.resources import register_resource_routes

BASE = '/api/workbench/v1/execution'


def success(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body['ok'] is True
    return body


def make_app(path):
    app = Flask('ak-field-only')
    app.config['TESTING'] = True
    statements = []
    bp = Blueprint('workbench', __name__)
    register_execution_routes(bp)
    register_resource_routes(bp)
    register_command_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        from core.infrastructure.sqlite_udf import register_schedule_time_sql_functions

        g.db = sqlite3.connect(str(path))
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        register_schedule_time_sql_functions(g.db)
        if request.method == 'GET' or request.path.endswith('/preview'):
            g.db.execute('PRAGMA query_only=ON')
        g.db.set_trace_callback(statements.append)

    @app.teardown_request
    def close(error):
        g.db.close()

    app.ak_statements = statements
    return app


class FieldAPI:
    def __init__(self, case):
        self.case = case
        self.path = case.conn.execute('PRAGMA database_list').fetchone()[2]
        self.app = make_app(self.path)
        self.client = self.app.test_client()

    def read(self, suffix='/tasks', **scope):
        return success(self.client.get(BASE + suffix, query_string=scope))

    def task(self, **scope):
        return self.read(**scope)['data']['tasks'][0]

    def body(self, context, payload):
        return {'request_key': 'field-' + uuid.uuid4().hex, 'write_token': context['write_token'], 'input': payload}

    def create(self, values=None, task=None):
        task = task or self.task()
        body = self.body(task['execution']['write_context'], values or self.case.values(2))
        return success(self.client.post(BASE + '/tasks/' + task['task_ref'] + '/reports', json=body))

    def upload(self, content, reading=None):
        reading = reading or self.read()
        return self.client.post(BASE + '/files/preview', data={'file': (BytesIO(content), 'field.xlsx'),
            'scope': json.dumps(reading['data']['scope']), 'snapshot_ref': reading['meta']['snapshot_ref']})

    def confirm_body(self, preview):
        return self.body(preview['data']['write_context'], {'preview_ref': preview['data']['preview_ref']})


@pytest.fixture(name='field_api')
def field_api(ledger_case):
    return FieldAPI(ledger_case)
