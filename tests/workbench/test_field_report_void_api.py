"""Real HTTP preview/confirm binds reason, revision and all execution facts."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, _ledger_fixture, success  # noqa: F401
from tests.workbench.field_workspace_support import field_api as _field_api  # noqa: F401


def preview(api, record, reason="误报本次加工"):
    payload = {"original_revision_ref": record["revision_ref"], "reason": reason, "declared_operator": "班组长"}
    data = success(api.client.post(BASE + '/reports/' + record['report_ref'] + '/void-preview', json={"input": payload}))['data']
    return payload, data


def test_field_preview_confirm_refresh_and_original_receipt_replay(field_api):
    api = field_api
    api.create()
    record = api.task()['execution']['reports'][0]
    before = all_rows(api.case.conn)
    payload, data = preview(api, record)
    assert data['can_confirm'] and data['before']['known_completed_quantity'] == 2
    assert data['after']['known_completed_quantity'] == 0
    assert all_rows(api.case.conn) == before
    body = api.body(data['write_context'], payload)
    path = BASE + '/reports/' + record['report_ref'] + '/void'
    saved = success(api.client.post(path, json=body))
    replay = success(api.client.post(path, json={**body, 'write_token': 'expired'}))
    assert replay['replayed'] and replay['receipt_ref'] == saved['receipt_ref']
    task = api.task()
    assert task['execution']['reports'] == [] and task['execution']['execution_state'] == 'unreported'
    audit = task['execution']['voided_reports'][0]
    assert audit['report']['report_no'] == record['report_no'] and audit['report']['completed_quantity'] == 2
    assert audit['report']['actual_start'] == record['actual_start'] and audit['report']['actual_machine_label'] == 'Lathe'
    assert audit['void_fact']['reason'] == payload['reason']
    case = api.case
    case.event(case.op_id, 'start')
    case.event(case.op_id, 'finish', quantity=10)
    task = api.task()
    legacy_before = all_rows(case.conn)['WorkbenchExecutionLegacyFacts']
    api.create({'legacy_fact_ref': task['execution']['legacy_facts'][-1]['legacy_fact_ref'],
                'reason': '只补原记录的加工工时', 'effective_processing_hours': 1.5}, task)
    linked = api.task()['execution']['reports'][0]
    next_op = case.op('OP2', seq=2)
    case.plan(2, [case.op_id, next_op], start='2026-09-09T11:00:00', end='2026-09-09T12:00:00')
    reports = []
    for quantity, start, end in ((5, '11', '12'), (0, '12', '13'), (5, '13', '14')):
        next_task = api.read()['data']['tasks'][1]
        row = api.create(case.values(quantity, actual_start='2026-09-09T' + start + ':00:00',
            actual_end='2026-09-09T' + end + ':00:00', effective_processing_hours=.5), next_task)
        reports.append(row['data']['rows'][0]['report_ref'])
    before = all_rows(case.conn)
    payload, data = preview(api, linked, '撤销误填的工时明细，保留原实际')
    summary = api.read()['data']['summary']
    assert summary['effective_processing_hours'] == 3 and summary['unknown_hour_reports'] == 0
    assert data['can_confirm'] and data['downstream_impacts'] == []
    for field in ('execution_state', 'known_completed_quantity', 'unknown_record_count', 'first_actual_start', 'confirmed_finish'):
        assert data['before'][field] == data['after'][field]
    assert all_rows(case.conn) == before
    success(api.client.post(BASE + '/reports/' + linked['report_ref'] + '/void', json=api.body(data['write_context'], payload)))
    assert api.task()['execution']['reports'] == []
    summary = api.read()['data']['summary']
    assert summary['effective_processing_hours'] is None and summary['known_effective_processing_hours'] == 1.5
    assert summary['unknown_hour_reports'] == 2
    assert all_rows(case.conn)['WorkbenchExecutionLegacyFacts'] == legacy_before
    # Withdrawing the next operation's adopted quantity/actuals still conflicts.
    actual = next(row for row in api.read()['data']['tasks'][1]['execution']['reports'] if row['report_ref'] == reports[1])
    case.plan(3, [case.op_id, next_op], start='2026-09-09T11:00:00', end='2026-09-09T12:00:00')
    before = all_rows(case.conn)
    first = next(row for row in api.read()['data']['tasks'][1]['execution']['reports'] if row['report_ref'] == reports[0])
    response = api.client.post(BASE + '/reports/' + first['report_ref'] + '/correct', json=api.body(first['write_context'], {
        'original_revision_ref': first['revision_ref'], 'reason': '核对第一段结束', 'actual_end': '2026-09-09T13:00:00'}))
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'constraint_conflict'
    assert all_rows(case.conn) == before
    payload, data = preview(api, actual)
    assert not data['can_confirm'] and {item['code'] for item in data['downstream_impacts']} == {'adopted_actual_period_changed'}
    assert data['before']['known_completed_quantity'] == data['after']['known_completed_quantity'] == 10
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command('report_void', actual['report_ref'], payload)
    assert error.value.code == 'constraint_conflict' and all_rows(case.conn) == before
    actual = next(row for row in api.read()['data']['tasks'][1]['execution']['reports'] if row['report_ref'] == reports[0])
    payload, data = preview(api, actual)
    assert not data['can_confirm'] and 'adopted_execution_basis_changed' in {item['code'] for item in data['downstream_impacts']}
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command('report_void', actual['report_ref'], payload)
    assert error.value.code == 'constraint_conflict' and all_rows(case.conn) == before
