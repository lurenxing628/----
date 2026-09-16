"""Real HTTP preview/confirm binds reason, revision and all execution facts."""

from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, _ledger_fixture, success
from tests.workbench.field_workspace_support import field_api as _field_api


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


def test_changed_reason_and_new_report_require_a_fresh_preview(field_api):
    api = field_api
    api.create()
    record = api.task()['execution']['reports'][0]
    payload, data = preview(api, record)
    path = BASE + '/reports/' + record['report_ref'] + '/void'
    changed = api.body(data['write_context'], {**payload, 'reason': '另一原因'})
    response = api.client.post(path, json=changed)
    assert response.status_code == 409 and not response.get_json()['committed']
    api.create(api.case.values(1))
    response = api.client.post(path, json=api.body(data['write_context'], payload))
    assert response.status_code == 409 and not response.get_json()['committed']
    assert api.case.conn.execute('SELECT count(*) FROM WorkbenchProductionReportVoids').fetchone()[0] == 0
    payload, data = preview(api, record)
    success(api.client.post(path, json=api.body(data['write_context'], payload)))
    assert api.task()['execution']['known_completed_quantity'] == 1


def test_reason_is_required_and_unpreviewed_normal_record_token_is_rejected(field_api):
    api = field_api
    api.create()
    record = api.task()['execution']['reports'][0]
    path = BASE + '/reports/' + record['report_ref']
    response = api.client.post(path + '/void-preview', json={'input': {'original_revision_ref': record['revision_ref'], 'reason': ' '}})
    assert response.status_code == 422
    body = api.body(record['write_context'], {'original_revision_ref': record['revision_ref'], 'reason': '误录'})
    response = api.client.post(path + '/void', json=body)
    assert response.status_code == 409
    assert len(api.task()['execution']['reports']) == 1
