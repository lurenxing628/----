"""Downloaded explicit identities -> read-only preflight -> atomic real import."""

import hashlib
import json

import pytest

from core.services.workbench.field_report_files_codec import decode_reports, encode_reports
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_case
from tests.workbench.field_workspace_support import BASE, success
from tests.workbench.field_workspace_support import field_api as field_api
from tests.workbench.round1_field_piece_files_support import (
    PIECES,
    by_piece,
    confirm,
    download,
    fill_template,
    report_values,
)
from tests.workbench.round1_field_piece_files_support import (
    piece_file_api as piece_file_api,
)
from web.routes.workbench.execution_files import PREVIEW_NAMESPACE
from web.routes.workbench.resource_action_context import EXTENSION, resolve_context


def test_download_prefills_exact_task_scope_and_zero_import_does_not_complete(piece_file_api):
    api = piece_file_api
    tasks = by_piece(api)
    source = download(api)
    decoded = decode_reports(source)
    assert {row['values']['task_ref'] for row in decoded} == {task['task_ref'] for task in tasks.values()}
    assert len({task['operation_label'] for task in tasks.values()}) == 1
    assert {row['values']['operation_scope'] for row in decoded} == {'单件', '共同工序'}
    content = fill_template(source, {None: report_values(), PIECES[0]: report_values(), '0': report_values()})
    before = all_rows(api.case.conn)
    preview = success(api.upload(content))
    assert preview['data']['summary'] == {'total': 4, 'changed': 3, 'unchanged': 0, 'blank': 1, 'rejected': 0}
    assert preview['data']['file_sha256'] == hashlib.sha256(content).hexdigest()
    assert all_rows(api.case.conn) == before
    with api.app.app_context():
        document, original = resolve_context(PREVIEW_NAMESPACE, preview['data']['preview_ref'], 'stale_write')
    stored = json.loads(document)
    assert original == content and stored['read_snapshot'] and stored['preview']['snapshot']
    body = api.confirm_body(preview)
    result = success(api.client.post(BASE + '/files/confirm', json=body))
    after = by_piece(api)
    for piece in (None, PIECES[0], '0'):
        task = after[piece]
        report = task['execution']['reports'][0]
        assert report['completed_quantity'] == report['effective_processing_hours'] == 0
        assert task['execution']['execution_state'] != 'complete'
        assert report['recorded_against_task_ref'] == tasks[piece]['task_ref']
        assert report['recorded_against_plan_ref'] == tasks[piece]['plan_ref']
        assert report['operation_ref'] == tasks[piece]['operation_ref']
    assert after[PIECES[1]]['execution']['reports'] == []
    revisions = api.case.conn.execute('SELECT request_key FROM WorkbenchProductionReportRevisions').fetchall()
    assert [row[0] for row in revisions] == [body['request_key']] * 3
    state = all_rows(api.case.conn)
    api.app.extensions[EXTENSION].clear()
    replay = success(api.client.post(BASE + '/files/confirm', json={**body, 'write_token': 'expired'}))
    assert replay['replayed'] and replay['receipt_ref'] == result['receipt_ref']
    assert all_rows(api.case.conn) == state


@pytest.mark.parametrize('patch', [
    {'任务编号': 'f' * 48}, {'任务编号': ''}, {'批次号': '不存在'}, {'工序': '2 Turning'},
    {'单件编号': PIECES[1]}, {'单件编号': ''}, {'工序范围': '共同工序'}, {'工序范围': '未知'},
])
@pytest.mark.parametrize('mixed', [False, True])
def test_forged_identity_rejects_all_or_mixed_without_partial_writes(piece_file_api, patch, mixed):
    api = piece_file_api
    changes = {PIECES[0]: {**report_values(), **patch}}
    if mixed:
        changes[PIECES[1]] = report_values()
    before = all_rows(api.case.conn)
    preview = success(api.upload(fill_template(download(api), changes)))
    assert not preview['data']['can_confirm'] and preview['data']['summary']['rejected'] == 1
    assert preview['data']['summary']['changed'] == 0
    rejected = api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview))
    assert rejected.status_code == 409 and rejected.get_json()['committed'] is False
    assert all_rows(api.case.conn) == before


def test_common_requires_empty_piece_and_legacy_ambiguity_stays_rejected(piece_file_api):
    api = piece_file_api
    content = fill_template(download(api), {None: {**report_values(), '单件编号': '0'}})
    assert not success(api.upload(content))['data']['can_confirm']
    rows = decode_reports(fill_template(download(api), {PIECES[0]: report_values()}))
    old = encode_reports([row['values'] for row in rows])
    before = all_rows(api.case.conn)
    preview = success(api.upload(old))
    assert not preview['data']['can_confirm']
    rejected = next(row for row in preview['data']['rows'] if row['errors'])
    assert '不能猜关联' in rejected['errors'][0]['message']
    assert all_rows(api.case.conn) == before


def test_old_ten_columns_unique_match_and_zero_unknown_preserved(field_api):
    row = {'report_no': '旧报工', 'batch_id': 'B1', 'operation_label': '1 Turning',
           'actual_start': '2026-09-01T08:00:00', 'completed_quantity': 0, 'effective_processing_hours': None}
    confirm(field_api, encode_reports([row]))
    task = field_api.task()
    assert task['execution']['reports'][0]['effective_processing_hours'] is None
    assert task['execution']['reports'][0]['completed_quantity'] == 0
    assert task['execution']['execution_state'] != 'complete'


def test_duplicate_same_number_and_reimport_write_only_once(piece_file_api):
    api = piece_file_api
    content = fill_template(download(api), {PIECES[0]: report_values()})
    value = next(row['values'] for row in decode_reports(content) if row['values']['piece_id'] == PIECES[0])
    content = encode_reports([value, value], format_version=2)
    preview, _, _ = confirm(api, content)
    assert preview['data']['summary']['changed'] == preview['data']['summary']['unchanged'] == 1
    _, _, repeat = confirm(api, content)
    assert repeat['result'] == 'unchanged'
    assert len(by_piece(api)[PIECES[0]]['execution']['reports']) == 1


def test_old_task_ref_and_stale_precheck_cannot_switch_to_new_plan(piece_file_api):
    api = piece_file_api
    old = api.read()
    content = fill_template(download(api, reading=old), {PIECES[0]: report_values()})
    preview = success(api.upload(content, old))
    ids = [row[0] for row in api.case.conn.execute('SELECT id FROM BatchOperations')]
    api.case.plan(3, ids)
    before = all_rows(api.case.conn)
    result = api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview))
    assert result.status_code == 409 and result.get_json()['committed'] is False
    assert not success(api.upload(content))['data']['can_confirm']
    assert not success(api.upload(content, api.read(plan_ref=old['data']['scope']['plan_ref'])))['data']['can_confirm']
    assert all_rows(api.case.conn) == before


def test_partial_append_failure_rolls_back_every_row_and_same_request_retries_once(piece_file_api):
    api = piece_file_api
    content = fill_template(download(api), {PIECES[0]: report_values(), PIECES[1]: report_values()})
    preview = success(api.upload(content))
    body = api.confirm_body(preview)
    api.case.conn.execute('''CREATE TRIGGER round1_fail_second_revision BEFORE INSERT ON WorkbenchProductionReportRevisions
        WHEN (SELECT count(*) FROM WorkbenchProductionReportRevisions) > 0
        BEGIN SELECT RAISE(ABORT, 'R1-B injected second-row failure'); END''')
    api.case.conn.commit()
    before = all_rows(api.case.conn)
    response = api.client.post(BASE + '/files/confirm', json=body)
    assert response.status_code >= 500 and response.get_json()['committed'] == 'unknown'
    assert all_rows(api.case.conn) == before
    api.case.conn.execute('DROP TRIGGER round1_fail_second_revision')
    api.case.conn.commit()
    result = success(api.client.post(BASE + '/files/confirm', json=body))
    assert result['data']['summary']['changed'] == 2
    state = all_rows(api.case.conn)
    replay = success(api.client.post(BASE + '/files/confirm', json=body))
    assert replay['replayed'] and replay['receipt_ref'] == result['receipt_ref']
    assert all_rows(api.case.conn) == state


def test_one_piece_completion_does_not_complete_sibling_or_common(piece_file_api):
    api = piece_file_api
    content = fill_template(download(api), {PIECES[0]: report_values(1)})
    confirm(api, content)
    tasks = by_piece(api)
    assert tasks[PIECES[0]]['execution']['execution_state'] == 'complete'
    assert all(task['execution']['execution_state'] == 'unreported'
               for piece, task in tasks.items() if piece != PIECES[0])
