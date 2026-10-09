"""Execution reads keep their real cohort without unrelated plan projections."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan import queries
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import FieldAPI, _ledger_fixture  # noqa: F401
from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read


def _three_tasks(case):
    second, third = case.op('OP2', seq=2), case.op('OP3', seq=3)
    case.plan(2, [case.op_id, second, third])
    for op_id, start, end in ((case.op_id, '08:00:00', '10:00:00'),
                              (second, '10:00:00', '12:00:00'), (third, '12:00:00', '14:00:00')):
        case.conn.execute('UPDATE Schedule SET start_time=?,end_time=? WHERE version=2 AND op_id=?',
                          ('2026-09-09T' + start, '2026-09-09T' + end, op_id))
    case.conn.commit()
    case.install()
    case.path = case.conn.execute('PRAGMA database_list').fetchone()[2]
    return case.plan_ref(2), [case.task(2, op_id) for op_id in (case.op_id, second, third)]


def _unrelated_too_large(*args, **kwargs):
    raise WorkbenchCommandRejected('query_too_large', 'Oversized unrelated baseline comparison.', 413)


def test_unrelated_plan_projection_cannot_block_execution_cohort(ledger_case, monkeypatch):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    api = FieldAPI(case)
    task = api.task(plan_ref=plan_ref)
    api.create(case.values(2), task)
    client = app_for(case).test_client()
    before = all_rows(case.conn)
    monkeypatch.setattr(queries, 'workspace_projections', _unrelated_too_large)
    full = client.get('/api/workbench/v1/plans/' + plan_ref + '/workspace')
    assert full.status_code == 413 and full.get_json()['error']['code'] == 'query_too_large'
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T08:00:00', range_end='2026-09-09T10:00:00')
    field = read(client, FIELD + '/tasks', **scope)
    actual = read(client, ACTUAL, **scope)
    row, = field['data']['tasks']
    item, = actual['data']['items']
    assert row['task_ref'] == item['task']['task_ref'] == refs[0]
    # This legacy plan did not capture adopted quantity evidence. Keep its
    # explicit unknown task quantity while the live ledger has a known target.
    assert row['quantity'] is item['task']['quantity'] is None
    assert row['quantity_basis'] == item['task']['quantity_basis'] == 'unknown'
    assert row['execution']['target_quantity'] == item['execution']['target_quantity'] == 10
    assert row['planned_start'] == item['task']['start'] == scope['range_start']
    assert row['planned_end'] == item['task']['end'] == scope['range_end']
    assert row['execution']['execution_state'] == item['execution']['execution_state'] == 'partial'
    assert row['execution']['reports'][0]['revision_ref'] == item['execution']['reports'][0]['revision_ref']
    detail = read(client, FIELD + '/tasks/' + refs[0], **scope, snapshot_ref=field['meta']['snapshot_ref'])
    assert detail['data']['task'] == row
    assert actual['data']['calendar']['time_scope']['range_start'] == scope['range_start']
    assert actual['data']['calendar']['time_scope']['range_end'] == scope['range_end']
    assert all_rows(case.conn) == before


def test_scoped_actual_chain_retains_outside_predecessors_and_snapshot(ledger_case):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    client = app_for(case).test_client()
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T12:00:00', range_end='2026-09-09T14:00:00')
    actual = read(client, ACTUAL, **scope)
    chain = actual['data']['critical_chain']
    assert actual['data']['task_count'] == 1 and actual['data']['items_complete'] is True
    assert chain['state'] == 'available' and chain['scope'] == 'full_plan'
    assert chain['plan_task_count'] == 3 and chain['task_refs'] == refs
    assert [node['in_scope'] for node in chain['nodes']] == [False, False, True]
    token = actual['meta']['snapshot_ref']
    related = read(client, ACTUAL + '/chain', **scope, snapshot_ref=token, target_task_ref=refs[-1])
    assert related['data']['critical_chain']['task_refs'] == refs
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T09:30:00' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    for path, extra in ((ACTUAL + '/chain', dict(target_task_ref=refs[-1])),
                        (ACTUAL + '/export', dict(format='csv'))):
        response = client.get(path, query_string=dict(scope, snapshot_ref=token, **extra))
        assert response.status_code == 409 and response.get_json()['error']['code'] == 'snapshot_stale'


def test_field_scoped_page_write_and_files_keep_same_snapshot(ledger_case):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    api = FieldAPI(case)
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T08:00:00', range_end='2026-09-09T14:00:00')
    first = api.read(**scope, size=1)
    token = first['meta']['snapshot_ref']
    second = api.read(**scope, size=1, page=2, snapshot_ref=token)
    assert second['meta']['snapshot_ref'] == token and second['meta']['as_of'] == first['meta']['as_of']
    assert second['data']['tasks'][0]['task_ref'] == refs[1]
    response = api.client.get(FIELD + '/files/template', query_string=dict(scope, snapshot_ref=token))
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data)); assert book.worksheets[0].max_row == 4; book.close()
    changed = api.client.get(FIELD + '/tasks', query_string=dict(scope, range_end='2026-09-09T12:00:00', snapshot_ref=token))
    assert changed.status_code == 409 and changed.get_json()['error']['code'] == 'snapshot_stale'
    api.create(case.values(2), first['data']['tasks'][0])
    for path, extra in ((FIELD + '/tasks', dict(page=2, size=1)),
                        (FIELD + '/files/template', {}), (FIELD + '/files/export', {})):
        response = api.client.get(path, query_string=dict(scope, snapshot_ref=token, **extra))
        assert response.status_code == 409 and response.get_json()['error']['code'] == 'snapshot_stale'


def test_required_task_payload_still_has_original_plan_budget(ledger_case):
    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    # The required task data itself exceeds 8 MiB; removing unused projections
    # cannot admit it or silently truncate it.
    case.conn.execute('UPDATE BatchOperations SET op_type_name=?', ('工序' * (2 * 1024 * 1024),))
    case.conn.commit()
    before = all_rows(case.conn)
    reader = queries.WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            reader.execution_workspace(PlanReadScope(plan_ref))
    assert rejected.value.code == 'query_too_large' and rejected.value.status == 413
    assert all_rows(case.conn) == before
