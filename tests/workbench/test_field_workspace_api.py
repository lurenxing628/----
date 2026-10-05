"""Field route evidence against a real, isolated database and AJ's real ledger."""


from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, FieldAPI, _ledger_fixture, success  # noqa: F401
from tests.workbench.field_workspace_support import field_api as _field_api  # noqa: F401


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


def test_missing_schema_is_unavailable_and_never_installed(request):
    case = request.getfixturevalue('ledger_case')
    api = FieldAPI(case)
    before = all_rows(case.conn)
    response = api.client.get(BASE + '/tasks')
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'execution_ledger_unavailable'
    assert all_rows(case.conn) == before
