"""Real HTTP preview/confirm binds reason, revision and all execution facts."""

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
