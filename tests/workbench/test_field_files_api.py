"""File preview/confirm use AJ's real domain with zero-write preview enforcement."""

from io import BytesIO

from openpyxl import load_workbook

from core.services.workbench.execution.field_report_files_codec import encode_reports
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, _ledger_fixture, success
from tests.workbench.field_workspace_support import field_api as _field_api


def rows(quantity=3):
    return [{'report_no': 'BG-EXCEL-1', 'batch_id': 'B1', 'operation_label': '1 Turning',
        'completed_quantity': quantity, 'actual_start': '2026-09-01T08:00:00', 'actual_end': '2026-09-01T10:00:00',
        'effective_processing_hours': 1.5, 'machine_label': 'Lathe', 'operator_label': 'Operator', 'remark': '现场核对'}]


def test_real_preview_original_bytes_replay_and_no_duplicate(field_api):
    api = field_api
    content = encode_reports(rows())
    before = all_rows(api.case.conn)
    preview = success(api.upload(content))
    assert preview['data']['can_confirm'] and preview['data']['summary']['changed'] == 1
    assert all_rows(api.case.conn) == before
    body = api.confirm_body(preview)
    result = success(api.client.post(BASE + '/files/confirm', json=body))
    assert result['result'] == 'committed' and api.task()['execution']['known_completed_quantity'] == 3
    repeated = success(api.client.post(BASE + '/files/confirm', json={**body, 'write_token': 'expired'}))
    assert repeated['replayed'] and repeated['receipt_ref'] == result['receipt_ref']
    duplicate = success(api.upload(content))
    assert duplicate['data']['summary']['unchanged'] == 1
    success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(duplicate)))
    assert api.task()['execution']['known_completed_quantity'] == 3


def test_confirm_reuses_first_parse_and_digest_for_automatic_number(field_api, monkeypatch):
    from core.models import workbench_field_report_source as source_model
    from core.services.workbench.execution import field_report_files
    from web.routes.workbench import execution_files

    api = field_api
    value = rows()
    value[0]['report_no'] = ''
    content = encode_reports(value)
    parse, digest = execution_files.decode_reports, source_model.sha256
    calls = []

    def decoded(original):
        calls.append('decode')
        return parse(original)

    def hashed(original):
        calls.append('digest')
        return digest(original)

    monkeypatch.setattr(execution_files, 'decode_reports', decoded)
    monkeypatch.setattr(source_model, 'sha256', hashed)
    preview = success(api.upload(content))
    assert calls == ['decode', 'digest']
    assert preview['data']['file_sha256'] == digest(content).hexdigest()

    def reparsed(_):
        raise AssertionError('confirmation must consume the retained parsed source')

    monkeypatch.setattr(field_report_files, 'decode_reports', reparsed)
    body = api.confirm_body(preview)
    committed = success(api.client.post(BASE + '/files/confirm', json=body))
    assert calls == ['decode', 'digest']
    assert committed['data']['rows'][0]['report_no'] == 'BG-X-' + preview['data']['file_sha256'][:32] + '-2'
    assert success(api.client.post(BASE + '/files/confirm', json={**body, 'write_token': 'expired'}))['replayed']

    # A subsequent preview gets fresh row diagnostics and keeps the original file identity.
    again = success(api.upload(content))
    assert again['data']['summary']['unchanged'] == 1
    assert calls == ['decode', 'digest', 'decode', 'digest']


def test_confirmation_token_must_match_the_retained_preview(field_api):
    api = field_api
    first = success(api.upload(encode_reports(rows())))
    values = rows()
    values[0]['report_no'] = 'BG-ANOTHER-PREVIEW'
    second = success(api.upload(encode_reports(values)))
    body = api.confirm_body(second)
    body['write_token'] = first['data']['write_context']['write_token']
    before = all_rows(api.case.conn)
    response = api.client.post(BASE + '/files/confirm', json=body)
    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'stale_write'
    assert all_rows(api.case.conn) == before


def test_preview_expiring_after_prefetch_is_rejected_by_the_locked_guard(field_api, monkeypatch):
    import time

    from core.services.workbench.execution.field_report_files import FieldReportFileService
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService
    from web.routes.workbench.execution_files import PREVIEW_NAMESPACE

    api = field_api
    preview = success(api.upload(encode_reports(rows())))
    ref = preview['data']['preview_ref']
    prepare, execute = FieldReportFileService.prepare_source, WorkbenchProductionReportService._execute
    prepared, waiting = [], []

    def source(self, original, cohort):
        prepared.append(ref)
        return prepare(self, original, cohort)

    def expire_before_write(self, items, request_key, action, context_ref, guard):
        assert prepared == [ref] and action == 'execution.import_confirm' and not self.conn.in_transaction
        entry = api.app.extensions['aps_public_opaque_tokens'][PREVIEW_NAMESPACE]['tokens'][ref]
        assert entry['expires_at'] > time.time()
        # Prefetch has checked the live preview; its lifetime ends while waiting for the write lock.
        entry['expires_at'] = 0
        waiting.append(ref)
        return execute(self, items, request_key, action, context_ref, guard)

    monkeypatch.setattr(FieldReportFileService, 'prepare_source', source)
    monkeypatch.setattr(WorkbenchProductionReportService, '_execute', expire_before_write)
    before = all_rows(api.case.conn)
    body = api.confirm_body(preview)
    response = api.client.post(BASE + '/files/confirm', json=body)
    assert response.status_code == 409, response.get_json()
    assert response.get_json()['error']['code'] == 'stale_write'
    assert prepared == waiting == [ref]
    assert all_rows(api.case.conn) == before


def test_file_known_conflict_atomic_and_unknown_supplement(field_api):
    api = field_api
    source = rows(); source[0].pop('completed_quantity'); source[0].pop('effective_processing_hours')
    preview = success(api.upload(encode_reports(source)))
    success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview)))
    full = success(api.upload(encode_reports(rows())))
    assert full['data']['can_confirm']
    success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(full)))
    before = all_rows(api.case.conn)
    conflict = success(api.upload(encode_reports(rows(4))))
    assert not conflict['data']['can_confirm'] and conflict['data']['summary']['rejected'] == 1
    assert all_rows(api.case.conn) == before


def test_export_whole_scope_and_stale_bytes_confirm(field_api):
    api = field_api
    ids = [api.case.op_id] + [api.case.op('X' + str(index), seq=index) for index in range(2, 24)]
    api.case.plan(2, ids)
    for op in ids:
        api.case.command('create', api.case.task(2, op), api.case.values(1))
    first = api.read(size=10)
    response = api.client.get(BASE + '/files/export', query_string={**first['data']['scope'], 'snapshot_ref': first['meta']['snapshot_ref'], 'page': 1, 'size': 10})
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data)); assert book.active.max_row == 24; book.close()
    preview = success(api.upload(encode_reports(rows()), first))
    api.case.conn.execute("UPDATE Batches SET quantity=11 WHERE batch_id='B1'"); api.case.conn.commit()
    result = api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview))
    assert result.status_code == 409


def test_file_batch_overreport_and_missing_snapshot(field_api):
    api = field_api
    values = rows(6); second = dict(values[0], report_no='BG-EXCEL-2', actual_start='2026-09-01T11:00:00', actual_end='2026-09-01T13:00:00'); values.append(second)
    before = all_rows(api.case.conn)
    preview = success(api.upload(encode_reports(values)))
    assert not preview['data']['can_confirm'] and preview['data']['rows'][1]['errors']
    assert all_rows(api.case.conn) == before
    assert api.client.get(BASE + '/files/export').status_code == 400


def test_import_replay_after_context_expiry_and_conflicting_preview(field_api):
    api = field_api
    preview = success(api.upload(encode_reports(rows())))
    body = api.confirm_body(preview)
    first = success(api.client.post(BASE + '/files/confirm', json=body))
    from web.routes.workbench.resource_action_context import EXTENSION
    api.app.extensions[EXTENSION].clear()
    replay = success(api.client.post(BASE + '/files/confirm', json={**body, 'write_token': 'expired'}))
    assert replay['receipt_ref'] == first['receipt_ref'] and replay['replayed']
    other = api.client.post(BASE + '/files/confirm', json={**body, 'input': {'preview_ref': 'x' * 32}})
    assert other.status_code == 409 and other.get_json()['error']['code'] == 'request_key_conflict'


def test_unknown_no_number_repeat_and_problem_download(field_api):
    api = field_api
    value = rows(); value[0]['report_no'] = ''
    content = encode_reports(value)
    preview = success(api.upload(content))
    success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview)))
    duplicate = success(api.upload(content))
    assert duplicate['data']['summary']['unchanged'] == 1
    values = rows(); values[0]['batch_id'] = 'not-found'
    rejected = success(api.upload(encode_reports(values)))
    response = api.client.get(BASE + '/files/errors', query_string={'preview_ref': rejected['data']['preview_ref']})
    assert response.status_code == 200
    # 出了预检结果后报工文件弹窗里的按钮叫「重新预检」，不再是早已改名的「预检文件」。
    missing = api.client.get(BASE + '/files/errors')
    assert missing.status_code == 400 and missing.get_json()['error']['message'] == '预检结果已过期，没有开始下载。请点「重新预检」。'
    book = load_workbook(BytesIO(response.data)); assert book.active['A2'].value == 2; book.close()


def test_unchanged_old_external_row_round_trips_and_new_resource_is_refused(field_api, monkeypatch):
    from core.services.workbench.execution import production_report_validation

    api = field_api
    case = api.case
    second = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, second])
    case.conn.execute("UPDATE BatchOperations SET source='external' WHERE id=?", (case.op_id,))
    case.conn.commit()
    # 修复前写入的旧外协报工带了本厂设备人员：原样导出再导回不应整份被拒，交给排产检查指出。
    monkeypatch.setattr(production_report_validation, "_reject_external_resources", lambda operation, values: None)
    case.command("create", case.task(2, case.op_id), case.values(1))
    monkeypatch.undo()
    reading = api.read()
    exported = api.client.get(BASE + '/files/export', query_string={**reading['data']['scope'],
                              'snapshot_ref': reading['meta']['snapshot_ref'], 'page': 1, 'size': 50})
    assert exported.status_code == 200
    checked = success(api.upload(exported.data))['data']
    assert checked['can_confirm'] and checked['summary']['unchanged'] == 1 and checked['summary']['rejected'] == 0
    # 新登记的外协行带本厂设备人员仍在入口拒绝。
    fresh = rows(1)
    fresh[0].update(report_no='BG-EXCEL-EXTERNAL', operation_label='1 Turning')
    refused = success(api.upload(encode_reports(fresh)))['data']
    assert not refused['can_confirm'] and '经办人' in refused['rows'][0]['errors'][0]['message']


def _other_writer_can_lock(path):
    import sqlite3

    other = sqlite3.connect(path, timeout=0)
    other.isolation_level = None
    try:
        other.execute('BEGIN IMMEDIATE')
        other.execute('ROLLBACK')
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        other.close()


def test_confirm_rebuilds_the_cohort_outside_the_write_lock_and_reuses_it(field_api, monkeypatch):
    from core.services.workbench.execution.field_workspace import FieldWorkspaceService
    from core.services.workbench.execution.production_report_prepare import ReportBatchPreparation

    api = field_api
    preview = success(api.upload(encode_reports(rows())))
    built, original = [], FieldWorkspaceService.cohort
    checked, prepare_original = [], ReportBatchPreparation.prepare

    def cohort(self, scope):
        built.append(_other_writer_can_lock(api.path))
        return original(self, scope)

    def prepare(self):
        checked.append(_other_writer_can_lock(api.path))
        return prepare_original(self)

    monkeypatch.setattr(FieldWorkspaceService, 'cohort', cohort)
    monkeypatch.setattr(ReportBatchPreparation, 'prepare', prepare)
    result = success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview)))
    assert result['result'] == 'committed'
    # 整份现场范围只在写锁外重建一次（这时别的连接仍能拿写锁）；写锁里库没变就直接沿用，只核对并写入报工。
    assert built == [True]
    assert checked == [True]


def test_preview_parses_before_the_slot_and_export_writes_after_it(field_api, monkeypatch):
    from flask import g

    from core.services.workbench.execution.field_report_files import FieldReportFileService
    from web.routes.workbench import execution_files, read_budget

    api = field_api
    calls, decode, download = [], execution_files.decode_reports, FieldReportFileService.download

    def parse(content):
        calls.append(('parse', read_budget.PLAN_READ_SLOTS._available, g.db.in_transaction))
        return decode(content)

    def write(self, cohort, template=False):
        calls.append(('write', read_budget.PLAN_READ_SLOTS._available, g.db.in_transaction))
        return download(self, cohort, template)

    monkeypatch.setattr(execution_files, 'decode_reports', parse)
    monkeypatch.setattr(FieldReportFileService, 'download', write)
    assert success(api.upload(encode_reports(rows())))['data']['can_confirm']
    reading = api.read()
    response = api.client.get(BASE + '/files/export', query_string={**reading['data']['scope'], 'snapshot_ref': reading['meta']['snapshot_ref']})
    assert response.status_code == 200
    # 解析在排队读现场范围之前，生成 XLSX 在读事务和读额度都释放之后。
    assert calls == [('parse', 1, False), ('write', 1, False)]


def test_retry_racing_its_own_commit_replays_instead_of_reporting_nothing_written(field_api, monkeypatch):
    # R2 用同一请求编号重试时，锁外查回执那一刻 R1 还没提交；R1 提交后，R2 预取现场资料就会因数据已变被拒。
    # 拒绝前要再查一次回执，按 R1 的结果重放，不能回"没有写入"。
    from core.services.workbench.commands import WorkbenchCommandService

    api = field_api
    preview = success(api.upload(encode_reports(rows())))
    body = api.confirm_body(preview)
    first = success(api.client.post(BASE + '/files/confirm', json=body))
    original, misses = WorkbenchCommandService.replay, []

    def replay_once_missed(self, **intent):
        if not misses:
            misses.append(intent['request_key'])
            return None
        return original(self, **intent)

    monkeypatch.setattr(WorkbenchCommandService, 'replay', replay_once_missed)
    second = success(api.client.post(BASE + '/files/confirm', json=body))
    assert misses and second['replayed'] and second['receipt_ref'] == first['receipt_ref']
    assert api.task()['execution']['known_completed_quantity'] == 3
