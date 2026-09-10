"""Field route evidence against a real, isolated database and AJ's real ledger."""

from datetime import date, datetime

import pytest

from core.services.workbench.plan_fact_serialization import plain_plan_facts
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, FieldAPI, _ledger_fixture, success
from tests.workbench.field_workspace_support import field_api as _field_api


def test_unreported_null_zero_partial_finish_and_readonly(field_api):
    api = field_api
    before = all_rows(api.case.conn)
    task = api.task()
    assert task['execution']['execution_state'] == 'unreported'
    assert task['execution']['reports'] == []
    assert all_rows(api.case.conn) == before
    assert not any(sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE', 'CREATE') for sql in api.app.ak_statements)
    api.create({'actual_start': '2026-09-01T08:00:00'})
    p = api.task()['execution']
    assert p['execution_state'] == 'started' and p['remaining_quantity'] is None
    record = p['reports'][0]
    body = api.body(record['write_context'], {'original_revision_ref': record['revision_ref'], 'reason': '核对现场记录',
        **api.case.values(0, actual_start='2026-09-01T08:00:00', actual_end='2026-09-01T10:00:00', effective_processing_hours=0)})
    success(api.client.post(BASE + '/reports/' + record['report_ref'] + '/supplement', json=body))
    assert api.task()['execution']['reports'][0]['completed_quantity'] == 0
    api.create(api.case.values(4, actual_start='2026-09-01T11:00:00', actual_end='2026-09-01T13:00:00'))
    assert api.task()['execution']['execution_state'] == 'partial'
    api.create(api.case.values(6, actual_start='2026-09-01T14:00:00', actual_end='2026-09-01T16:00:00'))
    p = api.task()['execution']
    assert p['execution_state'] == 'complete' and p['known_completed_quantity'] == 10 and p['remaining_quantity'] == 0
    assert api.case.conn.execute('SELECT count(*) FROM OperationExecutionEvents').fetchone()[0] == 0


def test_correction_history_old_revision_and_original_request(field_api):
    api = field_api
    api.create()
    record = api.task()['execution']['reports'][0]
    body = api.body(record['write_context'], {'original_revision_ref': record['revision_ref'], 'reason': '工时复核', 'effective_processing_hours': 1.25})
    first = success(api.client.post(BASE + '/reports/' + record['report_ref'] + '/correct', json=body))
    second = success(api.client.post(BASE + '/reports/' + record['report_ref'] + '/correct', json={**body, 'write_token': 'expired'}))
    assert second['replayed'] and second['receipt_ref'] == first['receipt_ref']
    conflict = api.client.post(BASE + '/reports/' + record['report_ref'] + '/correct', json={**body, 'input': {**body['input'], 'reason': 'another'}})
    assert conflict.status_code == 409 and conflict.get_json()['error']['code'] == 'request_key_conflict'
    fresh = api.task()['execution']['reports'][0]
    assert fresh['report_ref'] == record['report_ref'] and fresh['revision_ref'] != record['revision_ref']
    assert len(fresh['correction_history']) == 2
    stale = api.body(fresh['write_context'], body['input'])
    assert api.client.post(BASE + '/reports/' + record['report_ref'] + '/correct', json=stale).status_code == 409


def test_pages_filter_detail_scope_and_old_plan_identity(field_api):
    api = field_api
    ids = [api.case.op_id] + [api.case.op('OP' + str(index), seq=index) for index in range(2, 27)]
    api.case.plan(2, ids)
    first = api.read(size=10)
    second = api.read(size=10, page=2, snapshot_ref=first['meta']['snapshot_ref'], **first['data']['scope'])
    assert second['meta']['as_of'] == first['meta']['as_of']
    assert len(second['data']['tasks']) == 10 and second['data']['page']['total'] == 26
    task = second['data']['tasks'][0]
    detail = api.read('/tasks/' + task['task_ref'], snapshot_ref=first['meta']['snapshot_ref'], **first['data']['scope'])
    assert detail['data']['task'] == task
    bad = api.client.get(BASE + '/tasks', query_string={'query': 'changed', 'snapshot_ref': first['meta']['snapshot_ref']})
    assert bad.status_code == 409
    old = api.task(plan_ref=api.case.plan_ref(1))
    assert not old['execution']['write_context']['capabilities']['create']
    current = next(row for row in first['data']['tasks'] if row['operation_ref'] == old['operation_ref'])
    assert old['task_ref'] != current['task_ref']


def test_cross_plan_reports_legacy_finish_and_raw_preservation(field_api):
    api = field_api
    api.create(api.case.values(2))
    old = api.task()
    raw = [tuple(row) for row in api.case.conn.execute('SELECT * FROM WorkbenchProductionReports')]
    api.case.plan(2, [api.case.op_id])
    current = api.task()
    report = current['execution']['reports'][0]
    assert current['task_ref'] != old['task_ref'] and report['recorded_against_task_ref'] == old['task_ref']
    assert [tuple(row) for row in api.case.conn.execute('SELECT * FROM WorkbenchProductionReports')] == raw


def test_missing_schema_is_unavailable_and_never_installed(request):
    case = request.getfixturevalue('ledger_case')
    api = FieldAPI(case)
    before = all_rows(case.conn)
    response = api.client.get(BASE + '/tasks')
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'execution_ledger_unavailable'
    assert all_rows(case.conn) == before


def test_blob_and_date_private_facts_are_typed(field_api):
    api = field_api
    api.case.conn.execute('UPDATE BatchOperations SET status=? WHERE id=?', (b'old\x00status', api.case.op_id))
    api.case.conn.commit()
    task = api.task()
    assert task['execution']['write_context']['write_token']
    api.create(task=task)
    typed = plain_plan_facts({'date': date(2026, 9, 1), 'time': datetime(2026, 9, 1, 1, 2), 'blob': b'\x00'})
    assert typed['date']['storage_type'] == 'date' and typed['blob']['hex'] == '00'


def test_initial_cross_page_focus_and_common_gantt_scope(field_api):
    api = field_api
    ids = [api.case.op_id] + [api.case.op('FOCUS-' + str(index), seq=index) for index in range(2, 30)]
    api.case.plan(2, ids)
    selected = api.case.task(2, ids[-1])
    result = api.read(size=10, task_ref=selected, batch_ids='["B1"]', range_start='2026-09-09T07:00:00', range_end='2026-09-09T11:00:00')
    assert result['data']['page']['number'] == 3 and any(row['task_ref'] == selected for row in result['data']['tasks'])
    wrong = api.client.get(BASE + '/tasks', query_string={'plan_ref': api.case.plan_ref(1), 'task_ref': selected})
    assert wrong.status_code == 404


def test_legacy_finish_explicit_supplement_and_preserved_events(field_api):
    api = field_api
    api.case.event(api.case.op_id, 'start')
    api.case.event(api.case.op_id, 'finish', quantity=None)
    # Explicit installation records newly appended old events in this test database.
    api.case.install()
    before = [tuple(row) for row in api.case.conn.execute('SELECT * FROM OperationExecutionEvents')]
    task = api.task()
    assert task['execution']['execution_state'] == 'complete' and task['execution']['data_quality'] == 'legacy_incomplete'
    assert task['execution']['reports'] == [] and task['execution']['remaining_quantity'] is None
    legacy = next(row for row in task['execution']['legacy_facts'] if row['event_type'] == 'finish')
    api.create(api.case.values(10, legacy_fact_ref=legacy['legacy_fact_ref'], reason='人工复核原始完工'), task=task)
    assert api.task()['execution']['known_completed_quantity'] == 10
    assert [tuple(row) for row in api.case.conn.execute('SELECT * FROM OperationExecutionEvents')] == before


@pytest.mark.parametrize('query', [{'page': 2}, {'page': '1.5'}, {'source': 'demo'}, {'state': 'done'}, {'event_id': 1},
    {'plan_finish_date_from': '2026-02-30', 'plan_finish_date_to': '2026-03-02'}, {'plan_finish_date_from': '2026-09-01'}])
def test_invalid_queries_do_not_fallback(field_api, query):
    response = field_api.client.get(BASE + '/tasks', query_string=query)
    assert response.status_code == 400 and response.get_json()['committed'] is False
