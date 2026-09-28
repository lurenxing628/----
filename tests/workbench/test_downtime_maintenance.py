"""Real resource routes, permanent downtime identities and command transactions."""

import pytest
from flask import Blueprint, Flask, g

from tests.workbench.resource_entity_support import resource_database

_resource_fixture = resource_database
BASE = '/api/workbench/v1/entities/machine/'
WINDOW = {'start_time': '2026-10-05T08:00', 'end_time': '2026-10-05T10:00', 'reason_code': 'maintenance', 'reason_detail': '保养'}


@pytest.fixture
def downtime_client(resource_conn):
    from web.routes.workbench.resources import register_resource_routes

    resource_conn.execute("DELETE FROM MachineDowntimes")
    resource_conn.commit()
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='downtime-fixture-only')
    bp = Blueprint('workbench', __name__)
    register_resource_routes(bp)
    app.register_blueprint(bp)
    @app.before_request
    def isolated():
        g.db = resource_conn
    client = app.test_client()
    client.conn = resource_conn
    return client


def ref(client, kind='machine', code='M1'):
    return client.conn.execute('SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1', (kind, code)).fetchone()[0]


def listing(client):
    response = client.get(BASE + ref(client) + '/downtimes')
    assert response.status_code == 200, response.get_json()
    return response.get_json()['data']


def command(client, action, payload, key, token=None):
    token = token or listing(client)['write_context']['write_token']
    return client.post(BASE + ref(client) + '/downtimes/' + action, json={'request_key': key, 'write_token': token, 'input': payload})


def test_create_edit_cancel_replay_and_schedule_constraint_remains_until_cancel(downtime_client):
    client = downtime_client
    token = listing(client)['write_context']['write_token']
    result = command(client, 'create', WINDOW, 'downtime-create-0001', token)
    assert result.status_code == 200, result.get_json()
    assert command(client, 'create', WINDOW, 'downtime-create-0001', token).get_json()['replayed'] is True
    row = listing(client)['rows'][0]
    assert row['status'] == 'active' and row['start_time'] == '2026-10-05 08:00:00'
    client.conn.execute("UPDATE Machines SET status='active' WHERE machine_id='M1'")
    client.conn.commit()
    from data.repositories.machine_downtime_repo import MachineDowntimeRepository
    repo = MachineDowntimeRepository(client.conn)
    assert repo.has_overlap('M1', '2026-10-05 09:00:00', '2026-10-05 11:00:00')
    patch = dict(WINDOW, downtime_ref=row['ref'], end_time='2026-10-05T11:00')
    assert command(client, 'update', patch, 'downtime-update-0001').status_code == 200
    assert command(client, 'cancel', {'downtime_ref': row['ref']}, 'downtime-cancel-0001').status_code == 200
    assert listing(client)['rows'][0]['status'] == 'cancelled'
    assert not repo.has_overlap('M1', '2026-10-05 09:00:00', '2026-10-05 11:00:00')


def test_overlap_stale_and_foreign_ref_reject_without_writing(downtime_client):
    client = downtime_client
    token = listing(client)['write_context']['write_token']
    assert command(client, 'create', WINDOW, 'downtime-create-0001', token).status_code == 200
    assert command(client, 'create', WINDOW, 'downtime-create-0002', token).get_json()['error']['code'] == 'stale_write'
    assert command(client, 'create', WINDOW, 'downtime-create-0003').get_json()['error']['code'] == 'constraint_conflict'
    assert command(client, 'cancel', {'downtime_ref': 'f' * 48}, 'downtime-cancel-0001').status_code == 404
    assert len(listing(client)['rows']) == 1


def test_personal_calendar_dependency_blocks_single_delete(downtime_client):
    client = downtime_client
    client.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_hours,efficiency,allow_normal,allow_urgent) VALUES ('EMPTY','2026-10-05','workday',8,1,'yes','yes')")
    client.conn.commit()
    path = '/api/workbench/v1/entities/operator/' + ref(client, 'operator', 'EMPTY')
    data = client.get(path).get_json()['data']
    assert data['write_context']['capabilities']['operator.delete'] is False
    result = client.post(path + '/delete', json={'request_key': 'delete-operator-0001', 'write_token': data['write_context']['write_token'], 'input': {}})
    assert result.status_code != 200
    assert client.conn.execute("SELECT COUNT(*) FROM OperatorCalendar WHERE operator_id='EMPTY'").fetchone()[0] == 1
